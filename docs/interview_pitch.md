# Interview Pitch: SQL Slippage Risk Project

## STAR Answer

**Situation:** I wanted to evaluate operational risk and hidden financial leakage caused by execution lag across multiple liquidity providers for high-volatility assets such as crypto, FX, gold, and index CFDs.

**Task:** I needed to build an automated tracking pipeline that standardized price discrepancies, converted them into USD impact, and flagged users or venues breaking risk controls.

**Action:** I designed a relational schema with user profiles, broker metadata, asset conversion rates, and trade logs. Then I wrote SQL views using CTEs, exposure normalization, broker-level variance calculations, and a window-function velocity signal to identify repeated high-risk execution loops.

**Result:** The final dashboard turns raw trade logs into an operational risk tape. It highlights `CRITICAL: LIMIT BREACH` exposure events, `FAIL` latency statuses, unstable broker routing, and total USD slippage loss in one live Streamlit interface.

## One-Minute Version

This project shows that I can move beyond writing isolated SQL queries. I modeled a realistic execution-risk problem, created normalized relational tables, wrote reusable SQL risk views, and exposed the output in a live dashboard. The most important metric is not only the average slippage, but the variance of slippage by broker and asset class, because unstable execution quality creates unpredictable capital leakage.
