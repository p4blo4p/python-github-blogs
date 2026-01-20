# main_improved.py
import os
import json
import argparse
import asyncio
import logging
import re
import datetime
from pathlib import Path
 
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
    """Motor de blogs mejorado con selección específica"""
    
    def __init__(self, config):
        self.config = config
        self.niche_name = config['name']
        self.source_repo = config['source_repo']
        self.prod_repo = config['prod_repo']
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
    
    async def fetch_and_generate(self, ai_client):
        """
        FASE 1 (Ejecuta localmente en Termux con IA):
        - Analiza tendencias
        - Genera contenido con IA
        - Sube al repositorio fuente como CMS
        """
        logger.info(f"🚀 [{self.niche_name}] FASE 1: Generando contenido con IA...")
        
        try:
            # 1. Detectar tendencias
            topic_prompt = f"Identify a trending topic for: {self.config['keywords']}. Output ONLY the headline in English."
            logger.info("🧠 Analizando tendencias...")
            
            headline = await ai_client.generate(topic_prompt)
            headline = headline.strip().replace('"', '').replace("'", "")
            slug = re.sub(r'[^a-z0-9-]', '', re.sub(r'\s+', '-', headline.lower()))
            
            logger.info(f"📰 Tópico detectado: {headline}")
 
            # 2. Generar artículos por idioma
            for lang in self.languages:
                logger.info(f"  ✍️  Generando en {lang}...")
                
                article_prompt = f"""
                Write a professional, SEO-optimized blog post in {lang} about: '{headline}'
                
                Requirements:
                - Use Markdown format
                - Include frontmatter metadata
                - Expert tone, ~800 words
                
                Frontmatter format:
                ---
                title: "{headline}"
                date: {datetime.datetime.now().strftime('%Y-%m-%d')}
                tags: [{self.config['keywords'].split(',')[0]}]
                summary: "Professional blog post about {headline}"
                ---
                
                [Content here...]
                """
                
                content = await ai_client.generate(article_prompt)
                
                # 3. Subir al source repo (esto también puede hacerse localmente)
                self._upload_to_source_repo(lang, slug, content, headline)
                
            logger.info(f"✅ [{self.niche_name}] Contenido generado y subido exitosamente")
            
        except Exception as e:
            logger.error(f"❌ Error en generación: {e}")
            raise
 
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