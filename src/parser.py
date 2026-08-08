"""BOQ parser: CSV/Excel -> normalized item list.
Handles: section, item ref, description, unit, qty, rate.
CSV/Excel native; PDF text via simple line parsing (MVP)."""
import csv
import io
import re

from .rates import match_rate

FIELDS = ["section", "item", "description", "unit", "qty", "rate"]

# normalize units
UNIT_MAP = {
    "m2": "m2", "sq.m": "m2", "sqm": "m2", "square metre": "m2", "square metres": "m2",
    "m3": "m3", "cu.m": "m3", "cum": "m3", "cubic metre": "m3",
    "m": "m", "lm": "m", "lin.m": "m", "linear metre": "m", "linear metres": "m",
    "kg": "kg", "t": "kg", "tonne": "kg", "tonnes": "kg",
    "no.": "no.", "no": "no.", "nr": "no.", "each": "no.", "ea": "no.",
    "ls": "ls", "l.s.": "ls", "lump sum": "ls", "sum": "ls",
}


def _clean(x):
    if x is None:
        return ""
    return str(x).strip()


def _to_float(x):
    x = _clean(x).replace(",", "").replace("$", "").replace("HK$", "")
    if not x:
        return None
    try:
        return float(x)
    except ValueError:
        return None


def parse_csv(text: str):
    rows = []
    reader = csv.reader(io.StringIO(text))
    header = next(reader, None)
    if header is None:
        return rows
    # map header names (case-insensitive) to fields
    idx = {}
    for i, h in enumerate(header):
        key = h.strip().lower()
        for f in FIELDS:
            if f in key or key in f:
                idx[f] = i
                break
    if "description" not in idx:
        # try positional fallback
        idx = {f: i for i, f in enumerate(FIELDS[: len(header)])}
    for line in reader:
        if len(line) < 2:
            continue
        rec = {
            "section": _clean(line[idx["section"]] if "section" in idx else ""),
            "item": _clean(line[idx["item"]] if "item" in idx else ""),
            "description": _clean(line[idx["description"]] if "description" in idx else ""),
            "unit": _clean(line[idx["unit"]] if "unit" in idx else ""),
            "qty": _to_float(line[idx["qty"]] if "qty" in idx else ""),
            "rate": _to_float(line[idx["rate"]] if "rate" in idx else ""),
        }
        if not rec["description"] and rec["item"]:
            rec["description"] = rec["item"]
        rec["unit"] = UNIT_MAP.get(rec["unit"].lower(), rec["unit"].lower())
        if rec["description"]:
            rows.append(rec)
    return rows


def parse_pdf_text(text: str):
    """MVP: best-effort parse of plain-text BOQ lines like:
    'A1  Excavation for foundation (machine dig)  350  m3  340.00'"""
    rows = []
    pat = re.compile(
        r"^\s*([A-Z]{1,3}\d{1,4})?\s*(.+?)\s+([\d,]+(?:\.\d+)?)\s+([A-Za-z.]+)\s+([\d,]+(?:\.\d+)?)\s*$"
    )
    for line in text.splitlines():
        m = pat.match(line)
        if not m:
            continue
        item, desc, qty, unit, rate = m.groups()
        rows.append({
            "section": "", "item": (item or "").strip(), "description": desc.strip(),
            "unit": UNIT_MAP.get(unit.lower(), unit.lower()),
            "qty": _to_float(qty), "rate": _to_float(rate),
        })
    return rows


def enrich(rows):
    """Attach matched rate-db key + reference rate to each item."""
    for r in rows:
        key, meta = match_rate(r["description"])
        r["rate_key"] = key
        r["ref_rate"] = meta["rate"] if meta else None
    return rows
