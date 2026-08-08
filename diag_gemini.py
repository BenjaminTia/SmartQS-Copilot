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

review, status = llm_review(len(rows), est["trades"], flags, est["grand_total"])
print("STATUS:", status)
print("REVIEW len:", len(review) if review else 0)
print("REVIEW:", (review or "")[:400])

# raw dump from Gemini
keys = _keys()
p = PROVIDERS[0]
prompt = "Write a 40 word plain text review. No markdown. No em-dashes."
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
    print("\nRAW RESPONSE (first 600):")
    print(raw[:600])
    data = json.loads(raw)
    msg = data["choices"][0]["message"]
    print("\nmessage keys:", list(msg.keys()))
    print("content:", (msg.get("content") or "")[:300])
    print("finish_reason:", data["choices"][0].get("finish_reason"))
    print("usage:", data.get("usage"))
except Exception as e:
    print("RAW CALL ERROR:", e)
