from __future__ import annotations

import sqlite3

from create_database import DB_PATH, build_database


CHECKS = {
    "critical_risk_tape": """
        SELECT COUNT(*)
        FROM v_trade_slippage_risk
        WHERE exposure_status != 'PASS' OR latency_status != 'PASS';
    """,
    "broker_scorecard": """
        SELECT COUNT(*)
        FROM v_broker_slippage_variance
        WHERE broker_risk_status IN ('FAIL', 'WATCHLIST');
    """,
    "velocity_loops": """
        SELECT COUNT(*)
        FROM v_user_velocity_loops
        WHERE velocity_status != 'PASS';
    """,
    "slippage_direction_mismatches": """
        SELECT COUNT(*)
        FROM v_trade_slippage_risk
        WHERE
            (adverse_slippage_points > 0 AND slippage_direction != 'ADVERSE')
            OR (adverse_slippage_points < 0 AND slippage_direction != 'PRICE IMPROVEMENT')
            OR (adverse_slippage_points = 0 AND slippage_direction != 'FLAT');
    """,
    "slippage_bps_mismatches": """
        SELECT COUNT(*)
        FROM v_trade_slippage_risk
        WHERE slippage_bps != ROUND(
            (adverse_slippage_points / NULLIF(requested_price, 0)) * 10000,
            2
        );
    """,
}


def main() -> None:
    build_database()
    with sqlite3.connect(DB_PATH) as conn:
        for name, query in CHECKS.items():
            count = conn.execute(query).fetchone()[0]
            if name.endswith("_mismatches"):
                if count != 0:
                    raise SystemExit(f"Validation failed: {name} returned {count} mismatches.")
                print(f"{name}: 0 mismatches")
            elif count < 1:
                raise SystemExit(f"Validation failed: {name} returned no risk rows.")
            else:
                print(f"{name}: {count} risk rows")


if __name__ == "__main__":
    main()
