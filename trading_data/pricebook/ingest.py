"""Reuters / LSEG export (xlsx / csv) -> normalized daily files.

Accepted layouts:
  * long table with a RIC column (many instruments, many dates)
  * one sheet per RIC (sheet name = RIC), title rows above the header are skipped
  * one file per RIC (pass --ric, or file stem = RIC)
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .config import Config
from .contracts import Instrument, RicError, load_ric_map, parse_ric
from .store import PRICE_FIELDS, QTY_FIELDS, upsert_day

HEADER_SCAN_ROWS = 30


class IngestError(ValueError):
    pass


@dataclass
class IngestReport:
    rows: int = 0
    files_written: set[Path] = field(default_factory=set)
    skipped_rows: int = 0


def _norm(s: object) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", str(s).lower())).strip()


def _find_header(raw: pd.DataFrame, cfg: Config) -> int:
    date_aliases = {_norm(a) for a in cfg.column_aliases["trade_date"]}
    price_aliases = {_norm(a) for f in PRICE_FIELDS for a in cfg.column_aliases[f]}
    for i in range(min(HEADER_SCAN_ROWS, len(raw))):
        cells = {_norm(c) for c in raw.iloc[i].tolist() if pd.notna(c)}
        if cells & date_aliases and cells & price_aliases:
            return i
    raise IngestError("No header row with a date column and a price column in the first "
                      f"{HEADER_SCAN_ROWS} rows; add the header text to config/reuters_columns.yaml")


def _map_columns(columns: list[object], cfg: Config) -> dict[str, object]:
    by_norm = {_norm(c): c for c in columns if pd.notna(c)}
    mapping = {}
    for canon, aliases in cfg.column_aliases.items():
        for a in aliases:
            if _norm(a) in by_norm:
                mapping[canon] = by_norm[_norm(a)]
                break
    return mapping


def _to_number(s: pd.Series) -> pd.Series:
    s = s.astype(str).str.replace(",", "", regex=False).str.strip()
    return pd.to_numeric(s.where(~s.isin(["", "-", "nan", "NaN", "None", "N/A", "NA"])), errors="coerce")


def read_tables(path: Path) -> list[tuple[str, pd.DataFrame]]:
    if path.suffix.lower() in {".xlsx", ".xlsm", ".xls"}:
        sheets = pd.read_excel(path, sheet_name=None, header=None, dtype=object)
        return list(sheets.items())
    if path.suffix.lower() == ".csv":
        # Ragged read: title/metadata rows above the header have fewer fields than the table.
        with open(path, newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.reader(fh))
        width = max((len(r) for r in rows), default=0)
        raw = pd.DataFrame([r + [None] * (width - len(r)) for r in rows], dtype=object)
        return [(path.stem, raw.replace({"": None}))]
    raise IngestError(f"Unsupported file type: {path.suffix}")


def normalize_table(raw: pd.DataFrame, cfg: Config, sheet_ric: str | None, dayfirst: bool) -> pd.DataFrame:
    """Return canonical columns: trade_date, ric, open..settle, volume, open_interest."""
    hdr = _find_header(raw, cfg)
    df = raw.iloc[hdr + 1:].copy()
    df.columns = raw.iloc[hdr].tolist()
    cols = _map_columns(list(df.columns), cfg)

    out = pd.DataFrame(index=df.index)
    out["trade_date"] = pd.to_datetime(df[cols["trade_date"]], errors="coerce", dayfirst=dayfirst).dt.date
    if "ric" in cols:
        ric_col = df[cols["ric"]].astype(str).str.strip()
        # Block-style exports print the RIC once per block: forward-fill blanks.
        out["ric"] = ric_col.where(~ric_col.isin(["", "nan", "None"])).ffill()
    elif sheet_ric:
        out["ric"] = sheet_ric
    else:
        raise IngestError("No RIC column; pass --ric or name the sheet/file after the RIC")
    for f in PRICE_FIELDS + QTY_FIELDS:
        out[f] = _to_number(df[cols[f]]) if f in cols else pd.NA
    has_value = out[PRICE_FIELDS].notna().any(axis=1)
    return out[out["trade_date"].notna() & out["ric"].notna() & has_value]


def ingest_file(path: Path | str, cfg: Config, ric: str | None = None, session: str | None = None,
                dayfirst: bool = False) -> IngestReport:
    path = Path(path)
    session = session or cfg.default_session
    ric_map = load_ric_map(cfg)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    today = datetime.now(timezone.utc).date()

    frames = []
    for sheet, raw in read_tables(path):
        try:
            default_sheet = re.fullmatch(r"(sheet|tabelle|feuil)\d*", str(sheet), re.I)
            sheet_ric = ric or (path.stem if default_sheet else str(sheet))
            frames.append(normalize_table(raw, cfg, sheet_ric, dayfirst))
        except IngestError as e:
            raise IngestError(f"{path.name} [{sheet}]: {e}") from None
    data = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if data.empty:
        raise IngestError(f"{path.name}: no price rows found")
    if (future := data[data["trade_date"] > today]).shape[0]:
        raise IngestError(f"{path.name}: {len(future)} rows dated in the future — wrong date format? try --dayfirst")

    # Resolve each (ric, date) once; collect all failures before raising.
    resolved: dict[tuple[str, object], Instrument] = {}
    failures: set[str] = set()
    for key in data[["ric", "trade_date"]].drop_duplicates().itertuples(index=False):
        try:
            resolved[(key.ric, key.trade_date)] = parse_ric(key.ric, key.trade_date, cfg, ric_map)
        except RicError as e:
            failures.add(str(e))
    if failures:
        raise IngestError("Unresolved RICs — add them to data/reference/ric_map.csv "
                          "(ric,product,structure,legs):\n  " + "\n  ".join(sorted(failures)))

    inst = [resolved[(r, d)] for r, d in zip(data["ric"], data["trade_date"])]
    data["product"] = [i.product for i in inst]
    data["structure"] = [i.structure for i in inst]
    data["legs"] = [i.legs_str for i in inst]
    data["front_month"] = [i.front_month for i in inst]
    data["contract_month"] = data["front_month"]
    data["exchange"] = [cfg.product(p).exchange for p in data["product"]]
    data["currency"] = [cfg.product(p).currency for p in data["product"]]
    data["session"], data["source"], data["ingested_at"] = session, cfg.source, now
    data["trade_date"] = data["trade_date"].astype(str)

    report = IngestReport(rows=len(data))
    data["kind"] = ["outrights" if s == "OUTRIGHT" else "spreads" for s in data["structure"]]
    for (kind, product, td), rows in data.groupby(["kind", "product", "trade_date"]):
        report.files_written.add(upsert_day(cfg, kind, product, td, rows))
    return report
