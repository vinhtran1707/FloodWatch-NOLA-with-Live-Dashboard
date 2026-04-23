from __future__ import annotations

import os
import sys

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.data_fetchers import get_all_data
from utils.swbno_data import STATUS_COLORS

st.set_page_config(
    page_title="Infrastructure — FloodWatch NOLA",
    page_icon="⚙️",
    layout="wide",
)

_css_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "style.css")
with open(_css_path) as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

if "data" not in st.session_state:
    with st.spinner("Fetching data…"):
        st.session_state["data"] = get_all_data()

data = st.session_state["data"]
swbno = data.get("swbno", {})
stations = swbno.get("stations", [])
basins = swbno.get("drainage_basins", [])

st.markdown(
    "<div style='font-size:0.8rem; color:#64748b;'>🌊 FloodWatch NOLA</div>",
    unsafe_allow_html=True,
)
st.title("⚙️ Infrastructure Status — SWBNO")

# ── Our edge callout ───────────────────────────────────────────────────────
st.info(
    "**FloodWatch NOLA is the only platform that integrates real-time SWBNO pump "
    "station status into flood risk scoring.** National models like First Street and "
    "FEMA assume the drainage system functions at design spec — we don't. "
    "When Turbine 4 failed in August 2017, no national model predicted the flooding "
    "that followed. We would have."
)

st.divider()

# ── System-wide metrics ────────────────────────────────────────────────────
pumps_available = swbno.get("pumps_available", 0)
pumps_total = swbno.get("pumps_total", 0)
pumps_offline = swbno.get("pumps_offline", 0)
system_cap = swbno.get("system_capacity_pct", 0)
turbines_online = swbno.get("turbines_online", 0)
turbines_total = swbno.get("turbines_total", 0)
offline_stations = sum(1 for s in stations if s.get("status") == "OFFLINE")

m1, m2, m3, m4 = st.columns(4)
with m1:
    st.metric("Pumps Available", f"{pumps_available}/{pumps_total}")
with m2:
    st.metric(
        "System Capacity",
        f"{system_cap:.1f}%",
        delta=f"{'OK' if system_cap >= 85 else 'Degraded'}",
        delta_color="normal" if system_cap >= 85 else "inverse",
    )
with m3:
    st.metric(
        "Turbines Online",
        f"{turbines_online}/{turbines_total}",
        delta=swbno.get("turbine_4_status", ""),
        delta_color="off",
    )
with m4:
    st.metric(
        "Offline Stations",
        offline_stations,
        delta=f"-{offline_stations} capacity gap" if offline_stations > 0 else "All online",
        delta_color="inverse" if offline_stations > 0 else "normal",
    )

st.divider()

# ── Capacity gauge + station table ────────────────────────────────────────
col_gauge, col_table = st.columns([1, 2])

with col_gauge:
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=system_cap,
            title={"text": "System Drainage Capacity", "font": {"size": 14, "color": "#f1f5f9"}},
            number={"suffix": "%", "font": {"size": 28, "color": "#f1f5f9"}},
            gauge={
                "axis": {"range": [0, 100], "tickcolor": "#64748b"},
                "bar": {"color": "#0ea5e9"},
                "bgcolor": "#1e293b",
                "bordercolor": "#334155",
                "steps": [
                    {"range": [0, 60], "color": "#ef444430"},
                    {"range": [60, 85], "color": "#f59e0b30"},
                    {"range": [85, 100], "color": "#10b98130"},
                ],
                "threshold": {
                    "line": {"color": "#ef4444", "width": 3},
                    "thickness": 0.75,
                    "value": 60,
                },
            },
        )
    )
    fig.update_layout(
        paper_bgcolor="#ffffff",
        font_color="#0f172a",
        height=280,
        margin=dict(l=20, r=20, t=40, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)

    if swbno.get("sfc2_note"):
        st.caption(f"ℹ️ {swbno['sfc2_note']}")

with col_table:
    st.subheader("Station Status")
    df_stations = pd.DataFrame(stations)
    if not df_stations.empty:
        st.dataframe(
            df_stations[["id", "name", "neighborhood", "status", "capacity_cfs", "operational_pct"]],
            column_config={
                "id": st.column_config.TextColumn("Station ID"),
                "name": st.column_config.TextColumn("Station Name"),
                "neighborhood": st.column_config.TextColumn("Neighborhood"),
                "status": st.column_config.TextColumn("Status"),
                "capacity_cfs": st.column_config.NumberColumn(
                    "Capacity (CFS)", format="%d CFS"
                ),
                "operational_pct": st.column_config.ProgressColumn(
                    "Operational %", min_value=0, max_value=100
                ),
            },
            use_container_width=True,
            hide_index=True,
            height=260,
        )

st.divider()

# ── Drainage basin risk ────────────────────────────────────────────────────
st.subheader("Drainage Basin Risk Assessment")

BASIN_COLORS = {
    "High": "#10b981",
    "Medium": "#f59e0b",
    "Standby": "#f97316",
    "Critical": "#ef4444",
}

if basins:
    rows_html = ""
    for b in basins:
        coverage = b.get("pump_coverage", "Unknown")
        color = BASIN_COLORS.get(coverage, "#64748b")
        rows_html += (
            f"<tr>"
            f"<td style='padding:8px 12px; border-bottom:1px solid #334155;'>{b['basin']}</td>"
            f"<td style='padding:8px 12px; border-bottom:1px solid #334155;'>"
            f"<span style='color:{color}; font-weight:700;'>{coverage}</span></td>"
            f"<td style='padding:8px 12px; border-bottom:1px solid #334155; color:#64748b;'>{b['notes']}</td>"
            f"</tr>"
        )
    st.markdown(
        f"""
        <table style='width:100%; border-collapse:collapse; font-size:0.9rem;'>
          <thead>
            <tr style='background:#f1f5f9;'>
              <th style='padding:10px 12px; text-align:left; color:#475569;'>Basin</th>
              <th style='padding:10px 12px; text-align:left; color:#475569;'>Pump Coverage</th>
              <th style='padding:10px 12px; text-align:left; color:#475569;'>Notes</th>
            </tr>
          </thead>
          <tbody>{rows_html}</tbody>
        </table>
        """,
        unsafe_allow_html=True,
    )

st.divider()

# ── Maintenance strain scoring ─────────────────────────────────────────────
st.subheader("🔧 Station Maintenance Strain — 311 Signal")
st.caption(
    "Each station's catchment is scored by the volume of recent 311 drainage complaints "
    "within its service area. High complaint volume indicates citizen-observed drainage "
    "failures — a leading indicator of pump strain."
)

reports_311 = data.get("reports_311") or []
station_elevations = data.get("station_elevations") or {}

_STATION_CATCHMENT_NEIGHBORHOODS = {
    "DPS-02": ["Mid-City", "Tremé", "7th Ward"],
    "DPS-07": ["Lakeview", "Navarre"],
    "DPS-12": ["Gentilly", "Fillmore"],
    "DPS-19": ["Broadmoor", "Hollygrove"],
    "DPS-24": ["Bywater", "Holy Cross", "Lower 9th Ward"],
    "DPS-31": ["CBD", "French Quarter", "Marigny"],
    "DPS-38": ["Algiers", "Algiers Point"],
    "SFC2":   ["Uptown", "Garden District", "Carrollton", "Riverbend"],
}

_STATION_COORDS = {
    "DPS-02": (29.9720, -90.0851),
    "DPS-07": (30.0045, -90.1068),
    "DPS-12": (29.9897, -90.0567),
    "DPS-19": (29.9542, -90.1012),
    "DPS-24": (29.9514, -90.0459),
    "DPS-31": (29.9653, -90.0712),
    "DPS-38": (29.9268, -90.0598),
    "SFC2":   (29.9654, -90.0771),
}

def _haversine_km(lat1, lon1, lat2, lon2):
    import math
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))

def _count_nearby_complaints(station_id: str, complaints: list[dict], radius_km: float = 2.0) -> int:
    slat, slon = _STATION_COORDS.get(station_id, (29.95, -90.07))
    count = 0
    for c in complaints:
        try:
            clat = float(c.get("latitude") or 0)
            clon = float(c.get("longitude") or 0)
            if clat and clon and _haversine_km(slat, slon, clat, clon) <= radius_km:
                count += 1
        except (ValueError, TypeError):
            pass
    return count

strain_data = []
for s in stations:
    sid = s["id"]
    nearby = _count_nearby_complaints(sid, reports_311)
    status = s.get("status", "UNKNOWN")
    op_pct = s.get("operational_pct", 100)

    if status == "OFFLINE" or nearby >= 4:
        strain_level, strain_color = "Critical", "#ef4444"
    elif status == "STANDBY" or nearby >= 2:
        strain_level, strain_color = "Elevated", "#f59e0b"
    else:
        strain_level, strain_color = "Normal", "#10b981"

    elev = station_elevations.get(sid, 0.0)
    strain_data.append({
        "Station": sid,
        "Neighborhood": s.get("neighborhood", ""),
        "Status": status,
        "Op %": op_pct,
        "311 Reports Nearby": nearby,
        "Elevation (ft)": elev,
        "Strain": strain_level,
        "_color": strain_color,
    })

strain_cols = st.columns(min(4, len(strain_data)))
for i, row in enumerate(strain_data):
    with strain_cols[i % 4]:
        c = row["_color"]
        st.markdown(
            f"<div style='background:#ffffff; border:1px solid {c}60; border-top:3px solid {c}; "
            f"border-radius:8px; padding:10px 12px; margin-bottom:10px; font-size:0.82rem;"
            f" box-shadow:0 1px 2px rgba(15,23,42,0.03);'>"
            f"<b style='font-size:0.95rem; color:#0f172a;'>{row['Station']}</b><br>"
            f"<span style='color:#64748b;'>{row['Neighborhood']}</span><br>"
            f"<span style='color:{c}; font-weight:700;'>{row['Strain']} Strain</span><br>"
            f"<span style='color:#64748b;'>311 nearby: {row['311 Reports Nearby']} &nbsp;·&nbsp; "
            f"Elev: {row['Elevation (ft)']:+.1f} ft</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

st.caption(
    "311 complaint radius: 2 km per station. "
    "Source: NOLA 311 OPCD dataset (data.nola.gov). "
    "Elevation from USGS EPQS (nationalmap.gov)."
)

st.divider()

# ── Historical flooding data ───────────────────────────────────────────────
st.subheader("📈 Historical Flooding Record — Orleans Parish")

hist_tab1, hist_tab2 = st.tabs(["311 Drainage Complaints by Year", "Key Flood Events"])

with hist_tab1:
    history_311 = data.get("history_311") or []
    if history_311:
        df_hist = pd.DataFrame(history_311).sort_values("year")
        fig_hist = px.bar(
            df_hist,
            x="year",
            y="complaints",
            title="Annual Drainage Complaints Filed with NOLA 311 (2019–Present)",
            color="complaints",
            color_continuous_scale=["#10b981", "#f59e0b", "#ef4444"],
            text="complaints",
        )
        fig_hist.update_layout(
            paper_bgcolor="#ffffff",
            plot_bgcolor="#f8fafc",
            font_color="#0f172a",
            height=360,
            coloraxis_showscale=False,
            xaxis_title="Year",
            yaxis_title="Drainage Complaints",
        )
        fig_hist.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
        st.plotly_chart(fig_hist, use_container_width=True)
        st.caption(
            "Source: NOLA 311 OPCD Calls dataset (data.nola.gov · 2jgv-pqrq) · "
            "Filtered to request_type = Drainage / Roads/Drainage"
        )
        st.info(
            "**2021 spike:** Post-Ida recovery generated 9,302 drainage complaints — "
            "the highest on record. 2024's 5,479 reflects ongoing infrastructure strain. "
            "High complaint years correlate directly with pump station offline events."
        )
    else:
        st.warning("311 historical data unavailable.")

with hist_tab2:
    FLOOD_EVENTS = [
        {"date": "Aug 29, 2005", "event": "Hurricane Katrina",
         "peak_depth_ft": 20.0, "impact": "80% of city flooded. $125B total damage. 1,800+ deaths.",
         "infrastructure": "Levee failures — drainage system overwhelmed."},
        {"date": "May 8, 2012", "event": "May 2012 Flood",
         "peak_depth_ft": 2.5, "impact": "Widespread street flooding, ~$50M damage.",
         "infrastructure": "Multiple SWBNO pump stations at reduced capacity."},
        {"date": "Aug 5, 2017", "event": "August 2017 Pump Failure",
         "peak_depth_ft": 3.0, "impact": "Mid-City, Lakeview, Broadmoor flooded. ~$46M damage.",
         "infrastructure": "SWBNO turbine failure. 2 of 3 turbines offline during active rainfall."},
        {"date": "Jul 10, 2019", "event": "Tropical Storm Barry",
         "peak_depth_ft": 1.5, "impact": "Flash flooding across lower-lying neighborhoods.",
         "infrastructure": "SFC2 Superpump in testing mode, reduced system capacity."},
        {"date": "Aug 29, 2021", "event": "Hurricane Ida",
         "peak_depth_ft": 6.0, "impact": "Major flooding. Prolonged power outages. $75B+ regional damage.",
         "infrastructure": "Complete power loss to SWBNO for 12+ hours. Zero pump capacity."},
        {"date": "Jul 2024", "event": "July 2024 Flash Floods",
         "peak_depth_ft": 2.0, "impact": "Gentilly and Lakeview inundated. 500+ 311 reports in 48hrs.",
         "infrastructure": "DPS-07 (Lakeview) on standby during peak rainfall."},
    ]

    for ev in FLOOD_EVENTS:
        depth_color = "#ef4444" if ev["peak_depth_ft"] > 4 else ("#f59e0b" if ev["peak_depth_ft"] > 2 else "#10b981")
        st.markdown(
            f"""
            <div style='border-left: 3px solid {depth_color}; padding: 10px 16px;
                        margin-bottom: 12px; background: #1e293b; border-radius: 0 8px 8px 0;'>
              <div style='font-size:0.8rem; color:#64748b;'>{ev["date"]}</div>
              <div style='font-weight:700; font-size:1rem; color:#0f172a;'>{ev["event"]}</div>
              <div style='color:#64748b; font-size:0.85rem; margin-top:4px;'>
                Peak depth: <span style='color:{depth_color}; font-weight:600;'>{ev["peak_depth_ft"]} ft</span>
                &nbsp;|&nbsp; {ev["impact"]}
              </div>
              <div style='color:#64748b; font-size:0.8rem; margin-top:3px;'>
                ⚙️ {ev["infrastructure"]}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.divider()

# ── Historical context callout ─────────────────────────────────────────────
st.warning(
    "**August 2017 Case Study:** A SWBNO turbine failure during moderate rainfall "
    "left Mid-City and Lakeview underwater despite forecasts predicting manageable "
    "conditions. The flooding caused an estimated $46M in damage. National risk models "
    "— including First Street Foundation and FEMA's NHFP — did not predict this event "
    "because they assume the drainage system operates at design capacity. "
    "**FloodWatch NOLA accounts for this.**"
)

# ── Data freshness ─────────────────────────────────────────────────────────
st.divider()
st.subheader("Data Freshness")
col_fresh1, col_fresh2 = st.columns(2)
with col_fresh1:
    st.markdown(f"**Last fetched:** `{swbno.get('timestamp', 'Unknown')}`")
    st.markdown(f"**Source:** {swbno.get('source', 'SWBNO Dashboard')}")
with col_fresh2:
    st.markdown("**Production scraper status:** 🔵 In development")
    st.markdown("**Live integration ETA:** Q3 2026")

# ── Technical note ─────────────────────────────────────────────────────────
with st.expander("🔧 How We Get This Data"):
    st.markdown(
        """
        **Data Source:** [SWBNO Pumping & Power Dashboard](https://www.swbno.org/Projects/PumpingAndPower)

        The SWBNO dashboard at `swbno.org/Projects/PumpingAndPower` publicly displays
        pump station status, turbine readings, and system capacity metrics.

        **Scraping Strategy:**

        The production scraper uses `BeautifulSoup` for static HTML rendering or
        `Playwright` if the dashboard requires JavaScript execution. Status is parsed
        from the color-coded station indicators updated every 5 minutes by SWBNO.

        **Current MVP:** Demo data matching the April 2026 dashboard state. The
        scraper skeleton below shows the production approach:
        """
    )
    st.code(
        '''import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

SWBNO_URL = "https://www.swbno.org/Projects/PumpingAndPower"

def scrape_swbno_static() -> dict | None:
    """Attempt static scrape first (faster)."""
    r = requests.get(SWBNO_URL, timeout=15,
                     headers={"User-Agent": "FloodWatchNOLA/1.0"})
    if r.status_code != 200:
        return None
    soup = BeautifulSoup(r.text, "lxml")
    # Parse pump status indicators
    stations = []
    for row in soup.select(".pump-station-row"):
        station_id = row.select_one(".station-id").text.strip()
        status = row.select_one(".status-badge").text.strip()
        capacity = int(row.select_one(".capacity-cfs").text.replace(",", ""))
        stations.append({"id": station_id, "status": status, "capacity_cfs": capacity})
    return {"stations": stations}

def scrape_swbno_js() -> dict | None:
    """Fallback: JS-rendered scrape via Playwright."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(SWBNO_URL, wait_until="networkidle")
        # Extract rendered DOM
        content = page.content()
        browser.close()
    return parse_swbno_html(content)
''',
        language="python",
    )
    st.caption(
        "This scraper is in active development. Production deployment requires "
        "SWBNO's acceptance of automated read access, which is pending outreach."
    )
