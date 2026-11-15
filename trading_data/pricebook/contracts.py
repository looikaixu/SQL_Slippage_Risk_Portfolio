"""RIC -> instrument resolution (outright or exchange-traded spread)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from .config import Config

MONTH_CODES = "FGHJKMNQUVXZ"  # F=Jan ... Z=Dec
_LEG = r"([FGHJKMNQUVXZ])(\d{1,2})"
# Expired LSEG RICs carry a decade suffix, e.g. FCPOF7^2 -> Jan 2027.  VERIFY on first export.
_DECADE = r"(?:\^(\d))?"


class RicError(ValueError):
    pass


@dataclass(frozen=True)
class Instrument:
    ric: str
    product: str
    structure: str            # OUTRIGHT, S1, S2, FLY, DFLY, CONDOR, ...
    legs: tuple[str, ...]     # contract months 'YYYY-MM', nearest first

    @property
    def is_outright(self) -> bool:
        return self.structure == "OUTRIGHT"

    @property
    def front_month(self) -> str:
        return self.legs[0]

    @property
    def legs_str(self) -> str:
        return "|".join(self.legs)


def _resolve_year(ydigits: str, month: int, trade_date: date, decade: str | None) -> int:
    if len(ydigits) == 2:
        return 2000 + int(ydigits)
    d = int(ydigits)
    if decade is not None:
        return 2000 + int(decade) * 10 + d
    # Live RIC: nearest year ending in `d` whose contract month has not expired at trade_date.
    for y in range(trade_date.year, trade_date.year + 11):
        if y % 10 == d and (y, month) >= (trade_date.year, trade_date.month):
            return y
    raise RicError(f"Cannot resolve year digit {ydigits}")


def load_ric_map(cfg: Config) -> dict[str, Instrument]:
    path: Path = cfg.ric_map_path
    if not path.exists():
        return {}
    df = pd.read_csv(path, dtype=str).fillna("")
    out = {}
    for row in df.itertuples(index=False):
        if not row.ric:
            continue
        cfg.product(row.product)  # raises on unknown product
        legs = tuple(x.strip() for x in row.legs.split("|") if x.strip())
        out[row.ric.strip()] = Instrument(row.ric.strip(), row.product, row.structure.strip().upper(), legs)
    return out


def parse_ric(ric: str, trade_date: date, cfg: Config, ric_map: dict[str, Instrument] | None = None) -> Instrument:
    """Resolve a RIC. Explicit ric_map entries win; otherwise parse ROOT+MonthCode+Year[-[ROOT]MonthCode+Year][^decade]."""
    ric = ric.strip()
    if ric_map and ric in ric_map:
        return ric_map[ric]
    if re.search(r"c\d+$", ric):
        raise RicError(f"{ric}: continuation RIC (rolls over time) — export dated contracts instead")

    for code, prod in cfg.products.items():
        for root in sorted(prod.ric_roots, key=len, reverse=True):
            if not ric.startswith(root):
                continue
            m = re.fullmatch(rf"{_LEG}(?:-(?:{re.escape(root)})?{_LEG})?{_DECADE}", ric[len(root):])
            if not m:
                continue
            m1, y1, m2, y2, decade = m.groups()
            legs = [f"{_resolve_year(y1, MONTH_CODES.index(m1) + 1, trade_date, decade):04d}-{MONTH_CODES.index(m1) + 1:02d}"]
            if m2:
                legs.append(f"{_resolve_year(y2, MONTH_CODES.index(m2) + 1, trade_date, decade):04d}-{MONTH_CODES.index(m2) + 1:02d}")
                gap = prod.listed_gap(legs[0], legs[1])
                if gap is None:
                    raise RicError(f"{ric}: legs {legs} are not ordered listed months of {code}")
                structure = f"S{gap}"
            else:
                structure = "OUTRIGHT"
            return Instrument(ric, code, structure, tuple(legs))

    raise RicError(f"{ric}: no matching ric_root in products.yaml and not in ric_map.csv")
