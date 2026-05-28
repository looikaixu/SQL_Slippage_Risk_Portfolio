CREATE VIEW v_trade_slippage_risk AS
WITH normalized AS (
    SELECT
        t.trade_id,
        t.executed_at,
        u.user_name,
        u.desk_segment,
        u.country,
        u.usd_exposure_limit,
        b.broker_name,
        b.venue_type,
        b.region AS broker_region,
        b.sla_latency_ms,
        a.asset_class,
        t.symbol,
        t.side,
        t.requested_price,
        t.executed_price,
        t.quantity,
        t.execution_latency_ms,
        a.usd_conversion_rate,
        a.contract_multiplier,
        CASE
            WHEN t.side = 'BUY' THEN t.executed_price - t.requested_price
            ELSE t.requested_price - t.executed_price
        END AS adverse_slippage_points,
        ABS(t.quantity * t.executed_price * a.contract_multiplier * a.usd_conversion_rate) AS total_usd_exposure
    FROM trade_logs t
    JOIN user_profiles u ON u.user_id = t.user_id
    JOIN brokers b ON b.broker_id = t.broker_id
    JOIN asset_rates a ON a.symbol = t.symbol
),
rounded_metrics AS (
    SELECT
        *,
        ROUND(usd_exposure_limit, 2) AS rounded_usd_exposure_limit,
        ROUND(requested_price, 2) AS rounded_requested_price,
        ROUND(executed_price, 2) AS rounded_executed_price,
        ROUND(quantity, 2) AS rounded_quantity,
        ROUND(usd_conversion_rate, 2) AS rounded_usd_conversion_rate,
        ROUND(contract_multiplier, 2) AS rounded_contract_multiplier,
        ROUND(adverse_slippage_points, 2) AS rounded_adverse_slippage_points,
        ROUND(total_usd_exposure, 2) AS rounded_total_usd_exposure
    FROM normalized
)
SELECT
    trade_id,
    executed_at,
    user_name,
    desk_segment,
    country,
    rounded_usd_exposure_limit AS usd_exposure_limit,
    broker_name,
    venue_type,
    broker_region,
    sla_latency_ms,
    asset_class,
    symbol,
    side,
    rounded_requested_price AS requested_price,
    rounded_executed_price AS executed_price,
    rounded_quantity AS quantity,
    execution_latency_ms,
    rounded_usd_conversion_rate AS usd_conversion_rate,
    rounded_contract_multiplier AS contract_multiplier,
    rounded_adverse_slippage_points AS adverse_slippage_points,
    rounded_total_usd_exposure AS total_usd_exposure,
    ROUND((rounded_adverse_slippage_points / NULLIF(rounded_requested_price, 0)) * 10000, 2) AS slippage_bps,
    ROUND(
        rounded_adverse_slippage_points
        * rounded_quantity
        * rounded_contract_multiplier
        * rounded_usd_conversion_rate,
        2
    ) AS usd_slippage_loss,
    CASE
        WHEN total_usd_exposure > usd_exposure_limit THEN 'CRITICAL: LIMIT BREACH'
        WHEN total_usd_exposure > usd_exposure_limit * 0.85 THEN 'WATCHLIST'
        ELSE 'PASS'
    END AS exposure_status,
    CASE
        WHEN execution_latency_ms > sla_latency_ms * 2 THEN 'FAIL'
        WHEN execution_latency_ms > sla_latency_ms THEN 'WARN'
        ELSE 'PASS'
    END AS latency_status,
    CASE
        WHEN rounded_adverse_slippage_points > 0 THEN 'ADVERSE'
        WHEN rounded_adverse_slippage_points < 0 THEN 'PRICE IMPROVEMENT'
        ELSE 'FLAT'
    END AS slippage_direction
FROM rounded_metrics;

CREATE VIEW v_broker_slippage_variance AS
WITH broker_stats AS (
    SELECT
        broker_name,
        asset_class,
        COUNT(*) AS trade_count,
        AVG(slippage_bps) AS avg_slippage_bps,
        AVG(slippage_bps * slippage_bps) - AVG(slippage_bps) * AVG(slippage_bps) AS slippage_variance,
        SUM(usd_slippage_loss) AS total_usd_slippage_loss,
        SUM(total_usd_exposure) AS total_usd_exposure,
        SUM(CASE WHEN exposure_status = 'CRITICAL: LIMIT BREACH' THEN 1 ELSE 0 END) AS limit_breach_count,
        SUM(CASE WHEN latency_status = 'FAIL' THEN 1 ELSE 0 END) AS latency_fail_count
    FROM v_trade_slippage_risk
    GROUP BY broker_name, asset_class
)
SELECT
    broker_name,
    asset_class,
    trade_count,
    ROUND(avg_slippage_bps, 2) AS avg_slippage_bps,
    ROUND(slippage_variance, 2) AS slippage_variance,
    ROUND(total_usd_slippage_loss, 2) AS total_usd_slippage_loss,
    ROUND(total_usd_exposure, 2) AS total_usd_exposure,
    limit_breach_count,
    latency_fail_count,
    CASE
        WHEN limit_breach_count > 0 OR latency_fail_count > 0 OR slippage_variance > 100 THEN 'FAIL'
        WHEN slippage_variance > 35 THEN 'WATCHLIST'
        ELSE 'PASS'
    END AS broker_risk_status
FROM broker_stats;

CREATE VIEW v_user_velocity_loops AS
WITH ordered_trades AS (
    SELECT
        t.user_id,
        u.user_name,
        t.symbol,
        t.trade_id,
        t.executed_at,
        COUNT(*) OVER (
            PARTITION BY t.user_id, t.symbol
            ORDER BY julianday(t.executed_at)
            RANGE BETWEEN (5.00 / 1440.00) PRECEDING AND CURRENT ROW
        ) AS trades_in_prior_5_minutes
    FROM trade_logs t
    JOIN user_profiles u ON u.user_id = t.user_id
)
SELECT
    user_name,
    symbol,
    MAX(trades_in_prior_5_minutes) AS max_trades_in_5_minutes,
    CASE
        WHEN MAX(trades_in_prior_5_minutes) >= 3 THEN 'FAIL'
        WHEN MAX(trades_in_prior_5_minutes) = 2 THEN 'WATCHLIST'
        ELSE 'PASS'
    END AS velocity_status
FROM ordered_trades
GROUP BY user_name, symbol;
