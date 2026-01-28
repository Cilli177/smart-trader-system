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

# Limpeza de chaves
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "").replace('"', '').replace("'", "").strip()
PERPLEXITY_KEY = os.getenv("PERPLEXITY_API_KEY", "").replace('"', '').replace("'", "").strip()

if not DB_URL:
    print("❌ ERRO: DATABASE_URL não definida!")
    exit(1)

engine = create_engine(DB_URL)

# Variável para guardar o modelo que funciona (Cache)
CURRENT_VALID_MODEL = None

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

def find_available_model():
    """PERGUNTA AO GOOGLE QUAIS MODELOS A CHAVE TEM ACESSO"""
    global CURRENT_VALID_MODEL
    if CURRENT_VALID_MODEL: return CURRENT_VALID_MODEL

    print("🔍 Buscando modelos disponíveis na sua conta Google...")
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_KEY}"
    
    try:
        res = requests.get(url, timeout=10).json()
        
        if 'error' in res:
            print(f"❌ Erro ao listar modelos: {res['error']['message']}")
            return None
            
        # Procura um modelo que sirva para gerar texto
        for m in res.get('models', []):
            name = m['name'] # ex: models/gemini-1.5-flash
            methods = m.get('supportedGenerationMethods', [])
            
            # Prioridade para modelos Flash ou Pro
            if 'generateContent' in methods:
                print(f"✅ Modelo Encontrado: {name}")
                CURRENT_VALID_MODEL = name
                return name
                
    except Exception as e:
        print(f"❌ Erro na Auto-Descoberta: {e}")
    
    # Fallback se a descoberta falhar
    return "models/gemini-1.5-flash"

def get_ai_analysis(ticker, info):
    if not GEMINI_KEY: return "ERRO: Chave Gemini vazia."

    # 1. Descobre qual modelo usar
    model_name = find_available_model()
    if not model_name: return "ERRO: Nenhum modelo disponível na sua conta."

    # 2. Monta a URL com o modelo descoberto
    # O model_name já vem como "models/nome", então a URL fica correta
    url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={GEMINI_KEY}"
    
    prompt = f"""
    Ativo: {ticker}. Preço: R$ {info.get('currentPrice')}. P/L: {info.get('trailingPE')}.
    Responda em 1 frase curta: O indicador P/L indica oportunidade ou risco?
    """
    
    headers = {'Content-Type': 'application/json'}
    data = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            return f"Erro Google ({response.status_code}): {response.text[:40]}"
            
    except Exception as e:
        return f"Erro Request: {str(e)[:30]}"

def get_news_from_perplexity(ticker):
    # MANTIDO IGUAL - ESTÁ FUNCIONANDO PERFEITAMENTE
    if not PERPLEXITY_KEY: return "ERRO: Chave News vazia."
    
    url = "https://api.perplexity.ai/chat/completions"
    payload = {
        "model": "sonar", 
        "messages": [{"role": "user", "content": f"Manchete mais importante de {ticker} hoje (1 frase)."}]
    }
    headers = {"Authorization": f"Bearer {PERPLEXITY_KEY}", "Content-Type": "application/json"}
    
    try:
        res = requests.post(url, json=payload, headers=headers).json()
        if 'error' in res: return f"Erro API: {res['error']['message'][:50]}"
        if 'choices' in res: return res['choices'][0]['message']['content']
        return "Sem dados."
    except Exception as e:
        return f"Erro News: {str(e)[:30]}"

def fix_ticker(ticker):
    ticker = ticker.upper().strip()
    if not ticker.endswith(".SA") and len(ticker) <= 6: return ticker + ".SA"
    return ticker

def run_market_update():
    print(f"\n--- 🚀 Inteligência V8 (Auto-Discovery): {datetime.now()} ---")
    
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
            print(f"✅ R$ {current_price} | IA: {analysis[:15]}...")
            
        except Exception as e:
            print(f"❌ Erro: {e}")

if __name__ == "__main__":
    ensure_schema()
    run_market_update()
    schedule.every(6).hours.do(run_market_update)
    while True:
        schedule.run_pending()
        time.sleep(60)