import os
import time
import schedule
import yfinance as yf
import requests
from google import genai
from google.genai import types
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
    """Gera análise via Gemini com FALLBACK de modelos"""
    if not GEMINI_KEY: return "Chave Gemini ausente."
    
    # Lista de modelos para tentar (do mais novo para o mais estável)
    # Isso evita o erro 404 se um modelo específico mudar de nome
    models_to_try = ['gemini-1.5-flash', 'gemini-1.5-flash-001', 'gemini-1.5-flash-latest']
    
    client = genai.Client(api_key=GEMINI_KEY)
    
    prompt = f"""
    Aja como um investidor experiente na B3.
    Ativo: {ticker}
    P/L: {info.get('trailingPE', 'N/A')}
    Dividend Yield: {info.get('dividendYield', 0)*100 if info.get('dividendYield') else 0:.2f}%
    
    Em UMA frase curta e direta (max 20 palavras): O indicador P/L sugere que está cara ou barata? Vale o risco?
    """

    for model_name in models_to_try:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            return response.text
        except Exception as e:
            # Se der erro 404, ele apenas tenta o próximo modelo da lista
            continue
            
    print(f"⚠️ Todos os modelos Gemini falharam para {ticker}")
    return "Análise indisponível no momento."

def get_news_from_perplexity(ticker):
    """Busca notícias via Perplexity"""
    if not PERPLEXITY_KEY: return "Chave News ausente."
    
    url = "https://api.perplexity.ai/chat/completions"
    payload = {
        "model": "llama-3.1-sonar-small-128k-online",
        "messages": [{"role": "user", "content": f"Resuma em 1 frase a notícia mais importante de hoje sobre {ticker}. Se não houver, fale sobre o setor."}]
    }
    headers = {"Authorization": f"Bearer {PERPLEXITY_KEY}", "Content-Type": "application/json"}
    
    try:
        res = requests.post(url, json=payload, headers=headers).json()
        if 'choices' in res:
            return res['choices'][0]['message']['content']
        return "Sem notícias recentes."
    except Exception as e:
        print(f"⚠️ Erro Perplexity ({ticker}): {e}")
        return "Erro nas notícias."

def fix_ticker(ticker):
    ticker = ticker.upper().strip()
    if not ticker.endswith(".SA") and len(ticker) <= 6:
        return ticker + ".SA"
    return ticker

def run_market_update():
    print(f"\n--- 🚀 Inteligência V4 (Multi-Model): {datetime.now()} ---")
    
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
                print("⚠️ Sem preço.")
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