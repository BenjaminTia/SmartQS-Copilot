# Smart QS Copilot v2 — Build Plan (AI Builders Hackathon 2026)

Deadline: 16 Sep 2026, 11:00 GMT+8. Solo build, Streamlit + Python + free/cheap LLM chain (OpenRouter free → DeepSeek → rule-based). Research: `research/qs-construction-hk-research-report.md`.

## Product thesis (what v2 actually is)
v1 "checks a PDF". v2 treats the **BOQ as the hub of the post-award workflow**: money in HK construction is lost after award — re-measurement, variations, interim payment, SOP Cap. 652 compliance, cashflow gaps. One upload should take the user from **cost → compliance → cashflow → documents** in a single Hong-Kong-native flow.

## Demo arc (the one story the video tells)
1. Upload a deliberately messy, real-looking bilingual HK BOQ (merged cells, EN/中文, item codes).
2. Parser survives it (honest about limits) → HKSMM trade map + flags upgraded (missing trades, bilingual items, duplicates, outliers) [F4].
3. Each anomalous/new rate gets a **fair-rate build-up** vs ArchSD SoR, scaled by the BOQ's own rate index [F2].
4. S-curve cashflow forecast + 60-day working-capital gap months [F3].
5. Generate a **Cap. 652-compliant payment claim + response** with statutory deadlines (30/60/28 days) and audit an uploaded subcontract for banned pay-when-paid clauses [F1].

## Architecture (files)
- `src/llm.py` — DONE: multi-fallback chain (verified 10 Sep): OR free GLM-5.2 → MiniMax-M3 → Gemma-4-31B → DeepSeek chat → rule-based. Groq/Gemini disabled w/ reasons.
- `src/hksmm.py` (NEW) — trade taxonomy + fuzzy trade mapping + bilingual-item detection + missing-trade scan. Data: `data/hksmm_trades.csv`.
- `src/sor.py` (NEW) — ArchSD SoR mini-lookup (curated ~40-item subset of SOR2026 Vol.1/2 for demo, clearly labelled subset w/ source note) + project rate-index calc.
- `src/fairrate.py` (NEW) — rate build-up: labour + material + plant + OH&P anchored to SoR subset scaled by BOQ rate index.
- `src/cashflow.py` (NEW) — S-curve + monthly interim cashflow + 60-day gap months (pure pandas; plotly/altair at UI layer).
- `src/sop652.py` (NEW) — statutory deadline engine (30/60/28) from claim date; compliant claim/response document generators (template fill); pay-when-paid / conditional-payment clause auditor (regex fallback + optional LLM).
- `src/parser.py` — harden for messy bilingual real-world BOQs (merged cells, multi-header, item codes, 中文 descriptions).
- `app.py` — rebuild into the 5-step demo arc (tabs/steps); rule-based fallbacks everywhere so demo never breaks offline.
- `samples/` — add 2 messy real-style HK sample BOQs (bilingual).
- Tests: plain-assert `tests/test_*.py` runnable without pytest where possible.
- `README.md` — human, honest: what it does, what it refuses to claim.

## Grounding rules (never look obviously-AI)
- Every flag cites item + number + the HK reference it deviates from; show the work (build-up arithmetic, source of rule). Never claim detection accuracy. Never quote foreign/global rates. HK regime only (HKSMM5, NEC, SOP Cap. 652, ArchSD SoR/TPI). No em-dashes anywhere. Sources list in-app.

## Execution order (lh-harness rounds, Sol executor + auditor)
- Run A: data assets + `hksmm.py` (taxonomy, fuzzy map, bilingual scan) + tests
- Run B: `sop652.py` (dates engine + claim/response generators + clause audit) + tests
- Run C: `sor.py` + `fairrate.py` + `cashflow.py` + tests
- Run D: parser hardening + `app.py` 5-step UI + messy samples
- Run E: audit sweep, README/pitch, then manual end-to-end test by parent + GitHub push + submission copy
