from __future__ import annotations
import math

_M_TO_FT = 3.28084


def _interpolate_elev(lat: float, lon: float, elev_grid: dict) -> float:
    """Nearest-neighbour elevation lookup (metres) from a DEM grid dict."""
    lats = elev_grid.get("lats", [])
    lons = elev_grid.get("lons", [])
    dem  = elev_grid.get("dem")
    if not dem or not lats or not lons:
        return 0.0
    r = min(range(len(lats)), key=lambda i: abs(lats[i] - lat))
    c = min(range(len(lons)), key=lambda j: abs(lons[j] - lon))
    return float(dem[r][c])


def _estimate_base_depth(precip_pct: float, station: dict | None) -> float:
    """Rough neighbourhood-level standing water estimate (inches) from current conditions."""
    if precip_pct < 20:
        return 0.0
    # Rough PoP → rainfall in/hr for tropical Louisiana climate
    inhr = max(0.0, (precip_pct - 20) / 80 * 2.5)
    excess = max(0.0, inhr - 1.0)           # NOLA design capacity ~1 in/hr
    if station:
        status = station.get("status", "")
        if status == "OFFLINE":
            excess += 1.2
        elif status == "STANDBY":
            excess += 0.4
        op = station.get("operational_pct", 100) / 100
        excess *= (1.0 + (1.0 - op) * 0.5)  # degraded pumping amplifies excess
    return round(min(excess, 10.0), 1)


def _clamp(value: float, lo: float = 0, hi: float = 100) -> int:
    return int(max(lo, min(hi, value)))


def _level_and_color(score: int) -> tuple[str, str]:
    if score < 25:
        return "LOW", "#10b981"
    if score < 50:
        return "MODERATE", "#f59e0b"
    if score < 75:
        return "HIGH", "#ef4444"
    return "CRITICAL", "#a855f7"


def compute_risk_score(data: dict) -> dict:
    forecast = data.get("forecast")
    alerts = data.get("alerts") or []
    swbno = data.get("swbno") or {}
    river_gauge = data.get("river_gauge")

    stations = swbno.get("stations", [])

    # ── Weather score ──────────────────────────────────────────────
    if forecast is None:
        weather_score = 35
        precip_pct = 0
    else:
        precip_pct = (
            (forecast.get("probabilityOfPrecipitation") or {}).get("value") or 0
        )
        weather_score = 10
        if precip_pct > 80:
            weather_score += 70
        elif precip_pct > 60:
            weather_score += 50
        elif precip_pct > 40:
            weather_score += 30
        elif precip_pct > 20:
            weather_score += 15
    weather_score = _clamp(weather_score)

    # ── Infrastructure score ───────────────────────────────────────
    offline_count = sum(1 for s in stations if s.get("status") == "OFFLINE")
    standby_count = sum(1 for s in stations if s.get("status") == "STANDBY")
    infra_score = 5
    infra_score += offline_count * 18
    infra_score += standby_count * 6
    turbines_total = swbno.get("turbines_total", 3)
    turbines_online = swbno.get("turbines_online", 3)
    if turbines_online < turbines_total:
        infra_score += (turbines_total - turbines_online) * 15
    system_cap = swbno.get("system_capacity_pct", 100)
    if system_cap < 70:
        infra_score += 20
    elif system_cap < 85:
        infra_score += 10
    infra_score = _clamp(infra_score)

    # ── Alerts score ───────────────────────────────────────────────
    flood_alerts = [
        a for a in alerts
        if "flood" in a.get("properties", {}).get("event", "").lower()
    ]
    n_flood = len(flood_alerts)
    if data.get("alerts") is None:
        alerts_score = 20
    elif n_flood >= 3:
        alerts_score = 95
    elif n_flood >= 2:
        alerts_score = 80
    elif n_flood >= 1:
        alerts_score = 60
    else:
        alerts_score = 0
    if any(
        a.get("properties", {}).get("urgency") == "Immediate"
        for a in flood_alerts
    ):
        alerts_score = min(alerts_score + 20, 100)
    alerts_score = _clamp(alerts_score)

    # ── Water levels score ─────────────────────────────────────────
    if river_gauge is None:
        water_score = 20
        river_ft = 0.0
    else:
        river_ft = float(river_gauge.get("value_ft") or 0)
        if river_ft > 20:
            water_score = 80
        elif river_ft > 17:
            water_score = 60
        elif river_ft > 14:
            water_score = 30
        elif river_ft > 10:
            water_score = 15
        else:
            water_score = 0
    water_score = _clamp(water_score)

    # ── Composite ──────────────────────────────────────────────────
    composite = round(
        weather_score * 0.30
        + infra_score * 0.40
        + alerts_score * 0.20
        + water_score * 0.10
    )
    level, color = _level_and_color(composite)

    # ── Labels ─────────────────────────────────────────────────────
    def _weather_label(s: int, p: float) -> str:
        if s >= 70:
            return f"Severe precip risk ({p:.0f}%)"
        if s >= 40:
            return f"Moderate precip ({p:.0f}%)"
        if s >= 20:
            return f"Low precip ({p:.0f}%)"
        return "Clear conditions"

    def _infra_label(s: int, off: int) -> str:
        if off > 0:
            return f"{off} station(s) offline"
        if s >= 20:
            return "Reduced capacity"
        return "Full capacity"

    def _alerts_label(n: int) -> str:
        if n == 0:
            return "No active flood alerts"
        if n == 1:
            return "1 active flood alert"
        return f"{n} active flood alerts"

    def _water_label(s: int, ft: float) -> str:
        if s >= 60:
            return f"River elevated ({ft:.1f} ft)"
        if s >= 20:
            return f"River moderate ({ft:.1f} ft)"
        return f"River normal ({ft:.1f} ft)"

    risk_result = {
        "score": composite,
        "level": level,
        "color": color,
        "components": {
            "weather": {
                "score": weather_score,
                "label": _weather_label(weather_score, precip_pct),
                "weight": 0.30,
            },
            "infrastructure": {
                "score": infra_score,
                "label": _infra_label(infra_score, offline_count),
                "weight": 0.40,
            },
            "alerts": {
                "score": alerts_score,
                "label": _alerts_label(n_flood),
                "weight": 0.20,
            },
            "water_levels": {
                "score": water_score,
                "label": _water_label(water_score, river_ft),
                "weight": 0.10,
            },
        },
        "flood_alerts_count": n_flood,
        "offline_pumps_count": offline_count,
        "precip_pct": precip_pct,
        "river_ft": river_ft,
    }

    risk_result["smb_actions"] = get_actions(risk_result, "smb")
    risk_result["renter_actions"] = get_actions(risk_result, "renter")
    risk_result["recommended_actions"] = risk_result["smb_actions"][:3]

    return risk_result


def get_actions(risk_result: dict, user_type: str = "smb") -> list[str]:
    score = risk_result.get("score", 0)
    infra_score = risk_result.get("components", {}).get("infrastructure", {}).get("score", 0)
    weather_score = risk_result.get("components", {}).get("weather", {}).get("score", 0)
    offline_count = risk_result.get("offline_pumps_count", 0)
    precip_pct = risk_result.get("precip_pct", 0)

    if user_type == "smb":
        actions = ["Check your NFIP business policy number and coverage limits"]
        if infra_score > 40:
            actions.append("Verify your drainage basin pump status before opening")
        if weather_score > 40:
            actions.append("Move ground-level inventory to shelves above 18 inches")
        if score > 50:
            actions.append("Activate your business continuity plan. Alert staff.")
        if score > 70:
            actions.append(
                "Coordinate with neighboring businesses on shared equipment storage"
            )
        if offline_count > 0:
            actions.append(
                "Contact SWBNO at (504) 529-2837 to report pump station status"
            )
        return actions

    # renter
    actions = [
        "Locate and photograph all personal property for insurance purposes"
    ]
    if score > 30:
        actions.append("Elevate electronics and valuables off the floor now")
    if score > 50:
        actions.append("Review your renters insurance policy for contents coverage")
    if score > 70:
        actions.append(
            "Prepare a go-bag: documents, medications, charger, 3 days cash"
        )
    if precip_pct > 60:
        actions.append(
            "Move vehicles to upper-level parking before 6AM"
        )
    return actions


# ── Street-segment flood risk ──────────────────────────────────────────────

# Named streets per neighborhood with approximate polyline coords [lat, lon]
NEIGHBORHOOD_STREETS: dict[str, list[dict]] = {
    "Broadmoor": [
        {"name": "Palmyra St",      "coords": [[29.952,-90.112],[29.952,-90.092]]},
        {"name": "Washington Ave",  "coords": [[29.950,-90.112],[29.950,-90.092]]},
        {"name": "Napoleon Ave",    "coords": [[29.948,-90.112],[29.948,-90.092]]},
        {"name": "S Broad St",      "coords": [[29.945,-90.102],[29.965,-90.102]]},
        {"name": "Earhart Blvd",    "coords": [[29.958,-90.112],[29.958,-90.092]]},
    ],
    "Lakeview": [
        {"name": "Canal Blvd",      "coords": [[29.993,-90.112],[30.010,-90.112]]},
        {"name": "Harrison Ave",    "coords": [[30.000,-90.112],[30.000,-90.095]]},
        {"name": "Robert E Lee Blvd","coords": [[30.005,-90.112],[30.005,-90.095]]},
        {"name": "Pontchartrain Blvd","coords": [[29.993,-90.105],[30.010,-90.105]]},
        {"name": "West End Blvd",   "coords": [[29.993,-90.118],[30.010,-90.118]]},
    ],
    "Gentilly": [
        {"name": "Gentilly Blvd",   "coords": [[29.983,-90.065],[29.995,-90.045]]},
        {"name": "Elysian Fields",  "coords": [[29.980,-90.062],[29.995,-90.042]]},
        {"name": "France Rd",       "coords": [[29.990,-90.060],[29.990,-90.040]]},
        {"name": "Peoples Ave",     "coords": [[29.985,-90.058],[29.985,-90.038]]},
    ],
    "Mid-City": [
        {"name": "Canal St",        "coords": [[29.968,-90.100],[29.968,-90.075]]},
        {"name": "Tulane Ave",      "coords": [[29.963,-90.100],[29.963,-90.075]]},
        {"name": "N Broad St",      "coords": [[29.960,-90.087],[29.980,-90.087]]},
        {"name": "Bienville Ave",   "coords": [[29.971,-90.100],[29.971,-90.075]]},
        {"name": "Lafitte St",      "coords": [[29.974,-90.100],[29.974,-90.075]]},
    ],
    "Bywater": [
        {"name": "St Claude Ave",   "coords": [[29.951,-90.048],[29.951,-90.035]]},
        {"name": "Magazine St",     "coords": [[29.949,-90.048],[29.949,-90.035]]},
        {"name": "Dauphine St",     "coords": [[29.947,-90.048],[29.947,-90.035]]},
        {"name": "Poland Ave",      "coords": [[29.945,-90.048],[29.945,-90.035]]},
    ],
    "Tremé": [
        {"name": "St Bernard Ave",  "coords": [[29.965,-90.075],[29.965,-90.060]]},
        {"name": "N Claiborne Ave", "coords": [[29.963,-90.075],[29.963,-90.060]]},
        {"name": "Esplanade Ave",   "coords": [[29.960,-90.075],[29.960,-90.060]]},
        {"name": "Tremé St",        "coords": [[29.958,-90.073],[29.958,-90.060]]},
    ],
    "Algiers": [
        {"name": "General Meyer",   "coords": [[29.926,-90.062],[29.926,-90.050]]},
        {"name": "Newton St",       "coords": [[29.929,-90.062],[29.929,-90.050]]},
        {"name": "Algiers Ave",     "coords": [[29.923,-90.062],[29.923,-90.050]]},
    ],
}

# Approximate elevation (ft AMSL) per neighborhood for street scoring
NEIGHBORHOOD_BASE_ELEVATION: dict[str, float] = {
    "Broadmoor": -1.9, "Lakeview": -5.7, "Gentilly": -5.6,
    "Mid-City": -0.2,  "Bywater": +4.5,  "Tremé": -0.9,
    "Algiers": +1.0,   "Garden District": +2.0, "Uptown": +1.5,
    "CBD / French Quarter": +1.0,
}

# Which pump station serves each neighborhood
NEIGHBORHOOD_STATION: dict[str, str] = {
    "Broadmoor": "DPS-19", "Lakeview": "DPS-07", "Gentilly": "DPS-12",
    "Mid-City": "DPS-02",  "Bywater": "DPS-24",  "Tremé": "DPS-31",
    "Algiers": "DPS-38",
}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def score_street_segment(
    street: dict,
    neighborhood: str,
    swbno_data: dict,
    precip_pct: float,
    reports_311: list[dict],
    street_elev_ft: float | None = None,
) -> dict:
    """Score flood risk for one street segment. street_elev_ft overrides the
    neighbourhood baseline when per-street SRTM data is available."""
    elevation = street_elev_ft if street_elev_ft is not None else NEIGHBORHOOD_BASE_ELEVATION.get(neighborhood, 0.0)
    station_id = NEIGHBORHOOD_STATION.get(neighborhood)
    stations = swbno_data.get("stations", [])
    station = next((s for s in stations if s["id"] == station_id), None)

    # Component 1: elevation risk (0-40 pts)
    if elevation < -4:
        elev_score = 40
    elif elevation < -2:
        elev_score = 30
    elif elevation < 0:
        elev_score = 20
    elif elevation < 2:
        elev_score = 10
    else:
        elev_score = 0

    # Component 2: pump status (0-40 pts)
    if station is None:
        pump_score = 20
    elif station["status"] == "OFFLINE":
        pump_score = 40
    elif station["status"] == "STANDBY":
        pump_score = 25
    elif station["status"] == "TESTING":
        pump_score = 15
    else:
        pump_score = max(0, 40 - int(station["operational_pct"] * 0.4))

    # Component 3: precipitation (0-15 pts)
    if precip_pct > 70:
        precip_score = 15
    elif precip_pct > 40:
        precip_score = 10
    elif precip_pct > 20:
        precip_score = 5
    else:
        precip_score = 0

    # Component 4: nearby 311 complaints (0-5 pts)
    mid_idx = len(street["coords"]) // 2
    street_mid = street["coords"][mid_idx]
    nearby = 0
    for rep in reports_311:
        try:
            rlat = float(rep.get("latitude") or 0)
            rlon = float(rep.get("longitude") or 0)
            if rlat and rlon and _haversine_km(street_mid[0], street_mid[1], rlat, rlon) < 0.4:
                nearby += 1
        except (ValueError, TypeError):
            continue
    complaint_score = min(nearby * 2, 5)

    total = elev_score + pump_score + precip_score + complaint_score

    if total >= 60:
        color, risk_label = "#ef4444", "HIGH"
    elif total >= 35:
        color, risk_label = "#f59e0b", "MODERATE"
    else:
        color, risk_label = "#10b981", "LOW"

    pump_status = station["status"] if station else "Unknown"
    return {
        "name": street["name"],
        "coords": street["coords"],
        "score": total,
        "color": color,
        "risk_label": risk_label,
        "elevation_ft": elevation,
        "pump_status": pump_status,
        "nearby_complaints": nearby,
    }


def score_neighborhood_streets(
    neighborhood: str,
    swbno_data: dict,
    precip_pct: float,
    reports_311: list[dict],
    streets: list[dict] | None = None,
    elev_grid: dict | None = None,
    station_depth_in: float | None = None,
) -> list[dict]:
    """Score street segments for the selected neighbourhood.

    elev_grid: DEM dict from get_elevation_grid() — enables per-street elevation ranking.
    station_depth_in: projected standing water (inches) from simulator; when supplied,
                      overrides the rough estimate so simulator depths are precise.
    """
    if streets is None:
        streets = NEIGHBORHOOD_STREETS.get(neighborhood, [])

    station_id = NEIGHBORHOOD_STATION.get(neighborhood)
    stations   = swbno_data.get("stations", [])
    station    = next((s for s in stations if s["id"] == station_id), None)

    # ── Per-street elevation from SRTM grid (metres → feet) ───────────────
    street_elev_ft_list: list[float | None] = []
    for s in streets:
        if elev_grid:
            mid_idx  = len(s["coords"]) // 2
            lat, lon = s["coords"][mid_idx]
            elev_m   = _interpolate_elev(lat, lon, elev_grid)
            street_elev_ft_list.append(elev_m * _M_TO_FT)
        else:
            street_elev_ft_list.append(None)

    # ── Score each segment ─────────────────────────────────────────────────
    scored = [
        score_street_segment(s, neighborhood, swbno_data, precip_pct, reports_311, e)
        for s, e in zip(streets, street_elev_ft_list)
    ]

    if not scored:
        return scored

    # ── Elevation rank (0 = lowest/floods first, 1 = highest/drains best) ─
    elevs     = [s["elevation_ft"] for s in scored]
    min_e     = min(elevs)
    max_e     = max(elevs)
    elev_span = max_e - min_e if max_e > min_e else 1.0

    # ── Neighbourhood-level base depth ─────────────────────────────────────
    if station_depth_in is not None:
        base_depth = float(station_depth_in)
    else:
        base_depth = _estimate_base_depth(precip_pct, station)

    # ── Attach depth / passability / flood status per street ───────────────
    for s in scored:
        rank  = (s["elevation_ft"] - min_e) / elev_span   # 0=lowest, 1=highest
        depth = round(max(0.0, base_depth * (1.0 - rank)), 1)
        s["depth_in"] = depth

        if depth >= 12:
            s["flood_status"] = "SEVERE"
            s["passability"]  = "🔴 Impassable — severe flooding"
            s["depth_label"]  = f"~{depth:.0f} in — DO NOT ENTER"
        elif depth >= 6:
            s["flood_status"] = "MAJOR"
            s["passability"]  = "🔴 Turn Around Don't Drown"
            s["depth_label"]  = f"~{depth:.0f} in — vehicles at risk"
        elif depth >= 1:
            s["flood_status"] = "FLOODING"
            s["passability"]  = "🟠 Use extreme caution"
            s["depth_label"]  = f"~{depth:.1f} in — ankle to knee deep"
        elif depth >= 0.3:
            s["flood_status"] = "WET"
            s["passability"]  = "🟡 Minor standing water"
            s["depth_label"]  = f"~{depth:.1f} in — passable with care"
        else:
            s["flood_status"] = "CLEAR"
            s["passability"]  = "🟢 Passable"
            s["depth_label"]  = "< 0.3 in — clear"

    return scored


def neighborhood_plain_language(
    neighborhood: str,
    risk: dict,
    swbno_data: dict,
    street_scores: list[dict],
    reports_311: list[dict],
    hourly_12: list[dict] | None,
) -> str:
    """Generate a resident-facing plain language flood outlook."""
    station_id = NEIGHBORHOOD_STATION.get(neighborhood, "Unknown")
    stations = swbno_data.get("stations", [])
    station = next((s for s in stations if s["id"] == station_id), None)
    pump_line = (
        f"Pump station {station['name']} ({station_id}) is currently **{station['status']}**"
        f" at {station['operational_pct']}% capacity."
        if station else "Pump station status unknown."
    )

    elev = NEIGHBORHOOD_BASE_ELEVATION.get(neighborhood, 0)
    elev_line = (
        f"Streets in {neighborhood} sit at **{elev:+.1f} ft** relative to sea level — "
        + ("well **below sea level**, meaning water cannot drain without active pumping." if elev < -2
           else "**below sea level**, requiring active pumping to drain." if elev < 0
           else "**above sea level**, providing some natural drainage advantage.")
    )

    flooding = [s for s in street_scores if s.get("flood_status") in ("FLOODING", "MAJOR", "SEVERE")]
    wet       = [s for s in street_scores if s.get("flood_status") == "WET"]
    if flooding:
        street_line = (
            f"**{len(flooding)} street(s) are actively flooding:** "
            + ", ".join(f"{s['name']} ({s['depth_label']})" for s in flooding[:4])
            + ("…" if len(flooding) > 4 else "") + "."
        )
    elif wet:
        street_line = (
            f"**{len(wet)} street(s) have minor standing water:** "
            + ", ".join(s["name"] for s in wet[:4]) + "."
        )
    else:
        street_line = "No streets are currently showing active flooding."

    recent_reports = [r for r in (reports_311 or []) if not r.get("is_mock")]
    report_line = (
        f"**{len(recent_reports)} active 311 drainage complaint(s)** filed in the past 24 hours nearby."
        if recent_reports else "No recent 311 drainage complaints in this area."
    )

    peak_hour = ""
    if hourly_12:
        peak = max(hourly_12, key=lambda h: h["precip"])
        if peak["precip"] > 30:
            peak_hour = f" Peak rain probability: **{peak['precip']}% at {peak['hour']}**."

    level_color = {"LOW": "🟢", "MODERATE": "🟡", "HIGH": "🔴", "CRITICAL": "🔴"}.get(risk["level"], "⚪")

    return (
        f"{level_color} **{neighborhood} Flood Outlook — {risk['level']} Risk ({risk['score']}/100)**\n\n"
        f"{elev_line}\n\n"
        f"{pump_line}\n\n"
        f"{street_line}\n\n"
        f"{report_line}{peak_hour}"
    )
