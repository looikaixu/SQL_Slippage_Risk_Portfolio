"""Data-quality gate. ERROR blocks the push (CI exit 1); WARN is reported only."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from .config import YM_RE, Config
from .store import KEYS, PRICE_FIELDS, QTY_FIELDS, SCHEMAS, read_file
from .structures import derive_from_outrights


@dataclass(frozen=True)
class Issue:
    level: str   # ERROR | WARN
    file: str
    message: str

    def __str__(self) -> str:
        return f"[{self.level}] {self.file}: {self.message}"


def _check_file(path: Path, kind: str, cfg: Config) -> list[Issue]:
    rel = str(path.relative_to(cfg.root))
    err = lambda m: Issue("ERROR", rel, m)  # noqa: E731
    warn = lambda m: Issue("WARN", rel, m)  # noqa: E731
    issues: list[Issue] = []

    raw_cols = pd.read_csv(path, nrows=0).columns.tolist()
    if missing := [c for c in SCHEMAS[kind] if c not in raw_cols]:
        return [err(f"missing columns {missing}")]
    df = read_file(path, kind)
    if df.empty:
        return [warn("empty file")]

    product_dir, file_date = path.parts[-3], path.stem[-10:]
    if product_dir not in cfg.products:
        issues.append(err(f"unknown product folder {product_dir}"))
        return issues
    prod = cfg.product(product_dir)
    if (df["product"] != product_dir).any():
        issues.append(err("product column does not match folder"))
    if (df["trade_date"] != file_date).any():
        issues.append(err(f"trade_date differs from file date {file_date}"))
    if date.fromisoformat(file_date).weekday() >= 5:
        issues.append(warn(f"{file_date} is a weekend"))
    if date.fromisoformat(file_date) > date.today():
        issues.append(err(f"{file_date} is in the future"))
    if (dups := df.duplicated(subset=KEYS[kind]).sum()):
        issues.append(err(f"{dups} duplicate keys {KEYS[kind]}"))

    px = df[PRICE_FIELDS].apply(pd.to_numeric, errors="coerce")
    hl = px["high"].notna() & px["low"].notna()
    if (bad := (hl & (px["high"] < px["low"])).sum()):
        issues.append(err(f"{bad} rows with high < low"))
    for f in ("open", "close", "settle"):
        out = hl & px[f].notna() & ((px[f] > px["high"]) | (px[f] < px["low"]))
        if out.sum():
            issues.append(warn(f"{out.sum()} rows with {f} outside [low, high] (settle can legitimately sit outside)"))
    for f in QTY_FIELDS:
        if (pd.to_numeric(df[f], errors="coerce") < 0).any():
            issues.append(err(f"negative {f}"))

    if kind == "outrights":
        bad_m = [m for m in df["contract_month"] if not prod.is_listed(str(m))]
        if bad_m:
            issues.append(err(f"contract months not listed for {prod.code}: {sorted(set(bad_m))}"))
        if (px["settle"] <= 0).any():
            issues.append(err("non-positive outright settle"))
        tick = prod.tick_on(file_date)
        off_tick = px.notna() & ((px / tick).round(6) % 1 != 0)
        if off_tick.any().any():
            issues.append(warn(f"prices not on tick grid ({tick:g})"))
    else:
        for legs, front, struct in zip(df["legs"], df["front_month"], df["structure"]):
            parts = str(legs).split("|")
            if not all(YM_RE.match(p) and prod.is_listed(p) for p in parts):
                issues.append(err(f"invalid legs {legs}"))
            elif parts != sorted(parts) or parts[0] != front:
                issues.append(err(f"legs {legs} not ascending / front_month mismatch"))
            elif struct in cfg.structures:
                expected = [prod.next_listed(front, k) for k in cfg.structures[struct].offsets]
                if parts != expected:
                    issues.append(err(f"{struct} legs {legs} != listed sequence {'|'.join(expected)}"))
    return issues


def _sign_check(cfg: Config) -> list[Issue]:
    """If exchange spread prices track -derived better than +derived, the sign convention is inverted."""
    from .store import load
    issues = []
    for code in cfg.products:
        ex = load(cfg, "spreads", code)
        if ex.empty:
            continue
        der = derive_from_outrights(load(cfg, "outrights", code), cfg)
        m = ex.merge(der, on=["trade_date", "session", "structure", "legs"]).dropna(subset=["settle", "derived"])
        m = m[m["derived"] != 0]
        if len(m) >= 5 and (m["settle"] + m["derived"]).abs().median() < (m["settle"] - m["derived"]).abs().median():
            issues.append(Issue("ERROR", f"data/spreads/{code}",
                                "exchange spread prices look sign-inverted vs near-minus-far convention"))
    return issues


def _check_fx(cfg: Config) -> list[Issue]:
    issues = []
    for path in sorted((cfg.data_dir / "fx").glob("*/*.csv")):
        rel = str(path.relative_to(cfg.root))
        df = pd.read_csv(path, dtype={"trade_date": str})
        if df["trade_date"].duplicated().any():
            issues.append(Issue("ERROR", rel, "duplicate trade_date"))
        if (pd.to_numeric(df["rate"], errors="coerce") <= 0).any() or df["rate"].isna().any():
            issues.append(Issue("ERROR", rel, "missing or non-positive rate"))
        if (df["trade_date"].str[:4] != path.stem[-4:]).any():
            issues.append(Issue("ERROR", rel, "trade_date outside file year"))
        jump = pd.to_numeric(df["rate"]).pct_change().abs().max()
        if jump > 0.05:
            issues.append(Issue("WARN", rel, f"day-on-day FX move {jump:.1%}"))
    return issues


def validate_all(cfg: Config) -> list[Issue]:
    issues: list[Issue] = []
    for kind in SCHEMAS:
        for path in sorted((cfg.data_dir / kind).glob("*/*/*.csv")):
            issues.extend(_check_file(path, kind, cfg))
    issues.extend(_check_fx(cfg))
    issues.extend(_sign_check(cfg))
    return issues
