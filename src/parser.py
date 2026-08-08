"""BOQ parser: CSV, Excel, and PDF to normalized item lists.
Handles: section, item ref, description, unit, qty, rate.
PDF parsing prefers detected tables and falls back to positioned words."""
import csv
import io
import os
import re

import fitz

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


def _flat_cell(value):
    """Collapse PDF cell line breaks and repeated whitespace."""
    return re.sub(r"\s+", " ", _clean(value)).strip()


def _is_pdf_header(cells):
    text = " ".join(_flat_cell(cell).lower() for cell in cells)
    hits = sum(word in text for word in ("item", "description", "unit", "quantity", "qty", "rate"))
    return hits >= 3 and "description" in text


def _is_pdf_footer(cells):
    text = " ".join(_flat_cell(cell) for cell in cells).strip()
    return bool(
        re.search(r"\bpage\s+\d+(?:\s+of\s+\d+)?\b", text, re.IGNORECASE)
        or text.lower().startswith("smartqs sample boq")
    )


def _pdf_record(cells):
    """Convert six extracted table cells into the public parser shape."""
    cells = [_flat_cell(cell) for cell in cells]
    if len(cells) < len(FIELDS):
        cells.extend([""] * (len(FIELDS) - len(cells)))
    if len(cells) > len(FIELDS):
        cells = cells[:2] + [" ".join(cells[2:-3])] + cells[-3:]
    if _is_pdf_header(cells) or _is_pdf_footer(cells):
        return None
    section, item, description, unit, qty, rate = cells[:6]
    unit = UNIT_MAP.get(unit.lower(), unit.lower())
    record = {
        "section": section,
        "item": item,
        "description": description,
        "unit": unit,
        "qty": _to_float(qty),
        "rate": _to_float(rate),
    }
    if not description or (record["qty"] is None and record["rate"] is None):
        return None
    return record


def _records_from_tables(document):
    records = []
    for page in document:
        try:
            finder = page.find_tables()
        except (AttributeError, RuntimeError, ValueError):
            continue
        for table in getattr(finder, "tables", []):
            for cells in table.extract():
                record = _pdf_record(cells or [])
                if record:
                    records.append(record)
    return records


def _line_groups(words, tolerance=3.0):
    """Group PyMuPDF words into visual lines in reading order."""
    lines = []
    for word in sorted(words, key=lambda w: (w[1], w[0])):
        y = (word[1] + word[3]) / 2
        if not lines or abs(lines[-1][0] - y) > tolerance:
            lines.append([y, [word]])
        else:
            lines[-1][1].append(word)
            count = len(lines[-1][1])
            lines[-1][0] = ((lines[-1][0] * (count - 1)) + y) / count
    return [sorted(line_words, key=lambda w: w[0]) for _, line_words in lines]


def _header_columns(lines):
    """Find column starts from a BOQ header line."""
    aliases = {
        "section": {"section"},
        "item": {"item", "ref"},
        "description": {"description", "details"},
        "unit": {"unit"},
        "qty": {"quantity", "qty"},
        "rate": {"rate"},
    }
    for index, words in enumerate(lines):
        found = {}
        for word in words:
            token = re.sub(r"[^a-z]", "", word[4].lower())
            for field, names in aliases.items():
                if token in names and field not in found:
                    found[field] = word[0]
        if len(found) >= 5 and "description" in found:
            if "section" not in found:
                found["section"] = min(word[0] for word in words)
            ordered = [found.get(field) for field in FIELDS]
            if all(value is not None for value in ordered):
                return index, ordered
    return None, None


def _records_from_words(document):
    """Parse pages by assigning positioned words to header-derived x bands."""
    records = []
    pending = None
    for page in document:
        lines = _line_groups(page.get_text("words"))
        header_index, starts = _header_columns(lines)
        if starts is None:
            continue
        # Header labels are left aligned at each column start. A small offset
        # keeps text touching a grid line in the column on its right.
        boundaries = [start - 2 for start in starts[1:]]
        for words in lines[header_index + 1:]:
            full_text = " ".join(word[4] for word in words)
            if _is_pdf_footer([full_text]) or _is_pdf_header([full_text]):
                continue
            cells = [[] for _ in FIELDS]
            for word in words:
                center = (word[0] + word[2]) / 2
                column = sum(center >= boundary for boundary in boundaries)
                cells[column].append(word[4])
            values = [" ".join(cell) for cell in cells]
            record = _pdf_record(values)
            if record:
                if pending:
                    records.append(pending)
                pending = record
            elif pending and values[2] and not values[1]:
                pending["description"] = f'{pending["description"]} {values[2]}'.strip()
        if pending:
            records.append(pending)
            pending = None
    return records


def parse_pdf(pdf_bytes_or_path):
    """Parse a BOQ PDF from bytes, a path, or a path-like object."""
    if isinstance(pdf_bytes_or_path, (str, os.PathLike)):
        document = fitz.open(os.fspath(pdf_bytes_or_path))
    else:
        document = fitz.open(stream=bytes(pdf_bytes_or_path), filetype="pdf")
    try:
        records = _records_from_tables(document)
        if records:
            return records
        return _records_from_words(document)
    finally:
        document.close()


def enrich(rows):
    """Attach matched rate-db key + reference rate to each item."""
    for r in rows:
        key, meta = match_rate(r["description"])
        r["rate_key"] = key
        r["ref_rate"] = meta["rate"] if meta else None
    return rows
