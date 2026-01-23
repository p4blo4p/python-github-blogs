import os
import asyncio
import argparse
import logging
import json
import datetime
import re
import traceback
import hashlib
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

# --- Librerías Externas para Mejoras (Items 2, 3, 4) ---
import feedparser
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import openai
import anthropic

# Importar módulos originales del proyecto
try:
    from core.ai_service import GeminiClient
    from core.github_service import GitHubManager
    from core.parser import ContentParser
except ImportError:
    logging.warning("⚠️ No se pudieron importar los módulos 'core'. Esto es normal si estás en un entorno donde aún no existen.")

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ==========================================
# MÓDULOS DE MEJORA INTEGRADOS (Core Inline)
# ==========================================
# Para mantenerlo en un solo archivo, incluyo aquí las clases de las mejoras
# En producción, deberían estar en core/sources.py, core/seo.py, etc.

class EnhancedSources:
    """Item 3: Fuentes de Datos Reales"""
    
    @staticmethod
    def get_github_trending(language=""):
        url = f"https://github.com/trending/{language}" if language else "https://github.com/trending"
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            repos = []
            articles = soup.select('article.Box-row')
            
            for article in articles[:5]: # Top 5
                try:
                    title_tag = article.select_one('h2 a')
                    desc_tag = article.select_one('p')
                    title = title_tag.get_text().strip().replace("\n", "").replace(" ", "")
                    url_repo = "https://github.com" + title_tag['href']
                    description = desc_tag.get_text().strip() if desc_tag else "Sin descripción"
                    
                    repos.append({
                        "title": title,
                        "url": url_repo,
                        "description": description
                    })
                except Exception:
                    continue
            return repos
        except Exception as e:
            logger.error(f"Error scrapeando GitHub Trending: {e}")
            return []

    @staticmethod
    def get_external_rss(feed_url, limit=3):
        try:
            feed = feedparser.parse(feed_url)
            entries = []
            for entry in feed.entries[:limit]:
                entries.append({
                    "title": entry.title,
                    "link": entry.link,
                    "summary": entry.get('summary', '')
                })
            return entries
        except Exception as e:
            logger.error(f"Error leyendo RSS: {e}")
            return []

class SEOGenerator:
    """Item 2: Generación de Sitemap y RSS"""
    
    @staticmethod
    def generate_sitemap(posts, output_path, base_url):
        import xml.etree.ElementTree as ET
        urlset = ET.Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
        
        # Home
        url = ET.SubElement(urlset, "url")
        ET.SubElement(url, "loc").text = base_url
        ET.SubElement(url, "lastmod").text = datetime.datetime.now().strftime("%Y-%m-%d")
        
        for post in posts:
            url = ET.SubElement(urlset, "url")
            # Asumiendo estructura de URL del sistema original
            post_url = f"{base_url}{post['date'].strftime('%Y/%m')}/{post['slug']}" if base_url else post['slug']
            ET.SubElement(url, "loc").text = post_url
            ET.SubElement(url, "lastmod").text = post['date'].strftime("%Y-%m-%d")
            
        tree = ET.ElementTree(urlset)
        # En el sistema original, esto se sube a GitHub, no se guarda localmente necesariamente
        # Pero devolvemos el contenido string para subirlo
        import io
        output = io.StringIO()
        tree.write(output, encoding='unicode', xml_declaration=True)
        return output.getvalue()

    @staticmethod
    def generate_rss(posts, output_path, base_url, blog_title):
        import xml.etree.ElementTree as ET
        rss = ET.Element("rss", version="2.0")
        channel = ET.SubElement(rss, "channel")
        
        ET.SubElement(channel, "title").text = blog_title
        ET.SubElement(channel, "link").text = base_url
        ET.SubElement(channel, "description").text = "Automated Blog Content"
        
        for post in posts:
            item = ET.SubElement(channel, "item")
            ET.SubElement(item, "title").text = post['title']
            post_url = f"{base_url}{post['date'].strftime('%Y/%m')}/{post['slug']}" if base_url else post['slug']
            ET.SubElement(item, "link").text = post_url
            # Limpiar HTML del resumen
            clean_summary = re.sub('<[^<]+?>', '', post.get('summary', ''))[:200]
            ET.SubElement(item, "description").text = clean_summary
            
        tree = ET.ElementTree(rss)
        import io
        output = io.StringIO()
        tree.write(output, encoding='unicode', xml_declaration=True)
        return output.getvalue()

class MultiAIProvider:
    """Item 4: Fiabilidad y Fallback entre Modelos"""
    
    def __init__(self):
        self.clients = {}
        self._init_gemini()
        self._init_openai()
        self._init_anthropic()
        
    def _init_gemini(self):
        key = os.getenv("GEMINI_API_KEY")
        if key:
            try:
                # Usamos el cliente original si es posible, o creamos uno nuevo
                self.clients['gemini'] = GeminiClient() 
                logger.info("✅ Gemini cargado.")
            except Exception as e:
                logger.warning(f"⚠️ Error cargando Gemini: {e}")

    def _init_openai(self):
        key = os.getenv("OPENAI_API_KEY")
        if key:
            try:
                self.clients['openai'] = openai.OpenAI(api_key=key)
                logger.info("✅ OpenAI cargado.")
            except Exception as e:
                logger.warning(f"⚠️ Error cargando OpenAI: {e}")
    
    def _init_anthropic(self):
        key = os.getenv("ANTHROPIC_API_KEY")
        if key:
            try:
                self.clients['anthropic'] = anthropic.Anthropic(api_key=key)
                logger.info("✅ Anthropic cargado.")
            except Exception as e:
                logger.warning(f"⚠️ Error cargando Anthropic: {e}")

    async def generate(self, prompt, preferred="gemini"):
        """
        Ejecuta la generación con fallback.
        Intenta 'preferred' -> otros disponibles.
        """
        # Lista de prioridad
        priority = [preferred]
        if "gemini" in self.clients and "gemini" not in priority: priority.append("gemini")
        if "openai" in self.clients and "openai" not in priority: priority.append("openai")
        if "anthropic" in self.clients and "anthropic" not in priority: priority.append("anthropic")

        last_error = None
        
        for model in priority:
            if model not in self.clients:
                continue
                
            try:
                logger.info(f"🤖 Intentando generar con: {model.upper()}")
                
                if model == "gemini":
                    # El GeminiClient original es async
                    return await self.clients['gemini'].generate(prompt)
                
                elif model == "openai":
                    # OpenAI es síncrono, lo ejecutamos en un thread para no bloquear el event loop
                    def run_openai():
                        resp = self.clients['openai'].chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[{"role": "user", "content": prompt}]
                        )
                        return resp.choices[0].message.content
                    return await asyncio.to_thread(run_openai)
                
                elif model == "anthropic":
                    def run_anthropic():
                        msg = self.clients['anthropic'].messages.create(
                            model="claude-3-haiku-20240307",
                            max_tokens=1024,
                            messages=[{"role": "user", "content": prompt}]
                        )
                        return msg.content[0].text
                    return await asyncio.to_thread(run_anthropic)
                    
            except Exception as e:
                last_error = e
                logger.warning(f"❌ Fallo con {model}: {e}. Probando siguiente modelo...")
                continue
        
        logger.error("💥 Todos los modelos de IA fallaron.")
        raise Exception(f"No se pudo generar contenido con ningún proveedor. Último error: {last_error}")

# ==========================================
# CLASES ORIGINALES MEJORADAS
# ==========================================

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
        """Motor de blogs con prioridad de traducciones"""
        def __init__(self, config):
            self.config = config
            self.niche_name = config['name']
            self.repo = config['repo']
            self.source_branch = config.get('source_branch', 'main')
            self.prod_branch = config.get('prod_branch', 'gh-pages')
            self.languages = config.get('languages', ['en', 'es']) # Asegúrate de tener 'en' y 'es'
            self.domain = config.get('domain', "")
            
            try:
                self.ai = MultiAIProvider()
                self.github = GitHubManager()
                self.parser = ContentParser()
                self.jinja_env = Environment(loader=FileSystemLoader('templates'))
                self.sources = EnhancedSources()
            except Exception as e:
                logger.error(f"ERROR: No se pudieron inicializar los clientes: {e}")
                self.ai = None
                self.github = None
                self.parser = None
                self.jinja_env = None

            self.state_file = f".state_{self.niche_name.replace(' ', '_').lower()}.json"
            self.state = self._load_state()
            
            logger.info(f"Blog configurado: {self.niche_name}")
            logger.info(f"Source: {self.repo} (rama: {self.source_branch})")
            logger.info(f"Prod: {self.prod_branch}")
        
        def _load_state(self):
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            return {"processed_files": [], "last_build": None}
        
        def _save_state(self):
            self.state["last_build"] = datetime.datetime.now().isoformat()
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f)
        
        def _get_pending_translations(self, source_lang='en', target_lang='es'):
            """
            Busca archivos en 'source_lang' que no existen en 'target_lang'.
            Retorna una lista de nombres de archivo (slugs) pendientes.
            """
            if not self.github:
                return []
                
            try:
                source_files = self.github.get_files(self.repo, f"content/{source_lang}", branch=self.source_branch)
                target_files = self.github.get_files(self.repo, f"content/{target_lang}", branch=self.source_branch)
                
                # Extraer solo los slugs (nombres sin .md)
                source_slugs = set([f.replace('.md', '') for f in source_files.keys()])
                target_slugs = set([f.replace('.md', '') for f in target_files.keys()])
                
                # La diferencia son los pendientes
                pending = source_slugs - target_slugs
                return list(pending)
                
            except Exception as e:
                logger.warning(f"Error verificando traducciones pendientes: {e}")
                return []

        async def _translate_post(self, slug, source_lang, target_lang):
            """
            Descarga el post en source_lang, genera traducción y sube a target_lang.
            """
            logger.info(f"🌍 Traduciendo '{slug}' de {source_lang} a {target_lang}...")
            
            # 1. Obtener contenido original
            try:
                source_path = f"content/{source_lang}/{slug}.md"
                # get_files devuelve un dict {nombre: url}, necesitamos encontrar la URL
                files_map = self.github.get_files(self.repo, f"content/{source_lang}", branch=self.source_branch)
                raw_url = files_map.get(f"{slug}.md")
                
                if not raw_url:
                    logger.error(f"No se encontró el archivo origen: {source_path}")
                    return False

                raw_md = self.github.get_file_content(raw_url)
                original_post = self.parser.parse(raw_md, f"{slug}.md")
                
                if not original_post:
                    return False

            except Exception as e:
                logger.error(f"Error leyendo post original: {e}")
                return False

            # 2. Generar Prompt de Traducción
            # Extraemos solo el contenido sin frontmatter para traducir, o traducimos todo
            # Es mejor traducir el cuerpo y mantener el frontmatter estructurado
            
            translate_prompt = f"""
            Translate the following blog post content into {target_lang}.
            Maintain Markdown formatting, links, and code blocks exactly as they are.
            
            Title: {original_post['title']}
            Content:
            {original_post['content']}
            
            Output ONLY the translated content in Markdown.
            """

            try:
                # 3. Llamada a IA
                translated_content = await self.ai.generate(translate_prompt, preferred='gemini')
                
                # Reconstruir el frontmatter para el nuevo idioma
                # Aquí podríamos traducir el título y tags también si quisiéramos
                new_frontmatter = f"""---
title: "{original_post['title']}" # Puedes pedir a la IA que lo traduzca aparte si quieres
date: {original_post['date']}
tags: [{', '.join(original_post.get('tags', []))}]
summary: "{original_post.get('summary', '')}"
lang: {target_lang}
translated_from: {source_lang}
---
"""
                
                final_md = new_frontmatter + translated_content
                
                # 4. Subir
                target_path = f"content/{target_lang}/{slug}.md"
                commit_msg = f"translate: {slug} ({source_lang} -> {target_lang})"
                
                if self.github:
                    self.github.create_file(self.repo, target_path, final_md, commit_msg, branch=self.source_branch)
                    logger.info(f"✅ Traducción subida: {target_path}")
                    return True
                    
            except Exception as e:
                logger.error(f"❌ Error en traducción IA: {e}")
                return False

        async def fetch_and_generate(self):
            """Flujo mejorado: Prioriza traducciones, luego nuevos posts."""
            if not self.ai: return
            
            logger.info(f"[{self.niche_name}] Iniciando ciclo (Prioridad: Traducciones)...")
            
            # 1. Verificar si hay traducciones pendientes (Asumimos EN -> ES)
            # Solo si hay más de un idioma configurado
            pending_translations = []
            if len(self.languages) > 1:
                # Buscamos pendientes del primer idioma hacia el segundo
                src = self.languages[0]
                tgt = self.languages[1]
                pending_translations = self._get_pending_translations(src, tgt)
            
            # 2. ACCIÓN A: Traducir si hay pendientes
            if pending_translations:
                logger.info(f"🕒 Se encontraron {len(pending_translations)} traducciones pendientes. Procesando la más reciente...")
                # Procesar solo una para no exceder cuota en esta ejecución
                slug_to_translate = pending_translations[0] 
                success = await self._translate_post(slug_to_translate, self.languages[0], self.languages[1])
                
                if success:
                    logger.info("✅ Tarea de traducción completada en este ciclo.")
                else:
                    logger.error("❌ Falló la traducción.")
                return # Salimos aquí para no generar nuevo contenido en la misma hora

            # 3. ACCIÓN B: Generar nuevo contenido si no hay pendientes
            logger.info("✅ No hay traducciones pendientes. Generando nuevo artículo...")
            
            try:
                real_data_context = ""
                content_type = self.config.get('content_type', 'trending')
                current_date = datetime.datetime.now().strftime('%Y-%m-%d')
                
                # Lógica de obtención de datos (igual que antes)
                if content_type == 'github_trending':
                    repos = self.sources.get_github_trending(self.config.get('language_filter', 'python'))
                    if repos:
                        target = repos[0]
                        real_data_context = f"CONTEXT: GitHub Repo: {target['title']}. Desc: {target['description']}. URL: {target['url']}"
                        base_topic = target['title']
                    else:
                        base_topic = "Trending GitHub Development"
                
                elif content_type == 'rss_news':
                    news_list = self.sources.get_external_rss(self.config.get('rss_url', 'http://feeds.feedburner.com/TechCrunch/'))
                    if news_list:
                        target = news_list[0]
                        real_data_context = f"CONTEXT: News: {target['title']}. Summary: {target['summary']}"
                        base_topic = target['title']
                    else:
                        base_topic = "Latest Tech News"
                else:
                    topic_prompt = f"Identify a trending topic about: {self.config['keywords']}. Output ONLY the topic headline."
                    base_topic = await self.ai.generate(topic_prompt, preferred='gemini')

                logger.info(f"📰 Nuevo Tópico: {base_topic.strip()}")
                
                # Generar para TODOS los idiomas
                for lang in self.languages:
                    logger.info(f"  ✍️  [{lang}] Generando nuevo contenido...")
                    existing_titles = self._get_existing_titles(lang)
                    
                    title_gen_prompt = f"Translate and adapt the following topic into a compelling blog post title in {lang}. Topic: {base_topic}. Output ONLY the title."
                    new_title = await self.ai.generate(title_gen_prompt, preferred='gemini')
                    new_title = new_title.strip().replace('"', '').replace("'", "")
                    
                    if new_title.lower() in existing_titles:
                        logger.warning(f"⚠️ Duplicado remoto: {new_title}. Saltando.")
                        continue
                    
                    clean_slug = re.sub(r'[^a-z0-9-]', '', re.sub(r'\s+', '-', new_title.lower()))
                    
                    article_prompt = f"""
                    Write a professional, SEO-optimized blog post in {lang}.
                    Target Title: {new_title}
                    {real_data_context}
                    Today's date is {current_date}.
                    Requirements:
                    - Use Markdown.
                    - H1 Title must be exactly: {new_title}
                    - Include a summary in the frontmatter.
                    - Add relevant tags: {self.config['keywords']}
                    - Format Example:
                    ---
                    title: "{new_title}"
                    date: {current_date}
                    tags: [{self.config['keywords'].split(',')[0]}]
                    summary: "A brief summary here."
                    ---
                    """
                    
                    content = await self.ai.generate(article_prompt, preferred=self.config.get('preferred_ai', 'gemini'))
                    
                    remote_path = f"content/{lang}/{clean_slug}.md"
                    commit_msg = f"cms: auto-generated {clean_slug} ({lang})"
                    
                    if self.github:
                        self.github.create_file(self.repo, remote_path, content, commit_msg, branch=self.source_branch)
                    else:
                        path = Path(f"generated_content/{self.niche_name}/{lang}")
                        path.mkdir(parents=True, exist_ok=True)
                        (path / f"{clean_slug}.md").write_text(content, encoding='utf-8')
                        
            except Exception as e:
                logger.error(f"❌ Error en generación para {self.niche_name}: {e}")
                traceback.print_exc()
     
        # ... (El resto de métodos build_site, _get_existing_titles, etc. se mantienen igual que en la versión anterior) ...
     
        def build_site(self, github_token=None):
            """Paso 2: Leer MD -> Renderizar -> Generar SEO -> Subir"""
            if not self.github or not self.parser or not self.jinja_env:
                logger.error("❌ Faltan dependencias para construir el sitio.")
                return

            logger.info(f"🏗️  [{self.niche_name}] Construyendo sitio estático con SEO...")
            
            try:
                files = self.github.get_files(self.repo, "content", branch=self.source_branch)
            except Exception as e:
                logger.error(f"❌ Error obteniendo archivos: {e}")
                return

            posts = []
            for name, url in files.items():
                if name.endswith('.md'):
                    try:
                        raw_md = self.github.get_file_content(url)
                        post = self.parser.parse(raw_md, name)
                        posts.append(post)
                    except Exception:
                        continue
            
            if not posts:
                logger.warning("⚠️ No posts encontrados.")
                return
                
            posts.sort(key=lambda x: x.get('date', datetime.datetime.now()), reverse=True)
            
            # Función helper para subida segura
            def deploy_file(path, content, msg):
                try:
                    self.github.deploy_site(self.repo, path, content, branch=self.prod_branch)
                except Exception as e:
                    logger.error(f"❌ Fallo subiendo {path}: {e}")
                    raise

            # 1. Renderizar Index
            try:
                index_template = self.jinja_env.get_template('index.html')
                index_html = index_template.render(config=self.config, posts=posts, domain=self.domain)
                deploy_file("index.html", index_html, "Update index")
            except Exception as e:
                logger.error(f"❌ Error renderizando index: {e}")
                return

            # 2. Renderizar Posts
            try:
                post_template = self.jinja_env.get_template('post.html')
                for post in posts:
                    date_path = post['date'].strftime('%Y/%m')
                    full_path = f"{date_path}/{post['slug']}" if self.domain else post['slug']
                    post_html = post_template.render(config=self.config, post=post, domain=self.domain)
                    deploy_file(full_path, post_html, f"Update post {post['slug']}")
                    
            except Exception as e:
                logger.error(f"❌ Error renderizando posts: {e}")
                return

            # Item 2: Generación de Sitemap y RSS (NUEVO)
            try:
                logger.info("📈 Generando Sitemap.xml y RSS.xml...")
                
                base_url = f"https://{self.domain}/" if self.domain else ""
                
                sitemap_xml = SEOGenerator.generate_sitemap(posts, "sitemap.xml", base_url)
                deploy_file("sitemap.xml", sitemap_xml, "Update SEO Sitemap")
                
                rss_xml = SEOGenerator.generate_rss(posts, "rss.xml", base_url, self.niche_name)
                deploy_file("rss.xml", rss_xml, "Update SEO RSS")
                
                logger.info("✅ Archivos SEO generados y desplegados.")
            except Exception as e:
                logger.warning(f"⚠️ No se pudieron generar archivos SEO: {e}")

            logger.info(f"✅ Sitio {self.niche_name} desplegado exitosamente.")
            self._save_state()

async def main():
    parser = argparse.ArgumentParser(description="Motor de Blogs Autónomos - Versión Mejorada (v2.0)")
    parser.add_argument('--blog', '-b', type=str, help='Nombre del blog específico')
    parser.add_argument('--list', '-l', action='store_true', help='Listar blogs disponibles')
    parser.add_argument('--fetch', '-f', action='store_true', help='Generar contenido con IA')
    parser.add_argument('--build', action='store_true', help='Construir sitio estático')
    parser.add_argument('--all', action='store_true', help='Ejecutar ambas fases')
    
    args = parser.parse_args()
 
    try:
        blog_selector = BlogSelector()
    except FileNotFoundError as e:
        logger.error(str(e))
        return
 
    if args.list:
        print("\n📋 Blogs disponibles:")
        for i, name in enumerate(blog_selector.list_blogs(), 1):
            print(f"  {i}. {name}")
        return
 
    try:
        blog_configs = [blog_selector.get_blog_config(args.blog)] if args.blog else blog_selector.get_blog_config()
    except ValueError as e:
        logger.error(str(e))
        return
 
    if not args.fetch and not args.build and not args.all:
        parser.print_help()
        return
 
    for blog_config in blog_configs:
        engine = AutoBlogEngine(blog_config)
        try:
            if args.fetch or args.all:
                await engine.fetch_and_generate()
            if args.build or args.all:
                engine.build_site(os.getenv("GH_TOKEN"))
        except Exception as e:
            logger.error(f"❌ Error procesando {blog_config['name']}: {e}")
            traceback.print_exc()
 
if __name__ == "__main__":
    asyncio.run(main())