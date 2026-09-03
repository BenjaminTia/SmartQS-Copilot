"""ArchSD Schedule of Rates style demo unit-rate lookup.

A small curated subset of unit rates for common Hong Kong building works,
inspired by the public Hong Kong Architectural Services Department (ArchSD)
Schedule of Rates for Building Works. ArchSD publishes its Schedule of Rates
as a reference for pricing building works in Hong Kong; this module carries a
hand-picked slice of that idea, for demo purposes only.

The figures here are indicative demo values, not the official current
Schedule of Rates. They are not pricing advice and must not be used for
tendering, estimating or payment. Any real figure needs the current official
SoR and a quantity surveyor.

Data lives in data/sor_demo.csv with columns: item, unit, rate_hkd, keywords
(keywords are semicolon separated).
"""

import csv
import os


def _as_float(value):
    if value is None or value == "":
        return 0.0
    return float(value)


def _default_csv_path():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "..", "data", "sor_demo.csv")


def _load_rows(path=None):
    path = path or _default_csv_path()
    rows = []
    with open(path, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            row["rate_hkd"] = _as_float(row.get("rate_hkd"))
            row["keywords"] = [k.strip().lower() for k in row.get("keywords", "").split(";") if k.strip()]
            rows.append(row)
    return rows


def _lookup_in(rows, description):
    """Best match by keyword hits; returns the row dict or None."""
    text = (description or "").lower()
    if not text:
        return None
    best = None
    best_hits = 0
    for row in rows:
        hits = sum(1 for kw in row["keywords"] if kw in text)
        if hits > best_hits:
            best_hits = hits
            best = row
    return best


class SorLookup:
    """Holds the demo SoR rows and finds the best match for a description."""

    def __init__(self, path=None):
        self.rows = _load_rows(path)

    def lookup(self, description):
        return _lookup_in(self.rows, description)

    def __len__(self):
        return len(self.rows)

    def __iter__(self):
        return iter(self.rows)


_CACHE = {}


def load_sor(path=None):
    """Return a cached SorLookup for the demo SoR CSV."""
    key = path or _default_csv_path()
    if key not in _CACHE:
        _CACHE[key] = SorLookup(key)
    return _CACHE[key]


def lookup(description, rows=None):
    """Best-match SoR row for one description, or None when nothing matches."""
    if rows is None:
        return load_sor().lookup(description)
    return _lookup_in(list(rows), description)


def project_rate_index(boq_items, lookup=None):
    """Full-BOQ project rate index: average BOQ rate / average matched SoR rate.

    boq_items is a list of dicts with 'description' and 'rate' keys, or a list
    of (description, rate) tuples. Only items that match a SoR row are used.
    Returns a dict with the index, the matched count and the two averages, so
    the arithmetic is visible. When nothing matches or the SoR total is zero,
    the index falls back to 1.0 and the notes say why.

    Caveat: BOQ rates must be converted to the same unit as the SoR row before
    calling, otherwise the ratio is meaningless.
    """
    sor = lookup or load_sor()
    boq_sum = 0.0
    sor_sum = 0.0
    matched = 0
    for it in boq_items or []:
        if isinstance(it, dict):
            desc = it.get("description") or it.get("item_description") or it.get("desc") or ""
            rate = it.get("rate") if it.get("rate") is not None else it.get("unit_rate")
        else:
            desc, rate = it[0], it[1]
        row = sor.lookup(desc)
        if row is None:
            continue
        boq_sum += _as_float(rate)
        sor_sum += _as_float(row["rate_hkd"])
        matched += 1
    if matched == 0 or sor_sum <= 0:
        return {
            "index": 1.0,
            "matched": 0,
            "boq_avg": None,
            "sor_avg": None,
            "notes": ["No matched items or zero SoR total; index set to 1.0."],
        }
    boq_avg = boq_sum / matched
    sor_avg = sor_sum / matched
    return {
        "index": round(boq_avg / sor_avg, 4),
        "matched": matched,
        "boq_avg": round(boq_avg, 2),
        "sor_avg": round(sor_avg, 2),
        "notes": [],
    }
