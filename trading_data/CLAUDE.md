# Trade-idea chat: operating context

The user is a spread trader on **BMD FCPO**, and follows **DCE palm olein (DCE_P)** and **DCE soybean oil (DCE_Y)**.
Structures traded: S1, S2, Butterfly (FLY), Double Butterfly (DFLY), Condor. Roll trades around active-month change.

## Sources
| What | Where |
|---|---|
| Trade ideas, reasoning, mistakes | Notion → `FCPO Trading Journal` → `Daily Log` database (page title `DD MON YYYY`). Related DBs: Weekly Review, Monthly Review, Observation, News. Find via Notion search by title. |
| Prices (Reuters EOD) | `data/outrights/<PRODUCT>/<YYYY>/<PRODUCT>_<YYYY-MM-DD>.csv`, `data/spreads/...` |
| Contract specs / structure weights | `config/products.yaml` |

## How to answer a trade-idea question
1. Pull the journal entry for the date(s) from Notion (Trade Idea Today, Analysis, Trade Today, Discussion & Learning).
2. Pull prices with `pricebook` (run from this folder):
   - `python -m pricebook board FCPO 2026-11-13 --detail`: spread board with source of each price
   - `python -m pricebook roll FCPO [--old 2027-01 --new 2027-02]`: OI ratio across the roll
   - `python -m pricebook coverage`: what dates exist
   - Python: `from pricebook import load_config, load, spread_board, oi_ratio`
3. Test the idea against the data and say what supports or contradicts it. Quote numbers with their `price_source`.

## Rules
- **Price priority:** `EXCHANGE` (actual spread print) > `FROM_S1` (built from exchange S1 prints) > `DERIVED` (from outrights). The user regards outright-derived spreads as inexact; flag every `DERIVED` number.
- **Sign convention:** near minus far. JAN S1 = JAN − FEB; JAN FLY = JAN S1 − FEB S1; JAN DFLY = JAN FLY − FEB FLY; JAN CONDOR = JAN S1 − MAR S1.
- **Listed months:** DCE_Y lists 1,3,5,7,8,9,11,12, so its S1 is Jan–Mar, not Jan–Feb. Structures follow listed-month order.
- **Tick values:** FCPO = 25 t × MYR 1 = MYR 25/tick; DCE_P / DCE_Y = 10 t × CNY 2 = CNY 20/tick (verify in config).
- **Roll heuristic:** OI(new)/OI(old) ≥ 1.5 comes from the user's 13 NOV 2026 note. It is a rule of thumb, not a fact.
- If a date or contract is not in `data/`, say so. Never estimate or fill in prices.
- Data is Reuters-licensed: do not paste bulk price tables into external services.
