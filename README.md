# 🚀 AutoBlog Engine PRO MAX

Este repositorio contiene un sistema de automatización de blogs estáticos (SSG) diseñado para escalar nichos de alto CPM de forma desatendida.

## 🛠️ Cómo Funciona
1.  **Generación (Fetch):** El script usa **Gemini 3 Flash** para identificar tendencias en tus palabras clave, escribe artículos de +1000 palabras y genera imágenes hiperrealistas con **Gemini 2.5 Flash Image**.
2.  **Compilación (Build):** Transforma el Markdown en HTML estático usando **Jinja2**. Implementa un sistema de **Hash Shifting** para solo reconstruir lo que ha cambiado (Build Incremental).
3.  **Monetización:** Inyecta automáticamente tus IDs de **Google AdSense** y **Analytics (GA4)**.
4.  **Distribución:** El contenido se guarda en un repo "Source" y la web terminada se despliega en un repo "Production" (GitHub Pages).

## 📁 Archivos Faltantes / Estructura Necesaria
Para que el motor funcione al 100%, asegúrate de tener estas carpetas en tu repo local o de Termux:
- `templates/`: Contiene los archivos `.j2` (Post, Index, Sitemap, Robots, LLMS).
- `static/`: Contiene `styles.css` y `main.js`.
- `content/`: Carpeta donde se descargan los .md y las .png.

## 📈 Próximas Mejoras (Roadmap)
- [ ] **Interlinking Dinámico:** Escaneo de palabras clave entre posts para crear enlaces internos automáticos.
- [ ] **Traducción Contextual:** En lugar de generar de cero, traducir el post base a 10 idiomas manteniendo el contexto cultural.
- [ ] **WebP Auto-Convert:** Optimización de peso de imágenes antes de subir a producción.

## 🚀 Despliegue
```bash
pip install -r requirements.txt
export API_KEY="tu_llave_gemini"
export GH_TOKEN="tu_token_github"
python autoblog.py --fetch --build --incremental
```
