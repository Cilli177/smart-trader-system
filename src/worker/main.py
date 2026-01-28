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

# Carrega variáveis
load_dotenv()
DB_URL = os.getenv("DATABASE_URL")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
PERPLEXITY_KEY = os.getenv("PERPLEXITY_API_KEY")

# Configura IA
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

# Conexão Banco
if not DB_URL:
    print("❌ ERRO: DATABASE_URL não definida!")
    exit(1)

engine = create_engine(DB_URL)

def ensure_schema():
    """CORREÇÃO AUTOMÁTICA DO BANCO: Garante que as colunas existam"""
    print("🔧 Verificando schema do banco de dados...")
    with engine.begin() as conn:
        # Tenta adicionar as colunas. Se já existirem, o banco ignora o erro ou usamos IF NOT EXISTS
        try:
            conn.execute(text("ALTER TABLE assets ADD COLUMN IF NOT EXISTS price DECIMAL(18, 2) DEFAULT 0;"))
            conn.execute(text("ALTER TABLE assets ADD COLUMN IF NOT EXISTS pe_ratio DECIMAL(10, 2) DEFAULT 0;"))
            conn.execute(text("ALTER TABLE assets ADD COLUMN IF NOT EXISTS dy_percentage DECIMAL(10, 2) DEFAULT 0;"))
            conn.execute(text("ALTER TABLE assets ADD COLUMN IF NOT EXISTS roe_percentage DECIMAL(10, 2) DEFAULT 0;"))
            conn.execute(text("ALTER TABLE assets ADD COLUMN IF NOT EXISTS p_vp DECIMAL(10, 2) DEFAULT 0;"))
            conn.execute(text("ALTER TABLE assets ADD COLUMN IF NOT EXISTS ai_analysis TEXT;"))
            conn.execute(text("ALTER TABLE assets ADD COLUMN IF NOT EXISTS news_summary TEXT;"))
            conn.execute(text("ALTER TABLE assets ADD COLUMN IF NOT EXISTS last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP;"))
            print("✅ Schema verificado/corrigido com sucesso!")
        except Exception as e:
            print(f"⚠️ Aviso na verificação do schema: {e}")

def get_ai_analysis(ticker, info):
    """Gera análise via Gemini com tratamento de erro"""
    if not GEMINI_KEY: return "Chave Gemini não configurada."
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""
        Analise a ação {ticker} (B3 Brasil).
        Dados: P/L: {info.get('trailingPE', 'N/A')}, DY: {info.get('dividendYield', 0)*100 if info.get('dividendYield') else 0}%.
        Responda em 1 parágrafo curto: Vale a pena? Qual o risco?
        """
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"⚠️ Erro Gemini: {e}")
        return "Análise indisponível no momento."

def get_news_from_perplexity(ticker):
    """Busca notícias via Perplexity"""
    if not PERPLEXITY_KEY: return "Sem chave de notícias."
    
    url = "https://api.perplexity.ai/chat/completions"
    payload = {
        "model": "llama-3.1-sonar-small-128k-online", # Modelo atualizado
        "messages": [{"role": "user", "content": f"Resumo muito breve (2 frases) das últimas notícias de {ticker}."}]
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
    """Garante que o ticker tenha .SA se for brasileiro"""
    ticker = ticker.upper().strip()
    if not ticker.endswith(".SA") and len(ticker) <= 6: # Ex: PETR4 -> PETR4.SA
        return ticker + ".SA"
    return ticker

def run_market_update():
    print(f"\n--- 🚀 Iniciando Atualização: {datetime.now()} ---")
    
    # 1. Busca ativos ativos
    try:
        with engine.connect() as conn:
            assets = conn.execute(text("SELECT id, ticker FROM assets")).fetchall()
    except Exception as e:
        print(f"❌ Erro ao conectar no banco: {e}")
        return

    for asset in assets:
        real_ticker = fix_ticker(asset.ticker)
        print(f"🔄 Analisando: {real_ticker}...")
        
        try:
            # Baixa dados do Yahoo Finance
            t = yf.Ticker(real_ticker)
            info = t.info
            
            # Se não achou preço, pula
            current_price = info.get('currentPrice') or info.get('regularMarketPrice')
            if not current_price:
                print(f"   ⚠️ Preço não encontrado para {real_ticker}")
                continue

            # Inteligência
            analysis = get_ai_analysis(real_ticker, info)
            news = get_news_from_perplexity(real_ticker)
            
            # Atualiza no Banco
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
            print(f"   ✅ {real_ticker} atualizado: R$ {current_price}")
            
        except Exception as e:
            print(f"   ❌ Falha em {real_ticker}: {e}")

if __name__ == "__main__":
    # Garante o banco na inicialização
    ensure_schema()
    
    # Roda a primeira vez
    run_market_update()
    
    # Agenda
    schedule.every(6).hours.do(run_market_update)
    print("⏳ Worker em modo de espera...")
    while True:
        schedule.run_pending()
        time.sleep(60)