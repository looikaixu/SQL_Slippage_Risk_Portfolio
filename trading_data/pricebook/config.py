"""Configuration loading and contract-month arithmetic."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

DEFAULT_ROOT = Path(__file__).resolve().parents[1]
YM_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
MONTH_ABBR = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")


@dataclass(frozen=True)
class Product:
    code: str
    name: str
    exchange: str
    currency: str
    lot_size_t: float
    tick_size: float
    listed_months: tuple[int, ...]
    ric_roots: tuple[str, ...]
    tick_history: tuple[tuple[str, float], ...] = ()   # (effective_from ISO date, tick_size), ascending
    structures: tuple[str, ...] = ()                    # structure codes for this product; empty = all

    def tick_on(self, trade_date: str) -> float:
        """Tick size in force on trade_date."""
        tick = self.tick_size
        for start, size in self.tick_history:
            if trade_date >= start:
                tick = size
        return tick

    @property
    def tick_value(self) -> float:
        """Currency value of one tick on one lot (current tick size)."""
        return self.lot_size_t * (self.tick_history[-1][1] if self.tick_history else self.tick_size)

    def is_listed(self, ym: str) -> bool:
        return bool(YM_RE.match(ym)) and int(ym[5:7]) in self.listed_months

    def next_listed(self, ym: str, k: int = 1) -> str:
        """k-th listed contract month after `ym` (k=0 returns ym)."""
        y, m = int(ym[:4]), int(ym[5:7])
        while k > 0:
            m += 1
            if m > 12:
                y, m = y + 1, 1
            if m in self.listed_months:
                k -= 1
        return f"{y:04d}-{m:02d}"

    def listed_gap(self, front: str, back: str) -> int | None:
        """Number of listed-month steps from front to back; None if back is not reachable."""
        if not (self.is_listed(front) and self.is_listed(back)) or back <= front:
            return None
        for k in range(1, 49):
            nxt = self.next_listed(front, k)
            if nxt == back:
                return k
            if nxt > back:
                return None
        return None


@dataclass(frozen=True)
class Structure:
    code: str
    offsets: tuple[int, ...]
    weights: tuple[int, ...]


@dataclass(frozen=True)
class Config:
    root: Path
    source: str
    default_session: str
    products: dict[str, Product]
    structures: dict[str, Structure]
    column_aliases: dict[str, tuple[str, ...]]
    oi_ratio_threshold: float

    @property
    def data_dir(self) -> Path:
        return self.root / "data"

    @property
    def ric_map_path(self) -> Path:
        return self.data_dir / "reference" / "ric_map.csv"

    def structures_for(self, code: str) -> list[Structure]:
        wanted = self.product(code).structures
        return [s for c, s in self.structures.items() if not wanted or c in wanted]

    def product(self, code: str) -> Product:
        try:
            return self.products[code]
        except KeyError:
            raise KeyError(f"Unknown product {code!r}; known: {sorted(self.products)}") from None


def load_config(root: Path | str = DEFAULT_ROOT) -> Config:
    root = Path(root)
    spec = yaml.safe_load((root / "config" / "products.yaml").read_text())
    aliases = yaml.safe_load((root / "config" / "reuters_columns.yaml").read_text())

    products = {
        code: Product(
            code=code,
            name=p["name"],
            exchange=p["exchange"],
            currency=p["currency"],
            lot_size_t=float(p["lot_size_t"]),
            tick_size=float(p["tick_size"]),
            listed_months=tuple(int(m) for m in p["listed_months"]),
            ric_roots=tuple(p.get("ric_roots") or ()),
            tick_history=tuple(sorted((str(t["from"]), float(t["tick_size"])) for t in p.get("tick_history") or ())),
            structures=tuple(p.get("structures") or ()),
        )
        for code, p in spec["products"].items()
    }
    structures = {}
    for code, s in spec["structures"].items():
        if len(s["offsets"]) != len(s["weights"]) or s["offsets"][0] != 0:
            raise ValueError(f"Structure {code}: offsets/weights mismatch or offsets[0] != 0")
        structures[code] = Structure(code, tuple(s["offsets"]), tuple(s["weights"]))

    for prod in products.values():
        if unknown := set(prod.structures) - set(structures):
            raise ValueError(f"{prod.code}: unknown structures {sorted(unknown)}")
    return Config(
        root=root,
        source=spec.get("source", "REUTERS"),
        default_session=spec.get("default_session", "EOD"),
        products=products,
        structures=structures,
        column_aliases={k: tuple(v) for k, v in aliases.items()},
        oi_ratio_threshold=float(spec.get("roll", {}).get("oi_ratio_threshold", 1.5)),
    )


def month_label(ym: str) -> str:
    """'2027-01' -> 'JAN27'."""
    return f"{MONTH_ABBR[int(ym[5:7]) - 1]}{ym[2:4]}"
