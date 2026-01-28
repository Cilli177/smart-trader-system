-- Mantendo suas tabelas existentes e adicionando os campos de IA e Fundamentos
CREATE TABLE IF NOT EXISTS sectors (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS assets (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(100),
    sector_id INTEGER REFERENCES sectors(id),
    is_active BOOLEAN DEFAULT TRUE,
    
    -- NOVOS CAMPOS PARA FUNDAMENTOS E IA
    price DECIMAL(18, 2) DEFAULT 0,
    pe_ratio DECIMAL(10, 2) DEFAULT 0,       -- P/L
    dy_percentage DECIMAL(10, 2) DEFAULT 0,  -- Dividend Yield
    roe_percentage DECIMAL(10, 2) DEFAULT 0, -- ROE
    p_vp DECIMAL(10, 2) DEFAULT 0,           -- P/VP
    ai_analysis TEXT,                        -- Análise Fundamentalista (Gemini)
    news_summary TEXT,                       -- Resumo de Notícias (Perplexity)
    news_links JSONB,                        -- Links das fontes
    sentiment VARCHAR(20) DEFAULT 'Neutro',
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS market_quotes (
    id BIGSERIAL PRIMARY KEY,
    asset_id INTEGER NOT NULL REFERENCES assets(id),
    trade_date DATE NOT NULL,
    open_price DECIMAL(18, 4),
    high_price DECIMAL(18, 4),
    low_price DECIMAL(18, 4),
    close_price DECIMAL(18, 4),
    volume BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_market_quote UNIQUE (asset_id, trade_date)
);

-- Carga Inicial (Seed)
INSERT INTO sectors (name) VALUES ('Petroleo e Gas'), ('Mineracao'), ('Varejo') ON CONFLICT DO NOTHING;
INSERT INTO assets (ticker, name, sector_id) VALUES 
('PETR4.SA', 'Petrobras', 1),
('VALE3.SA', 'Vale', 2),
('MGLU3.SA', 'Magalu', 3)
ON CONFLICT DO NOTHING;