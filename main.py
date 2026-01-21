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
logger = logging.getLogger(__name__)
GH_TOKEN = os.getenv("GH_TOKEN")
 
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
    """Motor de blogs mejorado con selección específica"""
    def __init__(self, config):
        self.config = config
        self.niche_name = config['name']
        self.repo = config['repo']  # Nuevo: repo común
        self.source_branch = config.get('source_branch', 'main')  # Rama para contenido
        self.prod_branch = config.get('prod_branch', 'gh-pages')  # Rama para producción
        self.languages = config.get('languages', ['en'])
        self.domain = config.get('domain', "")
        
        # Inicializar clientes
        self.ai = GeminiClient()
        self.github = GitHubManager()
        self.parser = ContentParser()
        self.jinja_env = Environment(loader=FileSystemLoader('templates'))
 
    async def fetch_and_generate(self):
        """Paso 1: Investigar tendencia -> Generar Artículos -> Subir al Source Branch"""
        logging.info(f"🚀 [{self.niche_name}] Iniciando ciclo de generación...")
        
        try:
            # Obtener el tipo de contenido
            content_type = self.config.get('content_type', 'trending')
            current_date = datetime.datetime.now().strftime('%Y-%m-%d')
            
            # 1.1 Generar topic_prompt según content_type
            if content_type == 'trending':
                topic_prompt = f"""Today's date is {current_date}. Identify a single, trending news topic relevant to: {self.config['keywords']}. 
                Focus on recent developments, breaking news, or emerging trends. 
                Output ONLY the headline in English."""
                logging.info("🔥 Analizando tendencias de actualidad...")
            else:  # evergreen
                topic_prompt = f"""Identify a timeless, evergreen topic about: {self.config['keywords']}. 
                Focus on fundamental concepts, best practices, or educational content that remains relevant over time.
                Output ONLY the headline in English."""
                logging.info("🌲 Generando contenido evergreen...")
            
            # 1.2 Generar el headline
            headline = await self.ai.generate(topic_prompt)
            headline = headline.strip().replace('"', '').replace("'", "")
            slug = re.sub(r'[^a-z0-9-]', '', re.sub(r'\s+', '-', headline.lower()))
            
            logging.info(f"📰 Tópico seleccionado: {headline}")
 
            # 1.3 Generar artículos por idioma
            for lang in self.languages:
                logging.info(f"  ✍️  Generando en {lang}...")
                
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
                # Estructura: content/{lang}/{slug}.md
                remote_path = f"content/{lang}/{slug}.md"
                self.github.create_file(
                    self.repo, 
                    remote_path, 
                    content, 
                    f"cms: auto-generated {slug} ({lang}) - {content_type}",
                    branch=self.source_branch
                )
                
        except Exception as e:
            logging.error(f"❌ Error en generación para {self.niche_name}: {e}")
 
    def build_site(self):
        """Paso 2: Leer Source Branch -> Renderizar HTML -> Subir a Prod Branch"""
        logging.info(f"🏗️  [{self.niche_name}] Construyendo sitio estático...")
        
        # 2.1 Obtener todos los archivos MD del source branch
        files = self.github.get_files(self.repo, "content", branch=self.source_branch)
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
        self.github.deploy_site(self.repo, "index.html", index_html, branch=self.prod_branch)
        
        # 2.3 Renderizar Posts Individuales
        post_template = self.jinja_env.get_template('post.html')
        
        for post in posts:
            # Crear subcarpetas si es necesario (ej: 2023/10/post.html)
            date_path = post['date'].strftime('%Y/%m')
            full_path = f"{date_path}/{post['slug']}" if self.domain else post['slug']
            
            post_html = post_template.render(
                config=self.config, 
                post=post, 
                domain=self.domain
            )
            self.github.deploy_site(self.repo, full_path, post_html, branch=self.prod_branch)
            
        logging.info(f"✅ Sitio {self.niche_name} desplegado exitosamente en rama {self.prod_branch}")    
        
    
    def __init__(self, config):
        self.config = config
        self.niche_name = config['name']
        elf.repo = config['repo']
        self.source_branch = config['source_branch']
        self.prod_branch = config['prod_branch']
        self.languages = config.get('languages', ['es', 'en'])
        self.domain = config.get('domain', "")
        
        # Estado para construcción incremental
        self.state_file = f".state_{self.niche_name.replace(' ', '_').lower()}.json"
        self.state = self._load_state()
        
        logger.info(f"🎯 Blog configurado: {self.niche_name}")
        logger.info(f"📂 Source: {self.source_repo}")
        logger.info(f"🌐 Prod: {self.prod_repo}")
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
        """Paso 1: Investigar tendencia -> Generar Artículos -> Subir al Source Repo"""
        logging.info(f"🚀 [{self.niche_name}] Iniciando ciclo de generación...")
        
        try:
            # 获取内容类型，默认为 trending
            content_type = self.config.get('content_type', 'trending')
            current_date = datetime.datetime.now().strftime('%Y-%m-%d')
            
            # 1.1 根据 content_type 生成不同的 topic_prompt
            if content_type == 'trending':
                topic_prompt = f"""Today's date is {current_date}. Identify a single, trending news topic relevant to: {self.config['keywords']}. 
                Focus on recent developments, breaking news, or emerging trends. 
                Output ONLY the headline in English."""
                logging.info("🔥 Analizando tendencias de actualidad...")
            else:  # evergreen
                topic_prompt = f"""Identify a timeless, evergreen topic about: {self.config['keywords']}. 
                Focus on fundamental concepts, best practices, or educational content that remains relevant over time.
                Output ONLY the headline in English."""
                logging.info("🌲 Generando contenido evergreen...")
            
            # 1.2 生成标题
            headline = await self.ai.generate(topic_prompt)
            headline = headline.strip().replace('"', '').replace("'", "")
            slug = re.sub(r'[^a-z0-9-]', '', re.sub(r'\s+', '-', headline.lower()))
            
            logging.info(f"📰 Tópico seleccionado: {headline}")
    
            # 1.3 生成文章时，根据 content_type 调整提示词
            for lang in self.languages:
                logging.info(f"  ✍️  Generando en {lang}...")
                
                # 根据内容类型定制 article_prompt
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
                
                # 1.4 上传到 Source Repo
                remote_path = f"content/{lang}/{slug}.md"
                self.github.create_file(
                    self.source_repo, 
                    remote_path, 
                    content, 
                    f"cms: auto-generated {slug} ({lang}) - {content_type}"
                )
                
        except Exception as e:
            logging.error(f"❌ Error en generación para {self.niche_name}: {e}")
 
    def _upload_to_source_repo(self, lang, slug, content, headline):
        """Sube contenido generado al repositorio fuente (puede ejecutarse localmente)"""
        # Implementación básica - puedes mejorar con GitHub API local
        content_path = Path(f"generated_content/{self.niche_name}/{lang}")
        content_path.mkdir(parents=True, exist_ok=True)
        
        file_path = content_path / f"{slug}.md"
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"💾 Guardado localmente: {file_path}")
        logger.info(f"📤 Recuerda subir estos archivos a GitHub: {self.source_repo}")
    
    def build_site(self, github_token):
        """
        FASE 2 (Ejecuta en GitHub Actions SIN IA):
        - Lee contenido del repositorio fuente
        - Construye sitio estático
        - Sube a repositorio de producción
        """
        logger.info(f"🏗️  [{self.niche_name}] FASE 2: Construyendo sitio estático...")
        
        # Verificar que estamos en entorno de GitHub Actions
        if not os.getenv('GITHUB_ACTIONS') and not github_token:
            logger.warning("⚠️  Ejecutando localmente - para construcción completa usa GitHub Actions")
        
        # Aquí iría tu lógica actual de construcción
        # [generator.py, parser.py, etc.]
        
        logger.info(f"✅ [{self.niche_name}] Sitio construido exitosamente")
 
async def main():
    parser = argparse.ArgumentParser(
        description="Motor de Blogs Autónomos - Versión Mejorada",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  # Generar contenido para un blog específico (con IA - ejecuta en Termux)
  python main_improved.py --blog "Tech News AI" --fetch
  
  # Listar blogs disponibles
  python main_improved.py --list
  
  # Construir sitio sin IA (ejecuta en GitHub Actions)
  python main_improved.py --blog "Tech News AI" --build
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
 
    # Importar cliente de IA (solo si se necesita generación)
    ai_client = None
    if args.fetch or args.all:
        try:
            from core.ai_service import GeminiClient
            ai_client = GeminiClient()
            logger.info("✅ Cliente IA inicializado")
        except ImportError:
            logger.error("❌ No se pudo importar cliente IA - verifica core/ai_service.py")
            return
 
    # Ejecutar para cada blog
    for blog_config in blog_configs:
        engine = AutoBlogEngine(blog_config)
        
        try:
            if args.fetch or args.all:
                await engine.fetch_and_generate(ai_client)
            
            if args.build:
                engine.build_site(os.getenv("GH_TOKEN"))
                
        except Exception as e:
            logger.error(f"❌ Error procesando {blog_config['name']}: {e}")
            continue
 
if __name__ == "__main__":
    asyncio.run(main())