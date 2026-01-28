import os
import time
import schedule
import yfinance as yf
import requests
import json
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from datetime import datetime

# Carrega variáveis
load_dotenv()
DB_URL = os.getenv("DATABASE_URL")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
PERPLEXITY_KEY = os.getenv("PERPLEXITY_API_KEY")

if not DB_URL:
    print("❌ ERRO: DATABASE_URL não definida!")
    exit(1)

engine = create_engine(DB_URL)

def ensure_schema():
    """Garante schema do banco"""
    print("🔧 Verificando schema do banco...")
    with engine.begin() as conn:
        try:
            conn.execute(text("ALTER TABLE assets ADD COLUMN IF NOT EXISTS price DECIMAL(18, 2) DEFAULT 0;"))
            conn.execute(text("ALTER TABLE assets ADD COLUMN IF NOT EXISTS pe_ratio DECIMAL(10, 2) DEFAULT 0;"))
            conn.execute(text("ALTER TABLE assets ADD COLUMN IF NOT EXISTS dy_percentage DECIMAL(10, 2) DEFAULT 0;"))
            conn.execute(text("ALTER TABLE assets ADD COLUMN IF NOT EXISTS ai_analysis TEXT;"))
            conn.execute(text("ALTER TABLE assets ADD COLUMN IF NOT EXISTS news_summary TEXT;"))
            conn.execute(text("ALTER TABLE assets ADD COLUMN IF NOT EXISTS last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP;"))
        except Exception as e:
            print(f"⚠️ Aviso schema: {e}")

def get_ai_analysis(ticker, info):
    """Gera análise via REST API Direta (Sem SDK)"""
    if not GEMINI_KEY: return "Chave Gemini ausente."
    
    # URL Direta da API (Funciona sempre)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
    
    prompt = f"""
    Aja como um analista senior de ações da B3.
    Ativo: {ticker}
    Preço: R$ {info.get('currentPrice', 0)}
    P/L: {info.get('trailingPE', 'N/A')}
    Dividend Yield: {info.get('dividendYield', 0)*100 if info.get('dividendYield') else 0:.2f}%
    
    Responda em 1 frase curta (max 25 palavras): O valuation está atrativo? Qual o principal risco ou oportunidade?
    """
    
    headers = {'Content-Type': 'application/json'}
    data = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code == 200:
            # Parse do JSON de resposta do Google
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            print(f"⚠️ Erro Google API ({response.status_code}): {response.text}")
            return f"Erro na IA: {response.status_code}"
            
    except Exception as e:
        print(f"⚠️ Erro Request Gemini: {e}")
        return "Análise indisponível."

def get_news_from_perplexity(ticker):
    """Busca notícias via Perplexity"""
    if not PERPLEXITY_KEY: return "Chave News ausente."
    
    url = "https://api.perplexity.ai/chat/completions"
    payload = {
        "model": "llama-3.1-sonar-small-128k-online",
        "messages": [{"role": "user", "content": f"Qual a manchete financeira mais importante sobre {ticker} hoje? Resuma em 10 palavras."}]
    }
    headers = {"Authorization": f"Bearer {PERPLEXITY_KEY}", "Content-Type": "application/json"}
    
    try:
        res = requests.post(url, json=payload, headers=headers).json()
        if 'choices' in res:
            return res['choices'][0]['message']['content']
        return "Sem notícias relevantes."
    except Exception as e:
        print(f"⚠️ Erro Perplexity ({ticker}): {e}")
        return "Erro nas notícias."

def fix_ticker(ticker):
    ticker = ticker.upper().strip()
    if not ticker.endswith(".SA") and len(ticker) <= 6:
        return ticker + ".SA"
    return ticker

def run_market_update():
    print(f"\n--- 🚀 Inteligência V5 (Direct REST): {datetime.now()} ---")
    
    try:
        with engine.connect() as conn:
            assets = conn.execute(text("SELECT id, ticker FROM assets")).fetchall()
    except Exception as e:
        print(f"❌ Erro Conexão Banco: {e}")
        return

    for asset in assets:
        real_ticker = fix_ticker(asset.ticker)
        print(f"🔄 {real_ticker}...", end=" ")
        
        try:
            t = yf.Ticker(real_ticker)
            info = t.info
            current_price = info.get('currentPrice') or info.get('regularMarketPrice')
            
            if not current_price:
                print("⚠️ Sem preço (Ticker inválido?).")
                continue

            # Chama as IAs
            analysis = get_ai_analysis(real_ticker, info)
            news = get_news_from_perplexity(real_ticker)
            
            # Salva
            with engine.begin() as conn:
                sql = text("""
                    UPDATE assets SET 
                    price = :pr, pe_ratio = :pe, dy_percentage = :dy, 
                    ai_analysis = :ana, news_summary = :news, last_update = CURRENT_TIMESTAMP
                    WHERE id = :aid
                """)
                conn.execute(sql, {
                    "pr": current_price,
                    "pe": info.get('trailingPE', 0),
                    "dy": (info.get('dividendYield', 0) or 0) * 100,
                    "ana": analysis,
                    "news": news,
                    "aid": asset.id
                })
            print(f"✅ R$ {current_price} | IA: OK")
            
        except Exception as e:
            print(f"❌ Erro: {e}")

if __name__ == "__main__":
    ensure_schema()
    run_market_update()
    schedule.every(6).hours.do(run_market_update)
    while True:
        schedule.run_pending()
        time.sleep(60)