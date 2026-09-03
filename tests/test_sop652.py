"""Run B acceptance tests for src/sop652.py. Run directly: python tests/test_sop652.py"""
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from src import sop652


def test_response_deadline_30_days():
    d = sop652.deadlines(date(2026, 9, 1))
    assert d["payment_response_deadline"] == date(2026, 10, 1), d
    assert d["payment_response_deadline"] == date(2026, 9, 1) + timedelta(days=30)


def test_payment_deadline_60_days():
    d = sop652.deadlines(date(2026, 9, 1))
    assert d["payment_deadline"] == date(2026, 10, 31), d
    assert d["payment_deadline"] == date(2026, 9, 1) + timedelta(days=60)


def test_adjudication_window_computed():
    d = sop652.deadlines(date(2026, 9, 1))
    assert d["adjudication_window_open"] == d["payment_deadline"]
    assert d["adjudication_window_close"] == d["payment_deadline"] + timedelta(days=28)
    assert d["adjudication_window_close"] == date(2026, 11, 28), d


def test_deadlines_accepts_iso_string():
    d = sop652.deadlines("2026-09-01")
    assert d["payment_response_deadline"] == date(2026, 10, 1)
    assert d["payment_deadline"] == date(2026, 10, 31)


def test_deadlines_accepts_datetime():
    from datetime import datetime
    d = sop652.deadlines(datetime(2026, 9, 1, 12, 30))
    assert d["claim_date"] == date(2026, 9, 1)


def test_claim_contains_amount_and_work():
    doc = sop652.payment_claim({
        "work_period": "1-31 Aug 2026",
        "work_description": "Installation of drywall partitions to floors 5-8",
        "amount_claimed": 285000.0,
        "basis_of_calculation": "Measured quantities x contract rates, less 10% retention",
    })
    text = doc["text"]
    assert "285,000.00" in text
    assert "Installation of drywall partitions" in text
    assert doc["amount_claimed"] == 285000.0
    assert "in_writing" in doc["mandatory"]
    assert "states_amount" in doc["mandatory"]


def test_claim_has_numbered_clauses():
    doc = sop652.payment_claim({
        "work_period": "Aug 2026",
        "work_description": "Ceiling grid works",
        "amount_claimed": 50000.0,
    })
    assert len(doc["clauses"]) >= 5
    assert doc["clauses"][0]["no"] == 1
    assert "1." in doc["text"]


def test_response_separates_admitted_vs_disputed():
    doc = sop652.payment_response({
        "work_period": "1-31 Aug 2026",
        "amount_claimed": 285000.0,
        "admitted_amount": 200000.0,
        "disputed_amount": 85000.0,
        "reasons": "Daywork sheets for week 3 not yet verified",
        "calculation": "Approved measured quantities x contract rates",
    })
    text = doc["text"]
    assert "200,000.00" in text          # admitted
    assert "85,000.00" in text           # disputed
    assert "Admitted amount" in text
    assert "Disputed amount" in text
    assert doc["admitted_amount"] == 200000.0
    assert doc["disputed_amount"] == 85000.0


def test_audit_catches_pay_when_paid():
    flags = sop652.scan_contract(
        "The subcontractor shall be paid only on a pay when paid basis from the employer."
    )
    assert len(flags) >= 1
    assert flags[0]["severity"] == "critical"
    assert "pay when paid" in flags[0]["description"].lower()
    assert flags[0]["excerpt"]


def test_audit_catches_chinese_pattern():
    flags = sop652.scan_contract(
        "付款安排：收妥款項後才付款予分判商。"
    )
    assert len(flags) >= 1
    assert flags[0]["severity"] == "critical"
    assert "收妥款項後才付款" in flags[0]["description"] or "收妥款項後才付款" in flags[0]["excerpt"]


def test_audit_catches_case_insensitive():
    flags = sop652.scan_contract("No payment shall be due: PAY WHEN CERTIFIED by the Architect.")
    assert len(flags) >= 1
    assert flags[0]["severity"] == "critical"


def test_audit_clean_text_no_flags():
    flags = sop652.scan_contract(
        "The contractor shall submit monthly applications for payment. "
        "Progress payments shall be made within 60 days of the payment claim."
    )
    assert flags == []


def test_audit_empty_input_no_flags():
    assert sop652.scan_contract("") == []
    assert sop652.scan_contract(None) == []


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
