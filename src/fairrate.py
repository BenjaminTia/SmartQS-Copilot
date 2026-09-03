"""Fair-rate build-up anchored to the demo ArchSD-style SoR subset.

The idea: when a BOQ line rate looks off, build up a rough fair rate from a
SoR reference scaled by the project's own price level (the project rate
index), then split it into labour, material, plant, overheads and profit.

Everything here is a transparent, rough screening estimate. The component
split is a stated assumption, not a measured build-up, and the SoR reference
is a demo subset, not the official Schedule of Rates.
"""

try:
    from src import sor as _sor
except ImportError:  # pragma: no cover - standalone execution fallback
    import sor as _sor


# Stated component-split assumption. Overheads + profit together make up the
# classic OH&P 10%; we show them separately so the split stays visible.
SPLIT = {
    "material": 0.55,
    "labour": 0.25,
    "plant": 0.10,
    "overheads": 0.06,
    "profit": 0.04,
}


def _as_float(value):
    if value is None or value == "":
        return 0.0
    return float(value)


def _lookup_sor(sor_lookup, description):
    """Accept a SorLookup, a plain list of row dicts, the sor module, or None."""
    if sor_lookup is None:
        return None
    if hasattr(sor_lookup, "lookup") and callable(sor_lookup.lookup):
        return sor_lookup.lookup(description)
    if isinstance(sor_lookup, (list, tuple)):
        return _sor.lookup(description, rows=list(sor_lookup))
    return _sor.lookup(description)


def build_fair_rate(item_description, boq_rate, sor_lookup, project_index=None):
    """Build up a rough fair rate for one BOQ line item.

    Returns a dict with:
      matched_sor, sor_unit, sor_rate (the SoR demo reference, or None),
      project_rate_index, adjusted_rate,
      components {material, labour, plant, overheads, profit},
      total, and notes.

    The adjusted rate is the matched SoR demo rate scaled by the project rate
    index. When project_index is not supplied it is computed from this single
    item as boq_rate / sor_rate (guarded against divide by zero); pass a
    full-BOQ index via sor.project_rate_index for a project-wide figure. When
    nothing matches, the index is set to 1.0 and the split is taken from the
    BOQ rate only, and that is flagged in the notes.

    This is a screening estimate, not a priced bill. The figures are demo
    values and the component split is a stated assumption.
    """
    notes = []
    boq = _as_float(boq_rate)
    matched = _lookup_sor(sor_lookup, item_description)

    if matched is None:
        index = 1.0
        matched_sor = None
        sor_unit = None
        sor_rate = None
        base = boq
        notes.append(
            "No SoR demo match for this description; project rate index set to "
            "1.0 and the split is taken from the BOQ rate only."
        )
    else:
        matched_sor = matched.get("item")
        sor_unit = matched.get("unit")
        sor_rate = _as_float(matched.get("rate_hkd"))
        if project_index is not None:
            index = _as_float(project_index)
            notes.append("Project rate index supplied by caller (full-BOQ figure).")
        elif boq > 0 and sor_rate > 0:
            index = boq / sor_rate
            notes.append(
                "Project rate index computed from this single item (BOQ rate / "
                "SoR rate); pass a project-wide index for a full-BOQ comparison."
            )
        else:
            index = 1.0
            if sor_rate <= 0:
                notes.append("SoR demo rate is zero; index set to 1.0 to avoid divide by zero.")
            if boq <= 0:
                notes.append("BOQ rate is zero or missing; index set to 1.0 and the build-up is anchored to the SoR demo rate.")
        base = sor_rate * index
        notes.append("Adjusted rate = matched SoR demo rate x project rate index.")

    adjusted_rate = round(base, 2)

    # Split into components. Profit is the balancing remainder so the parts
    # always sum exactly to the total.
    material = round(adjusted_rate * SPLIT["material"], 2)
    labour = round(adjusted_rate * SPLIT["labour"], 2)
    plant = round(adjusted_rate * SPLIT["plant"], 2)
    overheads = round(adjusted_rate * SPLIT["overheads"], 2)
    profit = round(adjusted_rate - (material + labour + plant + overheads), 2)
    total = round(material + labour + plant + overheads + profit, 2)

    notes.append(
        "Component split is a stated assumption, not a measured build-up: "
        "material 55%, labour 25%, plant 10%, overheads 6%, profit 4% "
        "(OH&P 10% combined)."
    )
    notes.append(
        "SoR figures are indicative demo values, not the official current "
        "Schedule of Rates; treat this as a screening reference only."
    )

    return {
        "matched_sor": matched_sor,
        "sor_unit": sor_unit,
        "sor_rate": sor_rate,
        "project_rate_index": round(index, 4),
        "adjusted_rate": adjusted_rate,
        "components": {
            "material": material,
            "labour": labour,
            "plant": plant,
            "overheads": overheads,
            "profit": profit,
        },
        "total": total,
        "notes": notes,
    }
