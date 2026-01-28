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
    print("🔧 Schema check (V19)...")
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
    if not GEMINI_KEY: return ("Chave vazia", "Sem detalhes", 500)

    model_name = get_valid_model()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_KEY}"
    
    pl = info.get('trailingPE', 'N/A')
    roe = info.get('returnOnEquity', 0)
    high52 = info.get('fiftyTwoWeekHigh', 0)
    low52 = info.get('fiftyTwoWeekLow', 0)
    current = info.get('currentPrice', 0)
    
    tendencia = "Lateral"
    if current > high52 * 0.9: tendencia = "Alta Forte"
    elif current < low52 * 1.1: tendencia = "Baixa"
    
    prompt = f"""
    Analista B3. Ativo: {ticker}. Preço: {current}. P/L: {pl}. ROE: {roe}. Tendência: {tendencia}.
    JSON campos: "summary" (max 40 palavras), "full_report" (análise completa).
    """
    
    headers = {'Content-Type': 'application/json'}
    data = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        if response.status_code == 200:
            text_resp = response.json()['candidates'][0]['content']['parts'][0]['text']
            text_resp = text_resp.replace("```json", "").replace("```", "").strip()
            try:
                json_data = json.loads(text_resp)
                return (json_data.get("summary", "Erro resumo"), json_data.get("full_report", "Erro detalhe"), 200)
            except:
                return ("Erro JSON", text_resp, 200)
        elif response.status_code == 429:
            return ("⚠️ Cota Google Excedida", "Aguarde restabelecimento.", 429)
        else:
            return (f"Erro Google {response.status_code}", "", response.status_code)
            
    except Exception as e:
        return (f"Erro Req: {str(e)[:15]}", "", 500)

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
        
        if 'choices' in res:
            content = res['choices'][0]['message']['content']
            
            # --- EXTRAÇÃO DE LINKS (CITAÇÕES) ---
            citations = res.get('citations', [])
            
            if citations:
                # Monta o rodapé com os links
                formatted_text = content + "\n\nFontes:"
                for i, link in enumerate(citations):
                    # Formato: [1] http://url...
                    formatted_text += f"\n[{i+1}] {link}"
                return formatted_text
            
            return content
            
        return "Sem dados."
    except Exception as e:
        return f"Erro News: {str(e)[:20]}"

def fix_ticker(ticker):
    ticker = ticker.upper().strip()
    if not ticker.endswith(".SA") and len(ticker) <= 6: return ticker + ".SA"
    return ticker

def run_market_update():
    print(f"\n--- 🚀 V19 (Links Fontes + Blindado): {datetime.now()} ---")
    try:
        with engine.connect() as conn:
            assets = conn.execute(text("SELECT id, ticker, ai_analysis, last_update FROM assets")).fetchall()
    except Exception as e:
        print(f"❌ Erro Banco: {e}")
        return

    google_blocked = False

    for asset in assets:
        real_ticker = fix_ticker(asset.ticker)
        print(f"🔄 {real_ticker}...", end=" ")
        
        try:
            # 1. MERCADO
            t = yf.Ticker(real_ticker)
            info = t.info
            current_price = info.get('currentPrice') or info.get('regularMarketPrice')
            
            if not current_price:
                print("⚠️ Sem preço.")
                continue

            # 2. NOTÍCIAS (Agora com Links!)
            news = get_news_from_perplexity(real_ticker)
            
            # Salva preço e news imediatamente
            with engine.begin() as conn:
                conn.execute(text("""
                    UPDATE assets SET 
                    price = :pr, pe_ratio = :pe, dy_percentage = :dy, news_summary = :news, last_update = CURRENT_TIMESTAMP
                    WHERE id = :aid
                """), {
                    "pr": current_price,
                    "pe": info.get('trailingPE', 0),
                    "dy": (info.get('dividendYield', 0) or 0) * 100,
                    "news": news,
                    "aid": asset.id
                })
            
            print(f"💰 Dados salvos.", end=" ")

            # 3. IA (Com trava de segurança)
            if google_blocked:
                print("⏭️ 429 Ativo. Skip IA.")
                continue

            # Skip se recente
            last_up = asset.last_update
            current_ai = asset.ai_analysis or ""
            is_recent = last_up and (datetime.now() - last_up).total_seconds() < 14400
            has_valid_ai = "Erro" not in current_ai and "Cota" not in current_ai and len(current_ai) > 10

            if is_recent and has_valid_ai:
                print("✅ IA recente. Skip.")
                continue

            # Tenta IA
            summary, full_report, status_code = get_ai_analysis(real_ticker, info)
            
            if status_code == 429:
                print("🛑 429! Parando IAs.")
                google_blocked = True
                with engine.begin() as conn:
                    conn.execute(text("UPDATE assets SET ai_analysis = :ana WHERE id = :aid"), 
                                {"ana": "⚠️ Cota Excedida", "aid": asset.id})
            else:
                with engine.begin() as conn:
                    conn.execute(text("UPDATE assets SET ai_analysis = :ana, full_report = :full WHERE id = :aid"), 
                                {"ana": summary, "full": full_report, "aid": asset.id})
                print("✅ IA OK.")
                time.sleep(15) 

        except Exception as e:
            print(f"❌ Erro: {e}")

if __name__ == "__main__":
    ensure_schema()
    run_market_update()
    schedule.every(6).hours.do(run_market_update)
    while True:
        schedule.run_pending()
        time.sleep(60)