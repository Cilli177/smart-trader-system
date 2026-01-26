import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.getenv("DATABASE_URL")

if not DB_URL:
    print("❌ ERRO: DATABASE_URL não encontrada.")
    exit(1)

print(f"🔌 Conectando ao banco para expandir coluna URL...")
engine = create_engine(DB_URL)

# Comando para alterar o tipo da coluna para TEXT (Ilimitado)
sql_fix = """
ALTER TABLE market_news ALTER COLUMN url TYPE TEXT;
"""

try:
    with engine.begin() as conn:
        conn.execute(text(sql_fix))
    print("✅ Sucesso! Agora a tabela aceita links gigantes.")
except Exception as e:
    print(f"❌ Erro: {e}")