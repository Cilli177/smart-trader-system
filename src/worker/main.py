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
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "").replace('"', '').replace("'", "").strip()
PERPLEXITY_KEY = os.getenv("PERPLEXITY_API_KEY", "").replace('"', '').replace("'", "").strip()

if not DB_URL:
    print("❌ ERRO: DATABASE_URL não definida!")
    exit(1)

engine = create_engine(DB_URL)
CACHED_MODEL_NAME = None

def ensure_schema():
    print("🔧 Schema check (V16)...")
    with engine.begin() as conn:
        try:
            conn.execute(text("ALTER TABLE assets ADD COLUMN IF NOT EXISTS price DECIMAL(18, 2) DEFAULT 0;"))
            conn.execute(text("ALTER TABLE assets ADD COLUMN IF NOT EXISTS pe_ratio DECIMAL(10, 2) DEFAULT 0;"))
            conn.execute(text("ALTER TABLE assets ADD COLUMN IF NOT EXISTS dy_percentage DECIMAL(10, 2) DEFAULT 0;"))
            conn.execute(text("ALTER TABLE assets ADD COLUMN IF NOT EXISTS ai_analysis TEXT;"))
            conn.execute(text("ALTER TABLE assets ADD COLUMN IF NOT EXISTS full_report TEXT;"))
            conn.execute(text("ALTER TABLE assets ADD COLUMN IF NOT EXISTS news_summary TEXT;"))
            conn.execute(text("ALTER TABLE assets ADD COLUMN IF NOT EXISTS last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP;"))
        except Exception as e:
            print(f"⚠️ Aviso schema: {e}")

def get_valid_model():
    global CACHED_MODEL_NAME
    if CACHED_MODEL_NAME: return CACHED_MODEL_NAME
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_KEY}"
    try:
        data = requests.get(url, timeout=10).json()
        if 'models' not in data: return "gemini-1.5-flash"
        for m in data['models']:
            name = m['name'].replace("models/", "")
            if "gemini" in name and "generateContent" in m.get('supportedGenerationMethods', []):
                CACHED_MODEL_NAME = name
                return name
        return "gemini-1.5-flash"
    except: return "gemini-1.5-flash"

def get_ai_analysis(ticker, info):
    if not GEMINI_KEY: return ("Chave vazia", "Sem detalhes")

    model_name = get_valid_model()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_KEY}"
    
    # Dados Técnicos
    pl = info.get('trailingPE', 'N/A')
    roe = info.get('returnOnEquity', 0)
    high52 = info.get('fiftyTwoWeekHigh', 0)
    low52 = info.get('fiftyTwoWeekLow', 0)
    current = info.get('currentPrice', 0)
    
    tendencia = "Lateral"
    if current > high52 * 0.9: tendencia = "Alta Forte (Topo Histórico)"
    elif current < low52 * 1.1: tendencia = "Baixa (Perto da Mínima)"
    
    prompt = f"""
    Analista B3 Sênior. Ativo: {ticker}.
    Dados: Preço: {current} | P/L: {pl} | ROE: {roe} | Faixa 52 Semanas: {low52}-{high52} | Tendência: {tendencia}

    Gere JSON puro com dois campos:
    1. "summary": Resumo estratégico (max 40 palavras).
    2. "full_report": Análise completa com quebras de linha (Fundamentalista + Técnica + Veredito).
    """
    
    headers = {'Content-Type': 'application/json'}
    data = {"contents": [{"parts": [{"text": prompt}]}]}
    
    # --- SMART RETRY (TENTA ATÉ 3 VEZES SE DER 429) ---
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=data, timeout=40)
            
            if response.status_code == 200:
                text_resp = response.json()['candidates'][0]['content']['parts'][0]['text']
                text_resp = text_resp.replace("```json", "").replace("```", "").strip()
                try:
                    json_data = json.loads(text_resp)
                    return (json_data.get("summary", "Erro resumo"), json_data.get("full_report", "Erro detalhe"))
                except:
                    return ("Erro JSON", text_resp) # Retorna texto puro se falhar o JSON
            
            elif response.status_code == 429:
                print(f"⏳ Cota excedida (429). Esperando 60s para tentar de novo...")
                time.sleep(60) # Pausa longa para recuperar a cota
                continue # Tenta de novo
            
            else:
                return (f"Erro {response.status_code}", "")
                
        except Exception as e:
            return (f"Erro: {str(e)[:20]}", "")
            
    return ("Erro 429 Persistente", "Tente mais tarde.")

def get_news_from_perplexity(ticker):
    if not PERPLEXITY_KEY: return "Sem chave News"
    url = "https://api.perplexity.ai/chat/completions"
    payload = {
        "model": "sonar", 
        "messages": [{"role": "user", "content": f"Manchete financeira de {ticker} hoje (max 20 palavras)."}]
    }
    headers = {"Authorization": f"Bearer {PERPLEXITY_KEY}", "Content-Type": "application/json"}
    try:
        res = requests.post(url, json=payload, headers=headers).json()
        if 'choices' in res: return res['choices'][0]['message']['content']
        return "Sem dados."
    except: return "Erro News"

def fix_ticker(ticker):
    ticker = ticker.upper().strip()
    if not ticker.endswith(".SA") and len(ticker) <= 6: return ticker + ".SA"
    return ticker

def run_market_update():
    print(f"\n--- 🚀 V16 (Smart Retry Anti-429): {datetime.now()} ---")
    try:
        with engine.connect() as conn:
            assets = conn.execute(text("SELECT id, ticker FROM assets")).fetchall()
    except Exception as e:
        print(f"❌ Erro Banco: {e}")
        return

    for asset in assets:
        real_ticker = fix_ticker(asset.ticker)
        print(f"🔄 {real_ticker}...", end=" ")
        
        try:
            t = yf.Ticker(real_ticker)
            info = t.info
            current_price = info.get('currentPrice') or info.get('regularMarketPrice')
            
            if not current_price:
                print("⚠️ Sem preço.")
                continue

            # Chama IA (Com retry embutido)
            summary, full_report = get_ai_analysis(real_ticker, info)
            news = get_news_from_perplexity(real_ticker)
            
            with engine.begin() as conn:
                sql = text("""
                    UPDATE assets SET 
                    price = :pr, pe_ratio = :pe, dy_percentage = :dy, 
                    ai_analysis = :ana, full_report = :full, news_summary = :news, last_update = CURRENT_TIMESTAMP
                    WHERE id = :aid
                """)
                conn.execute(sql, {
                    "pr": current_price,
                    "pe": info.get('trailingPE', 0),
                    "dy": (info.get('dividendYield', 0) or 0) * 100,
                    "ana": summary,
                    "full": full_report,
                    "news": news,
                    "aid": asset.id
                })
            print(f"✅ R$ {current_price} | IA: {summary[:15]}...")
            
            # Pausa padrão entre ações (aumentei para 10s por segurança)
            time.sleep(10) 
            
        except Exception as e:
            print(f"❌ Erro: {e}")

if __name__ == "__main__":
    ensure_schema()
    run_market_update()
    schedule.every(6).hours.do(run_market_update)
    while True:
        schedule.run_pending()
        time.sleep(60)