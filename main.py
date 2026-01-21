import os
import asyncio
import argparse
import logging
import json
import datetime
import re
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
 
# Importar nuestros módulos
# Asegúrate de que estos archivos existan en la estructura de carpetas
try:
    from core.ai_service import GeminiClient
    from core.github_service import GitHubManager
    from core.parser import ContentParser
except ImportError:
    logging.warning("⚠️ No se pudieron importar los módulos 'core'. Esto es normal si estás en un entorno donde aún no existen.")
 
# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
 
class BlogSelector:
    """Gestiona la selección y carga de configuraciones de blogs"""
    
    def __init__(self, config_file='config.json'):
        self.config_file = config_file
        self.blogs = self._load_config()
    
    def _load_config(self):
        """Carga el archivo de configuración JSON"""
        if not os.path.exists(self.config_file):
            raise FileNotFoundError(f"❌ No se encontró {self.config_file}")
        
        with open(self.config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def list_blogs(self):
        """Lista todos los blogs disponibles"""
        return [blog['name'] for blog in self.blogs]
    
    def get_blog_config(self, blog_name=None):
        """Obtiene la configuración de un blog específico o todos"""
        if blog_name:
            for blog in self.blogs:
                if blog['name'].lower() == blog_name.lower():
                    return blog
            raise ValueError(f"❌ Blog '{blog_name}' no encontrado en config.json")
        return self.blogs
 
class AutoBlogEngine:
    """Motor de blogs unificado y corregido"""
    def __init__(self, config):
        self.config = config
        self.niche_name = config['name']
        self.repo = config['repo']
        self.source_branch = config.get('source_branch', 'main')
        self.prod_branch = config.get('prod_branch', 'gh-pages')
        self.languages = config.get('languages', ['en'])
        self.domain = config.get('domain', "")
        
        # Inicializar clientes
        try:
            self.ai = GeminiClient()
            self.github = GitHubManager()
            self.parser = ContentParser()
            self.jinja_env = Environment(loader=FileSystemLoader('templates'))
        except NameError:
            logger.error("❌ No se pudieron inicializar los clientes (GeminiClient, GitHubManager, etc). Verifica imports.")
            self.ai = None
            self.github = None
            self.parser = None
            self.jinja_env = None

        # Estado para construcción incremental
        self.state_file = f".state_{self.niche_name.replace(' ', '_').lower()}.json"
        self.state = self._load_state()
        
        logger.info(f"🎯 Blog configurado: {self.niche_name}")
        logger.info(f"📂 Source: {self.repo} (rama: {self.source_branch})")
        logger.info(f"🌐 Prod: {self.prod_branch}")
        logger.info(f"🗣️  Idiomas: {self.languages}")
    
    def _load_state(self):
        """Carga estado anterior para construcción incremental"""
        if os.path.exists(self.state_file):
            with open(self.state_file, 'r') as f:
                return json.load(f)
        return {"processed_files": [], "last_build": None}
    
    def _save_state(self):
        """Guarda estado actual"""
        self.state["last_build"] = datetime.datetime.now().isoformat()
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f)

    async def fetch_and_generate(self):
        """Paso 1: Investigar tendencia -> Generar Artículos -> Subir al Source Branch"""
        if not self.ai: return
        
        logger.info(f"🚀 [{self.niche_name}] Iniciando ciclo de generación...")
        
        try:
            # Obtener el tipo de contenido
            content_type = self.config.get('content_type', 'trending')
            current_date = datetime.datetime.now().strftime('%Y-%m-%d')
            
            # 1.1 Generar topic_prompt según content_type
            if content_type == 'trending':
                topic_prompt = f"""Today's date is {current_date}. Identify a single, trending news topic relevant to: {self.config['keywords']}. 
                Focus on recent developments, breaking news, or emerging trends. 
                Output ONLY the headline in English."""
                logger.info("🔥 Analizando tendencias de actualidad...")
            else:  # evergreen
                topic_prompt = f"""Identify a timeless, evergreen topic about: {self.config['keywords']}. 
                Focus on fundamental concepts, best practices, or educational content that remains relevant over time.
                Output ONLY the headline in English."""
                logger.info("🌲 Generando contenido evergreen...")
            
            # 1.2 Generar el headline
            headline = await self.ai.generate(topic_prompt)
            headline = headline.strip().replace('"', '').replace("'", "")
            slug = re.sub(r'[^a-z0-9-]', '', re.sub(r'\s+', '-', headline.lower()))
            
            logger.info(f"📰 Tópico seleccionado: {headline}")
 
            # 1.3 Generar artículos por idioma
            for lang in self.languages:
                logger.info(f"  ✍️  Generando en {lang}...")
                
                # Personalizar article_prompt según content_type
                if content_type == 'trending':
                    article_prompt = f"""
                    Write a professional, SEO-optimized blog post in {lang} about: '{headline}'.
                    Today's date is {current_date}. Focus on recent developments, news, or emerging trends.
                    Requirements:
                    - Use Markdown.
                    - Include a title line (H1).
                    - Include a summary in the frontmatter metadata.
                    - Add relevant tags in the frontmatter.
                    - Technical and expert tone.
                    - Length: ~800 words.
                    - Include current date references where appropriate.
                    Format Example:
                    ---
                    title: "{headline}"
                    date: {current_date}
                    tags: [{self.config['keywords'].split(',')[0]}]
                    summary: "A brief summary here."
                    ---
                    [Content starts here...]
                    """
                else:  # evergreen
                    article_prompt = f"""
                    Write a professional, SEO-optimized blog post in {lang} about: '{headline}'.
                    Focus on timeless content, fundamental concepts, and best practices that remain valuable over time.
                    Requirements:
                    - Use Markdown.
                    - Include a title line (H1).
                    - Include a summary in the frontmatter metadata.
                    - Add relevant tags in the frontmatter.
                    - Educational and expert tone.
                    - Length: ~800 words.
                    - Avoid time-sensitive references.
                    Format Example:
                    ---
                    title: "{headline}"
                    date: {current_date}
                    tags: [{self.config['keywords'].split(',')[0]}]
                    summary: "A brief summary here."
                    ---
                    [Content starts here...]
                    """
                
                content = await self.ai.generate(article_prompt)
                
                # 1.4 Subir al Source Branch (Headless CMS)
                remote_path = f"content/{lang}/{slug}.md"
                commit_msg = f"cms: auto-generated {slug} ({lang}) - {content_type}"
                
                if self.github:
                    self.github.create_file(
                        self.repo, 
                        remote_path, 
                        content, 
                        commit_msg,
                        branch=self.source_branch
                    )
                else:
                    # Fallback local si no hay github manager
                    self._upload_to_repo(lang, slug, content, headline)
                
        except Exception as e:
            logger.error(f"❌ Error en generación para {self.niche_name}: {e}")
 
    def _upload_to_repo(self, lang, slug, content, headline):
        """Sube contenido generado localmente si no hay servicio de GitHub activo"""
        content_path = Path(f"generated_content/{self.niche_name}/{lang}")
        content_path.mkdir(parents=True, exist_ok=True)
        
        file_path = content_path / f"{slug}.md"
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"💾 Guardado localmente: {file_path}")
        logger.info(f"📤 Recuerda subir estos archivos a GitHub: {self.repo}")
    
        def build_site(self, github_token=None):
        """Paso 2: Leer Source Branch -> Renderizar HTML -> Subir a Prod Branch"""
        if not self.github or not self.parser or not self.jinja_env:
            logger.error("❌ Faltan dependencias (github/parser/jinja) para construir el sitio.")
            return

        logger.info(f"🏗️  [{self.niche_name}] Construyendo sitio estático...")
        
        # Aseguramos que el token esté configurado en el cliente de GitHub
        if github_token:
            self.github.set_auth_token(github_token) # Asegúrate de que tu GitHubManager tenga este método
        elif not self.github.is_authenticated(): # Método hipotético de verificación
            logger.warning("⚠️ No se detectó token de GitHub. El deploy podría fallar.")

        # 2.1 Obtener todos los archivos MD del source branch
        try:
            files = self.github.get_files(self.repo, "content", branch=self.source_branch)
        except Exception as e:
            logger.error(f"❌ Error obteniendo archivos del repo: {e}")
            return

        posts = []
        
        for name, url in files.items():
            if name.endswith('.md'):
                try:
                    raw_md = self.github.get_file_content(url)
                    post = self.parser.parse(raw_md, name)
                    posts.append(post)
                except Exception as e:
                    logger.warning(f"⚠️ Error parseando {name}: {e}")
        
        if not posts:
            logger.warning("⚠️ No se encontraron posts para renderizar.")
            return
            
        # Ordenar por fecha (reciente primero)
        posts.sort(key=lambda x: x.get('date', datetime.datetime.now()), reverse=True)
        
        # Función auxiliar para intentar subir y manejar errores
        def deploy_file(path, content, msg):
            try:
                # Si deploy_site no lanza excepción, confiamos en que funcionó
                self.github.deploy_site(self.repo, path, content, branch=self.prod_branch)
            except Exception as e:
                logger.error(f"❌ Fallo crítico subiendo {path}: {e}")
                # Relanzamos la excepción para detener el proceso y no mostrar el mensaje de éxito
                raise Exception(f"Detenido por error en subida de {path}")

        # 2.2 Renderizar Index
        try:
            index_template = self.jinja_env.get_template('index.html')
            index_html = index_template.render(
                config=self.config, 
                posts=posts, 
                domain=self.domain
            )
            deploy_file("index.html", index_html, "Update index")
        except Exception as e:
            logger.error(f"❌ No se pudo desplegar el index: {e}")
            return

        # 2.3 Renderizar Posts Individuales
        try:
            post_template = self.jinja_env.get_template('post.html')
            
            for post in posts:
                date_path = post['date'].strftime('%Y/%m')
                full_path = f"{date_path}/{post['slug']}" if self.domain else post['slug']
                
                post_html = post_template.render(
                    config=self.config, 
                    post=post, 
                    domain=self.domain
                )
                deploy_file(full_path, post_html, f"Update post {post['slug']}")
                
            # Solo llegamos aquí si todo fue bien
            logger.info(f"✅ Sitio {self.niche_name} desplegado exitosamente en rama {self.prod_branch}")
            self._save_state()
        except Exception as e:
            logger.error(f"❌ Error general en el renderizado de posts: {e}")
            
async def main():
    parser = argparse.ArgumentParser(
        description="Motor de Blogs Autónomos - Versión Corregida",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  # Generar contenido para un blog específico (con IA - ejecuta en Termux)
  python main.py --blog "Tech News AI" --fetch
  
  # Listar blogs disponibles
  python main.py --list
  
  # Construir sitio sin IA (ejecuta en GitHub Actions)
  python main.py --blog "Tech News AI" --build
        """
    )
    
    # Argumentos principales
    parser.add_argument('--blog', '-b', type=str, 
                       help='Nombre del blog específico a procesar (de config.json)')
    parser.add_argument('--list', '-l', action='store_true',
                       help='Listar todos los blogs disponibles')
    
    # Fases de ejecución
    parser.add_argument('--fetch', '-f', action='store_true',
                       help='FASE 1: Generar contenido con IA (ejecutar en Termux)')
    parser.add_argument('--build', action='store_true',
                       help='FASE 2: Construir sitio estático (ejecutar en GitHub Actions)')
    parser.add_argument('--all', action='store_true',
                       help='Ejecutar ambas fases (solo para pruebas locales)')
    
    args = parser.parse_args()
 
    # Inicializar selector de blogs
    try:
        blog_selector = BlogSelector()
    except FileNotFoundError as e:
        logger.error(str(e))
        return
 
    # Listar blogs
    if args.list:
        print("\n📋 Blogs disponibles en config.json:")
        for i, blog_name in enumerate(blog_selector.list_blogs(), 1):
            print(f"  {i}. {blog_name}")
        return
 
    # Obtener configuración del blog
    try:
        if args.blog:
            blog_configs = [blog_selector.get_blog_config(args.blog)]
            logger.info(f"🎯 Procesando blog específico: {args.blog}")
        else:
            blog_configs = blog_selector.get_blog_config()
            logger.info(f"🎯 Procesando todos los blogs ({len(blog_configs)})")
    except ValueError as e:
        logger.error(str(e))
        return
 
    # Validar argumentos
    if not args.fetch and not args.build and not args.all:
        parser.print_help()
        return
 
    # Ejecutar para cada blog
    for blog_config in blog_configs:
        engine = AutoBlogEngine(blog_config)
        
        try:
            if args.fetch or args.all:
                # fetch_and_generate usa self.ai inicializado en __init__
                await engine.fetch_and_generate()
            
            if args.build or args.all:
                # build_site usa self.github inicializado en __init__
                engine.build_site(os.getenv("GH_TOKEN"))
                
        except Exception as e:
            logger.error(f"❌ Error procesando {blog_config['name']}: {e}")
            import traceback
            traceback.print_exc()
            continue
 
if __name__ == "__main__":
    asyncio.run(main())