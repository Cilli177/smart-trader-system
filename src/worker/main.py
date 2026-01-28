import os
import time
import schedule
import yfinance as yf
import requests
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

# Variável Global para Cache do Modelo
FOUND_MODEL = None

def ensure_schema():
    print("🔧 Schema check...")
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

def find_working_model():
    """DIAGNÓSTICO: Pergunta ao Google quais modelos a chave pode usar"""
    global FOUND_MODEL
    if FOUND_MODEL: return FOUND_MODEL

    # Tenta listar modelos na versão v1beta (mais abrangente)
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_KEY}"
    
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if 'error' in data:
            return f"ERRO API: {data['error']['message']}"
            
        if 'models' not in data:
            return "LISTA VAZIA (Sua chave não vê modelos)"

        # Procura o primeiro modelo que gera texto
        available_models = []
        for m in data['models']:
            name = m['name'].replace("models/", "")
            available_models.append(name)
            if 'generateContent' in m.get('supportedGenerationMethods', []):
                print(f"✅ Modelo Válido Encontrado: {name}")
                FOUND_MODEL = name # Salva para não buscar de novo
                return name
        
        return f"SEM MODELOS TEXTO. Disponíveis: {', '.join(available_models[:3])}"

    except Exception as e:
        return f"ERRO CONEXÃO: {str(e)}"

def get_ai_analysis(ticker, info):
    if not GEMINI_KEY: return "Chave Gemini vazia."

    # 1. Descobre qual modelo usar (ou o erro)
    model_name_or_error = find_working_model()
    
    # Se o retorno parecer um erro (tem espaços ou é longo), exibe na tela
    if " " in model_name_or_error and "gemini" not in model_name_or_error:
        return f"DIAGNÓSTICO: {model_name_or_error}"

    # 2. Usa o modelo descoberto
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name_or_error}:generateContent?key={GEMINI_KEY}"
    
    # Prompt V10 (Deep Analysis)
    prompt = f"""
    Analista B3 Sênior. Ativo: {ticker}.
    Preço: R$ {info.get('currentPrice')}. P/L: {info.get('trailingPE', 'N/A')}.
    ROE: {info.get('returnOnEquity', 0)}.
    
    Em 1 parágrafo técnico (max 35 palavras):
    O valuation (P/L) e a qualidade (ROE) indicam compra ou cautela?
    """
    
    headers = {'Content-Type': 'application/json'}
    data = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=15)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            return f"Erro {response.status_code} no modelo {model_name_or_error}"
    except Exception as e:
        return f"Erro Req: {str(e)[:20]}"

def get_news_from_perplexity(ticker):
    # Notícias estão funcionando, mantemos.
    if not PERPLEXITY_KEY: return "Chave News vazia."
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
    except Exception as e:
        return f"Erro News: {str(e)[:20]}"

def fix_ticker(ticker):
    ticker = ticker.upper().strip()
    if not ticker.endswith(".SA") and len(ticker) <= 6: return ticker + ".SA"
    return ticker

def run_market_update():
    print(f"\n--- 🚀 Inteligência V12 (Diagnóstico): {datetime.now()} ---")
    
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

            analysis = get_ai_analysis(real_ticker, info)
            news = get_news_from_perplexity(real_ticker)
            
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
            print(f"✅ R$ {current_price} | Resposta: {analysis[:20]}...")
            
        except Exception as e:
            print(f"❌ Erro: {e}")

if __name__ == "__main__":
    ensure_schema()
    run_market_update()
    schedule.every(6).hours.do(run_market_update)
    while True:
        schedule.run_pending()
        time.sleep(60)