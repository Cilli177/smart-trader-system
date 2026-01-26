import os
import time
import json
import requests
import feedparser
import google.generativeai as genai
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import warnings

# 1. Configuração
warnings.simplefilter(action='ignore', category=FutureWarning)
load_dotenv()

DB_URL = os.getenv("DATABASE_URL")
API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    print("❌ ERRO: GEMINI_API_KEY faltando.")
    exit(1)

# --- MUDANÇA: Usando o alias OFICIAL DE PRODUÇÃO (Estável) ---
genai.configure(api_key=API_KEY)
model_name = 'gemini-flash-latest' # Aponta para o modelo estável com cota grátis real
model = genai.GenerativeModel(model_name) 
engine = create_engine(DB_URL)

def get_google_news(query):
    url = f"https://news.google.com/rss/search?q={query}+ações&hl=pt-BR&gl=BR&ceid=BR:pt-419"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        return feedparser.parse(response.content)
    except Exception as e:
        print(f"   ⚠️ Erro RSS: {e}")
        return None

def analyze_with_retry(ticker, title):
    """Analisa com sistema de persistência para vencer o Rate Limit"""
    prompt = f"""
    Analise a manchete: "{title}" (Empresa: {ticker})
    Classifique o sentimento de -1.0 (Pessimista) a +1.0 (Otimista).
    Responda APENAS JSON: {{"score": 0.0, "summary": "Resumo curto"}}
    """
    
    # Reduzido para 2 tentativas, pois o modelo estável deve ir de primeira
    max_retries = 2
    for attempt in range(max_retries):
        try:
            response = model.generate_content(prompt)
            clean = response.text.replace("```json", "").replace("```", "").strip()
            return json.loads(clean)
            
        except Exception as e:
            if "429" in str(e) or "Quota" in str(e):
                print(f"   ⏳ Cota cheia. Aguardando 10s...")
                time.sleep(10)
            else:
                print(f"   ❌ Erro IA ({type(e).__name__}): {e}")
                return None
    
    return None

def run_analysis():
    print(f"\n--- 🧠 Morning Call AI (Modelo: {model_name}) ---")
    
    with engine.connect() as conn:
        assets = conn.execute(text("SELECT id, ticker, name FROM assets WHERE is_active = true")).fetchall()

    for asset in assets:
        print(f"\n🔍 Notícias sobre: {asset.name}...")
        feed = get_google_news(asset.name)
        
        if not feed or not feed.entries:
            print("   ⚠️ Nada encontrado.")
            continue

        for entry in feed.entries[:2]:
            link = entry.link
            title = entry.title
            
            with engine.connect() as conn:
                exists = conn.execute(text("SELECT 1 FROM market_news WHERE url = :url"), {"url": link}).scalar()
            
            if exists:
                print(f"   zzz Já li: {title[:30]}...")
                continue

            print(f"   🤖 Lendo: {title[:60]}...")
            analysis = analyze_with_retry(asset.name, title)
            
            if analysis:
                with engine.begin() as conn:
                    conn.execute(text("""
                        INSERT INTO market_news (asset_id, title, url, source, sentiment_score, sentiment_summary)
                        VALUES (:aid, :tit, :url, 'GoogleNews', :sc, :sum)
                    """), {
                        "aid": asset.id, "tit": title, "url": link,
                        "sc": analysis['score'], "sum": analysis['summary']
                    })
                print(f"   ✅ Score: {analysis['score']} | {analysis['summary']}")
                
                time.sleep(4) 

if __name__ == "__main__":
    run_analysis()