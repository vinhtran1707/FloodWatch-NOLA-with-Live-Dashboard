from __future__ import annotations

import os
import sys
from datetime import datetime

import folium
import folium.plugins as fplugins
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from streamlit_folium import st_folium

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.data_fetchers import get_all_data, get_osm_streets, get_elevation_grid
from utils.risk_engine import compute_risk_score, score_neighborhood_streets
from utils.swbno_data import STATUS_COLORS

st.set_page_config(
    page_title="Storm Simulator — FloodWatch NOLA",
    page_icon="⛈️",
    layout="wide",
)

_css_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "style.css")
with open(_css_path) as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

if "data" not in st.session_state:
    with st.spinner("Fetching live data…"):
        st.session_state["data"] = get_all_data()

data        = st.session_state["data"]
swbno       = data.get("swbno", {})
stations    = swbno.get("stations", [])
reports_311 = data.get("reports_311") or []

# ── Preset scenario definitions ────────────────────────────────────────────
PRESETS: dict[str, dict] = {
    "routine": {
        "label": "🌧️ Routine Heavy Rain",
        "color": "#10b981",
        "rainfall": 1.2, "duration": 2, "river_ft": 11.0,
        "saturation": 20, "turbines": 3, "surge_ft": 0.0, "wind_mph": 15,
        "offline": [], "standby": [],
        "alert": "None",
        "description": "1.2 in/hr for 2 hours. All pumps operational. System handles it.",
    },
    "barry": {
        "label": "⛈️ Tropical Storm Barry (2019)",
        "color": "#f59e0b",
        "rainfall": 1.5, "duration": 4, "river_ft": 15.8,
        "saturation": 60, "turbines": 3, "surge_ft": 1.2, "wind_mph": 45,
        "offline": [], "standby": ["SFC2", "DPS-12"],
        "alert": "Flood Watch",
        "description": "River near action stage restricts outfall. 1.2 ft lake surge. SFC2 Superpump in testing — reduced city-wide capacity.",
    },
    "aug2017": {
        "label": "⚠️ August 2017 — Turbine Failure",
        "color": "#f97316",
        "rainfall": 2.5, "duration": 3, "river_ft": 12.8,
        "saturation": 35, "turbines": 1, "surge_ft": 0.5, "wind_mph": 30,
        "offline": ["DPS-02", "DPS-07", "DPS-19"],
        "standby": ["DPS-31"],
        "alert": "Flood Warning",
        "description": "2 of 3 turbines failed simultaneously. Mid-City, Lakeview, Broadmoor lost pump power. $46M damage.",
    },
    "ida": {
        "label": "🌀 Hurricane Ida Approach (2021)",
        "color": "#ef4444",
        "rainfall": 3.8, "duration": 8, "river_ft": 17.8,
        "saturation": 85, "turbines": 0, "surge_ft": 4.5, "wind_mph": 150,
        "offline": ["DPS-02", "DPS-07", "DPS-12", "DPS-19", "DPS-24", "DPS-31", "DPS-38"],
        "standby": [],
        "alert": "Flash Flood Emergency",
        "description": "Complete SWBNO power failure. Zero pump capacity. River above action stage. 4.5 ft lake surge. 150 mph winds. $75B+ regional damage.",
    },
}

BASIN_AREA_ACRES: dict[str, int] = {
    "DPS-02": 2800, "DPS-07": 2200, "DPS-12": 3100,
    "DPS-19": 1900, "DPS-24": 1600, "DPS-31": 1400,
    "DPS-38": 1800, "SFC2":   8000,
}

TURBINE_POWER_FACTOR: dict[int, float] = {3: 1.00, 2: 0.72, 1: 0.40, 0: 0.05}

NEIGHBORHOOD_CENTER: dict[str, list[float]] = {
    "Mid-City":          [29.970, -90.087],
    "Lakeview":          [30.002, -90.107],
    "Broadmoor":         [29.955, -90.102],
    "Gentilly":          [29.988, -90.053],
    "Bywater":           [29.950, -90.043],
    "Tremé":             [29.962, -90.067],
    "Algiers":           [29.927, -90.056],
    "Garden District":   [29.932, -90.093],
    "Uptown":            [29.930, -90.110],
    "CBD / French Quarter": [29.952, -90.070],
}

STATION_COORDS: dict[str, list[float]] = {
    "DPS-02": [29.9720, -90.0851], "DPS-07": [30.0045, -90.1068],
    "DPS-12": [29.9897, -90.0567], "DPS-19": [29.9542, -90.1012],
    "DPS-24": [29.9514, -90.0459], "DPS-31": [29.9653, -90.0712],
    "DPS-38": [29.9268, -90.0598], "SFC2":   [29.9654, -90.0771],
}


# ── Simulation engine ──────────────────────────────────────────────────────
def _river_capacity_factor(river_ft: float) -> float:
    if river_ft >= 20: return 0.55
    if river_ft >= 17: return 0.70
    if river_ft >= 14: return 0.85
    return 1.00


def _lake_capacity_factor(surge_ft: float) -> float:
    """Lake Pontchartrain surge reduces lake-side outfall drainage capacity."""
    if surge_ft >= 6: return 0.50
    if surge_ft >= 4: return 0.65
    if surge_ft >= 2: return 0.80
    return 1.00


def _wind_category(wind_mph: float) -> tuple[str, str]:
    """Return (category label, hex color) for sustained wind speed."""
    if wind_mph >= 157: return "Category 5 Hurricane",   "#a855f7"
    if wind_mph >= 130: return "Category 4 Hurricane",   "#ef4444"
    if wind_mph >= 111: return "Category 3 Hurricane",   "#f97316"
    if wind_mph >= 96:  return "Category 2 Hurricane",   "#f59e0b"
    if wind_mph >= 74:  return "Category 1 Hurricane",   "#eab308"
    if wind_mph >= 39:  return "Tropical Storm Force",   "#3b82f6"
    return               "Below Storm Threshold",         "#10b981"


def _build_sim_swbno(
    real_swbno: dict,
    offline_ids: list[str],
    standby_ids: list[str],
    turbines_online: int,
) -> dict:
    turb_factor = TURBINE_POWER_FACTOR[turbines_online]
    sim_stations = []
    for s in real_swbno.get("stations", []):
        sim = dict(s)
        if s["id"] in offline_ids:
            sim["status"] = "OFFLINE"
            sim["operational_pct"] = 0
        elif s["id"] in standby_ids:
            sim["status"] = "STANDBY"
            sim["operational_pct"] = max(0, int(s["operational_pct"] * 0.25))
        else:
            sim["status"] = "PUMPING"
            sim["operational_pct"] = min(100, int(s["operational_pct"] * turb_factor))
        sim_stations.append(sim)

    total_cap = sum(s["capacity_cfs"] for s in sim_stations) or 1
    avail_cap  = sum(s["capacity_cfs"] * s["operational_pct"] / 100 for s in sim_stations)
    return {
        **real_swbno,
        "stations": sim_stations,
        "pumps_available": sum(1 for s in sim_stations if s["status"] == "PUMPING"),
        "pumps_offline":   sum(1 for s in sim_stations if s["status"] == "OFFLINE"),
        "system_capacity_pct": round(avail_cap / total_cap * 100, 1),
        "turbines_online": turbines_online,
    }


def _build_sim_data(
    real_data: dict,
    rainfall_in_hr: float,
    river_ft: float,
    wind_mph: float,
    alert_level: str,
    sim_swbno: dict,
) -> dict:
    precip_pct = min(100.0, rainfall_in_hr * 40)
    alert_props = {
        "None": [],
        "Flood Watch": [{"properties": {
            "event": "Flood Watch", "status": "Actual",
            "urgency": "Future", "areaDesc": "Orleans Parish"}}],
        "Flood Warning": [{"properties": {
            "event": "Flood Warning", "status": "Actual",
            "urgency": "Expected", "areaDesc": "Orleans Parish"}}],
        "Flash Flood Emergency": [{"properties": {
            "event": "Flash Flood Emergency", "status": "Actual",
            "urgency": "Immediate", "areaDesc": "Orleans Parish"}}],
    }
    return {
        **real_data,
        "swbno": sim_swbno,
        "forecast": {
            "probabilityOfPrecipitation": {"value": precip_pct},
            "shortForecast": f"Simulated storm — {rainfall_in_hr} in/hr · {wind_mph:.0f} mph winds",
            "temperature": 72, "temperatureUnit": "F",
            "windSpeed": f"{wind_mph:.0f} mph",
        },
        "alerts": alert_props.get(alert_level, []),
        "river_gauge": {"value_ft": river_ft, "datetime": datetime.now().isoformat()},
    }


def _project_station(
    station: dict,
    rainfall_in_hr: float,
    river_ft: float,
    surge_ft: float,
    saturation_pct: float,
    duration_hr: int,
) -> dict:
    basin_acres     = BASIN_AREA_ACRES.get(station["id"], 2000)
    river_factor    = _river_capacity_factor(river_ft)
    lake_factor     = _lake_capacity_factor(surge_ft)
    sat_factor      = 1.0 + (saturation_pct / 100) * 0.35
    runoff_cfs      = rainfall_in_hr * basin_acres * 1.008 * sat_factor
    # Both river and lake back-pressure compound on pump output
    combined_factor = river_factor * lake_factor
    pump_cfs        = station["capacity_cfs"] * (station["operational_pct"] / 100) * combined_factor

    overflow_pct = round(max(0.0, (runoff_cfs - pump_cfs) / runoff_cfs * 100)) if runoff_cfs > 0 else 0

    if runoff_cfs > pump_cfs:
        excess       = runoff_cfs - pump_cfs
        depth_per_hr = (excess / basin_acres) * 3600 / 43560 * 12
    else:
        depth_per_hr = 0.0

    hourly, cumulative = [], 0.0
    for h in range(1, duration_hr + 1):
        cumulative += depth_per_hr
        hourly.append({"hour": h, "depth_in": round(min(cumulative, 48), 2)})

    total_depth = hourly[-1]["depth_in"] if hourly else 0.0
    if total_depth >= 12:
        severity, sev_color = "SEVERE FLOODING",   "#a855f7"
    elif total_depth >= 6:
        severity, sev_color = "MAJOR FLOODING",    "#ef4444"
    elif total_depth >= 2:
        severity, sev_color = "MODERATE FLOODING", "#f97316"
    elif total_depth > 0:
        severity, sev_color = "MINOR FLOODING",    "#f59e0b"
    else:
        severity, sev_color = "DRAINING",          "#10b981"

    return {
        "id": station["id"], "name": station["name"],
        "neighborhood": station["neighborhood"], "status": station["status"],
        "runoff_cfs": round(runoff_cfs), "pump_cfs": round(pump_cfs),
        "overflow_pct": overflow_pct, "depth_in": total_depth,
        "severity": severity, "sev_color": sev_color, "hourly": hourly,
    }


def _score_to_color(score: int) -> str:
    score = max(0, min(100, score))
    if score <= 50:
        t = score / 50.0
        r = int(16  + t * (234 - 16))
        g = int(185 + t * (179 - 185))
        b = int(129 + t * (8   - 129))
    else:
        t = (score - 50) / 50.0
        r = int(234 + t * (239 - 234))
        g = int(179 + t * (68  - 179))
        b = int(8   + t * (68  - 8))
    return f"#{r:02x}{g:02x}{b:02x}"


# ── Session state init ─────────────────────────────────────────────────────
if "sim" not in st.session_state:
    st.session_state["sim"] = {
        "rainfall": 0.0, "duration": 2, "river_ft": 12.0,
        "saturation": 20, "turbines": 3, "surge_ft": 0.0, "wind_mph": 15,
        "offline": [], "standby": [],
        "alert": "None", "active_preset": None,
        "neighborhood": "Mid-City",
    }
if "sim_enabled" not in st.session_state:
    st.session_state["sim_enabled"] = False


def _apply_preset(key: str) -> None:
    p = PRESETS[key]
    st.session_state["sim"].update({
        "rainfall": p["rainfall"], "duration": p["duration"],
        "river_ft": p["river_ft"], "saturation": p["saturation"],
        "turbines": p["turbines"], "surge_ft": p["surge_ft"],
        "wind_mph": p["wind_mph"], "offline": list(p["offline"]),
        "standby": list(p["standby"]), "alert": p["alert"],
        "active_preset": key,
    })
    st.session_state["sim_enabled"] = True


def _reset_sim() -> None:
    st.session_state["sim"].update({
        "rainfall": 0.0, "duration": 2, "river_ft": 12.0,
        "saturation": 20, "turbines": 3, "surge_ft": 0.0, "wind_mph": 15,
        "offline": [], "standby": [], "alert": "None", "active_preset": None,
    })
    st.session_state["sim_enabled"] = False


# ── Header ─────────────────────────────────────────────────────────────────
st.markdown(
    "<div style='font-size:0.8rem; color:#64748b;'>🌊 FloodWatch NOLA</div>",
    unsafe_allow_html=True,
)

tog_col, title_col = st.columns([0.38, 0.62])
with tog_col:
    sim_enabled = st.toggle(
        "⛈️ Simulation Active",
        value=st.session_state["sim_enabled"],
        help="Turn simulation on to apply storm parameters. Turn off to view live conditions.",
    )
    st.session_state["sim_enabled"] = sim_enabled

with title_col:
    active_preset_key = st.session_state["sim"].get("active_preset")
    if sim_enabled and active_preset_key:
        p   = PRESETS[active_preset_key]
        _pc = p["color"]
        st.markdown(
            f"<div style='background:{_pc}22; border:1px solid {_pc}60; border-radius:10px; "
            f"padding:0.55rem 1rem;'>"
            f"<b style='font-size:1rem; color:{_pc};'>⛈️ SIMULATION — {p['label']}</b><br>"
            f"<span style='color:#374151; font-size:0.82rem;'>{p['description']}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
    elif not sim_enabled:
        st.info("Simulation paused — map and scores reflect current live conditions.", icon="📡")
    else:
        st.title("⛈️ Storm Simulator")

st.divider()

# ── Preset scenario buttons ────────────────────────────────────────────────
st.markdown("**Load a historical storm scenario:**")
pc1, pc2, pc3, pc4, pc5 = st.columns([1, 1, 1, 1, 0.6])
with pc1:
    st.button(PRESETS["routine"]["label"], on_click=_apply_preset, args=("routine",),
              use_container_width=True)
with pc2:
    st.button(PRESETS["barry"]["label"],   on_click=_apply_preset, args=("barry",),
              use_container_width=True)
with pc3:
    st.button(PRESETS["aug2017"]["label"], on_click=_apply_preset, args=("aug2017",),
              use_container_width=True)
with pc4:
    st.button(PRESETS["ida"]["label"],     on_click=_apply_preset, args=("ida",),
              use_container_width=True)
with pc5:
    st.button("🔄 Reset to Live", on_click=_reset_sim, use_container_width=True)

st.divider()

# ── Controls + impact summary ──────────────────────────────────────────────
ctrl_col, impact_col = st.columns([1.1, 0.9])
sim         = st.session_state["sim"]
station_ids = [s["id"] for s in stations]
_disabled   = not sim_enabled

with ctrl_col:
    st.markdown("### Storm Parameters")

    c1, c2 = st.columns(2)
    with c1:
        rainfall = st.slider(
            "Rainfall intensity (in/hr)", 0.0, 4.0,
            value=float(sim["rainfall"]), step=0.25, disabled=_disabled,
            help="NOLA drainage system rated for ~1 in/hr. Above that, overwhelm begins.",
        )
        river_ft = st.slider(
            "Mississippi River stage (ft)", 8.0, 22.0,
            value=float(sim["river_ft"]), step=0.5, disabled=_disabled,
            help="Action stage = 17 ft. Above 14 ft, outfall drainage is restricted.",
        )
        surge_ft = st.slider(
            "Lake Pontchartrain surge (ft)", 0.0, 8.0,
            value=float(sim.get("surge_ft", 0.0)), step=0.5, disabled=_disabled,
            help="Storm surge from Lake Pontchartrain restricts lake-side drainage outfalls. "
                 "Combines with river back-pressure when both are elevated.",
        )
    with c2:
        duration = st.slider(
            "Storm duration (hours)", 1, 12,
            value=int(sim["duration"]), disabled=_disabled,
            help="Longer storms saturate basins and overwhelm clearance capacity.",
        )
        saturation = st.slider(
            "Prior ground saturation (%)", 0, 100,
            value=int(sim["saturation"]), step=5, disabled=_disabled,
            help="A second storm hitting a saturated city runs off faster — pumps see more volume.",
        )
        wind_mph = st.slider(
            "Sustained wind speed (mph)", 5, 175,
            value=int(sim.get("wind_mph", 15)), disabled=_disabled,
            help="Category 1 hurricane begins at 74 mph. High winds damage infrastructure "
                 "and can knock stations offline. Use Station Overrides to model specific failures.",
        )

    alert_level = st.selectbox(
        "NWS Alert Level",
        ["None", "Flood Watch", "Flood Warning", "Flash Flood Emergency"],
        index=["None", "Flood Watch", "Flood Warning", "Flash Flood Emergency"].index(sim["alert"]),
        disabled=_disabled,
    )

    st.markdown("### Infrastructure Failures")
    ci1, ci2 = st.columns(2)
    with ci1:
        turbines_online = st.selectbox(
            "Turbines online (of 3)",
            [3, 2, 1, 0],
            index=[3, 2, 1, 0].index(int(sim["turbines"])),
            disabled=_disabled,
            help="SWBNO runs on its own steam turbine grid. Turbine failure cascades across stations.",
            format_func=lambda x: {
                3: "3 — Full power", 2: "2 — 72% capacity",
                1: "1 — 40% capacity", 0: "0 — Emergency only (5%)"
            }[x],
        )
    with ci2:
        st.markdown(
            "<div style='font-size:0.8rem; color:#64748b; padding-top:1.8rem;'>"
            f"System power: <b style='color:#0f172a;'>{int(TURBINE_POWER_FACTOR[turbines_online]*100)}%</b>"
            "</div>",
            unsafe_allow_html=True,
        )

    with st.expander("Station overrides (set individual stations offline/standby)"):
        offline_ids = st.multiselect(
            "OFFLINE stations (0% capacity)", station_ids,
            default=sim["offline"], disabled=_disabled,
        )
        standby_ids = st.multiselect(
            "STANDBY stations (25% capacity)",
            [s for s in station_ids if s not in offline_ids],
            default=[s for s in sim["standby"] if s not in offline_ids],
            disabled=_disabled,
        )

    neighborhood = st.selectbox(
        "Focus neighborhood for street map",
        list(NEIGHBORHOOD_CENTER.keys()),
        index=list(NEIGHBORHOOD_CENTER.keys()).index(sim.get("neighborhood", "Mid-City")),
    )

# ── Persist control values ─────────────────────────────────────────────────
st.session_state["sim"].update({
    "rainfall": rainfall, "duration": duration, "river_ft": river_ft,
    "saturation": saturation, "turbines": turbines_online,
    "surge_ft": surge_ft, "wind_mph": wind_mph,
    "offline": offline_ids, "standby": standby_ids,
    "alert": alert_level, "neighborhood": neighborhood,
})

# ── Run simulation ─────────────────────────────────────────────────────────
if sim_enabled:
    sim_swbno  = _build_sim_swbno(swbno, offline_ids, standby_ids, turbines_online)
    sim_data   = _build_sim_data(data, rainfall, river_ft, wind_mph, alert_level, sim_swbno)
    sim_risk   = compute_risk_score(sim_data)
    sim_precip = min(100.0, rainfall * 40)
    station_results = [
        _project_station(s, rainfall, river_ft, surge_ft, saturation, duration)
        for s in sim_swbno.get("stations", [])
    ]
else:
    sim_swbno       = swbno
    sim_risk        = compute_risk_score(data)
    sim_precip      = float(sim_risk.get("precip_pct", 0))
    station_results = []

flooded_stations = [r for r in station_results if r["depth_in"] > 0]
max_depth = max((r["depth_in"] for r in station_results), default=0)

_wind_label, _wind_color = _wind_category(wind_mph if sim_enabled else 0)

with impact_col:
    st.markdown("### Projected Impact")

    _sc  = sim_risk["score"]
    _slv = sim_risk["level"]
    _clr = sim_risk["color"]
    st.markdown(
        f"<div style='background:{_clr}18; border:1px solid {_clr}50; border-radius:12px; "
        f"padding:1.25rem; text-align:center; margin-bottom:0.75rem;'>"
        f"<div style='font-size:4rem; font-weight:900; color:{_clr}; line-height:1;'>{_sc}</div>"
        f"<div style='font-size:1.2rem; font-weight:700; color:{_clr};'>{_slv} RISK</div>"
        f"<div style='font-size:0.75rem; color:#64748b;'>Composite score / 100</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    mi1, mi2 = st.columns(2)
    _live_river = float(sim_risk.get("river_ft", 0))
    _disp_river = river_ft if sim_enabled else _live_river
    with mi1:
        if sim_enabled:
            st.metric("Stations Flooding", f"{len(flooded_stations)} / {len(station_results)}",
                      delta=f"{len(flooded_stations)} affected" if flooded_stations else "All clear",
                      delta_color="inverse" if flooded_stations else "normal")
        else:
            st.metric("Stations Flooding", "—", delta="Sim off — live view")
        st.metric("River Stage", f"{_disp_river:.1f} ft",
                  delta="Above action stage" if _disp_river >= 17 else "Normal range",
                  delta_color="inverse" if _disp_river >= 17 else "normal")
    with mi2:
        if sim_enabled:
            depth_str = f"{max_depth:.1f} in" if max_depth > 0 else "None"
            st.metric("Peak Flood Depth", depth_str,
                      delta=f"After {duration} hours" if max_depth > 0 else "Pumps keeping up",
                      delta_color="inverse" if max_depth > 3 else "normal")
        else:
            st.metric("Peak Flood Depth", "—", delta="Sim off — live view")
        st.metric("System Capacity", f"{sim_swbno.get('system_capacity_pct', 0):.0f}%",
                  delta="Degraded" if sim_swbno.get("system_capacity_pct", 100) < 70 else "Adequate",
                  delta_color="inverse" if sim_swbno.get("system_capacity_pct", 100) < 70 else "normal")

    # Wind alert banner
    if sim_enabled and wind_mph >= 39:
        _hurricane_note = (
            "Hurricane-force winds — expect infrastructure damage and power loss."
            if wind_mph >= 74 else
            "Tropical storm force — outdoor conditions hazardous."
        )
        st.markdown(
            f"<div style='background:{_wind_color}18; border-left:4px solid {_wind_color}; "
            f"border-radius:0 8px 8px 0; padding:8px 12px; margin-top:0.5rem;'>"
            f"<b style='color:{_wind_color};'>💨 {_wind_label}</b>"
            f" — <span style='color:#0f172a;'>{wind_mph} mph sustained</span><br>"
            f"<span style='color:#374151; font-size:0.78rem;'>{_hurricane_note}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

    # NWS alert banner
    _alert_styles = {
        "Flood Watch":           ("#f59e0b", "🟡 Flood Watch in effect — conditions favorable for flooding"),
        "Flood Warning":         ("#f97316", "🟠 Flood Warning — flooding is occurring or imminent"),
        "Flash Flood Emergency": ("#ef4444", "🔴 Flash Flood Emergency — catastrophic flooding underway"),
    }
    if sim_enabled and alert_level in _alert_styles:
        _ac, _at = _alert_styles[alert_level]
        st.markdown(
            f"<div style='background:{_ac}22; border-left:4px solid {_ac}; "
            f"border-radius:0 8px 8px 0; padding:8px 12px; font-size:0.85rem; "
            f"font-weight:600; margin-top:0.5rem; color:#0f172a;'>{_at}</div>",
            unsafe_allow_html=True,
        )

    # Back-pressure captions
    if sim_enabled and river_ft >= 14:
        _rfac = _river_capacity_factor(river_ft)
        st.caption(f"⚠️ Mississippi at {river_ft:.1f} ft — outfall drainage at {int(_rfac*100)}% capacity.")
    if sim_enabled and surge_ft >= 2:
        _lfac = _lake_capacity_factor(surge_ft)
        st.caption(f"⚠️ Lake surge {surge_ft:.1f} ft — lake outfall at {int(_lfac*100)}% capacity.")

st.divider()

# ── Simulation map ─────────────────────────────────────────────────────────
_map_title = "🗺️ Flood Risk Map — Simulation State" if sim_enabled else "🗺️ Flood Risk Map — Live Conditions"
st.subheader(_map_title)

with st.spinner("Scoring streets…"):
    osm_raw    = get_osm_streets(neighborhood)
    _elev_grid = get_elevation_grid(neighborhood)
    streets_to_score = osm_raw[:300] if osm_raw else None

    # Find projected depth for this neighbourhood's pump station
    _nbhd_station_id = {
        "Mid-City": "DPS-02", "Lakeview": "DPS-07", "Broadmoor": "DPS-19",
        "Gentilly": "DPS-12", "Bywater": "DPS-24",  "Tremé": "DPS-31",
        "Algiers": "DPS-38",  "Garden District": "SFC2", "Uptown": "SFC2",
        "CBD / French Quarter": "DPS-31",
    }.get(neighborhood)
    _nbhd_depth = None
    if sim_enabled and station_results and _nbhd_station_id:
        _match = next((r for r in station_results if r["id"] == _nbhd_station_id), None)
        if _match:
            _nbhd_depth = _match["depth_in"]

    street_scores = score_neighborhood_streets(
        neighborhood, sim_swbno, sim_precip, reports_311,
        streets=streets_to_score, elev_grid=_elev_grid,
        station_depth_in=_nbhd_depth,
    )

center  = NEIGHBORHOOD_CENTER.get(neighborhood, [29.9511, -90.0715])
sim_map = folium.Map(location=center, zoom_start=14, tiles=None)
folium.TileLayer(
    tiles="https://cartodb-basemaps-{s}.global.ssl.fastly.net/dark_all/{z}/{x}/{y}.png",
    attr="&copy; OpenStreetMap contributors &copy; CARTO",
    name="Dark", max_zoom=19,
).add_to(sim_map)

# Street gradient layer — depth-driven colors in sim mode, score-driven otherwise
if street_scores:
    sg = folium.FeatureGroup(name="Street Risk", show=True)
    for seg in street_scores:
        score       = seg["score"]
        depth_in    = seg.get("depth_in", 0.0)
        depth_label = seg.get("depth_label", "< 0.3 in — clear")
        passability = seg.get("passability", "🟢 Passable")

        if sim_enabled and depth_in >= 12: color = "#a855f7"
        elif sim_enabled and depth_in >= 6: color = "#ef4444"
        elif sim_enabled and depth_in >= 1: color = "#f97316"
        elif sim_enabled and depth_in >= 0.3: color = "#f59e0b"
        else: color = _score_to_color(score)

        weight = 2.0 + (score / 100.0) * 7.0
        if sim_enabled and depth_in >= 1:
            weight = 2.0 + (min(depth_in, 12) / 12) * 7.0

        if depth_in >= 0.3 or score >= 40:
            folium.PolyLine(seg["coords"], color=color,
                            weight=weight * 2.8, opacity=0.22).add_to(sg)
        folium.PolyLine(
            seg["coords"], color=color, weight=weight, opacity=0.88,
            tooltip=f"{seg['name']} — {depth_label} · {passability}",
            popup=folium.Popup(
                f"<div style='font-family:sans-serif; min-width:220px; color:#1e293b;'>"
                f"<b>{seg['name']}</b><br>"
                f"<span style='color:{color}; font-weight:700; font-size:1.05rem;'>{depth_label}</span><br>"
                f"<span style='font-size:0.85rem;'>{passability}</span><br>"
                f"<hr style='margin:4px 0; border-color:#64748b;'>"
                f"Risk score: {score}/100 &nbsp;·&nbsp; Elev: {seg['elevation_ft']:+.1f} ft<br>"
                f"Pump: {seg['pump_status']}",
                max_width=250,
            ),
        ).add_to(sg)
    sg.add_to(sim_map)

# Pump station markers
for res in station_results:
    coord = STATION_COORDS.get(res["id"])
    if not coord:
        continue
    color = STATUS_COLORS.get(res["status"], "#808080")
    depth_line = (
        f"<br>Projected: <b style='color:{res['sev_color']};'>{res['depth_in']:.1f} in — {res['severity']}</b>"
        if res["depth_in"] > 0 else "<br>Draining OK"
    )
    popup_html = (
        f"<div style='font-family:sans-serif; min-width:210px; color:#1e293b;'>"
        f"<b>{res['name']}</b><br>"
        f"<span style='color:{color}; font-weight:700;'>{res['status']}</span>"
        f"{depth_line}<br>"
        f"Runoff: {res['runoff_cfs']:,} CFS &nbsp;·&nbsp; Pumping: {res['pump_cfs']:,} CFS<br>"
        f"Overflow: <b>{res['overflow_pct']}%</b>"
        f"</div>"
    )
    folium.CircleMarker(
        location=coord, radius=14, color=color, weight=2,
        fill=True, fill_color=color, fill_opacity=0.85,
        popup=folium.Popup(popup_html, max_width=250),
        tooltip=f"{res['id']} — {res['status']} | {res['depth_in']:.1f}\" projected",
    ).add_to(sim_map)

# Heatmap overlay
if street_scores:
    heat_pts = []
    for seg in street_scores:
        mid = seg["coords"][len(seg["coords"]) // 2]
        heat_pts.append([mid[0], mid[1], seg["score"] / 100.0])
    if heat_pts:
        fplugins.HeatMap(
            heat_pts, min_opacity=0.2, max_opacity=0.55,
            radius=28, blur=22,
            gradient={"0.0": "#10b981", "0.4": "#84cc16", "0.6": "#eab308",
                      "0.75": "#f97316", "1.0": "#ef4444"},
        ).add_to(sim_map)

# Watermark (only in sim mode)
if sim_enabled:
    sim_map.get_root().html.add_child(folium.Element(
        "<div style='position:fixed; top:10px; left:50%; transform:translateX(-50%); "
        "z-index:9999; background:rgba(239,68,68,0.85); color:white; "
        "padding:4px 14px; border-radius:20px; font-family:sans-serif; "
        "font-size:12px; font-weight:700; letter-spacing:1px;'>⛈️ SIMULATION MODE</div>"
    ))

legend_html = """
<div style='position:fixed; bottom:30px; right:10px; z-index:9999;
            background:rgba(15,23,42,0.94); padding:12px 16px;
            border-radius:10px; border:1px solid #334155;
            font-family:sans-serif; font-size:11px; color:#0f172a; line-height:1.8;'>
  <b style='color:#0f172a;'>Street Flood Risk</b><br>
  <div style='background:linear-gradient(to right,#10b981,#eab308,#ef4444);
              height:8px; border-radius:4px; width:140px; margin:4px 0;'></div>
  <div style='display:flex;justify-content:space-between;width:140px;
              font-size:9px;color:#64748b;margin-bottom:6px;'>
    <span>LOW</span><span>MOD</span><span>HIGH</span>
  </div>
  <b style='color:#0f172a;'>Pump Stations</b><br>
  <span style='color:#10b981;'>⬤</span> <span style='color:#e2e8f0;'>PUMPING</span> &nbsp;
  <span style='color:#f59e0b;'>⬤</span> <span style='color:#e2e8f0;'>STANDBY</span><br>
  <span style='color:#ef4444;'>⬤</span> <span style='color:#e2e8f0;'>OFFLINE</span>
</div>"""
sim_map.get_root().html.add_child(folium.Element(legend_html))
folium.LayerControl(collapsed=True).add_to(sim_map)

st_folium(sim_map, width=None, height=580, returned_objects=[])

st.divider()

# ── Results tabs ───────────────────────────────────────────────────────────
tab1, tab2 = st.tabs(["📊 Station-by-Station Results", "⏱️ Hour-by-Hour Timeline"])

with tab1:
    if not sim_enabled:
        st.info("Enable simulation to see projected station-by-station flood results.")
    else:
        st.markdown(
            f"<span style='color:#374151;'>"
            f"<b style='color:#0f172a;'>Storm:</b> {rainfall} in/hr × {duration} hr &nbsp;·&nbsp; "
            f"<b style='color:#0f172a;'>River:</b> {river_ft:.1f} ft &nbsp;·&nbsp; "
            f"<b style='color:#0f172a;'>Lake surge:</b> {surge_ft:.1f} ft &nbsp;·&nbsp; "
            f"<b style='color:#0f172a;'>Wind:</b> {wind_mph} mph &nbsp;·&nbsp; "
            f"<b style='color:#0f172a;'>Saturation:</b> {saturation}%"
            f"</span>",
            unsafe_allow_html=True,
        )

        for r in sorted(station_results, key=lambda x: x["depth_in"], reverse=True):
            _c        = r["sev_color"]
            _st_color = STATUS_COLORS.get(r["status"], "#64748b")
            st.markdown(
                f"<div style='padding:10px 14px; margin-bottom:6px; background:#ffffff; border:1px solid #e2e8f0; "
                f"border-left:4px solid {_c}; border-radius:0 8px 8px 0; box-shadow:0 1px 2px rgba(15,23,42,0.03);'>"
                f"<b style='color:#0f172a;'>{r['name']}</b> &nbsp;"
                f"<span style='color:{_st_color}; font-weight:700;'>{r['status']}</span>"
                f" &nbsp;→&nbsp; "
                f"<span style='color:{_c}; font-weight:700;'>{r['severity']}</span>"
                f"<br><span style='color:#64748b; font-size:0.8rem;'>"
                f"Runoff: {r['runoff_cfs']:,} CFS &nbsp;|&nbsp; "
                f"Pumping: {r['pump_cfs']:,} CFS &nbsp;|&nbsp; "
                f"Overflow: {r['overflow_pct']}% &nbsp;|&nbsp; "
                f"Depth after {duration}h: <b style='color:{_c};'>{r['depth_in']:.1f} inches</b>"
                f"</span></div>",
                unsafe_allow_html=True,
            )

with tab2:
    if not sim_enabled:
        st.info("Enable simulation to see hour-by-hour flood projections.")
    else:
        rows = []
        for r in station_results:
            for h in r["hourly"]:
                rows.append({
                    "Hour": h["hour"],
                    "Station": f"{r['id']} ({r['neighborhood'][:10]})",
                    "Standing Water (inches)": h["depth_in"],
                })
        if rows:
            df_timeline = pd.DataFrame(rows)
            fig = px.line(
                df_timeline, x="Hour", y="Standing Water (inches)",
                color="Station",
                title=f"Projected Flood Accumulation Over {duration} Hours",
                markers=True,
            )
            fig.add_hline(y=1,  line_dash="dot", line_color="#f59e0b",
                          annotation_text="Ankle deep (1\")",   annotation_position="right")
            fig.add_hline(y=6,  line_dash="dot", line_color="#f97316",
                          annotation_text="Knee deep (6\")",    annotation_position="right")
            fig.add_hline(y=12, line_dash="dot", line_color="#ef4444",
                          annotation_text="Major flood (12\")", annotation_position="right")
            fig.update_layout(
                paper_bgcolor="#ffffff", plot_bgcolor="#f8fafc",
                font_color="#0f172a", height=420,
                margin=dict(l=20, r=120, t=50, b=20),
                xaxis_title="Hours into storm",
                yaxis_title="Standing water (inches)",
                legend=dict(orientation="v", x=1.02, y=1),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No flooding projected under current simulation parameters.")
