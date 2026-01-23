# 🚀 AutoBlog Engine PRO MAX

Sistema de automatización masiva de blogs con IA y despliegue en GitHub Pages.

## Configuración (config.json): Puedes añadir nuevas opciones a tu JSON para aprovechar las mejoras:
"content_type": "github_trending" (para que busque repos reales) o "rss_news".
"language_filter": "python" (para filtrar trending de Python).
"preferred_ai": "gemini" (para definir cuál IA intentar primero).

## 🔑 Configuración de Credenciales (PASO A PASO)

Para que GitHub pueda publicar automáticamente, necesitas configurar dos "Secrets".

### 1. Obtener GH_TOKEN (Personal Access Token)
Este token da permiso al bot para escribir en tus repositorios.
1.  Haz clic en tu **Foto de Perfil** (arriba a la derecha) > **Settings**.
2.  Baja hasta el final del menú izquierdo y haz clic en **<> Developer settings**.
3.  Haz clic en **Personal access tokens** > **Tokens (classic)**.
4.  Haz clic en el botón **Generate new token** > **Generate new token (classic)**.
5.  Ponle un nombre (ej: "AutoBlog Token").
6.  **IMPORTANTE (Selecciona estos checks):**
    *   [x] **repo** (Permiso completo para repositorios privados y públicos).
    *   [x] **workflow** (Permiso para actualizar archivos de GitHub Actions).
7.  Clica en **Generate token** al final y **COPIA EL CÓDIGO** inmediatamente (no lo verás otra vez).

### 2. Obtener API_KEY (Gemini)
1.  Ve a [Google AI Studio](https://aistudio.google.com/app/apikey).
2.  Clica en **Create API Key**.
3.  Copia el código de la llave.

### 3. Configurar Secrets en tu Repo

export GEMINI_API_KEY="AIza..."     # Gratis hasta quota
export OPENAI_API_KEY="sk-..."      # $0.15/1M tokens (gpt-4o-mini)
export ANTHROPIC_API_KEY="claude-..." # $0.25/1M tokens (claude-3-haiku)
export GH_TOKEN="ghp_..."




1.  Ve al repositorio donde tienes este código en GitHub.
2.  Haz clic en la pestaña superior **Settings**.
3.  En el menú izquierdo ve a **Secrets and variables** > **Actions**.
4.  Clica en **New repository secret** (botón verde).
5.  Crea uno llamado `API_KEY` y pega tu llave de Google.
6.  Crea otro llamado `GH_TOKEN` y pega tu Personal Access Token generado en el paso 1.

## 🛠️ Uso en Termux (Manual)
```bash
pkg update && pkg upgrade
pkg install python git
pip install requests jinja2 google-generativeai
export API_KEY="tu_llave"
export GH_TOKEN="tu_token_pat"
python autoblog.py --fetch --build --incremental
```

## 🚀 Despliegue Automático
Una vez configurados los Secrets, GitHub Actions ejecutará el script cada 4 horas automáticamente. Puedes ver el progreso en la pestaña **Actions** de tu repositorio.


Guía: Cómo conseguir las API Keys (GRATIS)
Aquí te explico cómo obtener las claves para los servicios anteriores. No necesitas tarjeta de crédito para las opciones recomendadas (Groq y Hugging Face).

1. Groq (Opción #1 Recomendada)
Es el más rápido y actualmente muy generoso con su nivel gratuito (Free Tier).

Ve a console.groq.com.
Regístrate (puedes usar tu cuenta de Google o GitHub).
En el menú izquierdo, haz clic en "Keys".
Crea una nueva Key y cópiala.
En tu terminal:
bash

# En Linux/Mac
export GROQ_API_KEY="gsk_...."

# En Windows (PowerShell)
setx GROQ_API_KEY "gsk_...."
(Nota: Te da muchas llamadas gratis por día)
2. Hugging Face (Opción #2)
Excelente si quieres probar diferentes modelos de código abierto.

Ve a huggingface.co/settings/tokens.
Regístrate si no tienes cuenta.
Crea un nuevo token (selecciona tipo "Read" o "Write" según prefieras).
Copia el token (empieza por hf_...).
En tu terminal:
bash

export HF_API_KEY="hf_...."
(Nota: El nivel gratuito tiene límites, pero es suficiente para generar varios posts al día)
3. Google Gemini (Opción #3)
Google suele dar créditos gratuitos iniciales o una cuota de uso libre para su modelo Flash.

Ve a aistudio.google.com/app/apikey.
Haz clic en "Create API Key".
Copia la key.
En tu terminal:
bash

export GEMINI_API_KEY="AIzaSy...