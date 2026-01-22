import os
import base64
import logging
import requests

GH_TOKEN = os.getenv("GH_TOKEN")
logger = logging.getLogger(__name__)

class GitHubManager:
    def __init__(self):
        token = GH_TOKEN or os.getenv("GITHUB_TOKEN")
        if not token:
            raise ValueError("❌ GH_TOKEN no definida")
        self.headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.v3+json"}

    def api_call(self, repo, path, method="GET", data=None, branch="main"):
        """API call con manejo estricto de errores para PUT, pero flexible para GET"""
        url = f"https://api.github.com/repos/{repo}/contents/{path}"
        params = {"ref": branch} if branch != "main" else {}
        
        try:
            if method == "GET": 
                r = requests.get(url, headers=self.headers, params=params)
                # Si es 404 (archivo no existe), devolvemos None (es normal)
                if r.status_code == 404:
                    return None
                # Si es otro error, lo lanzamos
                r.raise_for_status()
                return r.json()
                
            elif method == "PUT":
                if data and branch != "main":
                    data["branch"] = branch
                r = requests.put(url, headers=self.headers, json=data)
                # Para PUT, cualquier error es crítico y queremos verlo
                r.raise_for_status()
                return r
                
        except Exception as e:
            import traceback
            print("!!! ERROR EN API CALL !!!")
            print(traceback.format_exc()) # Esto imprime el error real en la consola
            print("!!! FIN ERROR !!!")
            # Re-lanzamos la excepción para que main.py la capture
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
                    sub_path = f"{path}/{item['name']}" if path else item['name']
                    files.update(self.get_files(repo, sub_path, branch=branch))
        return files
 
    def get_file_content(self, download_url):
        """Obtiene el contenido de un archivo"""
        r = requests.get(download_url)
        return r.text if r.status_code == 200 else None
 
    def create_file(self, repo, path, content, message, branch="main"):
        """Sube un archivo a GitHub en una rama específica"""
        # Codificar en Base64
        b64_content = base64.b64encode(content.encode()).decode()
        
        # Verificar si existe para obtener SHA
        # Esto devolverá None si es 404 (archivo nuevo)
        existing = self.api_call(repo, path, branch=branch)
        sha = existing.get('sha') if existing else None
        
        data = {
            "message": message,
            "content": b64_content
        }
        if sha:
            data["sha"] = sha
            
        # Aquí es donde ocurrirá el error si algo falla, y ahora lo veremos
        try:
            self.api_call(repo, path, "PUT", data, branch=branch)
            logger.info(f"✅ Subido a GitHub: {repo}/{path} @ {branch}")
            return True
        except Exception as e:
            logger.error(f"❌ No se pudo subir el archivo: {e}")
            # No relanzamos aquí, pero el traceback ya se imprimió en api_call
            return False
 
    def deploy_site(self, repo, path, content, branch="gh-pages"):
        """Sube el HTML generado al repo de producción"""
        return self.create_file(repo, path, content, "deploy: update site content", branch=branch)