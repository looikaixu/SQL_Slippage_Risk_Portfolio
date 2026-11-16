# pricebook: FCPO / DCE palm olein / DCE soybean oil price store

LSEG (Reuters) EOD prices normalized into **one CSV per product per trading day**. Raw prices are stored; every spread, fly, condor and DAPO value is computed in code. Exchange-traded spread prints are stored separately and always take priority over computed values.

## Coverage
| Dataset | Product | From | To | Notes |
|---|---|---|---|---|
| Outrights | `FCPO` | 2019-01-16 | 2026-11-13 | 95 contracts (Jan-20 to Nov-27); close, settle, volume, OI |
| Outrights | `DCE_P` palm olein | 2019-01-16 | 2026-11-13 | Jan / May / Sep only; close, settle, OI (no volume) |
| FX | `CNYMYR` | 2020-01-02 | 2026-11-13 | as exported (5 dp) |
| FX | `USDMYR` | 2020-01-02 | 2026-11-13 | **implied** (not exported), approx. ±0.0002 |
| Exchange spreads | none | | | Still needed: the LSEG spread sheet is outright arithmetic (see audit) |
| Outrights | `DCE_Y` soybean oil | none | | Not exported yet |

Source and reconciliation: [`docs/data_audit.md`](docs/data_audit.md). Run `python -m pricebook coverage` for the current state.

## Commands (run from `trading_data/`)
```bash
pip install -r requirements.txt
python -m pricebook coverage                      # what is stored
python -m pricebook board FCPO [2026-11-13]       # spread board (latest date by default)
python -m pricebook board DCE_P --detail          # long table: exchange / from_s1 / derived / basis
python -m pricebook roll DCE_P [--old 2027-01 --new 2027-05] [--start 2026-10-01]
python -m pricebook dapo --tail 20                # DCE active (MYR) - FCPO 3rd month, MYR and USD
python -m pricebook validate                      # data-quality gate (CI runs it on every push)
```

## Adding new data
| Export shape | Command |
|---|---|
| Reuters RIC export (`FCPOF7`, `FCPOF7-G7`, ...), xlsx/csv | `python -m pricebook ingest data/inbox/<file>` (`--dayfirst`, `--ric`) |
| Tidy LSEG table `date,contract(Jan-27),close,settle,volume,oi,expiry` | `python -m pricebook import-table <file> --product DCE_P --source-note "DCE data 1.xlsx/DCE Outright Price"` |

Re-importing a date overwrites by key, so corrections are safe. Put raw exports in `data/inbox/`, which is never committed.

## Layout
```
config/products.yaml          specs, listed months, tick history, structures per product, roll threshold
config/reuters_columns.yaml   Reuters header aliases
data/outrights/<P>/<YYYY>/<P>_<date>.csv
data/spreads/<P>/<YYYY>/<P>_<date>.csv       exchange spread prints only
data/fx/<PAIR>/<PAIR>_<YYYY>.csv
data/reference/contracts.csv  product, contract_month, expiry, expiry_basis
data/reference/ric_map.csv    explicit RIC overrides
docs/data_audit.md            provenance + reconciliation of the backfill
pricebook/                    library + CLI
scripts/backfill_dce_monitor.py   one-off import from the DCE Rolling Monitor datasets
```

## Schemas
**outrights**: `trade_date, session, exchange, product, contract_month, ric, open, high, low, close, settle, volume, open_interest, currency, source, ingested_at`. Key `(trade_date, session, contract_month)`.

**spreads**: same, with `structure, front_month, legs` in place of `contract_month`. Key `(trade_date, session, structure, legs)`; `legs` = `2027-01|2027-05`.

**fx**: `trade_date, pair, rate, source, note`. `rate` = MYR per 1 unit of the base currency.

`source` records the workbook and sheet, e.g. `REUTERS:DCE data 1.xlsx/DCE Outright Price+DCE OI historical data`.

## Conventions
- Contract months are ISO `YYYY-MM` and display as `JAN27`.
- Sign is near minus far. FCPO: JAN S1 = JAN − FEB; FLY = S1(m) − S1(m+1); DFLY = FLY(m) − FLY(m+1); CONDOR = S1(m) − S1(m+2).
- DCE_P works on main contracts: JAN S4 = Jan − May, MAY S4 = May − Sep, SEP S4 = Sep − next Jan.
- Spread board price priority: `EXCHANGE` (plain) > `FROM_S1` built from exchange S1 prints (`~`) > `DERIVED` from outrights (`*`).
- **DAPO** = DCE_P max-OI contract close × CNYMYR − FCPO 3rd nearest live contract close. USD = ÷ USDMYR. `*_roll` = 1 when the chosen contract changes.
- Roll monitor: OI(new)/OI(old), with the journal heuristic of 1.5 = roll done.

## Still to confirm
- [ ] DCE palm olein tick size went from 2 to 1 CNY around 2026-04-10. Prices first move in 1-CNY steps that day, and `tick_history` assumes the change.
- [ ] Export the **exchange spread prices** (DCE Jan-May / May-Sep / Sep-Jan; FCPO S1 / fly / condor). The current sheet is computed from outrights.
- [ ] Export `USDMYR` from LSEG so the stored rate isn't implied.
- [ ] Export DCE soybean oil, and check its listed months and structures in `products.yaml`.
- [ ] Confirm the RIC formats for `ingest`.

## Tests
```bash
python -m pytest -q tests      # synthetic data only
```
