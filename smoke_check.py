"""End-to-end smoke check: exercises every pipeline stage the app uses.

Run:  .venv\\Scripts\\python.exe smoke_check.py
Prints PASS/FAIL per stage per sample; any traceback means a real bug.
"""
import os
import sys
import traceback
from datetime import date

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO)

from src.parser import parse_csv, parse_excel, parse_pdf, parse_pdf_text, enrich  # noqa: E402
from src.estimator import estimate  # noqa: E402
from src.anomalies import detect  # noqa: E402
from src import hksmm, sor, fairrate, sop652  # noqa: E402
from src.cashflow import interim_payment_gap, s_curve_cashflow  # noqa: E402
from src.llm import fallback_review, llm_review  # noqa: E402

FAILURES = []


def build_flags(rows):
    """Mirror of app._build_flags so the smoke test covers the same path."""
    rows_by_item = {r["item"]: r for r in rows if r.get("item")}
    flags = list(detect(rows))
    flags += hksmm.scan_missing_trades(rows)
    flags += hksmm.find_duplicates(rows)
    for r in rows:
        is_bi, ratio = hksmm.detect_bilingual(r["description"])
        if is_bi:
            flags.append({
                "severity": "info", "type": "bilingual", "item": r["item"],
                "description": "Bilingual description (English + Chinese)",
                "detail": f"mixes EN/ZH (ratio {ratio:.0%})",
            })
    for f in flags:
        r = rows_by_item.get(f.get("item"))
        f.setdefault("number", None)
        f.setdefault("reference", None)
        if r is not None and f.get("type") == "rate":
            f["number"] = r.get("rate")
            f["reference"] = r.get("ref_rate")
    return flags


def stage(label, fn):
    try:
        out = fn()
        print(f"   PASS  {label}")
        return out
    except Exception as e:
        print(f"   FAIL  {label}: {type(e).__name__}: {e}")
        FAILURES.append((label, traceback.format_exc()))
        return None


def run(name, rows):
    print(f"\n=== {name} ===")
    if not rows:
        print("   FAIL  parse returned no rows")
        FAILURES.append((f"{name}:parse-empty", "no rows"))
        return
    rows = enrich(rows)
    est = stage("estimate", lambda: estimate(rows))
    flags = stage("flags", lambda: build_flags(rows))
    sor_lookup = stage("sor.load", sor.load_sor)
    proj_index = stage("sor.project_rate_index", lambda: sor.project_rate_index(rows))
    stage("hksmm.classify all rows", lambda: [hksmm.classify_trade(r["description"]) for r in rows])

    if est and proj_index:
        rate_flags = [f for f in (flags or []) if f.get("type") == "rate"]
        pick = rows[0]
        for r in rows:
            if r["item"] in {f.get("item") for f in rate_flags}:
                pick = r
                break
        stage("fairrate.build_fair_rate", lambda: fairrate.build_fair_rate(
            pick["description"], pick["rate"], sor_lookup,
            project_index=proj_index["index"]))

    if est:
        curve = stage("cashflow.s_curve (12m)", lambda: s_curve_cashflow(est["grand_total"], 12))
        if curve:
            stage("cashflow.interim_gap", lambda: interim_payment_gap(curve, payment_lag_months=2))

    stage("sop652.deadlines", lambda: sop652.deadlines(date.today()))
    stage("sop652.payment_claim", lambda: sop652.payment_claim({
        "claimant": "the contractor", "respondent": "the employer",
        "contract_ref": "REF", "claim_number": "1", "work_period": "Aug 2026",
        "work_description": "Measured work per the BOQ.", "amount_claimed": 1000.0,
        "basis_of_calculation": "quantities x rates",
    }))
    stage("sop652.payment_response", lambda: sop652.payment_response({
        "claimant": "the contractor", "respondent": "the employer",
        "contract_ref": "REF", "claim_number": "1", "work_period": "Aug 2026",
        "work_description": "work", "amount_claimed": 1000.0,
        "basis_of_calculation": "q x r", "admitted_amount": 900.0,
        "disputed_amount": 100.0, "reasons": "part measured short",
        "calculation": "900 admitted",
    }))
    stage("sop652.scan_contract (EN pay-when-paid)",
          lambda: sop652.scan_contract("Payment to the subcontractor is conditional upon "
                                       "receipt of payment from the employer."))
    stage("sop652.scan_contract (ZH pay-when-paid)",
          lambda: sop652.scan_contract("分包商須待僱主付款後方可獲支付款項。"))
    stage("review (rule-based)", lambda: fallback_review(flags or [], est["grand_total"]) if est else None)
    if est:
        stage("review (llm chain)", lambda: llm_review(len(rows), est["trades"], flags or [], est["grand_total"]))


def main():
    s = os.path.join(REPO, "samples")
    t = os.path.join(REPO, "tests", "fixtures")
    cases = [
        ("sample_boq_messy.csv", os.path.join(s, "sample_boq_messy.csv"), lambda p: parse_csv(open(p, encoding="utf-8", errors="ignore").read())),
        ("sample_boq.csv", os.path.join(s, "sample_boq.csv"), lambda p: parse_csv(open(p, encoding="utf-8", errors="ignore").read())),
        ("sample_boq_messy.xlsx", os.path.join(s, "sample_boq_messy.xlsx"), lambda p: parse_excel(open(p, "rb").read())),
        ("boq_community_hall.pdf", os.path.join(s, "boq_community_hall.pdf"), lambda p: parse_pdf(open(p, "rb").read())),
        ("tests/fixtures/sample_boq.pdf", os.path.join(t, "sample_boq.pdf"), lambda p: parse_pdf(open(p, "rb").read())),
    ]
    for name, path, fn in cases:
        if not os.path.exists(path):
            print(f"\n=== {name} ===\n   SKIP (missing)")
            continue
        try:
            rows = fn(path)
        except Exception as e:
            print(f"\n=== {name} ===\n   FAIL  parse: {type(e).__name__}: {e}")
            FAILURES.append((f"{name}:parse", traceback.format_exc()))
            continue
        run(name, rows)

    print("\n" + "=" * 70)
    if FAILURES:
        print(f"{len(FAILURES)} FAILURE(S):")
        for label, tb in FAILURES:
            print(f"\n--- {label} ---\n{tb}")
        sys.exit(1)
    print("all stages passed")


if __name__ == "__main__":
    main()
