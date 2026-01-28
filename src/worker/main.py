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

def get_ai_analysis(ticker, info):
    if not GEMINI_KEY: return "Chave Gemini vazia."

    # --- 1. DADOS FUNDAMENTALISTAS ---
    pl = info.get('trailingPE', 'N/A')
    p_vp = info.get('priceToBook', 'N/A')
    roe = info.get('returnOnEquity', 0)
    margem = info.get('profitMargins', 0)
    div_yield = (info.get('dividendYield', 0) or 0) * 100

    # Formatação
    roe_fmt = f"{roe*100:.1f}%" if isinstance(roe, (int, float)) else "N/A"
    margem_fmt = f"{margem*100:.1f}%" if isinstance(margem, (int, float)) else "N/A"
    dy_fmt = f"{div_yield:.1f}%"

    # --- 2. PROMPT AVANÇADO (V10) ---
    prompt = f"""
    Aja como um analista Sênior de Value Investing focado na B3.
    Analise o ativo {ticker}:
    - Preço: R$ {info.get('currentPrice')}
    - P/L: {pl} (Setor ~10)
    - P/VP: {p_vp}
    - ROE: {roe_fmt}
    - Margem Líquida: {margem_fmt}
    - Dividend Yield: {dy_fmt}

    Em 1 parágrafo DENSO (max 35 palavras):
    Interprete se o ativo está barato (P/L, P/VP) e se tem qualidade (ROE, Margem).
    Cite explicitamente os indicadores chave. Dê um veredito de risco ou oportunidade.
    """

    # --- 3. ESTRATÉGIA DE REDUNDÂNCIA (V7) ---
    # Tenta vários modelos. Se um der 404, pula para o próximo.
    attempts = [
        ("gemini-1.5-flash", "v1beta"),
        ("gemini-1.5-pro", "v1beta"),
        ("gemini-1.5-flash-latest", "v1beta"),
        ("gemini-pro", "v1")
    ]
    
    last_error = ""

    for model, version in attempts:
        url = f"https://generativelanguage.googleapis.com/{version}/models/{model}:generateContent?key={GEMINI_KEY}"
        headers = {'Content-Type': 'application/json'}
        data = {"contents": [{"parts": [{"text": prompt}]}]}
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=15)
            
            if response.status_code == 200:
                # SUCESSO!
                return response.json()['candidates'][0]['content']['parts'][0]['text']
            else:
                last_error = f"{model} ({response.status_code})"
                continue # Tenta o próximo
                
        except Exception as e:
            last_error = str(e)

    return f"FALHA IA: {last_error}"

def get_news_from_perplexity(ticker):
    # Notícias estão ótimas, mantemos igual
    if not PERPLEXITY_KEY: return "Chave News vazia."
    url = "https://api.perplexity.ai/chat/completions"
    payload = {
        "model": "sonar", 
        "messages": [{"role": "user", "content": f"Manchete financeira mais importante sobre {ticker} hoje (max 20 palavras)."}]
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
    print(f"\n--- 🚀 Inteligência V11 (Híbrida): {datetime.now()} ---")
    
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