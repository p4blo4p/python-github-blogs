import os
import base64
import logging
import requests
import json
import re

GH_TOKEN = os.getenv("GH_TOKEN")
logger = logging.getLogger(__name__)

class GitHubManager:
    def __init__(self):
        if not GH_TOKEN:
            raise ValueError("❌ GH_TOKEN no está definida en las variables de entorno")
        self.headers = {"Authorization": f"token {GH_TOKEN}", "Accept": "application/vnd.github.v3+json"}

    def api_call(self, repo, path, method="GET", data=None):
        url = f"https://api.github.com/repos/{repo}/contents/{path}"
        try:
            if method == "GET": 
                r = requests.get(url, headers=self.headers)
                return r.json() if r.status_code == 200 else None
            elif method == "PUT":
                return requests.put(url, headers=self.headers, json=data)
        except Exception as e:
            logger.error(f"GitHub API Error ({method} {repo}/{path}): {e}")
            return None

    def get_files(self, repo, path=""):
        """Lista archivos recursivamente"""
        data = self.api_call(repo, path)
        files = {}
        if isinstance(data, list):
            for item in data:
                if item['type'] == 'file':
                    files[item['name']] = item['download_url']
                elif item['type'] == 'dir':
                    files.update(self.get_files(repo, f"{path}/{item['name']}" if path else item['name']))
        return files

    def get_file_content(self, download_url):
        r = requests.get(download_url)
        return r.text if r.status_code == 200 else None

    def create_file(self, repo, path, content, message):
        """Sube un archivo a GitHub (Headless CMS)"""
        # Codificar en Base64
        b64_content = base64.b64encode(content.encode()).decode()
        
        # Verificar si existe para obtener SHA (evitar conflictos)
        existing = self.api_call(repo, path)
        sha = existing.get('sha') if existing else None
        
        data = {
            "message": message,
            "content": b64_content
        }
        if sha:
            data["sha"] = sha
            
        r = self.api_call(repo, path, "PUT", data)
        if r and r.status_code in [200, 201]:
            logger.info(f"✅ Subido a GitHub: {repo}/{path}")
            return True
        else:
            logger.error(f"❌ Error subiendo: {r.text if r else 'Unknown'}")
            return False

    def deploy_site(self, repo, path, content):
        """Sube el HTML generado al repo de producción"""
        return self.create_file(repo, path, content, "deploy: update site content")