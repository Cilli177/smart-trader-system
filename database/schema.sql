-- Tabela de Setores
CREATE TABLE IF NOT EXISTS sectors (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE
);

-- Tabela de Ativos
CREATE TABLE IF NOT EXISTS assets (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(100),
    sector_id INTEGER REFERENCES sectors(id),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabela de Cotações (Séries Temporais)
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