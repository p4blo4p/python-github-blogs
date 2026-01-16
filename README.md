# 🚀 AutoBlog Engine PRO MAX

Sistema de automatización masiva de nichos i18n con IA y despliegue estático.

## 📦 Estructura del Proyecto
- `autoblog.py`: El cerebro del sistema (Python + Jinja2 + Google Generative AI).
- `config.json`: Configuración de tus 10 nichos (repos, keywords, idiomas).
- `templates/`: Plantillas `.j2` para posts, índices y sitemaps.
- `static/`: Assets globales (CSS/JS).

## 🛠️ Instalación en Termux
```bash
pkg update && pkg upgrade
pkg install python git
pip install requests jinja2 google-generativeai
# Configura tus variables de entorno en ~/.bashrc
export API_KEY="tu_llave"
export GH_TOKEN="tu_token_github"
```

## 🚀 Uso Manual
- Generar solo contenido: `python autoblog.py --fetch`
- Compilar solo HTML: `python autoblog.py --build`
- Modo completo incremental: `python autoblog.py --fetch --build --incremental`

## 💎 Estrategia de Monetización
Este sistema inyecta **GA4** y **AdSense** automáticamente. Al usar idiomas de alto CPM (Alemán, Japonés, Noruego), maximizas el retorno por clic. La generación incremental asegura que GitHub no bloquee tu cuenta por exceso de tráfico de API.
