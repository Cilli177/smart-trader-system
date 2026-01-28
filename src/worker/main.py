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

# Cache para não ficar perguntando toda hora
CACHED_MODEL_NAME = None

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

def get_valid_model():
    """Pergunta ao Google qual modelo está disponível para esta chave"""
    global CACHED_MODEL_NAME
    if CACHED_MODEL_NAME: return CACHED_MODEL_NAME

    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_KEY}"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if 'models' not in data:
            return None # Chave inválida ou erro

        # Procura o primeiro modelo 'gemini' que gera texto
        for m in data['models']:
            name = m['name'].replace("models/", "")
            if "gemini" in name and "generateContent" in m.get('supportedGenerationMethods', []):
                print(f"✅ Modelo Detectado: {name}")
                CACHED_MODEL_NAME = name
                return name
        
        # Se não achar nada, tenta o flash padrão
        return "gemini-1.5-flash"
    except:
        return "gemini-1.5-flash"

def get_ai_analysis(ticker, info):
    if not GEMINI_KEY: return "Chave Gemini vazia."

    # 1. Pega o modelo correto
    model_name = get_valid_model()
    if not model_name: return "ERRO: Chave não acessa modelos."

    # 2. Monta a URL
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_KEY}"
    
    # 3. Prompt Rico (Igual ao da Petrobras que funcionou)
    pl = info.get('trailingPE', 'N/A')
    roe = info.get('returnOnEquity', 0)
    roe_fmt = f"{roe*100:.1f}%" if isinstance(roe, (int, float)) else "N/A"
    
    prompt = f"""
    Analista Sênior B3. Ativo: {ticker}.
    Preço: R$ {info.get('currentPrice')}. P/L: {pl}. ROE: {roe_fmt}.
    Em 1 parágrafo denso (PT-BR): Interprete os indicadores (P/L e ROE). Indica oportunidade ou risco?
    """
    
    headers = {'Content-Type': 'application/json'}
    data = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            return f"Erro Google ({response.status_code})"
    except Exception as e:
        return f"Erro Req: {str(e)[:20]}"

def get_news_from_perplexity(ticker):
    # Perplexity está ótimo, não mexe.
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
    print(f"\n--- 🚀 V13 (Auto-Modelo + Paciência): {datetime.now()} ---")
    
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

            # IA
            analysis = get_ai_analysis(real_ticker, info)
            
            # Notícias
            news = get_news_from_perplexity(real_ticker)
            
            # Salva no Banco
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
            print(f"✅ Salvo. Aguardando 5s...")
            
            # --- O SEGREDO DO SUCESSO ---
            # Pausa de 5 segundos para o Google não bloquear a gente
            time.sleep(5) 
            
        except Exception as e:
            print(f"❌ Erro: {e}")

if __name__ == "__main__":
    ensure_schema()
    run_market_update()
    schedule.every(6).hours.do(run_market_update)
    while True:
        schedule.run_pending()
        time.sleep(60)