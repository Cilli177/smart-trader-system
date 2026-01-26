import google.generativeai as genai
import os
from dotenv import load_dotenv

# Carrega a chave
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)

print(f"🔑 Testando chave: {api_key[:5]}... (Ocultada)")
print("📡 Perguntando ao Google quais modelos estão disponíveis...")

try:
    count = 0
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"   ✅ Disponível: {m.name}")
            count += 1
    
    if count == 0:
        print("⚠️ A API respondeu, mas não listou modelos de texto. Verifique se a chave tem permissões.")
        
except Exception as e:
    print(f"❌ Erro fatal: {e}")