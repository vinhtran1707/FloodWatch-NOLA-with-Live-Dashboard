"""
SWBNO infrastructure maintenance history — demo dataset.

Real sources this mirrors:
  • SWBNO Board of Directors meeting minutes
  • News reports (NOLA.com, WWL-TV) on force main bursts and turbine outages
  • SWBNO Capital Improvement Program status reports

The dataset lets us compute a reliability-adjusted risk score that goes beyond
"is the pump ON right now" — it factors in whether the station was recently
serviced (higher reliability), recently failed (lower reliability), or has
open work orders (degraded capacity).

This is the differentiator vs. FEMA / First Street: those platforms treat
the drainage system as a static design-capacity abstraction. We don't.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from math import radians, sin, cos, asin, sqrt
from typing import Iterable

# ── Reference date for the demo dataset ────────────────────────────────────
# All dates are expressed relative to "today" so the demo always looks fresh.
_TODAY = datetime.now()


def _days_ago(n: int) -> str:
    return (_TODAY - timedelta(days=n)).date().isoformat()


# ── Maintenance event catalogue ────────────────────────────────────────────
# event_type categories:
#   • overhaul        — major pump rebuild, IMPROVES reliability
#   • turbine_repair  — power plant turbine service
#   • burst_main      — force main / water main failure, DEGRADES capacity
#   • catch_basin     — drainage inlet cleaning, IMPROVES flow
#   • line_rehab      — drainage line relining / replacement
#   • generator_test  — routine resiliency test (neutral)
#   • power_feed      — Entergy / DPU power work (neutral–negative)
#   • sinkhole        — collapse from sub-surface drainage failure

MAINTENANCE_EVENTS: list[dict] = [
    # ── Mid-City ──────────────────────────────────────────────────
    {
        "id": "WO-2026-0412",
        "station_id": "DPS-02",
        "neighborhood": "Mid-City",
        "event_type": "overhaul",
        "date": _days_ago(21),
        "status": "Completed",
        "description": "Pump #3 full overhaul — impeller replaced, bearings rebuilt",
        "severity": "low",
        "capacity_impact_pct": 0,
        "reliability_delta": +8,
        "lat": 29.9720, "lon": -90.0712,
    },
    {
        "id": "WO-2026-0389",
        "station_id": None,
        "neighborhood": "Mid-City",
        "event_type": "catch_basin",
        "date": _days_ago(12),
        "status": "Completed",
        "description": "Catch basin cleaning — 47 basins along Canal St & S Carrollton",
        "severity": "low",
        "capacity_impact_pct": 0,
        "reliability_delta": +4,
        "lat": 29.9685, "lon": -90.0958,
    },
    {
        "id": "WO-2026-0421",
        "station_id": None,
        "neighborhood": "Mid-City",
        "event_type": "burst_main",
        "date": _days_ago(7),
        "status": "Repaired",
        "description": "36-inch force main rupture at S Jefferson Davis Pkwy & Banks St",
        "severity": "high",
        "capacity_impact_pct": -15,
        "reliability_delta": -10,
        "lat": 29.9619, "lon": -90.0976,
    },

    # ── Lakeview ──────────────────────────────────────────────────
    {
        "id": "WO-2026-0334",
        "station_id": "DPS-07",
        "neighborhood": "Lakeview",
        "event_type": "turbine_repair",
        "date": _days_ago(45),
        "status": "Completed",
        "description": "Carrollton Turbine 4 emergency standby return to service",
        "severity": "medium",
        "capacity_impact_pct": 0,
        "reliability_delta": +5,
        "lat": 29.9842, "lon": -90.1204,
    },
    {
        "id": "WO-2026-0445",
        "station_id": "DPS-07",
        "neighborhood": "Lakeview",
        "event_type": "power_feed",
        "date": _days_ago(3),
        "status": "In progress",
        "description": "Entergy feeder replacement — pump on manual standby",
        "severity": "medium",
        "capacity_impact_pct": -100,
        "reliability_delta": -15,
        "lat": 29.9842, "lon": -90.1204,
    },

    # ── Gentilly ──────────────────────────────────────────────────
    {
        "id": "WO-2026-0298",
        "station_id": "DPS-12",
        "neighborhood": "Gentilly",
        "event_type": "overhaul",
        "date": _days_ago(68),
        "status": "Completed",
        "description": "Pumps #1 and #2 rebuilt — discharge capacity restored",
        "severity": "low",
        "capacity_impact_pct": 0,
        "reliability_delta": +10,
        "lat": 29.9800, "lon": -90.0528,
    },
    {
        "id": "WO-2026-0402",
        "station_id": None,
        "neighborhood": "Gentilly",
        "event_type": "line_rehab",
        "date": _days_ago(18),
        "status": "In progress",
        "description": "Drainage line relining — Elysian Fields from Gentilly Blvd to I-610",
        "severity": "medium",
        "capacity_impact_pct": -8,
        "reliability_delta": -3,
        "lat": 29.9865, "lon": -90.0638,
    },

    # ── Broadmoor ─────────────────────────────────────────────────
    {
        "id": "WO-2026-0365",
        "station_id": "DPS-19",
        "neighborhood": "Broadmoor",
        "event_type": "burst_main",
        "date": _days_ago(14),
        "status": "Repaired",
        "description": "Suction line failure at DPS-19 — station offline for repairs",
        "severity": "high",
        "capacity_impact_pct": -60,
        "reliability_delta": -18,
        "lat": 29.9468, "lon": -90.1002,
    },
    {
        "id": "WO-2026-0432",
        "station_id": "DPS-19",
        "neighborhood": "Broadmoor",
        "event_type": "generator_test",
        "date": _days_ago(5),
        "status": "Completed",
        "description": "Backup generator 30-day load test — passed",
        "severity": "low",
        "capacity_impact_pct": 0,
        "reliability_delta": +2,
        "lat": 29.9468, "lon": -90.1002,
    },

    # ── Bywater ───────────────────────────────────────────────────
    {
        "id": "WO-2026-0375",
        "station_id": None,
        "neighborhood": "Bywater",
        "event_type": "catch_basin",
        "date": _days_ago(33),
        "status": "Completed",
        "description": "Catch basin cleaning — St Claude Ave corridor",
        "severity": "low",
        "capacity_impact_pct": 0,
        "reliability_delta": +3,
        "lat": 29.9612, "lon": -90.0412,
    },
    {
        "id": "WO-2026-0411",
        "station_id": "DPS-24",
        "neighborhood": "Bywater",
        "event_type": "overhaul",
        "date": _days_ago(9),
        "status": "Completed",
        "description": "Pump #4 impeller replacement — capacity restored",
        "severity": "low",
        "capacity_impact_pct": 0,
        "reliability_delta": +6,
        "lat": 29.9608, "lon": -90.0475,
    },

    # ── Tremé ─────────────────────────────────────────────────────
    {
        "id": "WO-2026-0356",
        "station_id": None,
        "neighborhood": "Tremé",
        "event_type": "sinkhole",
        "date": _days_ago(22),
        "status": "Repaired",
        "description": "Sinkhole at N Claiborne & Dumaine — drainage pipe collapse",
        "severity": "medium",
        "capacity_impact_pct": -5,
        "reliability_delta": -4,
        "lat": 29.9642, "lon": -90.0718,
    },

    # ── Algiers ───────────────────────────────────────────────────
    {
        "id": "WO-2026-0318",
        "station_id": "DPS-38",
        "neighborhood": "Algiers",
        "event_type": "overhaul",
        "date": _days_ago(52),
        "status": "Completed",
        "description": "West Bank station — full electrical upgrade",
        "severity": "low",
        "capacity_impact_pct": 0,
        "reliability_delta": +9,
        "lat": 29.9385, "lon": -90.0395,
    },

    # ── Garden District / Uptown ──────────────────────────────────
    {
        "id": "WO-2026-0398",
        "station_id": None,
        "neighborhood": "Garden District",
        "event_type": "burst_main",
        "date": _days_ago(11),
        "status": "Repaired",
        "description": "24-inch water main break at St Charles & Washington",
        "severity": "medium",
        "capacity_impact_pct": -8,
        "reliability_delta": -6,
        "lat": 29.9248, "lon": -90.0852,
    },
    {
        "id": "WO-2026-0424",
        "station_id": None,
        "neighborhood": "Uptown",
        "event_type": "catch_basin",
        "date": _days_ago(4),
        "status": "Completed",
        "description": "Catch basin cleaning — Magazine St from Napoleon to Jefferson",
        "severity": "low",
        "capacity_impact_pct": 0,
        "reliability_delta": +3,
        "lat": 29.9198, "lon": -90.1138,
    },

    # ── CBD / French Quarter ──────────────────────────────────────
    {
        "id": "WO-2026-0417",
        "station_id": None,
        "neighborhood": "CBD / French Quarter",
        "event_type": "line_rehab",
        "date": _days_ago(6),
        "status": "In progress",
        "description": "Poydras St drainage trunkline rehab — night work only",
        "severity": "medium",
        "capacity_impact_pct": -6,
        "reliability_delta": -3,
        "lat": 29.9495, "lon": -90.0712,
    },

    # ── System-wide ───────────────────────────────────────────────
    {
        "id": "WO-2026-0380",
        "station_id": "SFC2",
        "neighborhood": "System-Wide",
        "event_type": "turbine_repair",
        "date": _days_ago(15),
        "status": "In progress",
        "description": "Superpump SFC2 — 30-day reliability test, partial capacity",
        "severity": "medium",
        "capacity_impact_pct": -60,
        "reliability_delta": -8,
        "lat": 29.9511, "lon": -90.0714,
    },
]


# ── Station baseline reliability ──────────────────────────────────────────
# 0–100 scale. 100 = brand-new equipment, zero known issues.
# These are demo baselines reflecting documented SWBNO station condition
# reports; real production would pull from the asset management system.
_BASELINE_RELIABILITY = {
    "DPS-02": 82,   # Mid-City — aging but well-maintained
    "DPS-07": 74,   # Lakeview — older station, on standby often
    "DPS-12": 79,   # Gentilly — recent overhaul
    "DPS-19": 58,   # Broadmoor — known weak point
    "DPS-24": 86,   # Bywater — newer pumps
    "DPS-31": 80,   # Tremé
    "DPS-38": 88,   # Algiers — recent electrical upgrade
    "SFC2":   70,   # Superpump — in reliability testing
}


# ── Helpers ────────────────────────────────────────────────────────────────
def _haversine_mi(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in statute miles."""
    R_MI = 3958.8
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * R_MI * asin(sqrt(a))


def _parse_date(d: str) -> datetime:
    return datetime.fromisoformat(d)


# ── Public API ─────────────────────────────────────────────────────────────
def get_all_events() -> list[dict]:
    """Return all maintenance events, most recent first."""
    return sorted(MAINTENANCE_EVENTS, key=lambda e: e["date"], reverse=True)


def get_events_for_station(station_id: str, days_back: int = 180) -> list[dict]:
    """All events logged against a specific pump station in the window."""
    cutoff = _TODAY - timedelta(days=days_back)
    return sorted(
        [e for e in MAINTENANCE_EVENTS
         if e["station_id"] == station_id and _parse_date(e["date"]) >= cutoff],
        key=lambda e: e["date"],
        reverse=True,
    )


def get_events_for_neighborhood(neighborhood: str, days_back: int = 90) -> list[dict]:
    """All events in a neighborhood regardless of whether they hit a station."""
    cutoff = _TODAY - timedelta(days=days_back)
    return sorted(
        [e for e in MAINTENANCE_EVENTS
         if e["neighborhood"] == neighborhood and _parse_date(e["date"]) >= cutoff],
        key=lambda e: e["date"],
        reverse=True,
    )


def get_events_near(lat: float, lon: float,
                    radius_mi: float = 0.5, days_back: int = 90) -> list[dict]:
    """Events within radius_mi of a point (for address-level lookup)."""
    cutoff = _TODAY - timedelta(days=days_back)
    out = []
    for e in MAINTENANCE_EVENTS:
        if "lat" not in e or "lon" not in e:
            continue
        if _parse_date(e["date"]) < cutoff:
            continue
        d = _haversine_mi(lat, lon, e["lat"], e["lon"])
        if d <= radius_mi:
            ev = dict(e)
            ev["distance_mi"] = round(d, 2)
            out.append(ev)
    return sorted(out, key=lambda e: e["distance_mi"])


def get_recent_burst_pipes(days_back: int = 30) -> list[dict]:
    """Force main and water main failures in the window."""
    cutoff = _TODAY - timedelta(days=days_back)
    return sorted(
        [e for e in MAINTENANCE_EVENTS
         if e["event_type"] in ("burst_main", "sinkhole")
         and _parse_date(e["date"]) >= cutoff],
        key=lambda e: e["date"],
        reverse=True,
    )


def reliability_score_for_station(station_id: str, days_back: int = 90) -> dict:
    """
    Composite reliability score for a station (0–100).

    Starts from the baseline, then applies reliability_delta from every
    event logged against the station in the lookback window. Completed
    overhauls add to reliability; bursts, outages, and open work orders
    subtract from it.
    """
    base = _BASELINE_RELIABILITY.get(station_id, 75)
    events = get_events_for_station(station_id, days_back=days_back)
    delta_total = sum(e.get("reliability_delta", 0) for e in events)
    score = max(0, min(100, base + delta_total))

    # Narrative label
    if score >= 85:
        label, color = "Excellent", "#16a34a"
    elif score >= 70:
        label, color = "Good", "#65a30d"
    elif score >= 55:
        label, color = "Fair", "#f59e0b"
    else:
        label, color = "Degraded", "#dc2626"

    # Most impactful recent event
    headline = None
    if events:
        headline_event = max(events, key=lambda e: abs(e.get("reliability_delta", 0)))
        days_since = (_TODAY - _parse_date(headline_event["date"])).days
        headline = {
            "description": headline_event["description"],
            "days_ago": days_since,
            "event_type": headline_event["event_type"],
            "status": headline_event["status"],
        }

    return {
        "station_id": station_id,
        "baseline": base,
        "delta": delta_total,
        "score": score,
        "label": label,
        "color": color,
        "event_count": len(events),
        "headline": headline,
    }


def capacity_adjustment_for_neighborhood(neighborhood: str) -> float:
    """
    Returns a capacity multiplier (0.0–1.0+) for how much effective drainage
    capacity a neighborhood currently has relative to design. Starts at 1.0
    and applies capacity_impact_pct from events in the past 30 days that are
    not yet fully remediated.
    """
    cutoff = _TODAY - timedelta(days=30)
    mult = 1.0
    for e in MAINTENANCE_EVENTS:
        if e["neighborhood"] != neighborhood:
            continue
        if _parse_date(e["date"]) < cutoff:
            continue
        if e["status"].lower() == "completed" or e["status"].lower() == "repaired":
            # Apply only a residual drag — the system recovers but not instantly
            mult += e.get("capacity_impact_pct", 0) / 100 * 0.25
        else:
            # In-progress events hit at full severity
            mult += e.get("capacity_impact_pct", 0) / 100
    return max(0.1, min(1.2, mult))


# Event-type display helpers for the UI
EVENT_TYPE_META = {
    "overhaul":       {"icon": "🔧", "color": "#16a34a", "label": "Pump Overhaul"},
    "turbine_repair": {"icon": "⚡", "color": "#0284c7", "label": "Turbine Service"},
    "burst_main":     {"icon": "💥", "color": "#dc2626", "label": "Burst Main"},
    "catch_basin":    {"icon": "🕳️", "color": "#65a30d", "label": "Catch Basin"},
    "line_rehab":     {"icon": "🛠️", "color": "#f59e0b", "label": "Line Rehab"},
    "generator_test": {"icon": "🔋", "color": "#0891b2", "label": "Generator Test"},
    "power_feed":     {"icon": "🔌", "color": "#ea580c", "label": "Power Feed Work"},
    "sinkhole":       {"icon": "⚠️", "color": "#b91c1c", "label": "Sinkhole"},
}
