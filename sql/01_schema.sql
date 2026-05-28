PRAGMA foreign_keys = ON;

DROP VIEW IF EXISTS v_trade_slippage_risk;
DROP VIEW IF EXISTS v_broker_slippage_variance;
DROP VIEW IF EXISTS v_user_velocity_loops;

DROP TABLE IF EXISTS trade_logs;
DROP TABLE IF EXISTS asset_rates;
DROP TABLE IF EXISTS brokers;
DROP TABLE IF EXISTS user_profiles;

CREATE TABLE user_profiles (
    user_id INTEGER PRIMARY KEY,
    user_name TEXT NOT NULL,
    desk_segment TEXT NOT NULL CHECK (desk_segment IN ('Retail', 'Professional', 'Institutional')),
    country TEXT NOT NULL,
    usd_exposure_limit DECIMAL(18, 2) NOT NULL,
    is_active INTEGER NOT NULL CHECK (is_active IN (0, 1))
);

CREATE TABLE brokers (
    broker_id INTEGER PRIMARY KEY,
    broker_name TEXT NOT NULL,
    venue_type TEXT NOT NULL CHECK (venue_type IN ('Prime Broker', 'Liquidity Provider', 'Crypto Exchange', 'Internalizer')),
    region TEXT NOT NULL,
    sla_latency_ms INTEGER NOT NULL,
    is_preferred INTEGER NOT NULL CHECK (is_preferred IN (0, 1))
);

CREATE TABLE asset_rates (
    symbol TEXT PRIMARY KEY,
    asset_class TEXT NOT NULL CHECK (asset_class IN ('FX', 'Crypto', 'Metals', 'Index CFD')),
    quote_currency TEXT NOT NULL,
    usd_conversion_rate DECIMAL(18, 2) NOT NULL,
    contract_multiplier DECIMAL(18, 2) NOT NULL
);

CREATE TABLE trade_logs (
    trade_id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    broker_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
    requested_price DECIMAL(18, 2) NOT NULL,
    executed_price DECIMAL(18, 2) NOT NULL,
    quantity DECIMAL(24, 2) NOT NULL,
    execution_latency_ms INTEGER NOT NULL,
    executed_at TIMESTAMP NOT NULL,
    FOREIGN KEY (user_id) REFERENCES user_profiles (user_id),
    FOREIGN KEY (broker_id) REFERENCES brokers (broker_id),
    FOREIGN KEY (symbol) REFERENCES asset_rates (symbol)
);

CREATE INDEX idx_trade_logs_user_time ON trade_logs (user_id, executed_at);
CREATE INDEX idx_trade_logs_broker_symbol ON trade_logs (broker_id, symbol);
CREATE INDEX idx_trade_logs_symbol_time ON trade_logs (symbol, executed_at);
