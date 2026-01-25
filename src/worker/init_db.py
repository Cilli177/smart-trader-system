import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Carrega variáveis
load_dotenv()
DB_URL = os.getenv("DATABASE_URL")

if not DB_URL:
    print("❌ ERRO: DATABASE_URL não encontrada.")
    exit(1)

# Caminho do arquivo SQL
sql_file_path = os.path.join("database", "schema.sql")

print(f"🔌 Conectando ao banco...")
engine = create_engine(DB_URL)

try:
    with open(sql_file_path, "r") as file:
        sql_script = file.read()
        
    print(f"🔨 Aplicando schema do arquivo: {sql_file_path}")
    
    with engine.begin() as conn:
        conn.execute(text(sql_script))
        
    print("✅ SUCESSO! Tabelas criadas e dados iniciais inseridos.")

except FileNotFoundError:
    print(f"❌ ERRO: Arquivo '{sql_file_path}' não encontrado.")
except Exception as e:
    print(f"❌ ERRO SQL: {e}")