"""CLI:  python -m pricebook <ingest|validate|board|roll|coverage> ...  (run from trading_data/)"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from .config import load_config, month_label
from .ingest import IngestError, ingest_file
from .roll import oi_ratio
from .store import load
from .structures import board_matrix, spread_board
from .validate import validate_all


def _print_issues(issues) -> int:
    for i in issues:
        print(i)
    errors = sum(i.level == "ERROR" for i in issues)
    print(f"validate: {errors} error(s), {len(issues) - errors} warning(s)")
    return 1 if errors else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="pricebook")
    ap.add_argument("--root", default=None, help="trading_data root (default: package parent)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("ingest", help="Reuters export(s) -> data/outrights + data/spreads")
    p.add_argument("files", nargs="+", type=Path)
    p.add_argument("--ric", help="RIC for single-instrument files without a RIC column")
    p.add_argument("--session", help="EOD (default) | AM_CLOSE | PM_CLOSE | NIGHT")
    p.add_argument("--dayfirst", action="store_true", help="parse 13/11/2026 style dates")

    sub.add_parser("validate", help="data-quality checks (exit 1 on ERROR)")

    p = sub.add_parser("board", help="spread board for one date (exchange > from-S1 > from-outrights)")
    p.add_argument("product")
    p.add_argument("date", nargs="?", help="YYYY-MM-DD (default: latest)")
    p.add_argument("--field", default="settle")
    p.add_argument("--session")
    p.add_argument("--detail", action="store_true", help="long table with exchange / derived / basis")

    p = sub.add_parser("roll", help="OI ratio new vs old active month")
    p.add_argument("product")
    p.add_argument("--old")
    p.add_argument("--new")
    p.add_argument("--start")
    p.add_argument("--end")

    sub.add_parser("coverage", help="dates and row counts stored per product")

    a = ap.parse_args(argv)
    cfg = load_config(a.root) if a.root else load_config()
    pd.set_option("display.width", 200, "display.max_rows", 500, "display.max_columns", 30)

    if a.cmd == "ingest":
        try:
            for f in a.files:
                r = ingest_file(f, cfg, ric=a.ric, session=a.session, dayfirst=a.dayfirst)
                print(f"{f.name}: {r.rows} rows -> {len(r.files_written)} day files")
        except IngestError as e:
            print(f"ingest failed: {e}", file=sys.stderr)
            return 2
        return _print_issues(validate_all(cfg))

    if a.cmd == "validate":
        return _print_issues(validate_all(cfg))

    if a.cmd == "board":
        date = a.date or load(cfg, "outrights", a.product)["trade_date"].max()
        if not isinstance(date, str):
            print(f"No data for {a.product}", file=sys.stderr)
            return 1
        b = spread_board(cfg, a.product, date, a.session, a.field)
        print(f"{a.product} {date} {a.field}  (plain = exchange print, ~ = from exchange S1s, * = from outrights)")
        if a.detail:
            print(b[["label", "legs", "exchange", "from_s1", "derived", "basis", "price_source", "volume"]].to_string(index=False))
        else:
            print(board_matrix(b).to_string())
        return 0

    if a.cmd == "roll":
        r = oi_ratio(cfg, a.product, a.old, a.new, a.start, a.end)
        print(f"{a.product} roll {month_label(r.attrs['old'])} -> {month_label(r.attrs['new'])}"
              f"  threshold {r.attrs['threshold']}")
        print(r.to_string())
        return 0

    if a.cmd == "coverage":
        for kind in ("outrights", "spreads"):
            df = load(cfg, kind)
            if df.empty:
                print(f"{kind}: empty")
                continue
            s = df.groupby("product").agg(first=("trade_date", "min"), last=("trade_date", "max"),
                                          days=("trade_date", "nunique"), rows=("trade_date", "size"))
            print(f"{kind}:\n{s.to_string()}\n")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
