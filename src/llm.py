"""LLM layer: DeepSeek plain-language review of the BOQ analysis.
Falls back to a rule-based summary when the API is unavailable (offline demo safety)."""
import json
import os
import urllib.request
import ssl


def _key():
    # Streamlit Cloud secrets first (deployed env)
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "DEEPSEEK_API_KEY" in st.secrets:
            return st.secrets["DEEPSEEK_API_KEY"]
    except Exception:
        pass
    try:
        for line in open(r"C:\Users\Benjamin\AppData\Local\hermes\.env", encoding="utf-8", errors="ignore"):
            if line.strip().startswith("DEEPSEEK_API_KEY="):
                return line.strip().split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return os.environ.get("DEEPSEEK_API_KEY", "")


def llm_review(items_count, trades, flags, grand_total, market_ctx=None):
    key = _key()
    if not key:
        return None, "llm_unavailable"
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
    payload = json.dumps({
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 300,
    }).encode()
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        req = urllib.request.Request(
            "https://api.deepseek.com/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        )
        resp = json.loads(urllib.request.urlopen(req, timeout=90, context=ctx).read())
        return resp["choices"][0]["message"]["content"], "llm_ok"
    except Exception as e:
        return None, f"llm_error: {str(e)[:120]}"


def fallback_review(flags, grand_total):
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
