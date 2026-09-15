"""Benchmark free OpenRouter models on the real plain-language-review prompt.

Measures latency + output shape (not just "does it answer") so the fallback
chain can be ordered fastest-usable-first. Run with the project venv:

    .venv\\Scripts\\python.exe bench_models.py
"""
import json
import ssl
import sys
import time
import urllib.request

sys.path.insert(0, ".")
from src.parser import parse_csv, enrich  # noqa: E402
from src.anomalies import detect  # noqa: E402
from src.estimator import estimate  # noqa: E402
from src.llm import _keys  # noqa: E402

rows = enrich(parse_csv(open("samples/sample_boq.csv", encoding="utf-8").read()))
flags = detect(rows)
est = estimate(rows)

flags_text = "\n".join(f"- [{f['severity']}] {f['description']}: {f['detail']}" for f in flags) or "None"
trades_text = ", ".join(f"{k} ~HK${v['amount']:,.0f}" for k, v in est["trades"].items())
prompt = (
    "You are a quantity surveying assistant reviewing an automated BOQ screening.\n"
    f"Items: {len(rows)}. Estimated total: HK${est['grand_total']:,.0f} (reference-based).\n"
    f"Trades: {trades_text}.\n"
    f"Flags:\n{flags_text}\n"
    "Write a concise plain-language review for a non-expert project manager: "
    "1) is the estimate plausible, 2) which flags matter most and why, "
    "3) one concrete next step. Max 120 words. Plain text only. "
    "Never use em-dashes. Write amounts like 'HK$2,850'."
)
keys = _keys()
key = keys.get("OPENROUTER_API_KEY", "")
url = "https://openrouter.ai/api/v1/chat/completions"
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

MODELS = [
    "google/gemma-4-26b-a4b-it:free",
    "inclusionai/ling-3.0-flash-sante:free",
    "inclusionai/ling-3.0-flash-fin:free",
    "nex-agi/nex-n2.5-mini:free",
    "poolside/laguna-xs-2.1:free",
    "poolside/laguna-s-2.1:free",
    "thinkingmachines/inkling-small:free",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "z-ai/glm-5.2:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "openrouter/free",
]

THINK_MARKERS = ("thinking process", "we need to", "let me think", "here's a thinking",
                 "first, i need", "okay, the user", "1.  **")

results = []
for model in MODELS:
    t0 = time.time()
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 600,
        "temperature": 0.4,
        "reasoning": {"exclude": True},
    }).encode()
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}",
                 "HTTP-Referer": "https://smartqs-copilot.streamlit.app",
                 "X-Title": "Smart QS Copilot", "User-Agent": "Mozilla/5.0"},
    )
    try:
        raw = urllib.request.urlopen(req, timeout=150, context=ctx).read().decode()
        dt = time.time() - t0
        data = json.loads(raw)
        ch = data["choices"][0]
        content = (ch["message"].get("content") or "").strip()
        thinky = any(m in content.lower() for m in THINK_MARKERS)
        verdict = "GOOD" if (150 <= len(content) <= 1600 and not thinky) else (
            "THINKING-TEXT" if thinky else f"SHORT({len(content)})")
        results.append((dt, model, len(content), verdict))
        print(f"{dt:6.1f}s  {model:56} len={len(content):5}  {verdict}")
        print(f"        {content[:150]}".replace("\n", " "))
    except Exception as e:
        dt = time.time() - t0
        print(f"{dt:6.1f}s  {model:56} ERROR {type(e).__name__}: {str(e)[:70]}")
    time.sleep(2)

print("\n=== ranked by latency (GOOD only) ===")
for dt, model, ln, verdict in sorted([r for r in results if r[3] == "GOOD"]):
    print(f"  {dt:6.1f}s  {model}  ({ln} chars)")
