import json
import ssl
import sys
import urllib.request

sys.path.insert(0, ".")
from src.parser import parse_csv, enrich
from src.anomalies import detect
from src.estimator import estimate
from src.llm import PROVIDERS, _keys, llm_review

rows = enrich(parse_csv(open("samples/sample_boq.csv", encoding="utf-8").read()))
flags = detect(rows)
est = estimate(rows)

# rebuild the exact real prompt
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
    "Never use em-dashes (the long dash character). "
    "Write amounts like 'HK$2,850' but keep the rest of the text plain."
)
print("PROMPT len:", len(prompt))

p = PROVIDERS[0]
keys = _keys()
payload = json.dumps({"model": p["model"], "messages": [{"role": "user", "content": prompt}], "max_tokens": 300}).encode()
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
req = urllib.request.Request(
    p["url"], data=payload,
    headers={"Content-Type": "application/json", "Authorization": f"Bearer {keys.get('GOOGLE_API_KEY','')}"},
)
try:
    raw = urllib.request.urlopen(req, timeout=90, context=ctx).read().decode()
    print("RAW len:", len(raw))
    data = json.loads(raw)
    msg = data["choices"][0]["message"]
    print("finish_reason:", data["choices"][0].get("finish_reason"))
    print("usage:", data.get("usage"))
    print("message keys:", list(msg.keys()))
    print("content len:", len(msg.get("content") or ""))
    print("content:", (msg.get("content") or "")[:500])
except Exception as e:
    print("RAW CALL ERROR:", e)
