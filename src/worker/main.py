import os
import time
import schedule
import yfinance as yf
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from datetime import datetime

# Carrega .env se existir (para teste local)
load_dotenv()

# Pega URL do ambiente (Railway injeta isso automaticamente)
DB_URL = os.getenv("DATABASE_URL")

if not DB_URL:
    print("❌ ERRO: Variável DATABASE_URL não definida!")
    exit(1)

# Engine do banco
engine = create_engine(DB_URL)

def run_market_update():
    print(f"\n--- 🚀 Iniciando Atualização: {datetime.now()} ---")

    # 1. Busca ativos ativos no banco
    try:
        with engine.connect() as conn:
            assets = conn.execute(text("SELECT id, ticker FROM assets WHERE is_active = true")).fetchall()
    except Exception as e:
        print(f"❌ Erro de conexão com Banco: {e}")
        return

    # 2. Loop pelos ativos
    for asset in assets:
        print(f"🔄 Baixando: {asset.ticker}...")
        try:
            # Baixa último mês
            df = yf.download(asset.ticker, period="1mo", interval="1d", auto_adjust=True, progress=False)

            if df.empty:
                print(f"   ⚠️ Sem dados para {asset.ticker}")
                continue

            # Salva no banco
            inserted = 0
            with engine.begin() as conn:
                for index, row in df.iterrows():
                    # Tratamento seguro para extrair valores float do Pandas
                    # (O yfinance às vezes retorna Series, às vezes float direto)
                    def get_val(val):
                        return float(val.iloc[0]) if hasattr(val, 'iloc') else float(val)

                    try:
                        # Monta o Insert
                        sql = text("""
                            INSERT INTO market_quotes 
                            (asset_id, trade_date, open_price, high_price, low_price, close_price, volume)
                            VALUES (:aid, :dt, :op, :hi, :lo, :cl, :vol)
                            ON CONFLICT (asset_id, trade_date) DO NOTHING
                        """)

                        conn.execute(sql, {
                            "aid": asset.id,
                            "dt": index.date(),
                            "op": get_val(row['Open']),
                            "hi": get_val(row['High']),
                            "lo": get_val(row['Low']),
                            "cl": get_val(row['Close']),
                            "vol": int(get_val(row['Volume']))
                        })
                        inserted += 1
                    except Exception as insert_err:
                        # Ignora erros de duplicata se passar pelo filtro
                        pass

            print(f"   ✅ Processado. Registros verificados/inseridos.")

        except Exception as e:
            print(f"   ❌ Falha em {asset.ticker}: {e}")

# --- Execução ---
if __name__ == "__main__":
    # Roda uma vez imediatamente ao iniciar
    run_market_update()

    # Agenda para rodar a cada 6 horas
    schedule.every(6).hours.do(run_market_update)

    print("⏳ Worker em modo de espera (Agendado a cada 6h)...")
    while True:
        schedule.run_pending()
        time.sleep(60)