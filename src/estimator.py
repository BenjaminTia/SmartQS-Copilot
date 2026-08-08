"""Estimation engine: trade rollup + preliminaries + contingency."""
from collections import defaultdict

CONTINGENCY = 0.05
PRELIMINARIES = 0.08  # site establishment etc., reference only


def estimate(rows):
    trades = defaultdict(lambda: {"qty": 0.0, "amount": 0.0, "count": 0})
    total = 0.0
    for r in rows:
        qty, rate = r.get("qty") or 0, r.get("rate") or 0
        amt = qty * rate
        section = r.get("section") or "Unallocated"
        if not section.strip():
            section = "Unallocated"
        trades[section]["qty"] += qty
        trades[section]["amount"] += amt
        trades[section]["count"] += 1
        total += amt

    prelim = total * PRELIMINARIES
    contingency_amt = (total + prelim) * CONTINGENCY
    grand = total + prelim + contingency_amt

    return {
        "trades": {k: {"amount": v["amount"], "count": v["count"]} for k, v in trades.items()},
        "items_total": total,
        "preliminaries": prelim,
        "contingency": contingency_amt,
        "grand_total": grand,
        "confidence": "Reference-based estimate; treat as a screening figure (+-20%), not a tender price.",
    }
