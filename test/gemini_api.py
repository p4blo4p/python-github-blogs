from google import genai

# Usa automáticamente GEMINI_API_KEY o GOOGLE_API_KEY de entorno
client = genai.Client()

response = client.models.generate_content(
    model="gemini-2.0-flash",
    contents=["How does AI work?"])
print(response.text)