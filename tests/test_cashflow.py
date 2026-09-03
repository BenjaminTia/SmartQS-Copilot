"""Run C acceptance tests for src/cashflow.py.
Run directly: python tests/test_cashflow.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from src import cashflow


def test_scurve_cumulative_reaches_100():
    months = cashflow.s_curve_cashflow(10_000_000, 12)
    assert len(months) == 12
    assert months[0]["cumulative_pct"] < months[-1]["cumulative_pct"]
    assert months[-1]["cumulative_pct"] == 100.0
    assert abs(sum(m["monthly_amount"] for m in months) - 10_000_000) < 1.0


def test_scurve_rises_steepest_mid():
    months = cashflow.s_curve_cashflow(1_000_000, 12)
    increments = [m["monthly_amount"] for m in months]
    peak = increments.index(max(increments)) + 1  # 1-based month
    assert 4 <= peak <= 9


def test_scurve_zero_duration_empty():
    assert cashflow.s_curve_cashflow(1000, 0) == []


def test_payment_gap_positive_mid_project():
    months = cashflow.s_curve_cashflow(10_000_000, 12)
    gaps = cashflow.interim_payment_gap(months, payment_lag_months=2)
    assert len(gaps) == 12
    mid_gaps = [g["gap"] for g in gaps if 4 <= g["month"] <= 9]
    assert any(g > 0 for g in mid_gaps)
    # no payment can land before the lag has passed
    assert gaps[0]["paid"] == 0.0
    assert gaps[1]["paid"] == 0.0


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
