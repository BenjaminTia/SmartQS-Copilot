"""Reference unit rates for HK construction (2025-26 baseline).
Labeled as reference for anomaly screening, NOT pricing advice.
Sources: published HK market rate references (trade averages)."""

RATE_DB = {
    "excavation": {"rate": 355, "unit": "m3", "match": ["excav", "dig", "spoil", "disposal"]},
    "concrete": {"rate": 1780, "unit": "m3", "match": ["concrete", "blinding", "grade"]},
    "rebar": {"rate": 12, "unit": "kg", "match": ["reinforcement", "rebar", "bar"]},
    "formwork": {"rate": 460, "unit": "m2", "match": ["formwork"]},
    "masonry": {"rate": 650, "unit": "m2", "match": ["masonry", "wall in cement", "blockwork", "brickwork"]},
    "plaster": {"rate": 180, "unit": "m2", "match": ["plaster", "rendering"]},
    "paint": {"rate": 55, "unit": "m2", "match": ["paint", "emulsion"]},
    "tiling": {"rate": 320, "unit": "m2", "match": ["tiling", "tile"]},
    "waterproof": {"rate": 265, "unit": "m2", "match": ["waterproof"]},
    "ceiling": {"rate": 380, "unit": "m2", "match": ["false ceiling", "ceiling"]},
    "demolition": {"rate": 490, "unit": "m3", "match": ["demoli"]},
    "drainage": {"rate": 285, "unit": "m", "match": ["drain", "uPVC pipe"]},
    "road": {"rate": 620, "unit": "m2", "match": ["asphalt", "road base", "paving"]},
    "scaffold": {"rate": 118, "unit": "m2", "match": ["scaffold"]},
    "electrical": {"rate": 950, "unit": "no.", "match": ["electrical installation", "socket", "light point"]},
    "plumbing": {"rate": 1100, "unit": "no.", "match": ["plumbing", "water point", "sanitary"]},
    "firealarm": {"rate": 1250, "unit": "no.", "match": ["fire alarm", "detection point"]},
    "switchboard": {"rate": 185000, "unit": "no.", "match": ["switchboard", "LV panel"]},
    "door": {"rate": 2800, "unit": "no.", "match": ["door"]},
    "window": {"rate": 3100, "unit": "m2", "match": ["window", "glazing"]},
    "precast": {"rate": 1450, "unit": "m2", "match": ["precast"]},
    "safety": {"rate": None, "unit": "ls", "match": ["safety", "temporary works", "site establishment"]},
}

REQUIRED_SECTIONS = ["scaffold", "safety"]  # advisory: presence of access/safety items


def match_rate(description: str):
    d = description.lower()
    for key, meta in RATE_DB.items():
        for m in meta["match"]:
            if m in d:
                return key, meta
    return None, None
