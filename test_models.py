import json
import ssl
import sys
import urllib.request

sys.path.insert(0, ".")
from src.parser import parse_csv, enrich
from src.anomalies import detect
from src.estimator import estimate
from src.llm import _keys

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

models = [
    "openrouter/free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "google/gemma-4-31b-it:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
]
for model in models:
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 2048,
    }).encode()
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}",
                 "HTTP-Referer": "https://smartqs-copilot.streamlit.app", "X-Title": "Smart QS Copilot"},
    )
    try:
        raw = urllib.request.urlopen(req, timeout=90, context=ctx).read().decode()
        data = json.loads(raw)
        msg = data["choices"][0]["message"]
        content = msg.get("content") or ""
        fr = data["choices"][0].get("finish_reason")
        print(f"=== {model}")
        print(f"  len={len(content)} finish={fr}")
        print(f"  {content[:220]}")
    except Exception as e:
        print(f"=== {model} ERROR: {str(e)[:160]}")
