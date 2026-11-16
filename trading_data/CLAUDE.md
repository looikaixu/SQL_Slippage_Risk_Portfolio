# Trade-idea chat: operating context

The user is a spread trader on **BMD FCPO**, and follows **DCE palm olein (DCE_P)**, **DCE soybean oil (DCE_Y)** and **DAPO** (DCE palm olein vs FCPO).
Structures traded: S1, S2, Butterfly (FLY), Double Butterfly (DFLY), Condor; DCE main-contract spreads (JAN S4 = Jan − May). Roll trades around the active-month change.

## Sources
| What | Where |
|---|---|
| Trade ideas, reasoning, mistakes | Notion → `FCPO Trading Journal` → `Daily Log` database (page title `DD MON YYYY`). Related: Weekly Review, Monthly Review, Observation, News. Find via Notion search by title. |
| Prices (LSEG EOD) | `data/outrights/`, `data/spreads/`, `data/fx/` (see README coverage table) |
| Provenance and known gaps | `docs/data_audit.md` |
| Specs, structures, tick history | `config/products.yaml` |
| Live dashboard | Claude artifact "DCE Rolling Monitor" (same LSEG data; GitHub is the record) |

## How to answer a trade-idea question
1. Pull the journal entry for the date(s) from Notion (Trade Idea Today, Analysis, Trade Today, Discussion & Learning).
2. Pull prices with `pricebook` (run from this folder):
   - `python -m pricebook board FCPO 2026-11-13 --detail`: spreads with the source of each price
   - `python -m pricebook roll DCE_P` / `roll FCPO`: OI ratio across the roll
   - `python -m pricebook dapo --start 2026-10-01`: DAPO in MYR and USD
   - `python -m pricebook coverage`: what dates exist
   - Python: `from pricebook import load_config, load, spread_board, oi_ratio`; `from pricebook.cross import dapo`
3. Test the idea against the data and say what supports or contradicts it. Quote numbers with their `price_source`.

## Rules
- **Price priority:** `EXCHANGE` > `FROM_S1` > `DERIVED`. The user regards outright-derived spreads as inexact, so flag every `DERIVED` number. **No exchange spread prints are stored yet**, so every spread today is `DERIVED`. Say so.
- **Sign convention:** near minus far. JAN S1 = JAN − FEB; JAN FLY = JAN S1 − FEB S1; JAN DFLY = JAN FLY − FEB FLY; JAN CONDOR = JAN S1 − MAR S1.
- **DCE_P** has only Jan/May/Sep stored. Its tick size changed to 1 CNY from 2026-04-10 (inferred from the data, unconfirmed).
- **DAPO:** DCE leg = max-OI DCE_P contract close × CNYMYR. FCPO leg = 3rd nearest live contract close. USDMYR is implied, not exported.
- **Tick values:** FCPO = 25 t × MYR 1 = MYR 25/tick. DCE_P = 10 t × CNY 1 (from 2026-04-10).
- **Roll heuristic:** OI(new)/OI(old) ≥ 1.5 comes from the user's 13 NOV 2026 note. It is a rule of thumb, not a fact.
- If a date or contract is not in `data/`, say so. Never estimate or fill in prices.
- Data is LSEG-licensed: keep the repo private and don't paste bulk price tables into external services.
