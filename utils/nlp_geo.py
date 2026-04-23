from __future__ import annotations

# ── NOLA location reference: canonical name (lowercase) → [lat, lon] ──────
NOLA_LOCATIONS: dict[str, list[float]] = {
    # Neighborhoods
    "mid-city":                  [29.970, -90.087],
    "lakeview":                  [30.002, -90.107],
    "broadmoor":                 [29.955, -90.102],
    "gentilly":                  [29.988, -90.053],
    "bywater":                   [29.950, -90.043],
    "treme":                     [29.962, -90.067],
    "tremé":                     [29.962, -90.067],
    "algiers":                   [29.927, -90.056],
    "algiers point":             [29.942, -90.058],
    "garden district":           [29.932, -90.093],
    "uptown":                    [29.930, -90.110],
    "french quarter":            [29.958, -90.065],
    "marigny":                   [29.958, -90.055],
    "lower ninth ward":          [29.964, -89.994],
    "lower 9th ward":            [29.964, -89.994],
    "ninth ward":                [29.964, -89.994],
    "holy cross":                [29.961, -89.997],
    "warehouse district":        [29.943, -90.071],
    "cbd":                       [29.952, -90.070],
    "central business district": [29.952, -90.070],
    "carrollton":                [29.934, -90.127],
    "riverbend":                 [29.936, -90.126],
    "hollygrove":                [29.961, -90.124],
    "seventh ward":              [29.970, -90.057],
    "7th ward":                  [29.970, -90.057],
    "fillmore":                  [29.990, -90.052],
    "navarre":                   [30.005, -90.113],
    "lakeshore":                 [30.019, -90.065],
    "new orleans east":          [30.025, -89.975],
    "east new orleans":          [30.025, -89.975],
    "metairie":                  [30.003, -90.168],
    # Major streets
    "canal street":              [29.968, -90.087],
    "bourbon street":            [29.958, -90.066],
    "magazine street":           [29.929, -90.099],
    "st. charles avenue":        [29.938, -90.095],
    "st charles avenue":         [29.938, -90.095],
    "st charles":                [29.938, -90.095],
    "tulane avenue":             [29.963, -90.087],
    "claiborne avenue":          [29.963, -90.075],
    "north claiborne":           [29.963, -90.075],
    "elysian fields":            [29.980, -90.062],
    "esplanade avenue":          [29.960, -90.075],
    "napoleon avenue":           [29.948, -90.103],
    "washington avenue":         [29.950, -90.112],
    "earhart boulevard":         [29.958, -90.103],
    "palmyra street":            [29.952, -90.102],
    "north broad":               [29.975, -90.087],
    "south broad":               [29.950, -90.102],
    "broad street":              [29.968, -90.087],
    "harrison avenue":           [30.000, -90.103],
    "robert e lee":              [30.005, -90.103],
    "pontchartrain boulevard":   [30.003, -90.112],
    "west end boulevard":        [30.003, -90.117],
    "canal boulevard":           [29.998, -90.112],
    "chef menteur":              [30.025, -89.975],
    "gentilly boulevard":        [29.988, -90.053],
    "airline drive":             [29.992, -90.195],
    "veterans boulevard":        [30.004, -90.170],
    # Landmarks / infrastructure
    "superdome":                 [29.951, -90.081],
    "caesars superdome":         [29.951, -90.081],
    "city park":                 [30.000, -90.095],
    "lake pontchartrain":        [30.100, -90.070],
    "lakefront":                 [30.019, -90.049],
    "french market":             [29.956, -90.061],
    "jackson square":            [29.957, -90.063],
    "audubon park":              [29.924, -90.128],
    "tulane university":         [29.940, -90.120],
    "loyola":                    [29.939, -90.121],
    "xavier university":         [29.959, -90.123],
    "university medical center": [29.954, -90.093],
    "umc":                       [29.954, -90.093],
    # Generic city references — map to city center
    "new orleans":               [29.951, -90.071],
    "nola":                      [29.951, -90.071],
}

# Lowercase lookup (built once at import)
_LOC_LOWER: dict[str, list[float]] = {k.lower(): v for k, v in NOLA_LOCATIONS.items()}

# Lazy-loaded spaCy model
_nlp = None


def _get_nlp():
    global _nlp
    if _nlp is not None:
        return _nlp
    try:
        import spacy
        _nlp = spacy.load("en_core_web_sm")
    except Exception:
        _nlp = False  # mark as unavailable so we don't retry
    return _nlp


def geolocate_text(text: str) -> list[dict]:
    """
    Extract NOLA location mentions from a text string.

    Strategy:
      1. spaCy NER (GPE, LOC, FAC entities) — catches well-known places
         the model recognises from its training data.
      2. Direct substring match against NOLA_LOCATIONS dict — catches
         hyperlocal names like "Broadmoor" or "Bywater" that spaCy's small
         model may not label as location entities.

    Returns up to 2 matches: [{"name": str, "lat": float, "lon": float}, ...]
    """
    text_lower = text.lower()
    matched: list[dict] = []
    seen: set[str] = set()

    # ── Pass 1: spaCy NER ──────────────────────────────────────────────────
    nlp = _get_nlp()
    if nlp:
        doc = nlp(text)
        for ent in doc.ents:
            if ent.label_ not in ("GPE", "LOC", "FAC"):
                continue
            key = ent.text.lower().strip(".,;'\"")
            coords = _LOC_LOWER.get(key)
            if coords and key not in seen:
                matched.append({"name": ent.text, "lat": coords[0], "lon": coords[1]})
                seen.add(key)

    # ── Pass 2: direct substring match (catches spaCy misses) ─────────────
    for name, coords in _LOC_LOWER.items():
        if name in text_lower and name not in seen:
            matched.append({"name": name.title(), "lat": coords[0], "lon": coords[1]})
            seen.add(name)
            if len(matched) >= 2:
                break

    return matched[:2]


def geolocate_social_posts(posts: list[dict]) -> list[dict]:
    """
    Augment social feed posts with lat/lon/matched_location where a NOLA
    location can be extracted from the post title.  Posts with no match
    are returned unchanged (no lat/lon keys added).
    """
    result = []
    for post in posts:
        locs = geolocate_text(post.get("title", ""))
        if locs:
            post = dict(post)
            post["lat"] = locs[0]["lat"]
            post["lon"] = locs[0]["lon"]
            post["matched_location"] = locs[0]["name"]
        result.append(post)
    return result
