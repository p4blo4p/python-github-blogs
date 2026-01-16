import os
import json
import base64
import re
import datetime
import argparse
import logging
import asyncio
import requests
from google import genai as google_genai
from google.genai.types import GenerateContentConfig
from openai import OpenAI  # pip install openai
import anthropic  # pip install anthropic
from jinja2 import Environment, FileSystemLoader


# --- LOGGING CONFIG ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# --- API KEYS ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GH_TOKEN = os.getenv("GH_TOKEN")


class MultiAIClient:
    """Cliente rotativo multi-proveedor con fallback automático"""
    
    def __init__(self):
        self.providers = []
        
        # Google Gemini
        if GEMINI_API_KEY:
            try:
                self.providers.append({
                    'name': 'gemini',
                    'client': google_genai.Client(api_key=GEMINI_API_KEY),
                    'model': 'gemini-2.0-flash',
                    'priority': 1
                })
                logging.info("✅ Gemini client loaded")
            except Exception as e:
                logging.warning(f"Gemini init failed: {e}")
        
        # OpenAI (GPT-4o-mini es barato y rápido)
        if OPENAI_API_KEY:
            try:
                self.providers.append({
                    'name': 'openai',
                    'client': OpenAI(api_key=OPENAI_API_KEY),
                    'model': 'gpt-4o-mini',  # O 'gpt-4o'
                    'priority': 2
                })
                logging.info("✅ OpenAI client loaded")
            except Exception as e:
                logging.warning(f"OpenAI init failed: {e}")
        
        # Anthropic Claude
        if ANTHROPIC_API_KEY:
            try:
                self.providers.append({
                    'name': 'anthropic',
                    'client': anthropic.Anthropic(api_key=ANTHROPIC_API_KEY),
                    'model': 'claude-3-5-sonnet-20240620',  # O 'claude-3-haiku-20240307'
                    'priority': 3
                })
                logging.info("✅ Anthropic client loaded")
            except Exception as e:
                logging.warning(f"Anthropic init failed: {e}")
        
        if not self.providers:
            raise ValueError("❌ No AI providers available. Set GEMINI_API_KEY, OPENAI_API_KEY or ANTHROPIC_API_KEY")
    
    async def generate(self, prompt, max_retries=1):
        """Genera texto rotando providers automáticamente"""
        for provider in self.providers:
            try:
                logging.info(f"🤖 Probando {provider['name']} ({provider['model']})")
                
                if provider['name'] == 'gemini':
                    response = provider['client'].models.generate_content(
                        model=provider['model'],
                        contents=prompt
                    )
                    return response.text.strip()
                
                elif provider['name'] == 'openai':
                    response = provider['client'].chat.completions.create(
                        model=provider['model'],
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=2000,
                        temperature=0.7
                    )
                    return response.choices[0].message.content.strip()
                
                elif provider['name'] == 'anthropic':
                    response = provider['client'].messages.create(
                        model=provider['model'],
                        max_tokens=2000,
                        messages=[{"role": "user", "content": prompt}]
                    )
                    return response.content[0].text.strip()
                
            except Exception as e:
                logging.warning(f"❌ {provider['name']} falló: {str(e)[:100]}")
                continue
        
        raise Exception("Todas las IAs fallaron")


class AutoBlogEngine:
    def __init__(self, config, args):
        self.config = config
        self.args = args
        self.niche_name = config['name']
        self.source_repo = config['source_repo']
        self.prod_repo = config['prod_repo']
        self.languages = config.get('languages', ['en', 'es'])
        self.domain = config.get('domain', f"https://{self.prod_repo.split('/')[0]}.github.io/{self.prod_repo.split('/')[1]}")
        
        # Multi-AI client con fallback automático
        self.ai = MultiAIClient()
        
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
        """Genera artículos rotando múltiples IAs automáticamente"""
        logging.info(f"[{self.niche_name}] FETCH: Analizando tendencias...")
        
        try:
            # 1. Tópico viral
            topic_prompt = f"Identify a trending news topic for {self.config['keywords']}. Output ONLY the headline."
            headline = await self.ai.generate(topic_prompt)
            slug = re.sub(r'[s-]+', '-', re.sub(r'[^a-z0-9s-]', '', headline.lower()))
            logging.info(f"✅ Headline: {headline}")
            
            # 2. Artículos por idioma
            for lang in self.languages:
                logging.info(f"  -> Generando en {lang}: {slug}")
                art_prompt = f"Write a professional, SEO-optimized blog post in {lang} about '{headline}'. Use Markdown headers. Tone: Expert. Max 1500 words."
                article = await self.ai.generate(art_prompt)
                
                self.github_api(self.source_repo, f"content/{lang}/{slug}.md", "PUT", {
                    "message": f"cms: add {lang} content",
                    "content": base64.b64encode(article.encode()).decode()
                })
                logging.info(f"✅ {lang} article generated & uploaded")
                
        except Exception as e:
            logging.error(f"❌ Content generation failed: {e}")


    # ... resto del código build_site() y _render_to_prod() SIN CAMBIOS ...
    # (Mantén exactamente igual las funciones build_site y _render_to_prod del código anterior)


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
