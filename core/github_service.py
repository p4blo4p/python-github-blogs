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
 
    def api_call(self, repo, path, method="GET", data=None, branch="main"):
        """API call con soporte para ramas específicas"""
        url = f"https://api.github.com/repos/{repo}/contents/{path}"
        params = {"ref": branch} if branch != "main" else {}
        
        try:
            if method == "GET": 
                r = requests.get(url, headers=self.headers, params=params)
                return r.json() if r.status_code == 200 else None
            elif method == "PUT":
                # Para PUT, incluimos el branch en el body
                if data and branch != "main":
                    data["branch"] = branch
                return requests.put(url, headers=self.headers, json=data)
        # Busca donde capturas el error y cámbialo así para depurar:
        except Exception as e:
            # IMPORTANTE: Imprime el error completo para saber qué pasa
            import traceback
            print(traceback.format_exc()) 
            logger.error(f"❌ Error subiendo: {e}")
            # Opcional: Descomenta la siguiente línea para que el programa se detenga
            # raise e 
 
    def get_files(self, repo, path="", branch="main"):
        """Lista archivos recursivamente en una rama específica"""
        data = self.api_call(repo, path, branch=branch)
        files = {}
        if isinstance(data, list):
            for item in data:
                if item['type'] == 'file':
                    files[item['name']] = item['download_url']
                elif item['type'] == 'dir':
                    files.update(self.get_files(repo, f"{path}/{item['name']}" if path else item['name'], branch=branch))
        return files
 
    def get_file_content(self, download_url):
        """Obtiene el contenido de un archivo desde su download_url"""
        r = requests.get(download_url)
        return r.text if r.status_code == 200 else None
 
    def create_file(self, repo, path, content, message, branch="main"):
        """Sube un archivo a GitHub en una rama específica"""
        # Codificar en Base64
        b64_content = base64.b64encode(content.encode()).decode()
        
        # Verificar si existe para obtener SHA (evitar conflictos)
        existing = self.api_call(repo, path, branch=branch)
        sha = existing.get('sha') if existing else None
        
        data = {
            "message": message,
            "content": b64_content
        }
        if sha:
            data["sha"] = sha
            
        r = self.api_call(repo, path, "PUT", data, branch=branch)
        if r and r.status_code in [200, 201]:
            logger.info(f"✅ Subido a GitHub: {repo}/{path} @ {branch}")
            return True
        else:
            logger.error(f"❌ Error subiendo: {r.text if r else 'Unknown'}")
            return False
 
    def deploy_site(self, repo, path, content, branch="gh-pages"):
        """Sube el HTML generado al repo de producción en rama específica"""
        return self.create_file(repo, path, content, "deploy: update site content", branch=branch)