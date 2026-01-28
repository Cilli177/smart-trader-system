import os
import time
import schedule
import yfinance as yf
import pandas as pd
import requests
import google.generativeai as genai
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
DB_URL = os.getenv("DATABASE_URL")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
PERPLEXITY_KEY = os.getenv("PERPLEXITY_API_KEY")

genai.configure(api_key=GEMINI_KEY)
engine = create_engine(DB_URL)

def get_ai_analysis(ticker, info):
    """Gera análise fundamentalista via Gemini"""
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""
        Analise o ativo {ticker} com estes dados:
        P/L: {info.get('trailingPE', 0)}, DY: {info.get('dividendYield', 0)*100}%, 
        ROE: {info.get('returnOnEquity', 0)*100}%, P/VP: {info.get('priceToBook', 0)}.
        Seja breve (3 frases): O papel está barato ou caro? Qual o maior risco?
        """
        response = model.generate_content(prompt)
        return response.text
    except:
        return "Análise temporariamente indisponível."

def get_news_from_perplexity(ticker):
    """Busca notícias reais via Perplexity"""
    if not PERPLEXITY_KEY: return "Configure a API Key para notícias.", []
    
    url = "https://api.perplexity.ai/chat/completions"
    payload = {
        "model": "pplx-7b-online",
        "messages": [{"role": "user", "content": f"Resuma as 3 notícias mais importantes de hoje para {ticker} na B3 em português."}]
    }
    headers = {"Authorization": f"Bearer {PERPLEXITY_KEY}", "Content-Type": "application/json"}
    
    try:
        res = requests.post(url, json=payload, headers=headers).json()
        return res['choices'][0]['message']['content'], ["https://www.google.com/search?q="+ticker]
    except:
        return "Erro ao buscar notícias.", []

def run_market_update():
    print(f"\n--- 🚀 Inteligência Iniciada: {datetime.now()} ---")
    with engine.connect() as conn:
        assets = conn.execute(text("SELECT id, ticker FROM assets WHERE is_active = true")).fetchall()

    for asset in assets:
        try:
            print(f"🔄 Analisando: {asset.ticker}...")
            t = yf.Ticker(asset.ticker)
            info = t.info
            
            # 1. Inteligência
            analysis = get_ai_analysis(asset.ticker, info)
            news, links = get_news_from_perplexity(asset.ticker)
            
            # 2. Atualiza Tabela Assets (O Cérebro)
            with engine.begin() as conn:
                sql = text("""
                    UPDATE assets SET 
                    price = :pr, pe_ratio = :pe, dy_percentage = :dy, 
                    roe_percentage = :roe, p_vp = :pvp, ai_analysis = :ana,
                    news_summary = :news, last_update = CURRENT_TIMESTAMP
                    WHERE id = :aid
                """)
                conn.execute(sql, {
                    "pr": info.get('currentPrice', 0),
                    "pe": info.get('trailingPE', 0),
                    "dy": info.get('dividendYield', 0) * 100,
                    "roe": info.get('returnOnEquity', 0) * 100,
                    "pvp": info.get('priceToBook', 0),
                    "ana": analysis,
                    "news": news,
                    "aid": asset.id
                })
            
            # 3. Mantém seu código de cotações históricas
            df = t.history(period="1d")
            # ... (seu código de insert na market_quotes continua aqui)

        except Exception as e:
            print(f"❌ Erro em {asset.ticker}: {e}")

if __name__ == "__main__":
    run_market_update()
    schedule.every(6).hours.do(run_market_update)
    while True:
        schedule.run_pending()
        time.sleep(60)