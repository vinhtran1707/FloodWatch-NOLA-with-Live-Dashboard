"""
Curated NOLA place database for the address autocomplete search box.

Each entry has:
  • name         — displayed in the dropdown
  • category     — one of: landmark, street, intersection, neighborhood, business_district
  • lat, lon     — precise coordinates
  • neighborhood — maps to our 10-neighborhood taxonomy (None if outside)

Chosen to cover ~95% of realistic user queries during a demo:
major streets, famous landmarks, business districts, and frequently-referenced
intersections across Orleans Parish.
"""
from __future__ import annotations

NOLA_PLACES: list[dict] = [
    # ── Landmarks & institutions ──────────────────────────────────
    {"name": "Tulane University",           "category": "landmark", "lat": 29.9400, "lon": -90.1207, "neighborhood": "Uptown"},
    {"name": "Loyola University",           "category": "landmark", "lat": 29.9381, "lon": -90.1200, "neighborhood": "Uptown"},
    {"name": "Xavier University",           "category": "landmark", "lat": 29.9585, "lon": -90.0990, "neighborhood": "Mid-City"},
    {"name": "Dillard University",          "category": "landmark", "lat": 30.0025, "lon": -90.0521, "neighborhood": "Gentilly"},
    {"name": "UNO (Univ. of New Orleans)",  "category": "landmark", "lat": 30.0286, "lon": -90.0660, "neighborhood": "Gentilly"},
    {"name": "LSU Health Sciences Center",  "category": "landmark", "lat": 29.9534, "lon": -90.0820, "neighborhood": "CBD / French Quarter"},
    {"name": "Caesars Superdome",           "category": "landmark", "lat": 29.9511, "lon": -90.0812, "neighborhood": "CBD / French Quarter"},
    {"name": "Smoothie King Center",        "category": "landmark", "lat": 29.9490, "lon": -90.0820, "neighborhood": "CBD / French Quarter"},
    {"name": "Louis Armstrong Intl Airport","category": "landmark", "lat": 29.9934, "lon": -90.2580, "neighborhood": None},
    {"name": "Union Passenger Terminal",    "category": "landmark", "lat": 29.9470, "lon": -90.0785, "neighborhood": "CBD / French Quarter"},
    {"name": "Audubon Zoo",                 "category": "landmark", "lat": 29.9220, "lon": -90.1295, "neighborhood": "Uptown"},
    {"name": "Audubon Park",                "category": "landmark", "lat": 29.9285, "lon": -90.1265, "neighborhood": "Uptown"},
    {"name": "City Park",                   "category": "landmark", "lat": 29.9920, "lon": -90.0970, "neighborhood": "Mid-City"},
    {"name": "New Orleans Museum of Art",   "category": "landmark", "lat": 29.9864, "lon": -90.0932, "neighborhood": "Mid-City"},
    {"name": "Jackson Square",              "category": "landmark", "lat": 29.9574, "lon": -90.0629, "neighborhood": "CBD / French Quarter"},
    {"name": "French Market",               "category": "landmark", "lat": 29.9601, "lon": -90.0605, "neighborhood": "CBD / French Quarter"},
    {"name": "St. Louis Cathedral",         "category": "landmark", "lat": 29.9584, "lon": -90.0634, "neighborhood": "CBD / French Quarter"},
    {"name": "Lafayette Cemetery No. 1",    "category": "landmark", "lat": 29.9280, "lon": -90.0845, "neighborhood": "Garden District"},
    {"name": "St. Louis Cemetery No. 1",    "category": "landmark", "lat": 29.9597, "lon": -90.0712, "neighborhood": "Tremé"},
    {"name": "Louisiana Superdome",         "category": "landmark", "lat": 29.9511, "lon": -90.0812, "neighborhood": "CBD / French Quarter"},
    {"name": "Convention Center",           "category": "landmark", "lat": 29.9434, "lon": -90.0658, "neighborhood": "CBD / French Quarter"},
    {"name": "Harrah's New Orleans",        "category": "landmark", "lat": 29.9485, "lon": -90.0651, "neighborhood": "CBD / French Quarter"},
    {"name": "Mercedes-Benz Superdome",     "category": "landmark", "lat": 29.9511, "lon": -90.0812, "neighborhood": "CBD / French Quarter"},
    {"name": "Ochsner Baptist Hospital",    "category": "landmark", "lat": 29.9406, "lon": -90.1008, "neighborhood": "Broadmoor"},
    {"name": "Ochsner Medical Center",      "category": "landmark", "lat": 29.9510, "lon": -90.1710, "neighborhood": None},
    {"name": "University Medical Center",   "category": "landmark", "lat": 29.9600, "lon": -90.0800, "neighborhood": "Mid-City"},
    {"name": "Tulane Medical Center",       "category": "landmark", "lat": 29.9533, "lon": -90.0800, "neighborhood": "CBD / French Quarter"},
    {"name": "Mardi Gras World",            "category": "landmark", "lat": 29.9376, "lon": -90.0660, "neighborhood": "CBD / French Quarter"},
    {"name": "National WWII Museum",        "category": "landmark", "lat": 29.9427, "lon": -90.0702, "neighborhood": "CBD / French Quarter"},
    {"name": "Ogden Museum",                "category": "landmark", "lat": 29.9440, "lon": -90.0727, "neighborhood": "CBD / French Quarter"},
    {"name": "Contemporary Arts Center",    "category": "landmark", "lat": 29.9450, "lon": -90.0720, "neighborhood": "CBD / French Quarter"},
    {"name": "Fair Grounds Race Course",    "category": "landmark", "lat": 29.9828, "lon": -90.0738, "neighborhood": "Gentilly"},

    # ── Major streets (full corridor — use midpoints) ─────────────
    {"name": "Canal St",                    "category": "street", "lat": 29.9540, "lon": -90.0765, "neighborhood": "CBD / French Quarter"},
    {"name": "St. Charles Ave",             "category": "street", "lat": 29.9300, "lon": -90.0870, "neighborhood": "Garden District"},
    {"name": "Magazine St",                 "category": "street", "lat": 29.9260, "lon": -90.0960, "neighborhood": "Uptown"},
    {"name": "Tchoupitoulas St",            "category": "street", "lat": 29.9280, "lon": -90.0930, "neighborhood": "Uptown"},
    {"name": "Carrollton Ave",              "category": "street", "lat": 29.9610, "lon": -90.1090, "neighborhood": "Mid-City"},
    {"name": "Claiborne Ave",               "category": "street", "lat": 29.9620, "lon": -90.0700, "neighborhood": "Tremé"},
    {"name": "N. Broad St",                 "category": "street", "lat": 29.9715, "lon": -90.0870, "neighborhood": "Mid-City"},
    {"name": "Esplanade Ave",               "category": "street", "lat": 29.9680, "lon": -90.0700, "neighborhood": "Tremé"},
    {"name": "Napoleon Ave",                "category": "street", "lat": 29.9268, "lon": -90.1003, "neighborhood": "Uptown"},
    {"name": "Louisiana Ave",               "category": "street", "lat": 29.9295, "lon": -90.0940, "neighborhood": "Garden District"},
    {"name": "Jackson Ave",                 "category": "street", "lat": 29.9355, "lon": -90.0840, "neighborhood": "Garden District"},
    {"name": "Tulane Ave",                  "category": "street", "lat": 29.9590, "lon": -90.0887, "neighborhood": "Mid-City"},
    {"name": "Poydras St",                  "category": "street", "lat": 29.9498, "lon": -90.0710, "neighborhood": "CBD / French Quarter"},
    {"name": "Decatur St",                  "category": "street", "lat": 29.9585, "lon": -90.0620, "neighborhood": "CBD / French Quarter"},
    {"name": "Royal St",                    "category": "street", "lat": 29.9580, "lon": -90.0635, "neighborhood": "CBD / French Quarter"},
    {"name": "Bourbon St",                  "category": "street", "lat": 29.9585, "lon": -90.0655, "neighborhood": "CBD / French Quarter"},
    {"name": "Frenchmen St",                "category": "street", "lat": 29.9635, "lon": -90.0580, "neighborhood": "CBD / French Quarter"},
    {"name": "Rampart St",                  "category": "street", "lat": 29.9580, "lon": -90.0685, "neighborhood": "Tremé"},
    {"name": "Chartres St",                 "category": "street", "lat": 29.9585, "lon": -90.0625, "neighborhood": "CBD / French Quarter"},
    {"name": "Elysian Fields Ave",          "category": "street", "lat": 29.9780, "lon": -90.0540, "neighborhood": "Gentilly"},
    {"name": "Gentilly Blvd",               "category": "street", "lat": 29.9890, "lon": -90.0650, "neighborhood": "Gentilly"},
    {"name": "St. Claude Ave",              "category": "street", "lat": 29.9620, "lon": -90.0420, "neighborhood": "Bywater"},
    {"name": "Dauphine St",                 "category": "street", "lat": 29.9586, "lon": -90.0645, "neighborhood": "CBD / French Quarter"},
    {"name": "Burgundy St",                 "category": "street", "lat": 29.9588, "lon": -90.0665, "neighborhood": "CBD / French Quarter"},
    {"name": "Earhart Blvd",                "category": "street", "lat": 29.9580, "lon": -90.1050, "neighborhood": "Mid-City"},
    {"name": "Airline Dr",                  "category": "street", "lat": 29.9710, "lon": -90.1710, "neighborhood": None},
    {"name": "Jefferson Davis Pkwy",        "category": "street", "lat": 29.9680, "lon": -90.0980, "neighborhood": "Mid-City"},
    {"name": "Robert E. Lee Blvd",          "category": "street", "lat": 30.0180, "lon": -90.1100, "neighborhood": "Lakeview"},
    {"name": "Pontchartrain Blvd",          "category": "street", "lat": 30.0000, "lon": -90.1200, "neighborhood": "Lakeview"},
    {"name": "Lakeshore Dr",                "category": "street", "lat": 30.0300, "lon": -90.0700, "neighborhood": "Lakeview"},
    {"name": "West End Blvd",               "category": "street", "lat": 30.0050, "lon": -90.1280, "neighborhood": "Lakeview"},
    {"name": "Veterans Memorial Blvd",      "category": "street", "lat": 29.9940, "lon": -90.1700, "neighborhood": None},
    {"name": "Paris Rd",                    "category": "street", "lat": 29.9750, "lon": -89.9500, "neighborhood": None},
    {"name": "Tchefuncte Dr",               "category": "street", "lat": 29.9000, "lon": -90.0400, "neighborhood": "Algiers"},
    {"name": "General Meyer Ave",           "category": "street", "lat": 29.9260, "lon": -90.0570, "neighborhood": "Algiers"},
    {"name": "General de Gaulle Dr",        "category": "street", "lat": 29.9180, "lon": -90.0230, "neighborhood": "Algiers"},
    {"name": "Banks St",                    "category": "street", "lat": 29.9634, "lon": -90.0970, "neighborhood": "Mid-City"},
    {"name": "Orleans Ave",                 "category": "street", "lat": 29.9735, "lon": -90.0850, "neighborhood": "Mid-City"},
    {"name": "Washington Ave",              "category": "street", "lat": 29.9288, "lon": -90.0880, "neighborhood": "Garden District"},
    {"name": "Prytania St",                 "category": "street", "lat": 29.9295, "lon": -90.0855, "neighborhood": "Garden District"},
    {"name": "Camp St",                     "category": "street", "lat": 29.9415, "lon": -90.0740, "neighborhood": "CBD / French Quarter"},
    {"name": "Tchoupitoulas St Warehouse",  "category": "street", "lat": 29.9400, "lon": -90.0690, "neighborhood": "CBD / French Quarter"},
    {"name": "Oak St",                      "category": "street", "lat": 29.9425, "lon": -90.1245, "neighborhood": "Uptown"},
    {"name": "Maple St",                    "category": "street", "lat": 29.9400, "lon": -90.1290, "neighborhood": "Uptown"},
    {"name": "Freret St",                   "category": "street", "lat": 29.9380, "lon": -90.1040, "neighborhood": "Uptown"},
    {"name": "Franklin Ave",                "category": "street", "lat": 29.9720, "lon": -90.0470, "neighborhood": "Bywater"},
    {"name": "N. Claiborne Ave",            "category": "street", "lat": 29.9665, "lon": -90.0670, "neighborhood": "Tremé"},
    {"name": "N. Rampart St",               "category": "street", "lat": 29.9615, "lon": -90.0680, "neighborhood": "Tremé"},
    {"name": "N. Rocheblave St",            "category": "street", "lat": 29.9700, "lon": -90.0800, "neighborhood": "Tremé"},
    {"name": "Bienville St",                "category": "street", "lat": 29.9560, "lon": -90.0685, "neighborhood": "CBD / French Quarter"},
    {"name": "Iberville St",                "category": "street", "lat": 29.9555, "lon": -90.0690, "neighborhood": "CBD / French Quarter"},

    # ── Common intersections ──────────────────────────────────────
    {"name": "Canal St & Carrollton Ave",         "category": "intersection", "lat": 29.9685, "lon": -90.0958, "neighborhood": "Mid-City"},
    {"name": "Canal St & Claiborne Ave",          "category": "intersection", "lat": 29.9640, "lon": -90.0810, "neighborhood": "CBD / French Quarter"},
    {"name": "Canal St & Rampart St",             "category": "intersection", "lat": 29.9580, "lon": -90.0740, "neighborhood": "CBD / French Quarter"},
    {"name": "Canal St & Magazine St",            "category": "intersection", "lat": 29.9495, "lon": -90.0695, "neighborhood": "CBD / French Quarter"},
    {"name": "St. Charles & Napoleon",            "category": "intersection", "lat": 29.9268, "lon": -90.0950, "neighborhood": "Uptown"},
    {"name": "St. Charles & Jackson",             "category": "intersection", "lat": 29.9345, "lon": -90.0830, "neighborhood": "Garden District"},
    {"name": "St. Charles & Louisiana",            "category": "intersection", "lat": 29.9295, "lon": -90.0920, "neighborhood": "Garden District"},
    {"name": "S. Jefferson Davis & Banks St",     "category": "intersection", "lat": 29.9619, "lon": -90.0976, "neighborhood": "Mid-City"},
    {"name": "Tulane & Carrollton",                "category": "intersection", "lat": 29.9575, "lon": -90.1065, "neighborhood": "Mid-City"},
    {"name": "Magazine & Napoleon",                "category": "intersection", "lat": 29.9258, "lon": -90.0995, "neighborhood": "Uptown"},
    {"name": "Magazine & Washington",              "category": "intersection", "lat": 29.9275, "lon": -90.0882, "neighborhood": "Garden District"},
    {"name": "Magazine & Jefferson",               "category": "intersection", "lat": 29.9230, "lon": -90.1105, "neighborhood": "Uptown"},
    {"name": "Claiborne & Napoleon",               "category": "intersection", "lat": 29.9360, "lon": -90.1005, "neighborhood": "Broadmoor"},
    {"name": "Claiborne & Washington",             "category": "intersection", "lat": 29.9390, "lon": -90.0940, "neighborhood": "Broadmoor"},
    {"name": "Esplanade & N. Broad",               "category": "intersection", "lat": 29.9750, "lon": -90.0830, "neighborhood": "Mid-City"},
    {"name": "St. Claude & Franklin",              "category": "intersection", "lat": 29.9695, "lon": -90.0480, "neighborhood": "Bywater"},
    {"name": "St. Claude & Esplanade",             "category": "intersection", "lat": 29.9680, "lon": -90.0588, "neighborhood": "Bywater"},
    {"name": "N. Claiborne & Dumaine",             "category": "intersection", "lat": 29.9642, "lon": -90.0718, "neighborhood": "Tremé"},
    {"name": "Poydras & St. Charles",              "category": "intersection", "lat": 29.9498, "lon": -90.0720, "neighborhood": "CBD / French Quarter"},
    {"name": "Poydras & Loyola",                   "category": "intersection", "lat": 29.9498, "lon": -90.0755, "neighborhood": "CBD / French Quarter"},
    {"name": "Gentilly Blvd & Elysian Fields",     "category": "intersection", "lat": 29.9880, "lon": -90.0595, "neighborhood": "Gentilly"},
    {"name": "Robert E. Lee & Canal Blvd",         "category": "intersection", "lat": 30.0180, "lon": -90.1125, "neighborhood": "Lakeview"},
    {"name": "Canal Blvd & Harrison Ave",          "category": "intersection", "lat": 30.0100, "lon": -90.1125, "neighborhood": "Lakeview"},
    {"name": "West End Blvd & Veterans",           "category": "intersection", "lat": 30.0050, "lon": -90.1380, "neighborhood": "Lakeview"},

    # ── Business / dining districts ──────────────────────────────
    {"name": "Magazine St Shopping District",      "category": "business_district", "lat": 29.9275, "lon": -90.0880, "neighborhood": "Garden District"},
    {"name": "Oak St Business District",           "category": "business_district", "lat": 29.9425, "lon": -90.1245, "neighborhood": "Uptown"},
    {"name": "Freret St Business District",        "category": "business_district", "lat": 29.9380, "lon": -90.1040, "neighborhood": "Uptown"},
    {"name": "Maple St Business District",         "category": "business_district", "lat": 29.9400, "lon": -90.1290, "neighborhood": "Uptown"},
    {"name": "St. Claude Arts District",           "category": "business_district", "lat": 29.9685, "lon": -90.0510, "neighborhood": "Bywater"},
    {"name": "Warehouse / Arts District",          "category": "business_district", "lat": 29.9430, "lon": -90.0695, "neighborhood": "CBD / French Quarter"},
    {"name": "CBD — Poydras Corridor",             "category": "business_district", "lat": 29.9495, "lon": -90.0715, "neighborhood": "CBD / French Quarter"},
    {"name": "Riverbend",                          "category": "business_district", "lat": 29.9448, "lon": -90.1345, "neighborhood": "Uptown"},
    {"name": "Bywater Historic District",          "category": "business_district", "lat": 29.9610, "lon": -90.0425, "neighborhood": "Bywater"},
    {"name": "Marigny Historic District",          "category": "business_district", "lat": 29.9648, "lon": -90.0535, "neighborhood": "Bywater"},

    # ── Neighborhood centers (for "I'm near the center of X" queries) ──
    {"name": "Mid-City (center)",           "category": "neighborhood", "lat": 29.9720, "lon": -90.0950, "neighborhood": "Mid-City"},
    {"name": "Lakeview (center)",           "category": "neighborhood", "lat": 29.9950, "lon": -90.1150, "neighborhood": "Lakeview"},
    {"name": "Gentilly (center)",           "category": "neighborhood", "lat": 29.9900, "lon": -90.0550, "neighborhood": "Gentilly"},
    {"name": "Broadmoor (center)",          "category": "neighborhood", "lat": 29.9468, "lon": -90.1002, "neighborhood": "Broadmoor"},
    {"name": "Bywater (center)",            "category": "neighborhood", "lat": 29.9612, "lon": -90.0412, "neighborhood": "Bywater"},
    {"name": "Tremé (center)",              "category": "neighborhood", "lat": 29.9642, "lon": -90.0718, "neighborhood": "Tremé"},
    {"name": "Algiers Point",               "category": "neighborhood", "lat": 29.9511, "lon": -90.0525, "neighborhood": "Algiers"},
    {"name": "Garden District (center)",    "category": "neighborhood", "lat": 29.9248, "lon": -90.0852, "neighborhood": "Garden District"},
    {"name": "Uptown (center)",             "category": "neighborhood", "lat": 29.9198, "lon": -90.1138, "neighborhood": "Uptown"},
    {"name": "French Quarter (center)",     "category": "neighborhood", "lat": 29.9590, "lon": -90.0645, "neighborhood": "CBD / French Quarter"},
    {"name": "CBD (center)",                "category": "neighborhood", "lat": 29.9495, "lon": -90.0712, "neighborhood": "CBD / French Quarter"},
    {"name": "Faubourg Marigny",            "category": "neighborhood", "lat": 29.9648, "lon": -90.0535, "neighborhood": "Bywater"},
    {"name": "Irish Channel",               "category": "neighborhood", "lat": 29.9305, "lon": -90.0780, "neighborhood": "Garden District"},
    {"name": "Lower Garden District",       "category": "neighborhood", "lat": 29.9325, "lon": -90.0790, "neighborhood": "Garden District"},
    {"name": "Carrollton",                  "category": "neighborhood", "lat": 29.9445, "lon": -90.1340, "neighborhood": "Uptown"},
    {"name": "Black Pearl",                 "category": "neighborhood", "lat": 29.9450, "lon": -90.1395, "neighborhood": "Uptown"},
    {"name": "Holy Cross",                  "category": "neighborhood", "lat": 29.9630, "lon": -90.0080, "neighborhood": None},
    {"name": "Lower Ninth Ward",            "category": "neighborhood", "lat": 29.9685, "lon": -90.0150, "neighborhood": None},
    {"name": "Seventh Ward",                "category": "neighborhood", "lat": 29.9755, "lon": -90.0625, "neighborhood": "Tremé"},
    {"name": "Fairgrounds",                 "category": "neighborhood", "lat": 29.9828, "lon": -90.0738, "neighborhood": "Gentilly"},
]


# ── Category display metadata ─────────────────────────────────────
CATEGORY_ICONS = {
    "landmark":          "🏛️",
    "street":            "🛣️",
    "intersection":      "🚦",
    "neighborhood":      "📍",
    "business_district": "🏪",
}


def search_places(query: str, limit: int = 8) -> list[dict]:
    """
    Fuzzy search against the curated NOLA place list.

    Ranking (high to low):
      1. Exact case-insensitive match on name
      2. Prefix match — entry name starts with the query
      3. Word-start match — any word in the name starts with the query
      4. Substring match anywhere in the name
    """
    if not query or not query.strip():
        return []
    q = query.strip().lower()

    exact, prefix, word_start, substring = [], [], [], []

    for p in NOLA_PLACES:
        name_lower = p["name"].lower()
        if name_lower == q:
            exact.append(p)
        elif name_lower.startswith(q):
            prefix.append(p)
        else:
            words = name_lower.replace(".", "").replace(",", "").split()
            if any(w.startswith(q) for w in words):
                word_start.append(p)
            elif q in name_lower:
                substring.append(p)

    # Combine preserving rank
    results = exact + prefix + word_start + substring
    return results[:limit]


def format_place_label(place: dict) -> str:
    """Format a place entry for display in the dropdown."""
    icon = CATEGORY_ICONS.get(place["category"], "📍")
    nb = f" · {place['neighborhood']}" if place.get("neighborhood") else ""
    return f"{icon}  {place['name']}{nb}"


def get_place_by_name(name: str) -> dict | None:
    """Exact-match lookup — used when resolving a selected dropdown value back to its record."""
    for p in NOLA_PLACES:
        if p["name"] == name:
            return p
    return None
