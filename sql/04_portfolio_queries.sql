-- Query 1: Executive risk tape with breach and fail flags.
SELECT
    trade_id,
    executed_at,
    user_name,
    broker_name,
    symbol,
    side,
    ROUND(total_usd_exposure, 2) AS total_usd_exposure,
    ROUND(usd_slippage_loss, 2) AS usd_slippage_loss,
    slippage_bps,
    exposure_status,
    latency_status
FROM v_trade_slippage_risk
WHERE exposure_status != 'PASS' OR latency_status != 'PASS'
ORDER BY total_usd_exposure DESC;

-- Query 2: Broker stability score using variance as the core metric.
SELECT
    broker_name,
    asset_class,
    trade_count,
    avg_slippage_bps,
    slippage_variance,
    total_usd_slippage_loss,
    limit_breach_count,
    latency_fail_count,
    broker_risk_status
FROM v_broker_slippage_variance
ORDER BY
    CASE broker_risk_status WHEN 'FAIL' THEN 1 WHEN 'WATCHLIST' THEN 2 ELSE 3 END,
    slippage_variance DESC;

-- Query 3: CTE-driven USD slippage loss leaderboard.
WITH desk_loss AS (
    SELECT
        desk_segment,
        asset_class,
        SUM(usd_slippage_loss) AS usd_slippage_loss,
        SUM(total_usd_exposure) AS total_usd_exposure,
        COUNT(*) AS trade_count
    FROM v_trade_slippage_risk
    GROUP BY desk_segment, asset_class
)
SELECT
    desk_segment,
    asset_class,
    ROUND(usd_slippage_loss, 2) AS usd_slippage_loss,
    ROUND(total_usd_exposure, 2) AS total_usd_exposure,
    ROUND(usd_slippage_loss / NULLIF(total_usd_exposure, 0) * 10000, 2) AS loss_bps_of_exposure,
    trade_count
FROM desk_loss
ORDER BY usd_slippage_loss DESC;

-- Query 4: Window-function signal for high-velocity user loops.
SELECT
    user_name,
    symbol,
    max_trades_in_5_minutes,
    velocity_status
FROM v_user_velocity_loops
WHERE velocity_status != 'PASS'
ORDER BY max_trades_in_5_minutes DESC;
