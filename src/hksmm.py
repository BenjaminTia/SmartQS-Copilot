"""HKSMM-inspired trade classification helpers.

Small, honest utilities used to group BOQ line items into building trades
(loosely following the HKSMM5 trade structure for Hong Kong building works)
and to flag things a reviewer would notice: a whole trade missing, bilingual
mixed descriptions, and near-duplicate lines.

The taxonomy is a curated demo subset, not the full HKSMM. It exists to give
the app a Hong Kong native frame, not to replace a QS.
"""

import csv
import difflib
import os
import re
import unicodedata

_TRADES = None


def _load_trades():
    global _TRADES
    if _TRADES is not None:
        return _TRADES
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "..", "data", "hksmm_trades.csv")
    rows = []
    with open(path, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            row["keywords"] = [k.strip().lower() for k in row["keywords"].split(";") if k.strip()]
            rows.append(row)
    _TRADES = rows
    return rows


def _as_text(item):
    """Accept a plain string or a dict that carries a description field."""
    if isinstance(item, dict):
        for key in ("description", "desc", "item_description", "item desc"):
            if item.get(key):
                return str(item[key])
        return ""
    return str(item)


def _normalize(text):
    return re.sub(r"\s+", " ", text).strip().lower()


def _has_cjk(text):
    for ch in text:
        if unicodedata.name(ch, "").startswith("CJK"):
            return True
    return False


def classify_trade(description):
    """Best-guess trade for one line item.

    Returns (code, trade_en, score) where score is 0..1. Keyword hits are
    strong evidence; when nothing matches we fall back to fuzzy matching
    against the trade names themselves.
    """
    text = _as_text(description).lower()
    best = None
    best_hits = 0
    for row in _load_trades():
        hits = 0
        for kw in row["keywords"]:
            if kw in text:
                hits += 1
        if hits > best_hits:
            best_hits = hits
            best = row
    if best is not None:
        score = min(best_hits, 3) / 3.0
        return (best["code"], best["trade_en"], score)
    # fuzzy fallback against trade names
    names = [(r["code"], r["trade_en"], r["trade_en"].lower()) for r in _load_trades()]
    target = _normalize(text)
    best_name = None
    best_ratio = 0.0
    for code, en, low in names:
        ratio = difflib.SequenceMatcher(None, target, low).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_name = (code, en)
    if best_ratio >= 0.5:
        return (best_name[0], best_name[1], round(best_ratio, 2))
    return (None, "Unclassified", 0.0)


def scan_missing_trades(items, exclude=()):
    """Trades with zero keyword hits across the item set.

    Returns a list of flag dicts in the shape the app already uses for
    anomalies: severity, description, detail. Trades in 'exclude' are
    skipped, so a small demo BOQ is not flooded with noise.
    """
    rows = _load_trades()
    texts = [_normalize(_as_text(it)) for it in items]
    if not texts:
        return []
    joined = " ".join(texts)
    flags = []
    for row in rows:
        if row["code"] in exclude:
            continue
        hits = sum(1 for kw in row["keywords"] if kw in joined)
        if hits == 0:
            flags.append({
                "severity": "warning",
                "description": "Possible missing trade",
                "code": row["code"],
                "detail": f"No line items matched {row['trade_en']} ({row['trade_zh']}). Check scope.",
            })
    return flags


def detect_bilingual(text):
    """True when a description mixes English text with Chinese characters.

    Returns (is_bilingual, chinese_ratio). Pure Chinese or pure English
    descriptions are not flagged.
    """
    t = _as_text(text)
    cjk = sum(1 for ch in t if unicodedata.name(ch, "").startswith("CJK"))
    if cjk == 0:
        return (False, 0.0)
    letters = [ch for ch in t if ch.isalpha()]
    ratio = cjk / max(len(letters), 1)
    has_ascii = any(ch.isascii() and ch.isalpha() for ch in t)
    return (has_ascii, round(ratio, 3))


def find_duplicates(items, threshold=0.92):
    """Pairs of near-duplicate line items, judged on the description text.

    Returns a list of dicts: severity warning, description, detail naming
    the two items. O(n^2) over the cleaned descriptions, fine for BOQ-sized
    inputs.
    """
    cleaned = []
    for it in items:
        cleaned.append(_normalize(_as_text(it)))
    out = []
    n = len(cleaned)
    for i in range(n):
        for j in range(i + 1, n):
            if not cleaned[i] or not cleaned[j]:
                continue
            ratio = difflib.SequenceMatcher(None, cleaned[i], cleaned[j]).ratio()
            if ratio >= threshold:
                out.append({
                    "severity": "warning",
                    "description": "Possible duplicate item",
                    "detail": f"Items {i + 1} and {j + 1} look alike ({ratio:.0%} match): {cleaned[i][:60]} / {cleaned[j][:60]}",
                })
    return out
