"""S-curve cashflow and interim payment gap helpers.

Simple, transparent S-curve (logistic shape) for spreading a contract sum
over months, plus a working-capital gap view that shows how much cash the
builder is out of pocket before payments land. Pure stdlib, no pandas needed.
"""

import math


def s_curve_cashflow(total_amount, duration_months, peak_month=None):
    """Spread total_amount over duration_months with a logistic S-curve.

    Returns a list of dicts, one per month (1-indexed), each with:
      month, cumulative_pct, monthly_pct, cumulative_amount, monthly_amount.

    The curve starts near zero, rises steepest around the midpoint, and the
    cumulative amount ends at exactly total_amount (100%). peak_month shifts
    the steepest part; by default that is the middle of the programme.
    """
    n = int(duration_months)
    total = float(total_amount or 0.0)
    if n <= 0 or total <= 0:
        return []

    if peak_month is None:
        midpoint = n / 2.0
    else:
        midpoint = float(peak_month)

    # Steepness scaled to the programme length so the S shape stays sensible
    # for short and long jobs alike.
    k = 6.0 / n

    raw = []
    for i in range(1, n + 1):
        raw.append(1.0 / (1.0 + math.exp(-k * (i - midpoint))))

    lo = raw[0]
    hi = raw[-1]
    span = hi - lo
    if span <= 0:
        frac = [1.0]
    else:
        frac = [(r - lo) / span for r in raw]

    months = []
    prev = 0.0
    for i, f in enumerate(frac, start=1):
        monthly_frac = f - prev
        months.append({
            "month": i,
            "cumulative_pct": round(f * 100.0, 2),
            "monthly_pct": round(monthly_frac * 100.0, 2),
            "cumulative_amount": round(f * total, 2),
            "monthly_amount": round(monthly_frac * total, 2),
        })
        prev = f

    # Normalisation already lands the last month on 1.0; nudge the final
    # monthly amount so all monthly values sum exactly to the total.
    months[-1]["cumulative_pct"] = 100.0
    months[-1]["cumulative_amount"] = round(total, 2)
    months[-1]["monthly_amount"] = round(
        total - sum(m["monthly_amount"] for m in months[:-1]), 2
    )
    months[-1]["monthly_pct"] = round(
        100.0 - sum(m["monthly_pct"] for m in months[:-1]), 2
    )
    return months


def _monthly_amounts(monthly_values):
    amounts = []
    for v in monthly_values or []:
        if isinstance(v, dict):
            amt = v.get("monthly_amount", v.get("amount", v.get("value", 0.0)))
        else:
            amt = v
        amounts.append(float(amt))
    return amounts


def interim_payment_gap(monthly_values, payment_lag_months=2):
    """Monthly working-capital gap view.

    monthly_values is the list returned by s_curve_cashflow, or any list of
    dicts carrying a 'monthly_amount' key, or a list of plain numbers.

    Assumes work is certified at each month end (certified = cumulative spend)
    and payments are released payment_lag_months after certification. The gap
    is cumulative spend minus cash received so far; a positive gap is the
    working capital the builder must carry that month.

    Returns a list of dicts, one per month, with:
      month, cumulative_spend, certified, paid, gap.
    """
    amounts = _monthly_amounts(monthly_values)
    n = len(amounts)
    if n == 0:
        return []
    lag = max(0, int(payment_lag_months))

    out = []
    cum = 0.0
    for i, amt in enumerate(amounts, start=1):
        cum += amt
        paid_idx = i - 1 - lag  # 0-based index of the certificate paid now
        paid = 0.0
        if paid_idx >= 0:
            paid = sum(amounts[: paid_idx + 1])
        gap = cum - paid
        out.append({
            "month": i,
            "cumulative_spend": round(cum, 2),
            "certified": round(cum, 2),
            "paid": round(paid, 2),
            "gap": round(max(0.0, gap), 2),
        })
    return out
