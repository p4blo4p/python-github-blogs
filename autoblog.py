
import os
import json
import time
import requests
import re
import datetime
import argparse
import base64
import logging
from jinja2 import Environment, FileSystemLoader

# --- CONFIGURACIÓN DE LOGS ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

API_KEY = os.getenv("API_KEY")
GH_TOKEN = os.getenv("GH_TOKEN")

class AutoBlogPro:
    def __init__(self, config, args):
        self.config = config
        self.args = args
        self.niche = config['name']
        self.source_repo = config['source_repo']
        self.prod_repo = config['prod_repo']
        self.languages = config.get('languages', ['es', 'en'])
        self.domain = config.get('domain', f"https://{self.prod_repo.split('/')[0]}.github.io/{self.prod_repo.split('/')[1]}")
        self.env = Environment(loader=FileSystemLoader('templates'))
        
        # Estado incremental
        self.state_file = f".state_{self.niche.replace(' ', '_').lower()}.json"
        self.state = self._load_state()

        from google.genai import GoogleGenAI
        self.ai = GoogleGenAI(apiKey=API_KEY)

    def _load_state(self):
        if os.path.exists(self.state_file):
            with open(self.state_file, 'r') as f: return json.load(f)
        return {"built_shas": {}, "last_run": None}

    def _save_state(self):
        with open(self.state_file, 'w') as f: json.dump(self.state, f)

    def github_api(self, repo, path, method="GET", data=None):
        url = f"https://api.github.com/repos/{repo}/contents/{path}"
        headers = {"Authorization": f"token {GH_TOKEN}", "Accept": "application/vnd.github.v3+json"}
        try:
            if method == "GET": return requests.get(url, headers=headers)
            return requests.put(url, headers=headers, json=data)
        except Exception as e:
            logging.error(f"GitHub Error: {e}")
            return None

    async def run_fetch(self):
        """Fase 1: Generación de contenido i18n + Imágenes"""
        logging.info(f"[{self.niche}] FETCH: Buscando tendencias...")
        
        topic_res = await self.ai.models.generateContent({
            'model': 'gemini-3-flash-preview',
            'contents': f"Trending viral specific news topic about {self.config['keywords']}. Headline only."
        })
        base_topic = topic_res.text.strip()
        slug = re.sub(r'[s-]+', '-', re.sub(r'[^a-z0-9s-]', '', base_topic.lower()))

        # Imagen de Portada
        try:
            img_res = await self.ai.models.generateContent({
                'model': 'gemini-2.5-flash-image',
                'contents': f"Professional editorial photography for: {base_topic}. 16:9, high resolution."
            })
            for part in img_res.candidates[0].content.parts:
                if part.inlineData:
                    self.github_api(self.source_repo, f"content/images/{slug}.png", "PUT", {
                        "message": "header image", "content": part.inlineData.data
                    })
        except: pass

        for lang in self.languages:
            art_res = await self.ai.models.generateContent({
                'model': 'gemini-3-flash-preview',
                'contents': f"Expert blog post in {lang} about '{base_topic}'. Markdown, SEO optimized."
            })
            self.github_api(self.source_repo, f"content/{lang}/{slug}.md", "PUT", {
                "message": f"add {lang} post",
                "content": base64.b64encode(art_res.text.encode()).decode()
            })

    def run_build(self):
        """Fase 2: Build Incremental + SEO Avanzado"""
        logging.info(f"[{self.niche}] BUILD: Procesando cambios...")
        all_posts_by_lang = {}
        changes = False

        for lang in self.languages:
            res = self.github_api(self.source_repo, f"content/{lang}")
            if res.status_code != 200: continue
            
            lang_posts = []
            for item in res.json():
                sha = item['sha']
                path = item['path']
                slug = item['name'].replace('.md', '')

                # Lógica incremental
                if self.args.incremental and self.state["built_shas"].get(path) == sha:
                    lang_posts.append({"slug": slug, "path": path}) # Data mínima para índices
                    continue

                changes = True
                f_res = self.github_api(self.source_repo, path)
                md = base64.b64decode(f_res.json()['content']).decode()
                
                post_data = {
                    "title": md.split('\n')[0].replace('# ', ''),
                    "content": md, "slug": slug, "lang": lang,
                    "img": f"../images/{slug}.png",
                    "date": datetime.datetime.now().strftime("%Y-%m-%d")
                }
                self._render(f"{lang}/{slug}.html", 'post.j2', post=post_data, niche=self.config)
                self.state["built_shas"][path] = sha
                lang_posts.append(post_data)
            
            all_posts_by_lang[lang] = lang_posts

        if changes or not self.args.incremental:
            for lang, posts in all_posts_by_lang.items():
                self._render(f"{lang}/index.html", 'index.j2', posts=posts, lang=lang, niche=self.config)
                self._render(f"{lang}/sitemap.xml", 'sitemap.xml.j2', posts=posts, domain=self.domain, lang=lang)
            
            self._render("robots.txt", "robots.txt.j2", domain=self.domain)
            self._render("llms.txt", "llms.txt.j2", niche=self.config)
            self._render("index.html", "root.j2", niche=self.config)
            self._sync_assets()
            self._save_state()

    def _render(self, filename, template, **kwargs):
        content = self.env.get_template(template).render(**kwargs)
        check = self.github_api(self.prod_repo, filename)
        sha = check.json().get('sha') if check.status_code == 200 else None
        payload = {"message": f"update {filename}", "content": base64.b64encode(content.encode()).decode()}
        if sha: payload["sha"] = sha
        self.github_api(self.prod_repo, filename, "PUT", payload)

    def _sync_assets(self):
        for a in ['styles.css', 'main.js']:
            with open(f'static/{a}', 'r') as f:
                self._render(f"assets/{a}", "plain.j2", content=f.read())

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fetch', action='store_true')
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--incremental', action='store_true', default=True)
    args = parser.parse_args()

    with open('config.json', 'r') as f: niches = json.load(f)
    for cfg in niches:
        bot = AutoBlogPro(cfg, args)
        if args.fetch: await bot.run_fetch()
        if args.build: bot.run_build()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
