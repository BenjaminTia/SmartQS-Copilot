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

## Run your own copy

The app needs **no API key to work**. Parsing, the cost estimate, and all anomaly flags run entirely
locally and free. The only AI that touches an external service is the optional plain-language review,
which tries providers in order:

1. **Groq** (`GROQ_API_KEY`, `llama-3.3-70b-versatile`, free tier, ~1s)
2. **OpenRouter** (`OPENROUTER_API_KEY`, `nvidia/nemotron-3-nano-30b-a3b:free`)

- **Streamlit Cloud**: Manage app → Settings → Secrets, add the keys as TOML:
  `GROQ_API_KEY = "gsk-..."` and `OPENROUTER_API_KEY = "sk-or-..."`
- **Local**: export the env vars, or add the same lines to a local `.env`
- **Without keys**: the app silently falls back to a rule-based review. Nothing breaks.

Each review costs a fraction of a cent; the rest of the app costs nothing at all.
