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


# Column header aliases used to locate the real header row among junk rows and
# multiple header rows. More specific labels are listed first so a header like
# "Item Description" lands on description, not item, and "Unit Rate" lands on
# rate, not unit.
_HEADER_ALIASES = [
    ("description", ["item description", "description of works", "description of work",
                     "description", "particulars", "details"]),
    ("rate", ["rate (hk$)", "rate hk$", "unit rate", "unit price", "rate", "price"]),
    ("qty", ["quantity", "quantities", "qty"]),
    ("unit", ["unit"]),
    ("section", ["work section", "trade section", "section", "trade", "division"]),
    ("item", ["item code", "item no", "item ref", "item", "ref", "code"]),
]


def _match_header_field(header_cell):
    """Map one header cell to a BOQ field name, or None when it matches none."""
    key = _clean(header_cell).lower()
    if not key:
        return None
    for field, names in _HEADER_ALIASES:
        for name in names:
            if name in key:
                return field
    # Substring fallback keeps legacy single-word headers working.
    for field in FIELDS:
        if field in key or key in field:
            return field
    return None


def _header_index_map(header_cells):
    """Map header cells to column indexes. First alias hit per field wins."""
    mapping = {}
    for i, cell in enumerate(header_cells):
        field = _match_header_field(cell)
        if field is not None and field not in mapping:
            mapping[field] = i
    return mapping


def _pick(cells, mapping, field):
    idx = mapping.get(field)
    if idx is None or idx >= len(cells):
        return ""
    return _clean(cells[idx])


def _record_from_cells(cells, mapping):
    """Build one normalized item dict from raw cells and a column mapping."""
    rec = {
        "section": _pick(cells, mapping, "section"),
        "item": _pick(cells, mapping, "item"),
        "description": _pick(cells, mapping, "description"),
        "unit": _pick(cells, mapping, "unit"),
        "qty": _to_float(_pick(cells, mapping, "qty")),
        "rate": _to_float(_pick(cells, mapping, "rate")),
    }
    if not rec["description"] and rec["item"]:
        rec["description"] = rec["item"]
    rec["unit"] = UNIT_MAP.get(rec["unit"].lower(), rec["unit"].lower())
    if _is_junk_record(rec):
        return None
    return rec


def _is_junk_record(rec):
    """True for repeated header rows and fully empty rows.

    Chinese text is never treated as junk: the header-label set is all
    English, and a non-empty description always survives, whatever the script.
    """
    desc = rec["description"].lower()
    header_labels = {
        "description", "particulars", "details", "item description",
        "description of works", "description of work", "item", "ref",
        "unit", "qty", "quantity", "rate", "price", "section", "trade",
    }
    if desc in header_labels:
        return True
    if not desc:
        return True
    return False


def _forward_fill_sections(records):
    """Fill blank section labels from the previous non-blank label.

    Excel renders merged trade/section label cells as a value in the first row
    of each group and blanks below it; forward-filling restores the label on
    every row so it is not lost.
    """
    last = ""
    for rec in records:
        if not rec["section"]:
            rec["section"] = last
        else:
            last = rec["section"]
    return records


def _find_header_row(all_rows):
    """Return (header_index, mapping) for the best header row, or (None, None).

    A row is a header candidate when it maps a description column plus at
    least one of quantity, rate, or unit. Among candidates the row mapping the
    most fields wins, so a full two-tier header is preferred over a partial
    grouping banner.
    """
    best_idx = None
    best_map = None
    best_score = -1
    for i, row in enumerate(all_rows):
        mapping = _header_index_map(row)
        if "description" not in mapping:
            continue
        if not (("qty" in mapping) or ("rate" in mapping) or ("unit" in mapping)):
            continue
        score = len(mapping)
        if score > best_score:
            best_score = score
            best_idx = i
            best_map = mapping
    return best_idx, best_map


def parse_csv(text: str):
    rows = []
    text = text.lstrip("\ufeff")
    all_rows = [row for row in csv.reader(io.StringIO(text))]
    if not all_rows:
        return rows
    header_idx, mapping = _find_header_row(all_rows)
    if mapping is None:
        # No recognizable header: fall back to positional columns on row 0.
        header_idx = 0
        mapping = {f: i for i, f in enumerate(FIELDS[: len(all_rows[0])])}
    records = []
    for line in all_rows[header_idx + 1:]:
        if len(line) < 2:
            continue
        rec = _record_from_cells(line, mapping)
        if rec is not None:
            records.append(rec)
    return _forward_fill_sections(records)


def parse_excel(file_bytes_or_path):
    """Read an Excel workbook (bytes, path, or file-like) into normalized items.

    Tolerates leading junk rows, multiple header rows, and merged label cells:
    the real column header is located by keyword and merged section/trade
    labels are forward-filled with pandas so no label is lost.
    """
    import numpy as np
    import pandas as pd

    if isinstance(file_bytes_or_path, (bytes, bytearray)):
        file_bytes_or_path = io.BytesIO(bytes(file_bytes_or_path))
    df = pd.read_excel(file_bytes_or_path, header=None, dtype=object)
    all_rows = []
    for _, row in df.iterrows():
        all_rows.append(["" if pd.isna(v) else str(v) for v in row.tolist()])
    header_idx, mapping = _find_header_row(all_rows)
    if mapping is None:
        return []
    data = df.iloc[header_idx + 1:].reset_index(drop=True)
    if "section" in mapping and mapping["section"] < data.shape[1]:
        sec_col = data.iloc[:, mapping["section"]]
        data.iloc[:, mapping["section"]] = (
            sec_col.replace("", np.nan).ffill().fillna("")
        )
    records = []
    for _, row in data.iterrows():
        cells = ["" if pd.isna(v) else str(v) for v in row.tolist()]
        rec = _record_from_cells(cells, mapping)
        if rec is not None:
            records.append(rec)
    return records


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


def _map_pdf_columns(cells):
    """Map table header cells to fields by keyword. Returns {field: col_index} or None."""
    aliases = {
        "section": {"section", "trade"},
        "item": {"item", "ref", "no.", "no"},
        "description": {"description", "particulars", "details", "item description"},
        "unit": {"unit"},
        "qty": {"qty", "quantity", "quantities"},
        "rate": {"rate", "price", "amount", "rate (hk$)"},
    }
    mapping = {}
    for col, cell in enumerate(cells):
        token = _flat_cell(cell).lower().strip()
        for field, names in aliases.items():
            if field not in mapping and (token in names or any(n in token for n in names)):
                mapping[field] = col
    if "description" in mapping and ("qty" in mapping or "rate" in mapping):
        return mapping
    return None


def _pdf_record(cells, mapping=None):
    """Convert extracted table cells into the public parser shape.
    With a mapping, columns are read by header position (handles 5-col and
    6-col layouts, any column order). Without one, positional 6-col fallback."""
    cells = [_flat_cell(cell) for cell in cells]
    if mapping is None:
        if len(cells) < len(FIELDS):
            cells.extend([""] * (len(FIELDS) - len(cells)))
        if len(cells) > len(FIELDS):
            cells = cells[:2] + [" ".join(cells[2:-3])] + cells[-3:]
        if _is_pdf_header(cells) or _is_pdf_footer(cells):
            return None
        section, item, description, unit, qty, rate = cells[:6]
    else:
        if _is_pdf_header(cells) or _is_pdf_footer(cells):
            return None
        pick = lambda field: cells[mapping[field]] if mapping.get(field) is not None and mapping[field] < len(cells) else ""
        section, item, description = pick("section"), pick("item"), pick("description")
        unit, qty, rate = pick("unit"), pick("qty"), pick("rate")
        # a row that is itself a repeated header (e.g. page-2 continuation)
        if re.sub(r"[^a-z]", "", description.lower()) in {"description", "particulars"}:
            return None
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
            rows = [row or [] for row in table.extract()]
            mapping = None
            for cells in rows:
                mapping = _map_pdf_columns(cells)
                if mapping:
                    break
            for cells in rows:
                record = _pdf_record(cells, mapping)
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
