import sys
sys.path.insert(0, ".")
from src.parser import parse_csv, parse_pdf, enrich
from src.anomalies import detect
from src.estimator import estimate

# 1) new community-hall PDF
rows = enrich(parse_pdf("samples/boq_community_hall.pdf"))
print("PDF items:", len(rows))
for r in rows[:4]:
    print("  ", r["item"], "|", r["description"][:44], "|", r["unit"], "|", r["qty"], "|", r["rate"])
flags = detect(rows)
print("FLAGS:", len(flags))
for f in flags:
    print("  [%s] %s: %s | %s" % (f["severity"], f["type"], f["item"] or f["description"], f["detail"][:80]))
est = estimate(rows)
print("grand total: HK${:,.0f}".format(est["grand_total"]))
print()
# 2) regression: demo CSV + old PDF fixture still parse
demo = enrich(parse_csv(open("samples/sample_boq.csv", encoding="utf-8").read()))
print("demo CSV items:", len(demo), "| flags:", len(detect(demo)))
old = enrich(parse_pdf("tests/fixtures/sample_boq.pdf"))
print("old fixture PDF items:", len(old), "| flags:", len(detect(old)))
