"""LLM layer: plain-language review of the BOQ analysis.
Provider: OpenRouter zero-cost free models. Primary is NVIDIA Nemotron 3 Nano
(30B MoE, ~10x faster on the free tier); Nemotron 3 Ultra (550B) as backup.
If all fail, the caller falls back to the rule-based review. The analysis itself
(parse, estimate, flags) is deterministic software; the LLM only writes prose."""
import json
import os
import ssl
import urllib.request

PROVIDERS = [
    {
        "name": "openrouter-nemotron-nano",
        "key_var": "OPENROUTER_API_KEY",
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "nvidia/nemotron-3-nano-30b-a3b:free",
    },
    {
        "name": "openrouter-nemotron-ultra",
        "key_var": "OPENROUTER_API_KEY",
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "nvidia/nemotron-3-ultra-550b-a55b:free",
    },
]


def _keys():
    """All candidate keys: Streamlit secrets, local .env, environment."""
    found = {}
    try:
        import streamlit as st
        if hasattr(st, "secrets"):
            for p in PROVIDERS:
                if p["key_var"] in st.secrets:
                    found[p["key_var"]] = st.secrets[p["key_var"]]
    except Exception:
        pass
    try:
        for line in open(r"C:\Users\Benjamin\AppData\Local\hermes\.env", encoding="utf-8", errors="ignore"):
            m = line.strip()
            if m and not m.startswith("#") and "=" in m:
                k, v = m.split("=", 1)
                found.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except Exception:
        pass
    for k in os.environ:
        found.setdefault(k, os.environ[k])
    return found


def _call(provider, key, prompt):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    payload = json.dumps({
        "model": provider["model"],
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 2048,
    }).encode()
    req = urllib.request.Request(
        provider["url"],
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    resp = json.loads(urllib.request.urlopen(req, timeout=90, context=ctx).read())
    return resp["choices"][0]["message"]["content"]


def llm_review(items_count, trades, flags, grand_total):
    flags_text = "\n".join(
        f"- [{f['severity']}] {f['description']}: {f['detail']}" for f in flags
    ) or "None"
    trades_text = ", ".join(f"{k} ~HK${v['amount']:,.0f}" for k, v in trades.items())
    prompt = (
        "You are a quantity surveying assistant reviewing an automated BOQ screening.\n"
        f"Items: {items_count}. Estimated total: HK${grand_total:,.0f} (reference-based).\n"
        f"Trades: {trades_text}.\n"
        f"Flags:\n{flags_text}\n"
        "Write a concise plain-language review for a non-expert project manager: "
        "1) is the estimate plausible, 2) which flags matter most and why, "
        "3) one concrete next step. Max 120 words. Plain text only. "
        "Never use em-dashes (the long dash character). "
        "Write amounts like 'HK$2,850' but keep the rest of the text plain."
    )
    keys = _keys()
    last_error = "no providers configured"
    for provider in PROVIDERS:
        key = keys.get(provider["key_var"], "")
        if not key:
            continue
        try:
            return _call(provider, key, prompt), f"llm_ok ({provider['name']})"
        except Exception as e:
            last_error = f"{provider['name']}: {str(e)[:120]}"
            continue
    return None, f"llm_unavailable ({last_error})"


def fallback_review(flags, grand_total):
    """Rule-based review used when no LLM provider is reachable."""
    if not flags:
        return (f"The estimate (HK${grand_total:,.0f}) raised no automatic flags. "
                "It still needs a QS eye for scope omissions and provisional sums.")
    crit = [f for f in flags if f["severity"] == "critical"]
    warn = [f for f in flags if f["severity"] == "warning"]
    head = "Critical issue" if len(crit) == 1 else "Critical issues"
    body = f"Estimate HK${grand_total:,.0f}. {head}: "
    body += "; ".join(f"{f['description']} ({f['detail']})" for f in crit[:3])
    if warn:
        body += f". Plus {len(warn)} warning(s), including {warn[0]['description']}."
    body += " Next step: verify the flagged rates and quantities against the tender drawings before pricing."
    return body
