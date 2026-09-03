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

A Hong Kong quantity surveying workbench. Upload a Bill of Quantities and follow the money from the tender price all the way to the next payment claim: trade mapping and flags, transparent rate build-ups, a cashflow view, and Security of Payment documents that match the Cap. 652 rules.

Built for construction people, not as a demo toy. It started as an entry for the Smart QS Hackathon 2026 (Housing Bureau + Cyberport + HKU) and grew after talking to people who actually price and re-measure building works in Hong Kong.

## What it does (five steps)

1. **Upload.** Drop in a PDF, CSV or Excel BOQ. It handles messy real-world files: stray title lines, two header rows, merged section labels, item codes, and descriptions that mix English and Traditional Chinese. Try the sample BOQ button for a file with deliberately planted problems.
2. **Trade map and flags.** Every line is mapped to a trade (loosely HKSMM5), and flags cite the item, the number, and the reference it deviates from: odd rates, near-duplicate lines, trades with no items at all, bilingual mixed descriptions.
3. **Fair rate build-up.** When a rate looks off or an item is new, the app builds a transparent estimate: labour, material, plant, overheads and profit, anchored to ArchSD Schedule of Rates style figures, scaled by the project's own rate index. You see the arithmetic, not a verdict. The rates are a small indicative demo subset, not the official Schedule of Rates.
4. **Cashflow.** An S-curve of spend against the contract sum, with the months where a 60-day payment lag leaves a working capital gap. No AI involved, just the numbers.
5. **Security of Payment.** Generate a payment claim and a payment response that carry the content Cap. 652 expects, see the statutory deadlines (30 days to respond, 60 to pay, 28 to adjudicate), and paste in a subcontract to have it scanned for banned pay-when-paid clauses. This is a screening helper, not legal advice.

It ends with a plain-language review of the whole screening. The review is optional prose, not analysis; everything above it runs on rules and arithmetic that work offline with no API key.

## Run your own copy

The app needs **no API key to work**. Parsing, trade mapping, flags, rate build-ups, cashflow and the Cap. 652 documents all run locally. Only the closing plain-language review calls out, and it falls back gracefully:

1. OpenRouter free (`OPENROUTER_API_KEY`, e.g. `z-ai/glm-5.2:free`, then MiniMax and Gemma free models)
2. DeepSeek (`DEEPSEEK_API_KEY`, `deepseek-chat`, a fraction of a cent per review)
3. A rule-based review if no provider answers

Keys go in Streamlit secrets or a local `.env`. Groq and Google Gemini are coded but disabled until their keys work again (Groq's current key returns 403 on every model; see `src/llm.py` for the reasons).

## Layout

- `app.py` — the five-step Streamlit app
- `src/parser.py` — tolerant parsing (PDF, CSV, Excel, bilingual, merged cells)
- `src/hksmm.py` — trade taxonomy and mapping, missing-trade and duplicate scans
- `src/sor.py`, `src/fairrate.py` — indicative rate lookup and transparent build-ups
- `src/cashflow.py` — S-curve and payment-lag gap
- `src/sop652.py` — Security of Payment deadlines, claim/response documents, clause audit
- `src/rates.py`, `src/estimator.py`, `src/anomalies.py` — estimate rollup and flags
- `src/llm.py` — optional review chain
- `data/` — trade taxonomy and demo rates
- `samples/` — messy bilingual sample BOQs
- `tests/` — plain test suites, `python -m pytest tests/`

## What it will not claim

It does not measure work, certify payments, or replace a quantity surveyor. Flags are for a QS to review, rates are indicative, and nothing here is legal advice. The honest caveats are part of the point.
