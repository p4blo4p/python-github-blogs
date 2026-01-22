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
            # Si no hay token en env, intentamos usar el de Actions (aunque suele estar en GH_TOKEN)
            logger.warning("⚠️ GH_TOKEN no está definida explícitamente. Es posible que falle la autenticación.")
            self.headers = {"Authorization": f"Bearer {os.getenv('GITHUB_TOKEN', '')}", "Accept": "application/vnd.github.v3+json"}
        else:
            # Usamos 'Bearer' que es más moderno y compatible que 'token'
            self.headers = {"Authorization": f"Bearer {GH_TOKEN}", "Accept": "application/vnd.github.v3+json"}

    def api_call(self, repo, path, method="GET", data=None, branch="main"):
        """API call con soporte para ramas específicas y mejor manejo de errores"""
        url = f"https://api.github.com/repos/{repo}/contents/{path}"
        params = {"ref": branch} if branch != "main" else {}
        
        try:
            if method == "GET": 
                r = requests.get(url, headers=self.headers, params=params)
                return r.json() if r.status_code == 200 else None
            elif method == "PUT":
                if data and branch != "main":
                    data["branch"] = branch
                return requests.put(url, headers=self.headers, json=data)
                
        except Exception as e:
            # IMPORTANTE: Imprimimos el traceback completo para ver qué pasa
            import traceback
            print(traceback.format_exc()) 
            logger.error(f"❌ Excepción en API Call: {e}")
            # Relanzamos la excepción para que main.py la capture y detenga la ejecución
            # Si no relanzamos, la función devuelve None y luego da el error "Unknown"
            raise e
 
    def get_files(self, repo, path="", branch="main"):
        """Lista archivos recursivamente en una rama específica"""
        data = self.api_call(repo, path, branch=branch)
        files = {}
        if isinstance(data, list):
            for item in data:
                if item['type'] == 'file':
                    files[item['name']] = item['download_url']
                elif item['type'] == 'dir':
                    # Llamada recursiva correcta
                    sub_path = f"{path}/{item['name']}" if path else item['name']
                    files.update(self.get_files(repo, sub_path, branch=branch))
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
            
        # Esta llamada lanzará la excepción real si falla (gracias al 'raise' en api_call)
        r = self.api_call(repo, path, "PUT", data, branch=branch)
        
        if r and r.status_code in [200, 201]:
            logger.info(f"✅ Subido a GitHub: {repo}/{path} @ {branch}")
            return True
        else:
            # Si llegamos aquí, r podría ser None o tener un código de error distinto
            if r:
                logger.error(f"❌ Error subiendo (Status {r.status_code}): {r.text}")
            else:
                logger.error("❌ Error subiendo: No se recibió respuesta del servidor")
            return False
 
    def deploy_site(self, repo, path, content, branch="gh-pages"):
        """Sube el HTML generado al repo de producción en rama específica"""
        return self.create_file(repo, path, content, "deploy: update site content", branch=branch)