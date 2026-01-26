import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.getenv("DATABASE_URL")

if not DB_URL:
    print("❌ ERRO: DATABASE_URL não encontrada.")
    exit(1)

print(f"🔌 Conectando ao banco para criar tabela de Notícias...")
engine = create_engine(DB_URL)

sql_create_news = """
CREATE TABLE IF NOT EXISTS market_news (
    id BIGSERIAL PRIMARY KEY,
    asset_id INTEGER REFERENCES assets(id),
    title VARCHAR(255) NOT NULL,
    url VARCHAR(500) UNIQUE,
    published_at TIMESTAMP,
    source VARCHAR(100),
    
    -- Campos preenchidos pela IA
    sentiment_score DECIMAL(5, 4), -- De -1.0 (Ruim) a +1.0 (Bom)
    sentiment_summary TEXT,        -- A explicação da IA
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index para não buscar notícias velhas toda hora
CREATE INDEX IF NOT EXISTS idx_news_date ON market_news(published_at DESC);
"""

try:
    with engine.begin() as conn:
        conn.execute(text(sql_create_news))
    print("✅ Sucesso! Tabela 'market_news' criada.")
except Exception as e:
    print(f"❌ Erro: {e}")