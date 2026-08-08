import json
import ssl
import sys
import time
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
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "google/gemma-4-31b-it:free",
    "openai/gpt-oss-20b:free",
    "nvidia/nemotron-3-nano-30b-a3b:free",
]
for model in models:
    times = []
    lens = []
    for attempt in range(2):
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
        t0 = time.time()
        try:
            raw = urllib.request.urlopen(req, timeout=120, context=ctx).read().decode()
            dt = time.time() - t0
            data = json.loads(raw)
            content = data["choices"][0]["message"].get("content") or ""
            times.append(round(dt, 1))
            lens.append(len(content))
            quality = "OK" if len(content) > 150 else "SHORT"
            print(f"{model}  attempt{attempt+1}: {dt:.1f}s  len={len(content)}  {quality}")
        except Exception as e:
            print(f"{model}  attempt{attempt+1}: ERROR {str(e)[:90]}")
        time.sleep(3)
    if times:
        print(f"  -> median {sorted(times)[len(times)//2]}s, lens {lens}")
