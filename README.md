# SQL Slippage Risk Analytics Portfolio

An institutional-style SQL and Streamlit project that converts raw trade execution logs into an operational risk dashboard for slippage loss, broker stability, latency failure, and USD exposure breach monitoring.

This project is designed as a portfolio case study for roles such as:

- Risk Analyst
- Trading Operations Analyst
- Data Analyst
- SQL Analyst
- Brokerage / FinTech Operations Analyst
- Platform Risk Analyst

## Executive Summary

Trading platforms route orders through brokers, liquidity providers, crypto exchanges, and internal venues. Even when trades are successfully filled, poor execution quality can create hidden financial leakage through slippage, latency, and oversized exposure.

This project models a practical risk-control workflow:

- Normalize multi-asset trade logs into USD-equivalent exposure.
- Differentiate client-costly negative slippage from client-beneficial positive slippage.
- Measure adverse execution slippage in basis points and dollars.
- Detect exposure limit breaches at user level.
- Identify brokers and liquidity providers with unstable execution quality using slippage variance.
- Flag latency failures against broker service-level agreements.
- Recommend LP routing actions such as `Keep Preferred`, `Monitor / Review SLA`, or `Restrict Routing`.
- Present the result in a live Streamlit dashboard with filtered risk views and exportable investigation tables.

The final output is an analyst-ready dashboard that answers:

```text
Where did execution quality fail?
Which trades caused the largest slippage loss?
Which users breached exposure limits?
Which brokers or LPs should Risk Ops review first?
Which venues should the broker continue routing to, monitor, or restrict?
```

## Business Problem

Execution slippage is the difference between the price a trader expected and the price actually received. For high-volume trading platforms, small price differences can create large losses when multiplied across trade quantity, contract size, and asset conversion rates.

The operational risk is not only the loss from one trade. The deeper risk is whether a broker or routing venue is consistently unstable.

This project focuses on four realistic risk questions:

- **Client versus broker slippage:** Did the trade receive positive slippage that benefits the client, or negative slippage that creates client cost and broker execution-risk exposure?
- **Financial leakage:** Which trades created the highest USD slippage loss?
- **Compliance exposure:** Which users exceeded their approved USD exposure cap?
- **LP performance:** Which liquidity providers or execution venues have high slippage variance, slippage loss, or latency failures?
- **Operational triage:** Which trades should appear first in a risk analyst's investigation queue?

## Solution Overview

The project uses a small relational SQLite database and a Streamlit front end.

The SQL layer performs the core risk logic:

- joins users, brokers, assets, and trade logs
- calculates adverse slippage points
- calculates slippage basis points
- calculates USD slippage loss
- classifies slippage as `ADVERSE`, `PRICE IMPROVEMENT`, or `FLAT`
- calculates total USD exposure
- flags exposure breaches and latency failures
- ranks broker stability using slippage variance
- detects high-velocity trade loops using a window function

The Streamlit layer turns the SQL output into an operational dashboard:

- KPI cards
- executive risk summary
- broker variance chart
- top 5 worst trades chart
- client-costly versus client-beneficial slippage counters
- LP routing recommendation table
- critical risk tape
- filtered full SQL view
- export to Excel-compatible CSV

## Repository Structure

```text
SQL_Slippage_Risk_Portfolio/
    app.py
    requirements.txt
    README.md
    data/
        slippage_risk.db          # generated locally, ignored by git
    docs/
        interview_pitch.md
    scripts/
        create_database.py
        validate_project.py
    screenshots/
        .gitkeep
    sql/
        01_schema.sql
        02_seed_data.sql
        03_risk_views.sql
        04_portfolio_queries.sql
```

## Data Architecture

```text
user_profiles
    user_id PK
    user_name
    desk_segment
    country
    usd_exposure_limit
        |
        | 1-to-many
        v
trade_logs -------------------------------- brokers
    trade_id PK                              broker_id PK
    user_id FK                               broker_name
    broker_id FK                             venue_type
    symbol FK                                region
    side                                     sla_latency_ms
    requested_price
    executed_price
    quantity
    execution_latency_ms
        |
        | many-to-1
        v
asset_rates
    symbol PK
    asset_class
    quote_currency
    usd_conversion_rate
    contract_multiplier
```

The schema is intentionally simple but realistic:

- `user_profiles` defines user segments and USD exposure limits.
- `brokers` defines execution venues and latency SLA thresholds.
- `asset_rates` defines conversion and contract sizing rules.
- `trade_logs` stores the raw execution data used for risk analytics.

## SQL Files

| File | Purpose |
|---|---|
| `sql/01_schema.sql` | Creates normalized relational tables, constraints, foreign keys, and indexes. |
| `sql/02_seed_data.sql` | Inserts realistic demo trades with deliberate breaches, latency failures, and slippage anomalies. |
| `sql/03_risk_views.sql` | Builds reusable SQL views for trade-level risk, broker variance, and velocity-loop detection. |
| `sql/04_portfolio_queries.sql` | Provides recruiter-friendly query examples for screenshots and DBeaver demonstrations. |

## Key Risk Metrics

### 1. Adverse Slippage Points

For `BUY` trades:

```text
executed_price - requested_price
```

For `SELL` trades:

```text
requested_price - executed_price
```

Positive values mean the trade executed worse than expected. Zero means flat execution. Negative values would mean price improvement.

The dashboard translates this into a client-facing direction:

```text
ADVERSE
    negative slippage for the client; execution was worse than requested

PRICE IMPROVEMENT
    positive slippage for the client; execution was better than requested

FLAT
    executed price matched the requested price after 2-decimal rounding
```

This distinction matters in institutional brokerage because positive slippage can be a client-benefit signal, while persistent negative slippage can indicate poor routing, LP degradation, latency, or broker execution-risk exposure.

### 2. Slippage BPS

Slippage BPS standardizes the price difference into basis points:

```text
adverse_slippage_points / requested_price * 10,000
```

This makes slippage comparable across assets with very different price scales, such as EURUSD, BTC-USD, XAUUSD, and NAS100.

### 3. USD Slippage Loss

USD slippage loss converts execution quality into financial impact:

```text
adverse_slippage_points
* quantity
* contract_multiplier
* usd_conversion_rate
```

Example:

```text
BTC requested price: 74,250.00
BTC executed price: 74,540.00
Quantity: 44.00

Adverse slippage = 290.00
USD slippage loss = 290.00 * 44.00 * 1.00 * 1.00
                  = 12,760.00
```

### 4. Total USD Exposure

Total USD exposure standardizes multi-asset trade size into one risk threshold:

```text
ABS(quantity * executed_price * contract_multiplier * usd_conversion_rate)
```

This enables the dashboard to compare FX, crypto, metals, and index CFD trades using one common USD-equivalent exposure number.

### 5. Exposure Status

```text
CRITICAL: LIMIT BREACH
    total_usd_exposure > usd_exposure_limit

WATCHLIST
    total_usd_exposure > usd_exposure_limit * 0.85

PASS
    total_usd_exposure <= usd_exposure_limit * 0.85
```

### 6. Latency Status

```text
FAIL
    execution_latency_ms > sla_latency_ms * 2

WARN
    execution_latency_ms > sla_latency_ms

PASS
    execution_latency_ms <= sla_latency_ms
```

### 7. Broker Slippage Variance

Broker stability is measured using slippage variance:

```text
AVG(slippage_bps * slippage_bps) - AVG(slippage_bps) * AVG(slippage_bps)
```

Average slippage alone can hide instability. A broker with low average slippage but high variance can still create unpredictable routing risk.

### 8. LP Routing Recommendation

The dashboard simulates how an institutional broker might review liquidity-provider performance.

```text
Keep Preferred
    stable execution profile

Monitor / Review SLA
    elevated variance or latency warning/failure

Restrict Routing
    failed broker risk status with material slippage loss, high variance, or latency failure
```

In production, a broker could use this type of SQL output to reduce flow to underperforming venues such as a crypto exchange, prime broker, internalizer, or external liquidity provider.

## Dashboard Features

The Streamlit dashboard includes:

- **Executive Risk Summary:** plain-English risk summary generated from the filtered dataset.
- **Overall Risk Status:** `NORMAL`, `ELEVATED`, or `CRITICAL` based on breaches, latency failures, and slippage loss.
- **KPI Cards:** total USD exposure, total USD slippage loss, limit breaches, and latency failures.
- **Client Slippage Split:** counts trades with client-costly adverse slippage versus client-beneficial price improvement.
- **Broker Variance Chart:** identifies unstable brokers by slippage variance and asset class.
- **Top 5 Worst Trades Chart:** ranks trades by USD slippage loss.
- **Top 5 Worst Trades Table:** shows the exact trades behind the chart.
- **LP Routing Recommendations:** converts broker performance into action labels for routing review.
- **Critical Risk Tape:** investigation table for exposure breaches, watchlist items, latency warnings, and latency failures.
- **Full SQL View:** complete filtered trade-level output with risk metrics in a risk-control sequence.
- **Sidebar Filters:** broker, asset class, exposure status, and latency status.
- **Export to Excel:** downloads the Critical Risk Tape as an Excel-compatible CSV.

## Validation

The project includes a validation script:

```bash
python scripts/validate_project.py
```

It checks that:

- the critical risk tape returns risk rows
- broker scorecard returns risk rows
- velocity loop detection returns risk rows
- slippage direction matches rounded adverse slippage
- slippage BPS matches the displayed rounded calculation

Expected validation output:

```text
critical_risk_tape: 12 risk rows
broker_scorecard: 5 risk rows
velocity_loops: 3 risk rows
slippage_direction_mismatches: 0 mismatches
slippage_bps_mismatches: 0 mismatches
```

## Run Locally

Install dependencies:

```bash
pip install -r requirements.txt
```

Create the SQLite database:

```bash
python scripts/create_database.py
```

Validate the analytical views:

```bash
python scripts/validate_project.py
```

Run the dashboard:

```bash
streamlit run app.py
```

The app automatically builds `data/slippage_risk.db` if the database does not exist.

## Suggested DBeaver Demo Flow

For a hiring manager or interviewer, open the project database in DBeaver and run:

1. `sql/01_schema.sql` to show schema design.
2. `sql/02_seed_data.sql` to show controlled test data.
3. `sql/03_risk_views.sql` to show reusable analytical views.
4. `sql/04_portfolio_queries.sql` to show final evidence queries.

Recommended screenshots:

- entity-style table view of `user_profiles`, `brokers`, `asset_rates`, and `trade_logs`
- `v_trade_slippage_risk` showing `CRITICAL: LIMIT BREACH` and `FAIL`
- `v_broker_slippage_variance` showing broker risk ranking
- LP Routing Recommendations showing which venues to keep, monitor, or restrict
- Streamlit KPI section and Top 5 Worst Trades chart
- Critical Risk Tape with Export to Excel button

## Skills Demonstrated

This project demonstrates:

- relational database design
- primary keys, foreign keys, constraints, and indexes
- SQL joins across users, brokers, assets, and trades
- CTE-driven risk normalization
- financial metric calculation
- basis point analysis
- variance-based broker monitoring
- client-positive versus client-negative slippage classification
- liquidity-provider performance and routing recommendation logic
- window-function trade-loop detection
- compliance-style breach flagging
- Streamlit dashboard development
- Plotly charting
- operational export workflow
- portfolio storytelling for interviews

## Interview Pitch

Use the full STAR answer in [docs/interview_pitch.md](docs/interview_pitch.md).

Short version:

> I built a SQL-driven operational risk dashboard that converts raw trade execution logs into standardized USD slippage loss, exposure breach flags, latency failure signals, client-positive versus client-negative slippage classification, and broker stability scores. The project demonstrates how automated SQL views and dashboarding can help a trading platform identify hidden execution costs, review liquidity-provider performance, restrict underperforming venues, and detect users exceeding approved risk limits.

## Future Enhancements

Potential next upgrades:

- add true `.xlsx` export using `openpyxl`
- add date-range filters for multi-day trade surveillance
- add user-level exposure concentration charts
- connect to PostgreSQL instead of SQLite
- deploy the Streamlit dashboard publicly for portfolio sharing
