"""Tests use SYNTHETIC prices only (not market data)."""
from __future__ import annotations

import shutil
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pricebook import load, load_config, oi_ratio, spread_board  # noqa: E402
from pricebook.contracts import RicError, parse_ric  # noqa: E402
from pricebook.ingest import IngestError, ingest_file  # noqa: E402
from pricebook.structures import derive_from_outrights  # noqa: E402
from pricebook.validate import validate_all  # noqa: E402

TD = date(2026, 11, 13)


@pytest.fixture
def cfg(tmp_path):
    shutil.copytree(ROOT / "config", tmp_path / "config")
    (tmp_path / "data" / "reference").mkdir(parents=True)
    shutil.copy(ROOT / "data" / "reference" / "ric_map.csv", tmp_path / "data" / "reference" / "ric_map.csv")
    return load_config(tmp_path)


def _fcpo_long_csv(path: Path, rows: list[tuple]) -> Path:
    df = pd.DataFrame(rows, columns=["RIC", "Date", "Open", "High", "Low", "Settle", "Volume", "Open Interest"])
    with open(path, "w") as fh:
        fh.write("Price History Export\n\n")                  # title rows Reuters puts above the header
    df.to_csv(path, mode="a", index=False)
    return path


# --- contracts -----------------------------------------------------------------------------------------

def test_parse_outright_and_spread(cfg):
    i = parse_ric("FCPOF7", TD, cfg)
    assert (i.product, i.structure, i.legs) == ("FCPO", "OUTRIGHT", ("2027-01",))
    assert parse_ric("FCPOZ6", TD, cfg).legs == ("2026-12",)           # live Dec26 on 13 Nov 2026
    s = parse_ric("FCPOF7-G7", TD, cfg)
    assert (s.structure, s.legs) == ("S1", ("2027-01", "2027-02"))
    assert parse_ric("FCPOF7-FCPOH7", TD, cfg).structure == "S2"
    assert parse_ric("FCPOF3^2", TD, cfg).legs == ("2023-01",)         # expired RIC with decade suffix


def test_parse_rejects_continuation_and_unknown(cfg):
    with pytest.raises(RicError, match="continuation"):
        parse_ric("FCPOc1", TD, cfg)
    with pytest.raises(RicError):
        parse_ric("XYZF7", TD, cfg)


def test_listed_months_dce_soy_oil(cfg):
    y = cfg.product("DCE_Y")
    assert y.next_listed("2027-01") == "2027-03"
    assert y.next_listed("2026-12") == "2027-01"
    assert y.listed_gap("2027-01", "2027-05") == 2
    assert not y.is_listed("2027-02")


# --- ingest --------------------------------------------------------------------------------------------

def test_ingest_long_csv_and_upsert(cfg, tmp_path):
    f = _fcpo_long_csv(tmp_path / "export.csv", [
        ("FCPOF7", "2026-11-13", 4100, 4150, 4090, "4,120", 30000, 120000),
        ("FCPOG7", "2026-11-13", 4080, 4130, 4070, 4092, 25000, 90000),
        ("FCPOH7", "2026-11-13", 4060, 4110, 4050, 4070, 10000, 60000),
        ("FCPOJ7", "2026-11-13", 4040, 4090, 4030, 4051, 5000, 40000),
        ("FCPOF7-G7", "2026-11-13", 27, 33, 25, 30, 1500, None),
    ])
    r = ingest_file(f, cfg)
    assert r.rows == 5 and len(r.files_written) == 2
    o = load(cfg, "outrights", "FCPO")
    assert o.loc[o.contract_month == "2027-01", "settle"].item() == 4120        # thousands separator parsed
    sp = load(cfg, "spreads", "FCPO")
    assert sp[["structure", "legs", "settle"]].values.tolist() == [["S1", "2027-01|2027-02", 30]]

    ingest_file(f, cfg)                                                            # idempotent
    assert len(load(cfg, "outrights", "FCPO")) == 4


def test_ingest_xlsx_sheet_per_ric(cfg, tmp_path):
    path = tmp_path / "hist.xlsx"
    with pd.ExcelWriter(path) as xw:
        for ric, settle in [("FCPOF7", 4120), ("FCPOG7", 4092)]:
            body = pd.DataFrame({"Exchange Date": ["13-Nov-2026", "12-Nov-2026"],
                                 "Close": [settle, settle - 10], "Open Interest": [100, 90]})
            body.to_excel(xw, sheet_name=ric, index=False, startrow=3)
    ingest_file(path, cfg)
    o = load(cfg, "outrights", "FCPO")
    assert sorted(o.trade_date.unique()) == ["2026-11-12", "2026-11-13"]
    assert o.settle.isna().all() and o.close.notna().all()                        # Close stays close


def test_ingest_unresolved_ric_lists_all(cfg, tmp_path):
    f = _fcpo_long_csv(tmp_path / "e.csv", [
        ("DPOF7", "2026-11-13", 1, 2, 1, 1, 1, 1), ("DSOF7", "2026-11-13", 1, 2, 1, 1, 1, 1)])
    with pytest.raises(IngestError, match="ric_map.csv") as e:
        ingest_file(f, cfg)
    assert "DPOF7" in str(e.value) and "DSOF7" in str(e.value)


def test_ingest_ric_map_override_for_dce(cfg, tmp_path):
    cfg.ric_map_path.write_text("ric,product,structure,legs\n"
                                "SOY2701,DCE_Y,OUTRIGHT,2027-01\n"
                                "SOY2701-05,DCE_Y,S2,2027-01|2027-05\n")
    f = _fcpo_long_csv(tmp_path / "dce.csv", [
        ("SOY2701", "2026-11-13", 8000, 8100, 7990, 8050, 1, 1),
        ("SOY2701-05", "2026-11-13", -60, -40, -70, -50, 1, None)])
    ingest_file(f, cfg)
    assert load(cfg, "spreads", "DCE_Y")["settle"].item() == -50


def test_ingest_rejects_future_dates(cfg, tmp_path):
    f = _fcpo_long_csv(tmp_path / "e.csv", [("FCPOF7", "2099-01-01", 1, 2, 1, 1, 1, 1)])
    with pytest.raises(IngestError, match="future"):
        ingest_file(f, cfg)


# --- structures / board --------------------------------------------------------------------------------

def _outrights(prices: dict[str, float], product="FCPO") -> pd.DataFrame:
    return pd.DataFrame({"trade_date": "2026-11-13", "session": "EOD", "product": product,
                         "contract_month": list(prices), "settle": list(prices.values())})


def test_structure_weights(cfg):
    d = derive_from_outrights(_outrights({"2027-01": 4120, "2027-02": 4092, "2027-03": 4070, "2027-04": 4051}), cfg)
    v = {(r.structure, r.front_month): r.derived for r in d.itertuples()}
    assert v[("S1", "2027-01")] == 28
    assert v[("S2", "2027-01")] == 50
    assert v[("FLY", "2027-01")] == 28 - 22                 # JAN S1 - FEB S1
    assert v[("DFLY", "2027-01")] == (28 - 22) - (22 - 19)  # JAN FLY - FEB FLY
    assert v[("CONDOR", "2027-01")] == 28 - 19              # JAN S1 - MAR S1


def test_derived_uses_listed_sequence_for_soy_oil(cfg):
    d = derive_from_outrights(_outrights({"2027-01": 8050, "2027-03": 8020, "2027-05": 8000}, "DCE_Y"), cfg)
    s1 = d[(d.structure == "S1") & (d.front_month == "2027-01")]
    assert s1.legs.item() == "2027-01|2027-03" and s1.derived.item() == 30


def test_board_prefers_exchange_print(cfg, tmp_path):
    f = _fcpo_long_csv(tmp_path / "x.csv", [
        ("FCPOF7", "2026-11-13", 1, 9999, 1, 4120, 1, 1), ("FCPOG7", "2026-11-13", 1, 9999, 1, 4092, 1, 1),
        ("FCPOH7", "2026-11-13", 1, 9999, 1, 4070, 1, 1), ("FCPOF7-G7", "2026-11-13", 1, 99, -99, 30, 1, None)])
    ingest_file(f, cfg)
    b = spread_board(cfg, "FCPO", "2026-11-13").set_index("label")
    assert b.loc["JAN27 S1", "price"] == 30 and b.loc["JAN27 S1", "price_source"] == "EXCHANGE"
    assert b.loc["JAN27 S1", "basis"] == 2
    assert b.loc["FEB27 S1", "price"] == 22 and b.loc["FEB27 S1", "price_source"] == "DERIVED"


# --- roll / validate -----------------------------------------------------------------------------------

def test_roll_ratio(cfg, tmp_path):
    rows = []
    for d, oi_old, oi_new in [("2026-11-12", 100, 80), ("2026-11-13", 80, 130)]:
        rows += [("FCPOF7", d, 1, 2, 1, 1, 1, oi_old), ("FCPOG7", d, 1, 2, 1, 1, 1, oi_new)]
    ingest_file(_fcpo_long_csv(tmp_path / "r.csv", rows), cfg)
    r = oi_ratio(cfg, "FCPO")
    assert (r.attrs["old"], r.attrs["new"]) == ("2027-01", "2027-02")
    assert r["roll_done"].tolist() == [False, True]


def test_validate_flags_bad_rows(cfg, tmp_path):
    ingest_file(_fcpo_long_csv(tmp_path / "v.csv", [
        ("FCPOF7", "2026-11-13", 4100, 4000, 4090, 4120, -1, 1)]), cfg)     # high < low, negative volume
    msgs = [str(i) for i in validate_all(cfg) if i.level == "ERROR"]
    assert any("high < low" in m for m in msgs) and any("negative volume" in m for m in msgs)


def test_validate_detects_inverted_spread_sign(cfg, tmp_path):
    rows = []
    for d in ["2026-11-09", "2026-11-10", "2026-11-11", "2026-11-12", "2026-11-13"]:
        rows += [("FCPOF7", d, 1, 9999, 1, 4120, 1, 1), ("FCPOG7", d, 1, 9999, 1, 4092, 1, 1),
                 ("FCPOF7-G7", d, -99, 99, -99, -28, 1, None)]           # far-minus-near quoting
    ingest_file(_fcpo_long_csv(tmp_path / "s.csv", rows), cfg)
    assert any("sign-inverted" in str(i) for i in validate_all(cfg))


def test_fly_built_from_exchange_s1_before_outrights(cfg, tmp_path):
    f = _fcpo_long_csv(tmp_path / "f.csv", [
        ("FCPOF7", "2026-11-13", 1, 9999, 1, 4120, 1, 1), ("FCPOG7", "2026-11-13", 1, 9999, 1, 4092, 1, 1),
        ("FCPOH7", "2026-11-13", 1, 9999, 1, 4070, 1, 1), ("FCPOJ7", "2026-11-13", 1, 9999, 1, 4051, 1, 1),
        ("FCPOF7-G7", "2026-11-13", -99, 99, -99, 30, 1, None),
        ("FCPOG7-H7", "2026-11-13", -99, 99, -99, 21, 1, None),
        ("FCPOH7-J7", "2026-11-13", -99, 99, -99, 18, 1, None)])
    ingest_file(f, cfg)
    b = spread_board(cfg, "FCPO", "2026-11-13").set_index("label")
    assert (b.loc["JAN27 FLY", "price"], b.loc["JAN27 FLY", "price_source"]) == (9, "FROM_S1")        # 30-21
    assert b.loc["JAN27 FLY", "derived"] == 6                                                          # outrights
    assert b.loc["JAN27 DFLY", "price"] == 30 - 2 * 21 + 18
    assert b.loc["JAN27 CONDOR", "price"] == 30 - 18
    assert b.loc["JAN27 S2", "price"] == 30 + 21


# --- LSEG tidy tables / FX / DAPO ----------------------------------------------------------------------

from pricebook.cross import dapo  # noqa: E402
from pricebook.tables import contract_label_to_ym, import_contract_table, load_fx, upsert_fx  # noqa: E402


def _table(path: Path, rows: list[tuple], cols: str) -> Path:
    pd.DataFrame(rows, columns=cols.split(",")).to_csv(path, index=False)
    return path


def test_contract_label():
    assert contract_label_to_ym("Jan-27") == "2027-01" and contract_label_to_ym("Sep-20") == "2020-09"


def test_import_contract_table_and_reference(cfg, tmp_path):
    f = _table(tmp_path / "dce.csv", [("2026-11-13", "Jan-27", "2027-01-14", 500, 8961, 8950),
                                     ("2026-11-13", "May-27", "2027-05-14", 330, 9473, 9462)],
               "date,contract,expiry,oi,close,settle")
    r = import_contract_table(f, "DCE_P", cfg, "test")
    assert r == {"rows": 2, "days": 1, "contracts": 2}
    o = load(cfg, "outrights", "DCE_P")
    assert o.set_index("contract_month").loc["2027-05", "open_interest"] == 330
    ref = pd.read_csv(cfg.data_dir / "reference" / "contracts.csv", dtype=str)
    assert ref[["product", "contract_month", "expiry"]].values.tolist()[0] == ["DCE_P", "2027-01", "2027-01-14"]
    b = spread_board(cfg, "DCE_P", "2026-11-13").set_index("label")
    assert list(b.index) == ["JAN27 S4"] and b.loc["JAN27 S4", "price"] == 8950 - 9462     # only S4 for DCE_P


def test_tick_history(cfg):
    p = cfg.product("DCE_P")
    assert p.tick_on("2026-04-09") == 2 and p.tick_on("2026-04-10") == 1


def test_dapo_rules(cfg, tmp_path):
    # DCE: May has max OI on day 1, Sep on day 2 (roll). FCPO: 3rd nearest live contract.
    import_contract_table(_table(tmp_path / "d.csv", [
        ("2026-04-01", "May-26", 900, 9000, 9000), ("2026-04-01", "Sep-26", 800, 9100, 9100),
        ("2026-04-02", "May-26", 700, 9010, 9010), ("2026-04-02", "Sep-26", 950, 9120, 9120)],
        "date,contract,oi,close,settle"), "DCE_P", cfg, "t")
    rows = [(d, m, 4000 + i, 4000 + i, 1, 1) for d in ("2026-04-01", "2026-04-02")
            for i, m in enumerate(["Apr-26", "May-26", "Jun-26", "Jul-26"])]
    import_contract_table(_table(tmp_path / "f.csv", rows, "date,contract,close,settle,volume,oi"), "FCPO", cfg, "t")
    upsert_fx(cfg, "CNYMYR", pd.DataFrame({"trade_date": ["2026-04-01", "2026-04-02"], "rate": [0.6, 0.61]}), "t")
    upsert_fx(cfg, "USDMYR", pd.DataFrame({"trade_date": ["2026-04-01", "2026-04-02"], "rate": [4.0, 4.0]}), "t")
    assert load_fx(cfg, "CNYMYR").loc["2026-04-02"] == 0.61

    d = dapo(cfg).set_index("trade_date")
    assert d.loc["2026-04-01", "dce_month"] == "2026-05" and d.loc["2026-04-02", "dce_month"] == "2026-09"
    assert d.loc["2026-04-01", "fcpo_month"] == "2026-06"                      # 3rd: Apr, May, *Jun*
    assert d.loc["2026-04-01", "dapo_myr"] == pytest.approx(9000 * 0.6 - 4002)
    assert d.loc["2026-04-02", "dapo_usd"] == pytest.approx((9120 * 0.61 - 4002) / 4.0)
    assert d["dce_roll"].tolist() == [0, 1] and d["fcpo_roll"].tolist() == [0, 0]
