"""Cross-market: DAPO = DCE palm olein active month (in MYR) - FCPO 3rd month.

Rules reproduced from the DCE Rolling Monitor 'DAPO price' sheet:
  * DCE leg  = DCE_P contract with the highest open interest that day, close price, x CNYMYR
  * FCPO leg = 3rd nearest live FCPO contract that day, close price
  * USD view = both legs / USDMYR
  * *_roll   = 1 on the day the chosen contract changes
Only dates where both markets have a price and CNYMYR exists are returned.
"""
from __future__ import annotations

import pandas as pd

from .config import Config, month_label
from .store import load
from .tables import load_fx


def _dce_active(dce: pd.DataFrame) -> pd.DataFrame:
    d = dce.dropna(subset=["open_interest", "close"])
    idx = d.groupby("trade_date")["open_interest"].idxmax()
    return d.loc[idx, ["trade_date", "contract_month", "open_interest", "close"]].rename(
        columns={"contract_month": "dce_month", "open_interest": "dce_oi", "close": "dce_close_cny"})


def _fcpo_nth(fcpo: pd.DataFrame, n: int = 3) -> pd.DataFrame:
    f = fcpo.sort_values(["trade_date", "contract_month"])
    f = f.assign(rank=f.groupby("trade_date").cumcount() + 1)
    f = f[(f["rank"] == n) & f["close"].notna()]
    return f[["trade_date", "contract_month", "close"]].rename(
        columns={"contract_month": "fcpo_month", "close": "fcpo_close_myr"})


def dapo(cfg: Config, start: str | None = None, end: str | None = None, fcpo_rank: int = 3) -> pd.DataFrame:
    dce = load(cfg, "outrights", "DCE_P", start, end, cfg.default_session)
    fcpo = load(cfg, "outrights", "FCPO", start, end, cfg.default_session)
    out = _dce_active(dce).merge(_fcpo_nth(fcpo, fcpo_rank), on="trade_date", how="inner")

    cny = load_fx(cfg, "CNYMYR").rename("cny_myr")
    out = out.merge(cny, left_on="trade_date", right_index=True, how="inner")
    out["dce_close_myr"] = out["dce_close_cny"] * out["cny_myr"]
    out["dapo_myr"] = out["dce_close_myr"] - out["fcpo_close_myr"]

    try:
        usd = load_fx(cfg, "USDMYR").rename("usd_myr")
        out = out.merge(usd, left_on="trade_date", right_index=True, how="left")
        out["dapo_usd"] = out["dapo_myr"] / out["usd_myr"]
    except FileNotFoundError:
        pass

    out = out.sort_values("trade_date").reset_index(drop=True)
    out["dce_roll"] = (out["dce_month"] != out["dce_month"].shift()).astype(int)
    out["fcpo_roll"] = (out["fcpo_month"] != out["fcpo_month"].shift()).astype(int)
    out.loc[0, ["dce_roll", "fcpo_roll"]] = 0
    out["dce_label"] = out["dce_month"].map(month_label)
    out["fcpo_label"] = out["fcpo_month"].map(month_label)
    return out
