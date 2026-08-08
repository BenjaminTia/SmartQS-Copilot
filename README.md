---
title: Smart QS Copilot
emoji: 🏗️
colorFrom: blue
colorTo: red
sdk: streamlit
sdk_version: 1.61.1
app_file: app.py
pinned: false
---

# Smart QS Copilot

AI screening for Bills of Quantities: upload a BOQ (PDF, CSV, Excel), get a trade-by-trade cost estimate and anomaly flags against HK construction reference rates, plus a plain-language review.

Built for the Smart QS Hackathon 2026 (Housing Bureau + Cyberport + HKU).

- Structure-aware PDF parsing (multi-page tables, repeated headers, footers)
- Trade rollup with preliminaries and contingency (reference-based screening, not pricing advice)
- Anomaly detection: rate deviations, duplicates, missing safety/access sections, quantity outliers
- AI plain-language review (DeepSeek)

Try the sample BOQ for a one-click demo: it contains deliberately planted errors, and every one gets caught.
