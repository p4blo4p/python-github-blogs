import os
import json
import base64
import re
import datetime
import argparse
import logging
import asyncio
import requests  # Moved up to avoid lazy imports
from google import genai  # Correct import for new SDK
from google.genai.types import GenerateContentConfig  # For configs if needed
from jinja2 import Environment, FileSystemLoader


# --- LOGGING CONFIG ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# --- API KEYS ---
API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("API_KEY")  # Prefer GEMINI_API_KEY
GH_TOKEN = os.getenv("GH_TOKEN")


class AutoBlogEngine:
    def __init__(self, config, args):
        self.config = config
        self.args = args
        self.niche_name = config['name']
        self.source_repo = config['source_repo']
        self.prod_repo = config['prod_repo']
        self.languages = config.get('languages', ['en', 'es'])
        self.domain = config.get('domain', f"https://{self.prod_repo.split('/')[0]}.github.io/{self.prod_repo.split('/')[1]}")
        
        # Initialize Gemini client (new SDK pattern)
        self.client = genai.Client(api_key=API_KEY) if API_KEY else None
        
        # Jinja2 Environment
        self.env = Environment(loader=FileSystemLoader('templates'))
        
        # Incremental State
        self.state_file = f".state_{self.niche_name.replace(' ', '_').lower()}.json"
        self.state = self._load_state()


    def _load_state(self):
        if os.path.exists(self.state_file):
            with open(self.state_file, 'r') as f: return json.load(f)
        return {"shas": {}, "last_build": None}


    def _save_state(self):
        self.state["last_build"] = datetime.datetime.now().isoformat()
        with open(self.state_file, 'w') as f: json.dump(self.state, f)


    def github_api(self, repo, path, method="GET", data=None):
        url = f"https://api.github.com/repos/{repo}/contents/{path}"
        headers = {"Authorization": f"token {GH_TOKEN}", "Accept": "application/vnd.github.v3+json"}
        try:
            if method == "GET": 
                return requests.get(url, headers=headers)
            return requests.put(url, headers=headers, json=data)
        except Exception as e:
            logging.error(f"GitHub Error: {e}")
            return None


    async def generate_content(self):
        """Genera artículos e imágenes usando Gemini 2.0 Flash"""
        if not self.client:
            logging.error(f"[{self.niche_name}] No API key available. Skipping content generation.")
            return
            
        logging.info(f"[{self.niche_name}] FETCH: Analizando tendencias...")
        
        model_name = 'gemini-2.0-flash'
        
        # 1. Tópico viral
        topic_prompt = f"Identify a trending news topic for {self.config['keywords']}. Output ONLY the headline."
        try:
            response = self.client.models.generate_content(
                model=model_name,
                contents=topic_prompt
            )
            headline = response.text.strip()
            slug = re.sub(r'[s-]+', '-', re.sub(r'[^a-z0-9s-]', '', headline.lower()))
            logging.info(f"Generated headline: {headline}")
        except Exception as e:
            logging.error(f"Failed to generate headline: {e}")
            return
        
        # 2. Artículos por idioma
        for lang in self.languages:
            logging.info(f"  -> Generando en {lang}: {slug}")
            art_prompt = f"Write a professional, SEO-optimized blog post in {lang} about '{headline}'. Use Markdown headers. Tone: Expert."
            try:
                response = self.client.models.generate_content(
                    model=model_name,
                    contents=art_prompt
                )
                article = response.text
                
                self.github_api(self.source_repo, f"content/{lang}/{slug}.md", "PUT", {
                    "message": f"cms: add {lang} content",
                    "content": base64.b64encode(article.encode()).decode()
                })
            except Exception as e:
                logging.error(f"Failed to generate {lang} article: {e}")


    def build_site(self):
        """Compilación incremental a HTML estático"""
        logging.info(f"[{self.niche_name}] BUILD: Iniciando proceso...")
        all_posts = {}
        has_new_content = False

        for lang in self.languages:
            res = self.github_api(self.source_repo, f"content/{lang}")
            if not res or res.status_code != 200: 
                continue
            
            lang_posts = []
            for item in res.json():
                sha = item['sha']
                path = item['path']
                slug = item['name'].replace('.md', '')

                if self.args.incremental and self.state["shas"].get(path) == sha:
                    lang_posts.append({"slug": slug, "title": slug.replace('-', ' ').title()})
                    continue

                has_new_content = True
                f_res = self.github_api(self.source_repo, path)
                if not f_res or f_res.status_code != 200:
                    continue
                    
                md_content = base64.b64decode(f_res.json()['content']).decode()
                
                post_data = {
                    "title": md_content.split('\n')[0].replace('# ', ''),
                    "content": md_content, "slug": slug, "lang": lang,
                    "date": datetime.datetime.now().strftime("%Y-%m-%d")
                }
                
                self._render_to_prod(f"{lang}/{slug}.html", 'post.j2', post=post_data)
                self.state["shas"][path] = sha
                lang_posts.append(post_data)
            
            all_posts[lang] = lang_posts

        if has_new_content or not self.args.incremental:
            for lang, posts in all_posts.items():
                self._render_to_prod(f"{lang}/index.html", 'index.j2', posts=posts, lang=lang)
            
            self._render_to_prod("index.html", "root.j2")
            self._render_to_prod("robots.txt", "robots.txt.j2")
            self._save_state()


    def _render_to_prod(self, filename, template, **kwargs):
        tpl = self.env.get_template(template)
        content = tpl.render(niche=self.config, domain=self.domain, **kwargs)
        
        # Verificar SHA existente en prod para actualizar
        curr = self.github_api(self.prod_repo, filename)
        sha = curr.json().get('sha') if curr and curr.status_code == 200 else None
        
        payload = {
            "message": f"build: update {filename}",
            "content": base64.b64encode(content.encode()).decode()
        }
        if sha: payload["sha"] = sha
        self.github_api(self.prod_repo, filename, "PUT", payload)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fetch', action='store_true')
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--incremental', action='store_true', default=True)
    args = parser.parse_args()

    with open('config.json', 'r') as f: 
        niches = json.load(f)
    
    for n in niches:
        engine = AutoBlogEngine(n, args)
        if args.fetch: 
            await engine.generate_content()
        if args.build: 
            engine.build_site()


if __name__ == "__main__":
    asyncio.run(main())
