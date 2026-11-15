# pricebook: FCPO / DCE palm olein / DCE soybean oil price store

Reuters EOD exports are normalized into one CSV per product per day. Exchange-traded spread prices are stored as **first-class data**, separate from outrights, so the spread board never depends on outright leg prices when a real spread print exists.

## Daily workflow
```bash
pip install -r requirements.txt
# 1. drop Reuters export(s) into data/inbox/   (git-ignored)
python -m pricebook ingest data/inbox/*.xlsx      # add --dayfirst for 13/11/2026 dates, --ric X for single-RIC files
# 2. ingest runs validation automatically; fix any ERROR
python -m pricebook board FCPO                    # latest spread board
# 3. commit data/outrights + data/spreads and push; CI re-validates
```
Re-ingesting the same date overwrites by key, so corrections are safe.

## Layout
```
config/products.yaml        contract specs, listed months, structure weights, roll threshold
config/reuters_columns.yaml Reuters header aliases -> canonical fields
data/inbox/                 raw exports (not committed)
data/outrights/<P>/<YYYY>/<P>_<date>.csv
data/spreads/<P>/<YYYY>/<P>_<date>.csv
data/reference/ric_map.csv  explicit RIC -> product / structure / legs overrides
pricebook/                  ingest, validate, structures (board), roll, CLI
```

## Schemas
**outrights**: `trade_date, session, exchange, product, contract_month, ric, open, high, low, close, settle, volume, open_interest, currency, source, ingested_at`
Key: `(trade_date, session, contract_month)`

**spreads** (exchange prints): `trade_date, session, exchange, product, structure, front_month, legs, ric, open, high, low, close, settle, volume, open_interest, currency, source, ingested_at`
Key: `(trade_date, session, structure, legs)`. `legs` = `2027-01|2027-02`.

Products: `FCPO` (BMD, MYR), `DCE_P` (palm olein, CNY), `DCE_Y` (soybean oil, CNY). Contract months are ISO `YYYY-MM` and display as `JAN27`.

## Spread board price priority
| Source | Meaning | Board marker |
|---|---|---|
| `EXCHANGE` | the structure's own exchange print | plain |
| `FROM_S1` | built from exchange S1 prints (JAN FLY = JAN S1 − FEB S1) | `~` |
| `DERIVED` | built from outright prices (fallback, carries leg slippage) | `*` |

`basis = exchange − derived`: the gap between the real spread print and the outright-implied value.

Sign convention: near minus far. Validation fails if stored spread prints look sign-inverted relative to that.

## RIC resolution
1. `data/reference/ric_map.csv` (explicit, wins). Use it for DCE RICs, flies or condors, and any format the parser does not know.
2. Parser: `ROOT + MonthCode + Year[-[ROOT]MonthCode+Year][^decade]`, e.g. `FCPOF7`, `FCPOF7-G7`, `FCPOF3^2`. Roots are in `products.yaml`.
Continuation RICs (`FCPOc1`) are rejected because they change contract over time.

Unresolved RICs stop ingestion with the full list, so nothing is silently dropped.

## First Reuters export checklist
- [ ] Put the exact Reuters header text first in each list in `reuters_columns.yaml`
- [ ] Confirm the FCPO RIC root, then set `ric_roots` for DCE_P / DCE_Y or fill `ric_map.csv`
- [ ] Confirm how the spread RIC is formatted and whether butterfly / condor RICs exist
- [ ] Confirm the spread price sign (validation flags an inversion)
- [ ] Confirm the DCE_Y listed months and the tick sizes in `products.yaml`

## Tests
```bash
python -m pytest -q tests      # synthetic data only
```
