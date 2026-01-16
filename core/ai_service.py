import os
import logging
from google import genai as google_genai

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIGURACIÓN ---
# Solo necesitamos esta variable de entorno
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

class GeminiClient:
    """Cliente simple y directo para Google Gemini"""
    
    def __init__(self):
        if not GEMINI_API_KEY:
            raise ValueError("❌ GEMINI_API_KEY no está definida en las variables de entorno")
        
        try:
            self.client = google_genai.Client(api_key=GEMINI_API_KEY)
            # Usamos 'gemini-2.0-flash-exp' por velocidad, o 'gemini-1.5-flash' por estabilidad
            self.model = 'gemini-2.0-flash-lite'
            logger.info("✅ Cliente Gemini cargado correctamente")
        except Exception as e:
            logger.error(f"Error iniciando cliente Gemini: {e}")
            raise

    async def generate(self, prompt):
        """Genera contenido usando únicamente Gemini"""
        try:
            logger.info(f"🤖 Generando texto con modelo {self.model}...")
            
            # Llamada a la API de Gemini
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt
            )
            
            return response.text
            
        except Exception as e:
            logger.error(f"❌ Error en la generación: {e}")
            # Relanzamos el error para que el flujo principal lo maneje (reintentar o fallar)
            raise Exception(f"Error en Gemini: {str(e)}")