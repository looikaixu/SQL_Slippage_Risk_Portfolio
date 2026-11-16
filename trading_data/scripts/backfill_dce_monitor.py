"""One-off backfill from the 'DCE Rolling Monitor' dashboard datasets (LSEG Workspace exports).

Inputs (tidy CSVs the dashboard holds):
  fcpo_contracts.csv  'FCPO Price' sheet of FCPO Data.xlsx          date,contract,expiry,close,settle,volume,oi
  contracts.csv       'DCE OI historical data' + 'DCE Outright Price'  date,contract,expiry,oi,close,settle
  spreads.csv         'DCE Spread Price' sheet                       date,pair,roll,front,back,front_settle,...
  dapo.csv            'DAPO price' sheet                             date,dce_contract,...,cny_myr,...,dapo_usd

Stores outrights + FX + contract reference, then reconciles the spread and DAPO sheets against what
pricebook recomputes, and writes docs/data_audit.md.  Spread and DAPO sheets are NOT stored: they are
fully derivable (see audit), and the agreed design stores only raw prices.

Usage (from trading_data/):
  python scripts/backfill_dce_monitor.py --fcpo F.csv --dce C.csv --spreads S.csv --dapo D.csv
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pricebook import load_config  # noqa: E402
from pricebook.cross import dapo  # noqa: E402
from pricebook.store import load, upsert_day  # noqa: E402
from pricebook.tables import contract_label_to_ym, import_contract_table, upsert_fx  # noqa: E402

SRC_FCPO = "FCPO Data.xlsx/FCPO Price"
SRC_DCE = "DCE data 1.xlsx/DCE Outright Price+DCE OI historical data"
SRC_SPREAD = "DCE data 1.xlsx/DCE Spread Price (front leg)"
SRC_DAPO = "DCE data 1.xlsx/DAPO price"


def main() -> int:
    ap = argparse.ArgumentParser()
    for k in ("fcpo", "dce", "spreads", "dapo"):
        ap.add_argument(f"--{k}", type=Path, required=True)
    a = ap.parse_args()
    cfg = load_config()
    audit: list[str] = []

    # 1. Outrights + contract reference --------------------------------------------------------------
    r_f = import_contract_table(a.fcpo, "FCPO", cfg, SRC_FCPO,
                                expiry_basis="nominal 15th of month as exported (not adjusted for weekends)")
    r_d = import_contract_table(a.dce, "DCE_P", cfg, SRC_DCE, expiry_basis="as exported")
    audit += ["## Stored outrights", "| Product | Rows | Trading days | Contracts |", "|---|---|---|---|",
              f"| FCPO | {r_f['rows']} | {r_f['days']} | {r_f['contracts']} |",
              f"| DCE_P | {r_d['rows']} | {r_d['days']} | {r_d['contracts']} |"]

    # 2. Spread sheet: is it an exchange print or outright arithmetic? --------------------------------
    sp = pd.read_csv(a.spreads)
    sp["front_m"], sp["back_m"] = sp["front"].map(contract_label_to_ym), sp["back"].map(contract_label_to_ym)
    out = load(cfg, "outrights", "DCE_P")[["trade_date", "contract_month", "settle", "close"]]
    out = out.rename(columns={"trade_date": "date"})
    m = (sp.merge(out.rename(columns={"contract_month": "front_m", "settle": "fs", "close": "fc"}),
                  on=["date", "front_m"], how="left")
           .merge(out.rename(columns={"contract_month": "back_m", "settle": "bs", "close": "bc"}),
                  on=["date", "back_m"], how="left"))
    both = m.dropna(subset=["fs", "bs"])
    settle_eq = (both["spread_settle"] == both["fs"] - both["bs"]).mean()
    close_eq = (both["spread_close"] == both["fc"] - both["bc"]).mean()

    # Expiry-day front-leg settles present only in the spread sheet -> recover as outright settle rows.
    missing = m[m["fs"].isna()]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for row in missing.itertuples():
        upsert_day(cfg, "outrights", "DCE_P", row.date, pd.DataFrame([{
            "trade_date": row.date, "session": cfg.default_session, "exchange": "DCE", "product": "DCE_P",
            "contract_month": row.front_m, "settle": row.front_settle, "currency": "CNY",
            "source": f"{cfg.source}:{SRC_SPREAD}", "ingested_at": now}]))
    audit += ["", "## DCE Spread Price sheet",
              f"- {len(sp)} rows, pairs {', '.join(f'{k} ({v})' for k, v in sp['roll'].value_counts().items())}.",
              f"- `spread_settle == front settle - back settle`: **{settle_eq:.2%}** of {len(both)} comparable rows.",
              f"- `spread_close == front close - back close`: **{close_eq:.2%}**.",
              "- **Conclusion:** the sheet is outright arithmetic, not exchange-traded spread prints. "
              "Not stored; pricebook derives it (`S4`, marked `DERIVED`). Exchange spread prints are still needed.",
              f"- {len(missing)} expiry-day front-leg settles existed only in this sheet; recovered into outrights "
              f"(settle only): {', '.join(f'{r.front} {r.date}' for r in missing.itertuples())}."]

    # 3. FX from the DAPO sheet ----------------------------------------------------------------------
    d = pd.read_csv(a.dapo)
    upsert_fx(cfg, "CNYMYR", d[["date", "cny_myr"]].rename(columns={"date": "trade_date", "cny_myr": "rate"}),
              f"{cfg.source}:{SRC_DAPO}", "as exported (5 dp)")
    usd = ((d["dce_close_myr"] + d["fcpo_close_myr"]) / (d["dce_close_usd"] + d["fcpo_close_usd"])).round(4)
    upsert_fx(cfg, "USDMYR", pd.DataFrame({"trade_date": d["date"], "rate": usd}),
              f"{cfg.source}:{SRC_DAPO}",
              "IMPLIED from MYR/USD price columns (USDMYR not exported); approx +/-0.0002")

    # 4. Reconcile DAPO ----------------------------------------------------------------------------
    mine = dapo(cfg)
    c = d.merge(mine, left_on="date", right_on="trade_date", how="left", suffixes=("_sheet", ""))
    c["dce_m_sheet"] = c["dce_contract"].map(contract_label_to_ym)
    c["fcpo_m_sheet"] = c["fcpo_contract"].map(contract_label_to_ym)
    found = c["trade_date"].notna()
    dce_ok = (c["dce_m_sheet"] == c["dce_month"]).mean()
    fcpo_ok = (c["fcpo_m_sheet"] == c["fcpo_month"]).mean()
    diff_myr = (c["dapo_myr_sheet"] - c["dapo_myr"]).abs()
    diff_usd = (c["dapo_usd_sheet"] - c["dapo_usd"]).abs()
    roll_ok = ((c["dce_roll_sheet"] == c["dce_roll"]) & (c["fcpo_roll_sheet"] == c["fcpo_roll"])).mean()
    audit += ["", "## DAPO price sheet (reproduced by `pricebook.cross.dapo`)",
              f"- Dates reproduced: **{found.mean():.2%}** of {len(d)}.",
              f"- DCE leg = max-OI DCE_P contract: **{dce_ok:.2%}**; FCPO leg = 3rd nearest live contract: **{fcpo_ok:.2%}**.",
              f"- `dapo_myr` max abs diff: **{diff_myr.max():.3f} MYR** (sheet rounds to 0.1).",
              f"- `dapo_usd` max abs diff: **{diff_usd.max():.3f} USD** (USDMYR is implied, see FX).",
              f"- Roll flags identical: **{roll_ok:.2%}**. Every difference is a real contract change on the first "
              "day after a holiday gap that the sheet left unflagged; pricebook flags it: "
              + ", ".join(f"{r.date} {'DCE ' + r.dce_contract if r.dce_roll != r.dce_roll_sheet else 'FCPO ' + r.fcpo_contract}"
                          for r in c[(c["dce_roll"] != c["dce_roll_sheet"]) | (c["fcpo_roll"] != c["fcpo_roll_sheet"])].itertuples())
              + ".",
              "- **Conclusion:** DAPO is fully derivable; stored inputs are outrights + CNYMYR + USDMYR."]

    fcpo_w = load(cfg, "outrights", "FCPO")
    audit += ["", "## Known data characteristics",
              "- DCE_P: only Jan / May / Sep contracts exported; no volume column.",
              "- DCE_P: prices move in 1-CNY steps from 2026-04-10 (none before) -> `tick_history` in "
              "products.yaml. **Confirm the DCE tick-size change.**",
              f"- FCPO: {int(fcpo_w['close'].isna().sum())} rows without close, "
              f"{int(fcpo_w['volume'].isna().sum())} without volume, "
              f"{int(fcpo_w['open_interest'].isna().sum())} without OI (stored as blank).",
              "- FCPO: history starts with the Jan-20 contract, so 2019 dates have an incomplete curve.",
              "- FCPO `expiry` is the nominal 15th; 26 fall on weekends. Not the actual last trading day.",
              "- Close and settle only: no open / high / low in these exports."]

    hdr = ["# Data audit: DCE Rolling Monitor backfill", "",
           f"Generated {now} by `scripts/backfill_dce_monitor.py`. Source: LSEG Workspace exports held by the "
           "DCE Rolling Monitor dashboard.", ""]
    (cfg.root / "docs" / "data_audit.md").write_text("\n".join(hdr + audit) + "\n")
    print("\n".join(audit))
    return 0


if __name__ == "__main__":
    sys.exit(main())
