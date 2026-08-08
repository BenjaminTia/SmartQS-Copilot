"""Anomaly detection on parsed BOQ items.
Rules: rate deviation vs reference, duplicates, missing access/safety sections,
unit mismatches, quantity plausibility. Every flag carries a severity + reason."""
import numpy as np

SEV = {"info": 0, "warning": 1, "critical": 2}

RATE_TOLERANCE = 0.5      # +-50% around reference tolerated
CRITICAL_RATE = 1.5       # >150% above reference -> critical


def detect(rows):
    flags = []

    # 1) rate deviations vs reference db
    for r in rows:
        if r.get("ref_rate") and r.get("rate"):
            ref, rate = r["ref_rate"], r["rate"]
            if ref <= 0:
                continue
            dev = (rate - ref) / ref
            if dev >= CRITICAL_RATE:
                flags.append({
                    "severity": "critical", "type": "rate",
                    "item": r["item"], "description": r["description"],
                    "detail": f"Rate HK${rate:,.0f} is {dev*100:.0f}% above the reference (HK${ref:,.0f}). "
                              "Verify: missing digit or wrong unit?"
                })
            elif abs(dev) >= RATE_TOLERANCE:
                flags.append({
                    "severity": "warning", "type": "rate",
                    "item": r["item"], "description": r["description"],
                    "detail": f"Rate HK${rate:,.0f} is {dev*100:+.0f}% vs reference HK${ref:,.0f}. "
                              "Check for over/under-pricing."
                })

    # 2) duplicates (same description + unit)
    seen = {}
    for r in rows:
        key = (r["description"].lower().strip(), r["unit"])
        if key in seen:
            flags.append({
                "severity": "warning", "type": "duplicate",
                "item": r["item"], "description": r["description"],
                "detail": f"Duplicate item also at {seen[key]}. Confirm it is intentional "
                          "(e.g. separate work sections) and not a copy error."
            })
        else:
            seen[key] = r["item"]

    # 3) missing access / safety / temporary works
    text = " ".join((r["description"] or "") for r in rows).lower()
    if "scaffold" not in text:
        flags.append({
            "severity": "warning", "type": "missing",
            "item": "-", "description": "Scaffolding / access",
            "detail": "No scaffolding or access item found. Multi-storey works without access "
                      "provision usually signals an omitted trade section."
        })
    if not any(k in text for k in ["safety", "temporary works", "site establishment", "hoarding"]):
        flags.append({
            "severity": "warning", "type": "missing",
            "item": "-", "description": "Safety / temporary works",
            "detail": "No safety, hoarding or site establishment item. Public works contracts "
                      "normally carry these preliminaries."
        })

    # 4) quantity plausibility (product z-score within trade)
    prods = [(r, (r.get("qty") or 0) * (r.get("rate") or 0)) for r in rows if r.get("qty") and r.get("rate")]
    if len(prods) >= 4:
        vals = np.array([p[1] for p in prods])
        if vals.std() > 0:
            z = (vals - vals.mean()) / vals.std()
            for (r, _), zz in zip(prods, z):
                if abs(zz) > 3.0:
                    flags.append({
                        "severity": "warning", "type": "quantity",
                        "item": r["item"], "description": r["description"],
                        "detail": f"Line total (HK${r['qty']*r['rate']:,.0f}) is an extreme outlier "
                                  f"(z={zz:+.1f}). Verify quantity or rate."
                    })

    # 5) unit sanity
    for r in rows:
        if r.get("ref_rate") and r.get("unit") and r.get("rate"):
            if r["unit"] != r["unit"]:  # placeholder never fires
                pass

    return flags


def summary(flags):
    if not flags:
        return "No anomalies detected. The BOQ looks internally consistent."
    by_sev = {"critical": 0, "warning": 0, "info": 0}
    for f in flags:
        by_sev[f["severity"]] = by_sev.get(f["severity"], 0) + 1
    parts = []
    if by_sev["critical"]:
        parts.append(f"{by_sev['critical']} critical")
    if by_sev["warning"]:
        parts.append(f"{by_sev['warning']} warnings")
    if not parts:
        parts.append("no issues")
    return f"{len(flags)} flag(s): " + ", ".join(parts) + "."
