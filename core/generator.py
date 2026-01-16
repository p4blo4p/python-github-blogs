import os
from jinja2 import Environment, FileSystemLoader

class SiteGenerator:
    def __init__(self, config, posts):
        self.config = config
        self.posts = posts
        self.env = Environment(loader=FileSystemLoader('templates'))
        self.output_dir = config['output']['dir']

    def generate(self):
        # 1. Renderizar Indice
        self._render_index()
        
        # 2. Renderizar Posts Individuales
        self._render_posts()

    def _render_index(self):
        template = self.env.get_template('index.html')
        html = template.render(
            config=self.config['blog'],
            posts=self.posts
        )
        with open(f"{self.output_dir}/index.html", "w", encoding="utf-8") as f:
            f.write(html)

    def _render_posts(self):
        template = self.env.get_template('post.html')
        
        for post in self.posts:
            html = template.render(
                config=self.config['blog'],
                post=post
            )
            # Crear directorio si es necesario (opcional, aquí plano por ahora)
            with open(f"{self.output_dir}/{post['slug']}", "w", encoding="utf-8") as f:
                f.write(html)