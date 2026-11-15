"""Normalized storage: one CSV per product per trading day, outrights and exchange spreads kept separate."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .config import Config

PRICE_FIELDS = ["open", "high", "low", "close", "settle"]
QTY_FIELDS = ["volume", "open_interest"]

SCHEMAS: dict[str, list[str]] = {
    "outrights": ["trade_date", "session", "exchange", "product", "contract_month", "ric",
                  *PRICE_FIELDS, *QTY_FIELDS, "currency", "source", "ingested_at"],
    "spreads":   ["trade_date", "session", "exchange", "product", "structure", "front_month", "legs", "ric",
                  *PRICE_FIELDS, *QTY_FIELDS, "currency", "source", "ingested_at"],
}
KEYS: dict[str, list[str]] = {
    "outrights": ["trade_date", "session", "contract_month"],
    "spreads":   ["trade_date", "session", "structure", "legs"],
}


def day_path(cfg: Config, kind: str, product: str, trade_date: str) -> Path:
    return cfg.data_dir / kind / product / trade_date[:4] / f"{product}_{trade_date}.csv"


def read_file(path: Path, kind: str) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"trade_date": str, "contract_month": str, "front_month": str, "legs": str})
    return df.reindex(columns=SCHEMAS[kind])


def upsert_day(cfg: Config, kind: str, product: str, trade_date: str, rows: pd.DataFrame) -> Path:
    """Merge rows into the day file; re-ingesting the same key overwrites (latest wins)."""
    path = day_path(cfg, kind, product, trade_date)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = rows.reindex(columns=SCHEMAS[kind])
    if path.exists():
        rows = pd.concat([read_file(path, kind), rows], ignore_index=True)
    rows = rows.drop_duplicates(subset=KEYS[kind], keep="last").sort_values(KEYS[kind])
    rows.to_csv(path, index=False, float_format="%.10g")
    return path


def load(cfg: Config, kind: str, product: str | None = None, start: str | None = None,
         end: str | None = None, session: str | None = None) -> pd.DataFrame:
    """Load stored rows. Dates are ISO strings (inclusive bounds)."""
    files = sorted((cfg.data_dir / kind).glob(f"{product or '*'}/*/*.csv"))
    if start or end:
        files = [f for f in files if (not start or f.stem[-10:] >= start) and (not end or f.stem[-10:] <= end)]
    if not files:
        return pd.DataFrame(columns=SCHEMAS[kind])
    df = pd.concat([read_file(f, kind) for f in files], ignore_index=True)
    if session:
        df = df[df["session"] == session]
    return df.reset_index(drop=True)
