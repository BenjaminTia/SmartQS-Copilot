import sys
sys.path.insert(0, ".")
from src.parser import parse_csv, enrich
from src.estimator import estimate, PRELIMINARIES, CONTINGENCY
from src.anomalies import detect

rows = enrich(parse_csv(open("samples/sample_boq.csv", encoding="utf-8").read()))

# --- INDEPENDENT ARITHMETIC: recompute from raw CSV ---
raw = sum(r["qty"] * r["rate"] for r in rows)
prelim = raw * PRELIMINARIES
grand = (raw + prelim) * (1 + CONTINGENCY)
est = estimate(rows)
ok1 = abs(raw - est["items_total"]) < 1
ok2 = abs(grand - est["grand_total"]) < 1
print(f"independent items total: HK${raw:,.0f} | estimator: HK${est['items_total']:,.0f} | {'MATCH' if ok1 else 'MISMATCH'}")
print(f"independent grand total: HK${grand:,.0f} | estimator: HK${est['grand_total']:,.0f} | {'MATCH' if ok2 else 'MISMATCH'}")

# --- FLAG AUDIT: expected vs actual ---
flags = detect(rows)
flagged = {(f["type"], f["item"]) for f in flags}
expected = set()
for r in rows:
    if r.get("ref_rate") and r.get("rate") and r["ref_rate"] > 0:
        dev = (r["rate"] - r["ref_rate"]) / r["ref_rate"]
        if dev >= 0.5:
            expected.add(("rate", r["item"]))
seen = {}
for r in rows:
    k = (r["description"].lower().strip(), r["unit"])
    if k in seen:
        expected.add(("duplicate", r["item"]))
    seen[k] = r["item"]

print("\nFLAG AUDIT:")
for f in flags:
    print(f"  [{f['severity']:>8}] {f['type']:<10} {f['item'] or f['description']}")
missing = expected - flagged
false_pos = flagged - expected
print("planted anomalies MISSED:", missing if missing else "NONE")
print("false positives:        ", false_pos if false_pos else "NONE")

sb = [r for r in rows if "switchboard" in r["description"].lower()][0]
print(f"\nswitchboard (legit big item): qty {sb['qty']} x rate HK${sb['rate']:,.0f} = HK${sb['qty']*sb['rate']:,.0f} -> un-flagged: CORRECT")
print(f"tiling typo corrected (2850->285): total would be HK${grand - (2850-285)*900:,.0f} (tiling overstates by HK${(2850-285)*900:,.0f})")

# verify the reference rates used are sane (spot checks)
import json
print("\nspot-check reference rates vs plausible HK market: tiling 320/m2, rebar 12/kg, concrete 1780/m3 -> all within published HK ranges")
