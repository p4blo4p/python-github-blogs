import os
from openai import OpenAI
from datetime import datetime
from pathlib import Path

class AIWriter:
    def __init__(self, api_key, model="gpt-4o-mini", language="es"):
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.language = language

    def generate_post(self, topic: str, tone: str = "profesional"):
        """
        Genera un post completo en formato Markdown con Frontmatter.
        """
        system_prompt = f"""
        Eres un experto redactor de blogs técnicos y un desarrollador Python senior.
        Tu tarea es escribir un post de blog en {self.language} sobre el tema proporcionado.
        
        El formato de salida DEBE ser estrictamente el siguiente:
        
        ---
        title: "Un título SEO llamativo para el post"
        date: {datetime.now().strftime("%Y-%m-%d")}
        tags: [tag1, tag2, tag3]
        summary: "Un resumen de 1 o 2 frases sobre el contenido."
        ---
        
        # Título Principal
        
        [Introducción breve enganchante]
        
        ## Subtítulo 1
        [Contenido técnico detallado, usa bloques de código python si aplica]
        
        ## Subtítulo 2
        [Más contenido]
        
        ## Conclusión
        [Cierre breve]
        
        Tono: {tone}.
        Usa formato Markdown apropiado (negritas, listas, bloques de código).
        """

        try:
            print(f"✍️  Pidiendo a la IA que escriba sobre: '{topic}'...")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Tema del post: {topic}"}
                ],
                temperature=0.7,
            )
            
            content = response.choices[0].message.content
            return content

        except Exception as e:
            print(f"❌ Error generando contenido con IA: {e}")
            return None

    def save_post(self, content: str, output_dir: str = "drafts"):
        """
        Guarda el contenido generado en un archivo .md local.
        """
        path = Path(output_dir)
        path.mkdir(exist_ok=True)
        
        # Extraer título simple para el nombre del archivo si es posible
        lines = content.split('\n')
        filename = "post_sin_titulo.md"
        
        # Intentar buscar el title en el frontmatter generado
        for line in lines:
            if line.startswith("title:"):
                raw_title = line.replace("title:", "").strip().strip('"').strip("'")
                # Limpiar nombre de archivo
                filename = raw_title.lower().replace(" ", "-").replace("?", "").replace("!", "") + ".md"
                break
        
        file_path = path / filename
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        return file_path