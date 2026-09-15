"""Run A acceptance tests for src/hksmm.py. Run directly: python tests/test_hksmm.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from src import hksmm


def test_classify_english():
    code, trade, score = hksmm.classify_trade("demolish existing brick wall 300mm thick")
    assert code == "DEM", code
    assert trade == "Demolition", trade
    assert score > 0


def test_classify_chinese():
    code, trade, score = hksmm.classify_trade("拆卸現有磚牆300毫米厚")
    assert code == "DEM", code
    assert score > 0


def test_classify_reinforcement():
    code, trade, _ = hksmm.classify_trade("supply and fix high yield steel bar reinforcement to columns")
    assert code == "REB", code


def test_classify_fire():
    code, trade, _ = hksmm.classify_trade("automatic sprinkler system complete with detector heads")
    assert code == "FIR", code


def test_classify_accepts_dict():
    code, _, _ = hksmm.classify_trade({"description": "demolish existing brick wall"})
    assert code == "DEM"


def test_bilingual_true():
    ok, ratio = hksmm.detect_bilingual("supply and install 消防花灑系統 complete")
    assert ok is True
    assert ratio > 0


def test_bilingual_false_pure_english():
    ok, _ = hksmm.detect_bilingual("supply and install fire sprinkler system")
    assert ok is False


def test_missing_trade_flagged():
    items = [
        "demolish existing brick wall",
        "reinforced concrete columns",
        "ceramic wall tiling to toilet",
    ]
    flags = hksmm.scan_missing_trades(items, exclude=())
    codes = {f["code"] for f in flags}
    assert "FIR" in codes  # fire services absent


def test_duplicate_found():
    items = ["supply and fix ceramic wall tile", "supply and fix ceramic wall tile"]
    dups = hksmm.find_duplicates(items)
    assert len(dups) == 1


def test_duplicate_distinct():
    items = ["supply and fix ceramic wall tile", "demolish existing brick wall"]
    dups = hksmm.find_duplicates(items)
    assert len(dups) == 0


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print("PASS", fn.__name__)
        except AssertionError as e:
            failed += 1
            print("FAIL", fn.__name__, "->", e)
        except Exception as e:
            failed += 1
            print("ERROR", fn.__name__, "->", repr(e))
    print(f"{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)

def test_classify_masonry():
    code, trade, _ = hksmm.classify_trade("Masonry wall in cement sand mortar 磚牆砌築")
    assert code == "MAS", code
    assert trade == "Masonry", trade


def test_classify_blockwork():
    code, _, _ = hksmm.classify_trade("Blockwork wall 100mm 砌塊牆")
    assert code == "MAS", code


def test_classify_door_and_ironmongery():
    code, _, _ = hksmm.classify_trade("Hollow core door with frame and ironmongery 空心木門連框及五金")
    assert code == "DOR", code


def test_classify_ceiling():
    code, _, _ = hksmm.classify_trade("Ceiling false ceiling with metal frame")
    assert code == "CEI", code


def test_demolition_outranks_material():
    """The verb wins: demolishing a brick wall is Demolition, not Masonry."""
    code, _, _ = hksmm.classify_trade("demolish existing brick wall 300mm thick")
    assert code == "DEM", code
    code_zh, _, _ = hksmm.classify_trade("拆卸現有磚牆300毫米厚")
    assert code_zh == "DEM", code_zh

def test_short_trade_names():
    """Short forms exist for every trade and stay genuinely short (table columns)."""
    from src import hksmm
    rows = hksmm._load_trades()
    assert len(rows) >= 40
    for r in rows:
        short = hksmm.short_trade(r["code"])
        assert short, r["code"]
        assert len(short) <= 22, (r["code"], short)
    assert hksmm.short_trade("EXC") == "Excavation"
    assert hksmm.short_trade("SUP") == "Sanitary Fittings"
    assert hksmm.short_trade("") == ""
    assert hksmm.short_trade("NOPE") == ""
