INSERT INTO user_profiles (user_id, user_name, desk_segment, country, usd_exposure_limit, is_active) VALUES
    (101, 'Avery Tan', 'Professional', 'Malaysia', 750000.00, 1),
    (102, 'Northstar Macro Fund', 'Institutional', 'Singapore', 5000000.00, 1),
    (103, 'Helios Digital Assets LP', 'Institutional', 'United States', 3500000.00, 1),
    (104, 'Maya Rodriguez', 'Retail', 'Mexico', 250000.00, 1),
    (105, 'Sakura Pension Mandate', 'Institutional', 'Japan', 2000000.00, 1);

INSERT INTO brokers (broker_id, broker_name, venue_type, region, sla_latency_ms, is_preferred) VALUES
    (1, 'LP-Alpha', 'Liquidity Provider', 'London', 120, 1),
    (2, 'PB-Nova', 'Prime Broker', 'New York', 180, 1),
    (3, 'CEX-Orion', 'Crypto Exchange', 'Singapore', 250, 0),
    (4, 'Internal-B-Book', 'Internalizer', 'Global', 80, 0);

INSERT INTO asset_rates (symbol, asset_class, quote_currency, usd_conversion_rate, contract_multiplier) VALUES
    ('EURUSD', 'FX', 'USD', 1.00, 1.00),
    ('GBPUSD', 'FX', 'USD', 1.00, 1.00),
    ('USDJPY', 'FX', 'JPY', 0.01, 1.00),
    ('XAUUSD', 'Metals', 'USD', 1.00, 100.00),
    ('BTC-USD', 'Crypto', 'USD', 1.00, 1.00),
    ('ETH-USD', 'Crypto', 'USD', 1.00, 1.00),
    ('NAS100', 'Index CFD', 'USD', 1.00, 20.00);

INSERT INTO trade_logs (
    trade_id, user_id, broker_id, symbol, side, requested_price, executed_price,
    quantity, execution_latency_ms, executed_at
) VALUES
    (9001, 101, 1, 'EURUSD', 'BUY', 1.09, 1.09, 220000.00, 95, '2026-05-25T09:31:10Z'),
    (9002, 101, 1, 'EURUSD', 'SELL', 1.09, 1.09, 180000.00, 110, '2026-05-25T09:33:48Z'),
    (9003, 101, 4, 'XAUUSD', 'BUY', 2441.20, 2443.65, 35.00, 340, '2026-05-25T09:38:05Z'),
    (9004, 102, 2, 'NAS100', 'BUY', 18840.50, 18844.10, 18.00, 170, '2026-05-25T09:42:22Z'),
    (9005, 102, 1, 'USDJPY', 'SELL', 156.21, 156.16, 1600000.00, 145, '2026-05-25T09:47:39Z'),
    (9006, 102, 2, 'GBPUSD', 'BUY', 1.28, 1.28, 1250000.00, 190, '2026-05-25T09:55:12Z'),
    (9007, 103, 3, 'BTC-USD', 'BUY', 74250.00, 74540.00, 44.00, 620, '2026-05-25T10:03:44Z'),
    (9008, 103, 3, 'ETH-USD', 'BUY', 3865.00, 3881.50, 920.00, 510, '2026-05-25T10:05:16Z'),
    (9009, 103, 3, 'BTC-USD', 'SELL', 74610.00, 74420.00, 12.00, 590, '2026-05-25T10:06:59Z'),
    (9010, 104, 4, 'BTC-USD', 'BUY', 74310.00, 74790.00, 4.20, 710, '2026-05-25T10:12:01Z'),
    (9011, 104, 4, 'BTC-USD', 'BUY', 74680.00, 75120.00, 3.90, 780, '2026-05-25T10:13:14Z'),
    (9012, 104, 4, 'ETH-USD', 'BUY', 3872.00, 3908.00, 80.00, 660, '2026-05-25T10:14:03Z'),
    (9013, 105, 2, 'XAUUSD', 'SELL', 2446.00, 2444.10, 55.00, 205, '2026-05-25T10:21:17Z'),
    (9014, 105, 1, 'EURUSD', 'BUY', 1.09, 1.09, 850000.00, 115, '2026-05-25T10:24:33Z'),
    (9015, 105, 3, 'ETH-USD', 'SELL', 3895.00, 3879.00, 430.00, 470, '2026-05-25T10:27:58Z');
