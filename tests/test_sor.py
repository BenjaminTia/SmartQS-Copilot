"""Run C acceptance tests for src/sor.py and src/fairrate.py.
Run directly: python tests/test_sor.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from src import sor, fairrate


def test_lookup_returns_rate_for_known_item():
    row = sor.lookup("supply and fix high yield steel reinforcement bar")
    assert row is not None
    assert float(row["rate_hkd"]) > 0
    assert row["unit"]


def test_lookup_concrete_grade_30():
    row = sor.lookup("concrete grade 30 in columns")
    assert row is not None
    assert row["unit"] == "m3"
    assert float(row["rate_hkd"]) > 0


def test_lookup_unknown_returns_none():
    assert sor.lookup("quantum flux capacitor installation") is None


def test_csv_has_enough_rows():
    assert 25 <= len(sor.load_sor()) <= 40


def test_fairrate_positive_numbers_and_index_near_one():
    row = sor.lookup("emulsion painting")
    boq_rate = float(row["rate_hkd"])  # BOQ rate exactly matches the SoR demo rate
    result = fairrate.build_fair_rate("emulsion painting to internal walls", boq_rate, sor.load_sor())
    assert result["matched_sor"] is not None
    assert abs(result["project_rate_index"] - 1.0) < 1e-6
    assert result["adjusted_rate"] > 0
    assert result["total"] > 0
    for key in ("material", "labour", "plant", "overheads", "profit"):
        assert result["components"][key] > 0
    assert abs(result["total"] - sum(result["components"].values())) < 1e-6


def test_fairrate_no_match_flags_index_one():
    result = fairrate.build_fair_rate("some entirely unknown work item", 500.0, sor.load_sor())
    assert result["matched_sor"] is None
    assert result["project_rate_index"] == 1.0
    assert result["sor_rate"] is None
    assert result["total"] > 0
    assert any("match" in n.lower() for n in result["notes"])


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
