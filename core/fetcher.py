import requests
import base64

class GitHubFetcher:
    def __init__(self, config):
        self.owner, self.repo = config['repo'].split('/')
        self.token = config.get('token')
        self.base_path = config.get('path', '')
        self.api_url = f"https://api.github.com/repos/{self.owner}/{self.repo}/contents/{self.base_path}"
        self.raw_url = f"https://raw.githubusercontent.com/{self.owner}/{self.repo}/main/{self.base_path}"
        self.headers = {}
        if self.token:
            self.headers['Authorization'] = f"token {self.token}"

    def get_markdown_files(self):
        """Obtiene un diccionario {nombre_archivo: contenido} de todos los .md"""
        files = {}
        self._fetch_recursive(self.api_url, files)
        return files

    def _fetch_recursive(self, url, files):
        response = requests.get(url, headers=self.headers)
        if response.status_code != 200:
            print(f"Error fetching {url}: {response.status_code}")
            return

        data = response.json()
        
        # Si data es una lista, es un directorio. Si es dict, es un archivo.
        if isinstance(data, dict) and data.get('type') == 'file':
            if data['name'].endswith('.md'):
                content = self._fetch_content(data['download_url'])
                files[data['name']] = content
            return

        if isinstance(data, list):
            for item in data:
                if item['type'] == 'file' and item['name'].endswith('.md'):
                    content = self._fetch_content(item['download_url'])
                    files[item['name']] = content
                elif item['type'] == 'dir':
                    self._fetch_recursive(item['url'], files)

    def _fetch_content(self, download_url):
        # download_url es más fácil que decodificar base64 de la API
        r = requests.get(download_url, headers=self.headers)
        return r.text