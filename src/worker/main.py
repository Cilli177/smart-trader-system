import os
import time
import schedule
import yfinance as yf
import pandas as pd
import requests
from google import genai
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from datetime import datetime

# Carrega variáveis
load_dotenv()
DB_URL = os.getenv("DATABASE_URL")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
PERPLEXITY_KEY = os.getenv("PERPLEXITY_API_KEY")

# Conexão Banco
if not DB_URL:
    print("❌ ERRO: DATABASE_URL não definida!")
    exit(1)

engine = create_engine(DB_URL)

def ensure_schema():
    """Garante que as colunas existam"""
    print("🔧 Verificando schema do banco de dados...")
    with engine.begin() as conn:
        try:
            conn.execute(text("ALTER TABLE assets ADD COLUMN IF NOT EXISTS price DECIMAL(18, 2) DEFAULT 0;"))
            conn.execute(text("ALTER TABLE assets ADD COLUMN IF NOT EXISTS pe_ratio DECIMAL(10, 2) DEFAULT 0;"))
            conn.execute(text("ALTER TABLE assets ADD COLUMN IF NOT EXISTS dy_percentage DECIMAL(10, 2) DEFAULT 0;"))
            conn.execute(text("ALTER TABLE assets ADD COLUMN IF NOT EXISTS roe_percentage DECIMAL(10, 2) DEFAULT 0;"))
            conn.execute(text("ALTER TABLE assets ADD COLUMN IF NOT EXISTS p_vp DECIMAL(10, 2) DEFAULT 0;"))
            conn.execute(text("ALTER TABLE assets ADD COLUMN IF NOT EXISTS ai_analysis TEXT;"))
            conn.execute(text("ALTER TABLE assets ADD COLUMN IF NOT EXISTS news_summary TEXT;"))
            conn.execute(text("ALTER TABLE assets ADD COLUMN IF NOT EXISTS last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP;"))
            print("✅ Schema verificado.")
        except Exception as e:
            print(f"⚠️ Aviso schema: {e}")

def get_ai_analysis(ticker, info):
    """Gera análise usando a NOVA biblioteca google-genai"""
    if not GEMINI_KEY: return "Chave Gemini não configurada."
    
    try:
        # Nova Sintaxe: Cliente direto
        client = genai.Client(api_key=GEMINI_KEY)
        
        prompt = f"""
        Você é um analista financeiro experiente focado na B3 (Brasil).
        Analise a ação {ticker} com estes dados fundamentalistas:
        - P/L (Preço/Lucro): {info.get('trailingPE', 'N/A')}
        - Dividend Yield: {info.get('dividendYield', 0)*100 if info.get('dividendYield') else 0:.2f}%
        
        Responda em APENAS 1 parágrafo curto e direto (máximo 30 palavras).
        Diga se os indicadores sugerem que está barata ou cara e o motivo principal.
        """
        
        # Chamada atualizada para o modelo Flash
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=prompt
        )
        return response.text
    except Exception as e:
        print(f"⚠️ Erro Gemini: {e}")
        return "Análise indisponível no momento."

def get_news_from_perplexity(ticker):
    """Busca notícias via Perplexity"""
    if not PERPLEXITY_KEY: return "Sem chave de notícias."
    
    url = "https://api.perplexity.ai/chat/completions"
    payload = {
        "model": "llama-3.1-sonar-small-128k-online",
        "messages": [{"role": "user", "content": f"Resuma em 1 frase a notícia mais impactante de hoje para {ticker}."}]
    }
    headers = {"Authorization": f"Bearer {PERPLEXITY_KEY}", "Content-Type": "application/json"}
    
    try:
        res = requests.post(url, json=payload, headers=headers).json()
        if 'choices' in res:
            return res['choices'][0]['message']['content']
        return "Sem notícias relevantes."
    except Exception as e:
        print(f"⚠️ Erro Perplexity: {e}")
        return "Erro ao buscar notícias."

def fix_ticker(ticker):
    ticker = ticker.upper().strip()
    if not ticker.endswith(".SA") and len(ticker) <= 6:
        return ticker + ".SA"
    return ticker

def run_market_update():
    print(f"\n--- 🚀 Iniciando Atualização (V2): {datetime.now()} ---")
    
    try:
        with engine.connect() as conn:
            assets = conn.execute(text("SELECT id, ticker FROM assets")).fetchall()
    except Exception as e:
        print(f"❌ Erro Banco: {e}")
        return

    for asset in assets:
        real_ticker = fix_ticker(asset.ticker)
        print(f"🔄 Processando: {real_ticker}...")
        
        try:
            t = yf.Ticker(real_ticker)
            info = t.info
            current_price = info.get('currentPrice') or info.get('regularMarketPrice')
            
            if not current_price:
                print(f"   ⚠️ Sem preço para {real_ticker}")
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
            print(f"   ✅ {real_ticker}: R$ {current_price} | IA: OK")
            
        except Exception as e:
            print(f"   ❌ Falha {real_ticker}: {e}")

if __name__ == "__main__":
    ensure_schema()
    run_market_update()
    schedule.every(6).hours.do(run_market_update)
    while True:
        schedule.run_pending()
        time.sleep(60)