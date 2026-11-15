"""Roll monitoring: open-interest ratio between the new and old active month."""
from __future__ import annotations

import pandas as pd

from .config import Config
from .store import load


def active_pair(outrights: pd.DataFrame) -> tuple[str, str]:
    """(old_active, new_active) = the two highest-OI months on the latest date, ordered by month."""
    last = outrights[outrights["trade_date"] == outrights["trade_date"].max()].dropna(subset=["open_interest"])
    if len(last) < 2:
        raise ValueError("Need open_interest for at least two months on the latest date")
    top2 = sorted(last.nlargest(2, "open_interest")["contract_month"])
    return top2[0], top2[1]


def oi_ratio(cfg: Config, product: str, old: str | None = None, new: str | None = None,
             start: str | None = None, end: str | None = None, session: str | None = None) -> pd.DataFrame:
    df = load(cfg, "outrights", product, start, end, session or cfg.default_session)
    if df.empty:
        raise ValueError(f"No outright data for {product}")
    if not (old and new):
        old, new = active_pair(df)
    oi = df.pivot_table(index="trade_date", columns="contract_month", values="open_interest", aggfunc="last")
    missing = [m for m in (old, new) if m not in oi.columns]
    if missing:
        raise ValueError(f"No open_interest stored for {missing}")
    out = pd.DataFrame({"oi_old": oi[old], "oi_new": oi[new]})
    out["ratio"] = out["oi_new"] / out["oi_old"]
    out["oi_old_chg"] = out["oi_old"].diff()
    out["oi_new_chg"] = out["oi_new"].diff()
    out["roll_done"] = out["ratio"] >= cfg.oi_ratio_threshold
    out.attrs.update(old=old, new=new, threshold=cfg.oi_ratio_threshold)
    return out
