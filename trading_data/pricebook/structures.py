"""Spread board: exchange-traded spread prices first, outright-derived values only as flagged fallback."""
from __future__ import annotations

import pandas as pd

from .config import Config, month_label
from .store import load


def derive_from_outrights(outrights: pd.DataFrame, cfg: Config, field: str = "settle") -> pd.DataFrame:
    """Compute every configured structure from outright `field`, using the product's listed-month sequence.
    A structure is produced only when all its legs have a price on that date/session."""
    cols = ["trade_date", "session", "product", "structure", "front_month", "legs", "derived"]
    rows = []
    for (td, sess, prod_code), g in outrights.dropna(subset=[field]).groupby(["trade_date", "session", "product"]):
        prod = cfg.product(prod_code)
        px = dict(zip(g["contract_month"], g[field]))
        for front in sorted(px):
            for s in cfg.structures.values():
                legs = [prod.next_listed(front, k) for k in s.offsets]
                if all(leg in px for leg in legs):
                    value = sum(w * px[leg] for w, leg in zip(s.weights, legs))
                    rows.append((td, sess, prod_code, s.code, front, "|".join(legs), value))
    return pd.DataFrame(rows, columns=cols)


def _s1_coefficients(offsets: tuple[int, ...], weights: tuple[int, ...]) -> list[int] | None:
    """Express a zero-sum leg structure as a combination of consecutive S1s.
    S1_k = L_k - L_(k+1)  =>  coefficient on S1_k = cumulative sum of leg weights up to k."""
    dense = [0] * (max(offsets) + 1)
    for o, w in zip(offsets, weights):
        dense[o] = w
    if sum(dense) != 0:
        return None
    coeffs, run = [], 0
    for w in dense[:-1]:
        run += w
        coeffs.append(run)
    return coeffs


def derive_from_s1(spreads: pd.DataFrame, cfg: Config, field: str = "settle") -> pd.DataFrame:
    """Compute structures from EXCHANGE S1 prints only (e.g. JAN FLY = JAN S1 - FEB S1).
    Avoids outright leg slippage when the S1 market is printed but the fly/condor is not."""
    cols = ["trade_date", "session", "product", "structure", "front_month", "legs", "from_s1"]
    rows = []
    s1 = spreads[(spreads["structure"] == "S1")].dropna(subset=[field])
    for (td, sess, prod_code), g in s1.groupby(["trade_date", "session", "product"]):
        prod = cfg.product(prod_code)
        px = dict(zip(g["front_month"], g[field]))
        for front in sorted(px):
            for st in cfg.structures.values():
                coeffs = _s1_coefficients(st.offsets, st.weights)
                if coeffs is None or st.code == "S1":
                    continue
                fronts = [prod.next_listed(front, k) for k in range(len(coeffs))]
                if all(f in px for f, c in zip(fronts, coeffs) if c):
                    value = sum(c * px[f] for f, c in zip(fronts, coeffs) if c)
                    legs = "|".join(prod.next_listed(front, k) for k in st.offsets)
                    rows.append((td, sess, prod_code, st.code, front, legs, value))
    return pd.DataFrame(rows, columns=cols)


def spread_board(cfg: Config, product: str, trade_date: str, session: str | None = None,
                 field: str = "settle") -> pd.DataFrame:
    """One row per (structure, legs). Price priority:
        EXCHANGE  exchange print of that structure
        FROM_S1   built from exchange S1 prints (no outright slippage)
        DERIVED   built from outright prices (fallback; carries leg slippage)
    `basis` = exchange - derived (what legging via outrights would have cost / gained)."""
    session = session or cfg.default_session
    exch = load(cfg, "spreads", product, trade_date, trade_date, session)
    outr = load(cfg, "outrights", product, trade_date, trade_date, session)

    exch = exch[["structure", "front_month", "legs", field, "volume"]].rename(columns={field: "exchange"})
    der = derive_from_outrights(outr, cfg, field)[["structure", "front_month", "legs", "derived"]]
    s1x = derive_from_s1(load(cfg, "spreads", product, trade_date, trade_date, session), cfg, field)
    s1x = s1x[["structure", "front_month", "legs", "from_s1"]]

    key = ["structure", "front_month", "legs"]
    board = exch.merge(s1x, on=key, how="outer").merge(der, on=key, how="outer")
    board["price"] = board["exchange"].combine_first(board["from_s1"]).combine_first(board["derived"])
    board["price_source"] = None
    for col, tag in (("derived", "DERIVED"), ("from_s1", "FROM_S1"), ("exchange", "EXCHANGE")):
        board.loc[board[col].notna(), "price_source"] = tag
    board["basis"] = board["exchange"] - board["derived"]
    board["label"] = board["front_month"].map(month_label) + " " + board["structure"]
    order = {c: i for i, c in enumerate(["S1", "S2", "FLY", "DFLY", "CONDOR"])}
    board["_o"] = board["structure"].map(lambda s: order.get(s, 99))
    return board.sort_values(["_o", "front_month", "legs"]).drop(columns="_o").reset_index(drop=True)


def board_matrix(board: pd.DataFrame) -> pd.DataFrame:
    """Front month x structure grid. Suffix: none = exchange, '~' = from exchange S1s, '*' = from outrights."""
    mark = {"EXCHANGE": "", "FROM_S1": "~", "DERIVED": "*"}

    def fmt(r):
        if pd.isna(r["price"]):
            return ""
        return f"{r['price']:g}" + mark.get(r["price_source"], "?")
    b = board.assign(cell=board.apply(fmt, axis=1), month=board["front_month"].map(month_label))
    known = ["S1", "S2", "FLY", "DFLY", "CONDOR"]
    b = b[b["structure"].isin(known)]
    grid = b.pivot_table(index=["front_month", "month"], columns="structure", values="cell", aggfunc="first")
    return grid.reindex(columns=[c for c in known if c in grid.columns]).droplevel(0).fillna("")
