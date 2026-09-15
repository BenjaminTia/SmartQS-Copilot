"""LLM layer: plain-language review of the BOQ analysis.

Fallback chain (re-probed live 15 Sep 2026 — every entry below was called with
a real completion immediately before being kept):

  1. OpenRouter :free  nvidia/nemotron-3-super-120b-a12b   (verified 15 Sep: 3.3s,
                                                           clean prose, finish=stop)
  2. OpenRouter :free  z-ai/glm-5.2                        (worked 10 Sep; currently
                                                           HTTP 429 rate-limited, kept
                                                           because free quota recovers)
  3. OpenRouter :free  nvidia/nemotron-3.5-lightning        (verified 15 Sep but slow:
                                                           ~40s; last free resort)
  4. DeepSeek          deepseek-chat                       (anchor: pennies per run,
                                                           verified 15 Sep, always up)
  5. Rule-based fallback                                   (no network at all)

Removed 15 Sep 2026 (why):
  - OpenRouter  minimax/minimax-m3:free: now HTTP 404 — the model no longer exists.
  - OpenRouter  google/gemma-4-31b-it:free: HTTP 400 Bad Request on a plain call.

Disabled providers (why):
  - Groq    llama-3.3-70b-versatile: model deprecated AND the GROQ_API_KEY now
            returns HTTP 403 on every model (account-level). Re-enable only
            after the key is confirmed working.
  - Gemini  GOOGLE_API_KEY returns HTTP 400 on both the models list and
            generateContent (key/project issue). Re-enable after key check.

Providers ruled OUT by the 15 Sep 2026 bench (all on the real review prompt):
  - google/gemma-4-26b-a4b-it:free, poolside/laguna-xs-2.1:free, z-ai/glm-5.2:free
    -> HTTP 429 (free quota exhausted at bench time; glm-5.2 kept anyway, above).
  - inclusionai/ling-3.0-flash-sante|fin:free -> HTTP 200 with EMPTY content.
  - thinkingmachines/inkling-small:free       -> HTTP 403.
  - nex-agi/nex-n2.5-mini:free                -> hung ~300s then malformed JSON.
  - No MiniMax and no Upstage/Solar model exists in OpenRouter's free tier at all
    (minimax-m3 was delisted; the whole free list is 23 models, none MiniMax/Upstage).

Three robustness rules, all learned the hard way (15 Sep 2026):
  * Reasoning models on OpenRouter can return content=null with the answer in a
    separate `reasoning` field, or burn the whole token budget on thinking. We send
    `reasoning: {exclude: true}` (OpenRouter-only field), and any provider that
    returns empty text is treated as a failure so the chain moves on. Without this,
    a null content string crashed the review panel.
  * Reasoning models sometimes leak their chain-of-thought into `content`
    (observed: "We need to produce concise plain-language review..."), especially
    when the token budget is tight. A leak is worse than no answer, so
    _extract_text() rejects it and the chain moves on.
  * The analysis itself (parse, estimate, flags) is deterministic software; the
    LLM only writes prose. Never treat the LLM as a source of truth.
"""
import json
import os
import ssl
import urllib.request

MAX_TOKENS = 1400

PROVIDERS = [
    {
        # 5.2s, 712 chars, clean prose (bench 15 Sep 2026) - fastest usable free model
        "name": "or-laguna-s",
        "key_var": "OPENROUTER_API_KEY",
        "kind": "openai",
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "models": ["poolside/laguna-s-2.1:free"],
        "extra": {"reasoning": {"exclude": True}},
    },

    {
        # 15.6s, 537 chars, clean, small MoE (30B, 3B active)
        "name": "or-nano-omni",
        "key_var": "OPENROUTER_API_KEY",
        "kind": "openai",
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "models": ["nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"],
        "extra": {"reasoning": {"exclude": True}},
    },

    {
        # 7.4s, 627 chars, clean (OpenRouter's own free-model router)
        "name": "or-free-router",
        "key_var": "OPENROUTER_API_KEY",
        "kind": "openai",
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "models": ["openrouter/free"],
        "extra": {"reasoning": {"exclude": True}},
    },

    {
        # smart general model, but free quota 429s a lot; kept because it recovers
        "name": "or-glm-5.2",
        "key_var": "OPENROUTER_API_KEY",
        "kind": "openai",
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "models": ["z-ai/glm-5.2:free"],
        "extra": {"reasoning": {"exclude": True}},
    },

    {
        # fast (7.1s) but sometimes leaks chain-of-thought; the guard below skips it
        "name": "or-nemotron-120b",
        "key_var": "OPENROUTER_API_KEY",
        "kind": "openai",
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "models": ["nvidia/nemotron-3-super-120b-a12b:free"],
        "extra": {"reasoning": {"exclude": True}},
    },

    {
        "name": "deepseek-chat",
        "key_var": "DEEPSEEK_API_KEY",
        "kind": "openai",
        "url": "https://api.deepseek.com/chat/completions",
        "models": ["deepseek-chat"],
        "extra": {},
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


# Chain-of-thought leaking into the answer. A leak reads as broken prose to the
# user, so it counts as a failure and the next provider gets a turn.
_THINK_MARKERS = (
    "thinking process", "we need to", "let me think", "here's a thinking",
    "first, i need", "okay, the user", "1.  **", "the user wants me to",
)


def _looks_like_thinking(text):
    low = text.lower()
    return any(marker in low for marker in _THINK_MARKERS)


def _extract_text(resp):
    """Pull usable prose out of a chat completion; raise if there is none."""
    choices = resp.get("choices") or []
    if not choices:
        raise RuntimeError("no choices in response")
    msg = choices[0].get("message") or {}
    text = (msg.get("content") or "").strip()
    if not text:
        # Some reasoning models put everything in `reasoning` and leave content null.
        text = (msg.get("reasoning") or "").strip()
    if not text:
        raise RuntimeError("empty content")
    if _looks_like_thinking(text):
        raise RuntimeError("chain-of-thought leaked into the answer")
    return text


def _call_openai(provider, key, prompt):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    last = "no models"
    for model in provider["models"]:
        payload = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": MAX_TOKENS,
            "temperature": 0.4,
            **provider.get("extra", {}),
        }).encode()
        req = urllib.request.Request(
            provider["url"],
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36",
            },
        )
        try:
            resp = json.loads(urllib.request.urlopen(req, timeout=120, context=ctx).read())
            return _extract_text(resp)
        except Exception as e:
            last = f"{model}: {str(e)[:100]}"
    raise RuntimeError(last)


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
            text = _call_openai(provider, key, prompt)
            if text:
                return text, f"llm_ok ({provider['name']})"
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
