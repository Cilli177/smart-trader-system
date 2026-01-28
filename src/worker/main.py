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
    print("🔧 Schema check (V2)...")
    with engine.begin() as conn:
        try:
            # Colunas básicas
            conn.execute(text("ALTER TABLE assets ADD COLUMN IF NOT EXISTS price DECIMAL(18, 2) DEFAULT 0;"))
            conn.execute(text("ALTER TABLE assets ADD COLUMN IF NOT EXISTS pe_ratio DECIMAL(10, 2) DEFAULT 0;"))
            conn.execute(text("ALTER TABLE assets ADD COLUMN IF NOT EXISTS dy_percentage DECIMAL(10, 2) DEFAULT 0;"))
            conn.execute(text("ALTER TABLE assets ADD COLUMN IF NOT EXISTS ai_analysis TEXT;"))
            conn.execute(text("ALTER TABLE assets ADD COLUMN IF NOT EXISTS news_summary TEXT;"))
            conn.execute(text("ALTER TABLE assets ADD COLUMN IF NOT EXISTS last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP;"))
            
            # NOVA COLUNA PARA O RELATÓRIO COMPLETO
            conn.execute(text("ALTER TABLE assets ADD COLUMN IF NOT EXISTS full_report TEXT;"))
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
                print(f"✅ Modelo: {name}")
                CACHED_MODEL_NAME = name
                return name
        return "gemini-1.5-flash"
    except: return "gemini-1.5-flash"

def get_ai_analysis(ticker, info):
    if not GEMINI_KEY: return ("Chave vazia", "Sem detalhes")

    model_name = get_valid_model()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_KEY}"
    
    # --- DADOS TÉCNICOS PARA SIMULAR GRÁFICO ---
    pl = info.get('trailingPE', 'N/A')
    roe = info.get('returnOnEquity', 0)
    high52 = info.get('fiftyTwoWeekHigh', 0)
    low52 = info.get('fiftyTwoWeekLow', 0)
    current = info.get('currentPrice', 0)
    
    # Lógica simples de tendência
    tendencia = "Lateral"
    if current > high52 * 0.9: tendencia = "Alta Forte (Topo Histórico)"
    elif current < low52 * 1.1: tendencia = "Baixa (Perto da Mínima)"
    
    prompt = f"""
    Analista B3 Sênior. Ativo: {ticker}.
    Dados:
    - Preço: {current}
    - P/L: {pl} | ROE: {roe}
    - Faixa 52 Semanas: {low52} - {high52}
    - Tendência Técnica Aparente: {tendencia}

    Gere um JSON puro (sem markdown) com dois campos:
    1. "summary": Um resumo estratégico de no MÁXIMO 50 PALAVRAS. Foque no valuation.
    2. "full_report": Uma análise completa e detalhada. Use quebras de linha.
       - Inclua Análise Fundamentalista (P/L, ROE).
       - Inclua Análise Técnica (Baseada na tendência e preço vs máximas).
       - Inclua Veredito (Compra/Venda/Neutro).
    """
    
    headers = {'Content-Type': 'application/json'}
    data = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=40)
        if response.status_code == 200:
            text_resp = response.json()['candidates'][0]['content']['parts'][0]['text']
            # Limpeza do JSON (o Gemini as vezes manda ```json ... ```)
            text_resp = text_resp.replace("```json", "").replace("```", "").strip()
            json_data = json.loads(text_resp)
            return (json_data.get("summary", "Erro resumo"), json_data.get("full_report", "Erro detalhe"))
        else:
            return (f"Erro {response.status_code}", "")
    except Exception as e:
        return (f"Erro: {str(e)[:20]}", "")

def get_news_from_perplexity(ticker):
    # Mantido (Notícias estão ótimas)
    if not PERPLEXITY_KEY: return "Sem chave News"
    url = "https://api.perplexity.ai/chat/completions"
    payload = {
        "model": "sonar", 
        "messages": [{"role": "user", "content": f"Manchete financeira importante de {ticker} hoje (max 20 palavras)."}]
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
    print(f"\n--- 🚀 V15 (JSON + Full Report): {datetime.now()} ---")
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

            # Chama IA (Retorna Tupla: Resumo, Detalhe)
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
                    "full": full_report, # Salva o relatório completo
                    "news": news,
                    "aid": asset.id
                })
            print(f"✅ R$ {current_price} | Resumo: OK | Full: OK")
            time.sleep(5) # Paciência para API grátis
            
        except Exception as e:
            print(f"❌ Erro: {e}")

if __name__ == "__main__":
    ensure_schema()
    run_market_update()
    schedule.every(6).hours.do(run_market_update)
    while True:
        schedule.run_pending()
        time.sleep(60)