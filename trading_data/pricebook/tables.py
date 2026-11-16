"""Import tidy LSEG workbook tables (contract labelled 'Jan-27') and FX series."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .config import Config
from .store import upsert_day

CONTRACT_REF_COLS = ["product", "contract_month", "expiry", "expiry_basis"]
FX_COLS = ["trade_date", "pair", "rate", "source", "note"]


def contract_label_to_ym(label: str) -> str:
    """'Jan-27' -> '2027-01'."""
    return pd.to_datetime(label, format="%b-%y").strftime("%Y-%m")


def import_contract_table(path: Path | str, product: str, cfg: Config, source_note: str,
                          expiry_basis: str = "as exported") -> dict[str, int]:
    """Columns: date, contract, close?, settle?, volume?, oi?, expiry?  -> data/outrights + reference/contracts.csv."""
    prod = cfg.product(product)
    df = pd.read_csv(path)
    if not {"date", "contract"} <= set(df.columns):
        raise ValueError(f"{path}: needs 'date' and 'contract' columns, got {list(df.columns)}")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out = pd.DataFrame({
        "trade_date": pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d"),
        "session": cfg.default_session,
        "exchange": prod.exchange,
        "product": product,
        "contract_month": df["contract"].map(contract_label_to_ym),
        "ric": pd.NA,
        "close": df.get("close"),
        "settle": df.get("settle"),
        "volume": df.get("volume"),
        "open_interest": df.get("oi", df.get("open_interest")),
        "currency": prod.currency,
        "source": f"{cfg.source}:{source_note}",
        "ingested_at": now,
    })
    for td, rows in out.groupby("trade_date"):
        upsert_day(cfg, "outrights", product, td, rows)

    if "expiry" in df.columns:
        ref = (df[["contract", "expiry"]].drop_duplicates("contract")
               .assign(product=product, contract_month=lambda x: x["contract"].map(contract_label_to_ym),
                       expiry_basis=expiry_basis))
        upsert_contract_ref(cfg, ref[CONTRACT_REF_COLS])
    return {"rows": len(out), "days": out["trade_date"].nunique(), "contracts": out["contract_month"].nunique()}


def upsert_contract_ref(cfg: Config, rows: pd.DataFrame) -> Path:
    path = cfg.data_dir / "reference" / "contracts.csv"
    if path.exists():
        rows = pd.concat([pd.read_csv(path, dtype=str), rows.astype(str)], ignore_index=True)
    rows = rows.drop_duplicates(["product", "contract_month"], keep="last").sort_values(["product", "contract_month"])
    rows.to_csv(path, index=False)
    return path


def fx_path(cfg: Config, pair: str, year: str) -> Path:
    return cfg.data_dir / "fx" / pair / f"{pair}_{year}.csv"


def upsert_fx(cfg: Config, pair: str, series: pd.DataFrame, source: str, note: str = "") -> int:
    """series: trade_date, rate. One file per pair per year (one row per day is too small to split further)."""
    s = series.assign(pair=pair, source=source, note=note)[FX_COLS]
    s["trade_date"] = pd.to_datetime(s["trade_date"]).dt.strftime("%Y-%m-%d")
    for year, rows in s.groupby(s["trade_date"].str[:4]):
        path = fx_path(cfg, pair, year)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            rows = pd.concat([pd.read_csv(path, dtype={"trade_date": str}), rows], ignore_index=True)
        rows.drop_duplicates("trade_date", keep="last").sort_values("trade_date").to_csv(
            path, index=False, float_format="%.10g")
    return len(s)


def load_fx(cfg: Config, pair: str) -> pd.Series:
    files = sorted((cfg.data_dir / "fx" / pair).glob(f"{pair}_*.csv"))
    if not files:
        raise FileNotFoundError(f"No FX data for {pair}")
    df = pd.concat([pd.read_csv(f, dtype={"trade_date": str}) for f in files])
    return df.set_index("trade_date")["rate"].sort_index()
