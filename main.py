import os
import asyncio
import argparse
import logging
import json
import datetime
import re
from jinja2 import Environment, FileSystemLoader

# Importar nuestros módulos
from core.ai_service import GeminiClient
from core.github_service import GitHubManager
from core.parser import ContentParser

# Config
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
GH_TOKEN = os.getenv("GH_TOKEN")

class AutoBlogEngine:
    def __init__(self, config):
        self.config = config
        self.niche_name = config['name']
        self.source_repo = config['source_repo']
        self.prod_repo = config['prod_repo']
        self.languages = config.get('languages', ['en'])
        self.domain = config.get('domain', "")
        
        # Inicializar clientes
        self.ai = GeminiClient()
        self.github = GitHubManager()
        self.parser = ContentParser()
        self.jinja_env = Environment(loader=FileSystemLoader('templates'))

    async def fetch_and_generate(self):
        """Paso 1: Investigar tendencia -> Generar Artículos -> Subir al Source Repo"""
        logging.info(f"🚀 [{self.niche_name}] Iniciando ciclo de generación...")
        
        try:
            # 1.1 Obtener Tópico Viral/Tendencia
            topic_prompt = f"Identify a single, trending news topic relevant to: {self.config['keywords']}. Output ONLY the headline in English."
            logging.info("🧠 Analizando tendencias...")
            headline = await self.ai.generate(topic_prompt)
            headline = headline.strip().replace('"', '').replace("'", "")
            slug = re.sub(r'[^a-z0-9-]', '', re.sub(r'\s+', '-', headline.lower()))
            
            logging.info(f"📰 Tópico seleccionado: {headline}")

            # 1.2 Generar Artículos por Idioma
            for lang in self.languages:
                logging.info(f"  ✍️  Generando en {lang}...")
                
                # Prompt estructurado
                article_prompt = f"""
                Write a professional, SEO-optimized blog post in {lang} about: '{headline}'.
                
                Requirements:
                - Use Markdown.
                - Include a title line (H1).
                - Include a summary in the frontmatter metadata.
                - Add relevant tags in the frontmatter.
                - Technical and expert tone.
                - Length: ~800 words.
                
                Format Example:
                ---
                title: "{headline}"
                date: {datetime.datetime.now().strftime('%Y-%m-%d')}
                tags: [{self.config['keywords'].split(',')[0]}]
                summary: "A brief summary here."
                ---
                
                [Content starts here...]
                """
                
                content = await self.ai.generate(article_prompt)
                
                # 1.3 Subir al Source Repo (Headless CMS)
                # Estructura: content/{lang}/{slug}.md
                remote_path = f"content/{lang}/{slug}.md"
                self.github.create_file(
                    self.source_repo, 
                    remote_path, 
                    content, 
                    f"cms: auto-generated {slug} ({lang})"
                )
                
        except Exception as e:
            logging.error(f"❌ Error en generación para {self.niche_name}: {e}")

    def build_site(self):
        """Paso 2: Leer Source Repo -> Renderizar HTML -> Subir a Prod Repo"""
        logging.info(f"🏗️  [{self.niche_name}] Construyendo sitio estático...")
        
        # 2.1 Obtener todos los archivos MD del source repo
        files = self.github.get_files(self.source_repo, "content")
        posts = []
        
        for name, url in files.items():
            if name.endswith('.md'):
                raw_md = self.github.get_file_content(url)
                post = self.parser.parse(raw_md, name)
                posts.append(post)
        
        # Ordenar por fecha (reciente primero)
        posts.sort(key=lambda x: x['date'], reverse=True)
        
        # 2.2 Renderizar Index
        index_template = self.jinja_env.get_template('index.html')
        index_html = index_template.render(
            config=self.config, 
            posts=posts, 
            domain=self.domain
        )
        self.github.deploy_site(self.prod_repo, "index.html", index_html)
        
        # 2.3 Renderizar Posts Individuales
        post_template = self.jinja_env.get_template('post.html')
        
        for post in posts:
            # Crear subcarpetas si es necesario (ej: 2023/10/post.html)
            # Por simplicidad en GitHub Pages, usaremos ruta plana o año/mes
            
            date_path = post['date'].strftime('%Y/%m')
            full_path = f"{date_path}/{post['slug']}" if self.domain else post['slug']
            
            post_html = post_template.render(
                config=self.config, 
                post=post, 
                domain=self.domain
            )
            self.github.deploy_site(self.prod_repo, full_path, post_html)
            
        logging.info(f"✅ Sitio {self.niche_name} desplegado exitosamente.")


async def main():
    parser = argparse.ArgumentParser(description="Motor de Blogs Autónomos Multi-IA")
    parser.add_argument('--fetch', action='store_true', help="Generar contenido con IA y subir a Source Repo")
    parser.add_argument('--build', action='store_true', help="Leer Source Repo, compilar HTML y subir a Prod Repo")
    parser.add_argument('--all', action='store_true', help="Ejecutar Fetch y Build en secuencia")
    args = parser.parse_args()

    if not args.fetch and not args.build and not args.all:
        parser.print_help()
        return

    # Cargar configuración
    if not os.path.exists('config.json'):
        logging.error("❌ No se encontró config.json")
        return

    with open('config.json', 'r') as f: 
        niches = json.load(f)
    
    # Ejecutar para cada nicho configurado
    tasks = []
    for niche_config in niches:
        engine = AutoBlogEngine(niche_config)
        
        if args.fetch or args.all:
            tasks.append(engine.fetch_and_generate())
        
        if args.build:
            # Build es síncrono en este ejemplo por simplicidad de archivos,
            # pero se puede paralelizar si se desea.
            engine.build_site()
            
    if tasks:
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())