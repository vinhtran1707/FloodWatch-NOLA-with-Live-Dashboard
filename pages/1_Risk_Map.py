from __future__ import annotations

import os
import sys

import folium
import folium.plugins as fplugins
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from streamlit_folium import st_folium

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _score_to_color(score: int) -> str:
    """Continuous green → yellow → red hex for a 0–100 risk score."""
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


def _score_to_weight(score: int) -> float:
    """Line thickness: 2px (score=0) → 9px (score=100)."""
    return 2.0 + (score / 100.0) * 7.0

from utils.data_fetchers import get_all_data, geocode_address, get_osm_streets, get_elevation_grid
from utils.nlp_geo import geolocate_social_posts
from utils.risk_engine import (
    compute_risk_score,
    score_neighborhood_streets,
    neighborhood_plain_language,
    NEIGHBORHOOD_STREETS,
)
from utils.swbno_data import STATUS_COLORS

st.set_page_config(
    page_title="Risk Map — Crest",
    page_icon="📍",
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
elevations  = data.get("station_elevations", {})
nfip_claims = data.get("nfip_claims") or []
reports_311 = data.get("reports_311") or []
hourly_12   = data.get("hourly_12") or []
risk        = compute_risk_score(data)
precip_pct  = risk["precip_pct"]

_raw_social = data.get("social_feed") or []
social_posts = geolocate_social_posts(_raw_social)
social_mapped = [p for p in social_posts if "lat" in p]

st.markdown("<div style='font-size:0.8rem; color:#64748b;'>🌊 Crest</div>", unsafe_allow_html=True)
st.title("📍 Risk Map — Orleans Parish")

# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔍 Find My Street")
    address_input = st.text_input(
        "Enter your address",
        value=st.session_state.get("address", ""),
        placeholder="e.g. 900 Palmyra St, New Orleans",
        label_visibility="collapsed",
    )
    search_clicked = st.button("📍 Search", use_container_width=True)

    _all_neighborhoods = [
        "Mid-City", "Lakeview", "Broadmoor", "Gentilly", "Bywater",
        "Tremé", "Algiers", "Garden District", "Uptown", "CBD / French Quarter",
    ]
    neighborhood = st.selectbox(
        "My neighborhood",
        _all_neighborhoods,
        index=_all_neighborhoods.index(st.session_state.get("neighborhood", "Mid-City"))
        if st.session_state.get("neighborhood", "Mid-City") in _all_neighborhoods else 0,
    )
    st.session_state["neighborhood"] = neighborhood

    st.divider()
    st.markdown("**Show on map:**")
    show_streets      = True  # always on — primary layer
    show_311_pins     = st.checkbox("311 Flood Reports", value=True)
    show_social_pins  = st.checkbox("Social Media Reports", value=True)
    show_pumps        = st.checkbox("Pump Stations", value=True)
    show_heatmap      = st.checkbox("Flood Heatmap", value=False)

    with st.expander("Advanced layers"):
        show_elevation = st.checkbox("USGS Terrain (3DEP)", value=False)
        show_nfip      = st.checkbox("NFIP Claims by ZIP", value=False)
        show_gauges    = st.checkbox("USGS Water Gauges", value=False)

    st.divider()
    _mapped_ct = len(social_mapped)
    if _mapped_ct:
        st.caption(f"💬 {_mapped_ct} social report(s) mapped from live feed")
    st.caption("SWBNO station locations are approximate.")

# ── Geocode address ────────────────────────────────────────────────────────
geocode_result = None
if search_clicked and address_input:
    with st.spinner("Locating address…"):
        q = address_input if "new orleans" in address_input.lower() else address_input + ", New Orleans, LA"
        geocode_result = geocode_address(q)
    if not geocode_result:
        st.warning("Address not found. Try adding a street number or cross street.")

# ── Fetch real OSM street geometry + elevation grid (both cached) ──────────
with st.spinner(f"Loading street geometry for {neighborhood}…"):
    _osm_raw  = get_osm_streets(neighborhood)
    _elev_grid = get_elevation_grid(neighborhood)

_streets_to_score = _osm_raw[:300] if _osm_raw else None

# ── Score street segments with per-street SRTM elevation ──────────────────
street_scores = score_neighborhood_streets(
    neighborhood, swbno, precip_pct, reports_311,
    streets=_streets_to_score, elev_grid=_elev_grid,
)

# ── Plain-language outlook (above map) ────────────────────────────────────
outlook = neighborhood_plain_language(
    neighborhood, risk, swbno, street_scores, reports_311, hourly_12
)
_risk_color = risk["color"]
st.markdown(
    f"<div style='background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:1rem 1.25rem; "
    f"color:#0f172a; border-left:4px solid {_risk_color}; margin-bottom:1rem;'>{outlook}</div>",
    unsafe_allow_html=True,
)

# ── 12-hour forecast strip ─────────────────────────────────────────────────
if hourly_12:
    hours  = [h["hour"] for h in hourly_12]
    precips = [h["precip"] for h in hourly_12]
    colors  = ["#ef4444" if p >= 60 else "#f59e0b" if p >= 30 else "#10b981" for p in precips]
    fig_strip = go.Figure(go.Bar(
        x=hours, y=precips,
        marker_color=colors,
        text=[f"{p}%" for p in precips],
        textposition="outside",
        hovertemplate="%{x}<br>Precipitation: %{y}%<extra></extra>",
    ))
    fig_strip.add_hline(y=60, line_dash="dash", line_color="#ef4444",
                        annotation_text="High risk threshold", annotation_position="right")
    fig_strip.update_layout(
        title="12-Hour Precipitation Forecast",
        paper_bgcolor="#ffffff", plot_bgcolor="#f8fafc",
        font_color="#0f172a", height=200,
        margin=dict(l=20, r=80, t=40, b=20),
        xaxis_title="Hour", yaxis_title="Precip %",
        yaxis_range=[0, 110],
        showlegend=False,
    )
    st.plotly_chart(fig_strip, use_container_width=True)

# ── Station coordinates ────────────────────────────────────────────────────
STATION_COORDS: dict[str, list[float]] = {
    "DPS-02": [29.9720, -90.0851], "DPS-07": [30.0045, -90.1068],
    "DPS-12": [29.9897, -90.0567], "DPS-19": [29.9542, -90.1012],
    "DPS-24": [29.9514, -90.0459], "DPS-31": [29.9653, -90.0712],
    "DPS-38": [29.9268, -90.0598], "SFC2":   [29.9654, -90.0771],
}

# ── NFIP claims by ZIP ─────────────────────────────────────────────────────
ZIP_CENTROIDS = {
    "70112": [29.9500,-90.0760], "70113": [29.9380,-90.0830],
    "70114": [29.9310,-90.0460], "70115": [29.9290,-90.0990],
    "70116": [29.9680,-90.0620], "70117": [29.9580,-90.0490],
    "70118": [29.9400,-90.1180], "70119": [29.9790,-90.0870],
    "70122": [30.0050,-90.0390], "70124": [30.0090,-90.1140],
    "70125": [29.9500,-90.1090], "70126": [30.0020,-90.0260],
    "70127": [30.0170,-90.0050], "70128": [30.0250,-89.9840],
    "70130": [29.9440,-90.0690], "70131": [29.9110,-90.0360],
}
zip_claims: dict[str, int] = {}
for rec in nfip_claims:
    z = rec.get("reportedZipCode", "")
    if z:
        zip_claims[z] = zip_claims.get(z, 0) + 1
max_claims = max(zip_claims.values()) if zip_claims else 1

# ── Build map — center on selected neighborhood ────────────────────────────
NEIGHBORHOOD_CENTER = {
    "Broadmoor": [29.955, -90.102], "Lakeview": [30.002, -90.107],
    "Gentilly":  [29.988, -90.053], "Mid-City": [29.970, -90.087],
    "Bywater":   [29.950, -90.043], "Tremé":    [29.962, -90.067],
    "Algiers":   [29.927, -90.056], "Garden District": [29.932, -90.093],
    "Uptown":    [29.930, -90.110], "CBD / French Quarter": [29.952, -90.070],
}
center = NEIGHBORHOOD_CENTER.get(neighborhood, [29.9511, -90.0715])
zoom = 15 if neighborhood in NEIGHBORHOOD_CENTER else 12

m = folium.Map(location=center, zoom_start=zoom, tiles=None)

folium.TileLayer(
    tiles="https://cartodb-basemaps-{s}.global.ssl.fastly.net/dark_all/{z}/{x}/{y}.png",
    attr='&copy; OpenStreetMap contributors &copy; CARTO',
    name="CartoDB Dark Matter", max_zoom=19,
).add_to(m)
folium.TileLayer(tiles="CartoDB positron", name="CartoDB Positron").add_to(m)

# ── Layer: USGS elevation WMS ──────────────────────────────────────────────
if show_elevation:
    folium.WmsTileLayer(
        url="https://elevation.nationalmap.gov/arcgis/services/3DEPElevation/ImageServer/WMSServer",
        layers="3DEPElevation:Hillshade Gray",
        name="USGS Elevation (3DEP)",
        fmt="image/png", transparent=True, opacity=0.40,
        attr="USGS 3DEP Elevation",
    ).add_to(m)

# ── Layer: Street flood risk — Waze-style gradient ────────────────────────
if show_streets and street_scores:
    street_group = folium.FeatureGroup(name="Street Flood Risk", show=True)
    for seg in street_scores:
        score       = seg["score"]
        depth_in    = seg.get("depth_in", 0.0)
        depth_label = seg.get("depth_label", "< 0.3 in — clear")
        passability = seg.get("passability", "🟢 Passable")
        flood_status = seg.get("flood_status", "CLEAR")

        # Color: depth-driven when flooding, score-driven when clear
        if depth_in >= 1:
            if depth_in >= 12: color = "#a855f7"
            elif depth_in >= 6: color = "#ef4444"
            else:               color = "#f97316"
        else:
            color = _score_to_color(score)

        weight = _score_to_weight(score)
        complaint_note = (
            f"<br>⚠️ {seg['nearby_complaints']} nearby 311 report(s)"
            if seg["nearby_complaints"] > 0 else ""
        )
        popup_html = (
            f"<div style='font-family:sans-serif; min-width:220px; color:#1e293b;'>"
            f"<b style='font-size:1rem;'>{seg['name']}</b><br>"
            f"<span style='color:{color}; font-weight:700; font-size:1.1rem;'>"
            f"{depth_label}</span><br>"
            f"<span style='font-size:0.85rem;'>{passability}</span><br>"
            f"<hr style='margin:5px 0; border-color:#cbd5e1;'>"
            f"Risk score: <b>{score}/100</b><br>"
            f"Ground elevation: <b>{seg['elevation_ft']:+.1f} ft</b><br>"
            f"Pump station: <b>{seg['pump_status']}</b><br>"
            f"Precip probability: <b>{int(precip_pct)}%</b>"
            f"{complaint_note}"
            f"</div>"
        )
        if score >= 40:
            folium.PolyLine(
                locations=seg["coords"],
                color=color, weight=weight * 2.8, opacity=0.18,
            ).add_to(street_group)
        folium.PolyLine(
            locations=seg["coords"],
            color=color, weight=weight, opacity=0.88,
            popup=folium.Popup(popup_html, max_width=260),
            tooltip=f"{seg['name']} — {depth_label} · {passability}",
            line_cap="round", line_join="round",
        ).add_to(street_group)
    street_group.add_to(m)

# ── Layer: Flood zone heatmap overlay ─────────────────────────────────────
if show_heatmap and street_scores:
    heat_pts = []
    for seg in street_scores:
        mid = seg["coords"][len(seg["coords"]) // 2]
        heat_pts.append([mid[0], mid[1], seg["score"] / 100.0])
    if heat_pts:
        fplugins.HeatMap(
            heat_pts,
            name="Flood Zone Heatmap",
            min_opacity=0.25,
            max_opacity=0.65,
            radius=28,
            blur=22,
            gradient={
                "0.0": "#10b981",
                "0.4": "#84cc16",
                "0.6": "#eab308",
                "0.75": "#f97316",
                "1.0": "#ef4444",
            },
        ).add_to(m)

# ── Layer: 311 complaint pins (address-level) ─────────────────────────────
if show_311_pins:
    complaint_group = folium.FeatureGroup(name="311 Drainage Complaints")
    for rep in reports_311:
        try:
            lat = float(rep.get("latitude") or 0)
            lon = float(rep.get("longitude") or 0)
            if not lat or not lon:
                continue
            is_mock  = rep.get("is_mock", False)
            reason   = rep.get("request_reason", "Drainage issue")
            req_type = rep.get("request_type", "Drainage")
            date     = rep.get("date_created", "")[:10]
            svc_req  = rep.get("service_request", "N/A")
            popup_html = (
                f"<div style='font-family:sans-serif; min-width:190px;'>"
                f"<b>311 Report {'🔵 Demo' if is_mock else ''}</b><br>"
                f"<b>#{svc_req}</b><br>"
                f"<hr style='margin:4px 0; border-color:#334155;'>"
                f"Type: {req_type}<br>"
                f"Issue: {reason}<br>"
                f"Filed: {date}<br>"
                f"<span style='font-size:0.75rem; color:#64748b;'>"
                f"Lat: {lat:.4f}, Lon: {lon:.4f}</span>"
                f"</div>"
            )
            folium.CircleMarker(
                location=[lat, lon],
                radius=7,
                color="#a855f7",
                fill=True,
                fill_color="#a855f7",
                fill_opacity=0.85,
                popup=folium.Popup(popup_html, max_width=230),
                tooltip=f"311: {reason[:45]} — {date}",
            ).add_to(complaint_group)
        except (ValueError, TypeError):
            continue
    complaint_group.add_to(m)

# ── Layer: Social media reports (NLP-geolocated) ──────────────────────────
if show_social_pins and social_mapped:
    social_group = folium.FeatureGroup(name="Social Media Reports", show=True)
    for post in social_mapped:
        src      = post.get("source", "")
        title    = post.get("title", "")
        pub      = post.get("published", "")[:16].replace("T", " ")
        link     = post.get("link", "")
        loc_name = post.get("matched_location", "New Orleans")
        is_mock  = post.get("is_mock", False)
        reddit   = "reddit" in src.lower()
        upvotes  = post.get("score")

        bg_color = "#f97316" if reddit else "#0ea5e9"
        if is_mock:
            bg_color = "#6b7280"
        label = "Reddit" if reddit else "News"

        bubble_html = (
            f"<div style='position:relative; display:inline-block; cursor:pointer;'>"
            f"<div style='background:{bg_color}; color:white; padding:3px 8px; "
            f"border-radius:8px; font-size:10px; font-weight:700; "
            f"white-space:nowrap; box-shadow:0 2px 6px rgba(0,0,0,0.5);'>"
            f"💬 {label}</div>"
            f"<div style='position:absolute; left:50%; transform:translateX(-50%); "
            f"top:100%; width:0; height:0; "
            f"border-left:5px solid transparent; border-right:5px solid transparent; "
            f"border-top:6px solid {bg_color};'></div>"
            f"</div>"
        )

        score_line = f"<br>⬆️ {upvotes} upvotes" if upvotes is not None else ""
        link_line  = f"<br><a href='{link}' target='_blank' style='color:#38bdf8;'>→ Read post</a>" if link else ""
        mock_badge = " 🔵 Demo" if is_mock else ""
        popup_html = (
            f"<div style='font-family:sans-serif; min-width:230px; color:#0f172a;'>"
            f"<b style='font-size:0.85rem;'>{src}{mock_badge}</b><br>"
            f"<span style='font-size:0.9rem; color:#1e293b;'>{title[:110]}</span><br>"
            f"<hr style='margin:5px 0; border-color:#e2e8f0;'>"
            f"<span style='color:#64748b; font-size:0.75rem;'>"
            f"📍 {loc_name} &nbsp;·&nbsp; {pub}"
            f"{score_line}</span>"
            f"{link_line}"
            f"</div>"
        )

        folium.Marker(
            location=[post["lat"], post["lon"]],
            popup=folium.Popup(popup_html, max_width=260),
            tooltip=f"💬 {src}: {title[:60]}",
            icon=folium.DivIcon(
                html=bubble_html,
                icon_size=(80, 34),
                icon_anchor=(40, 34),
            ),
        ).add_to(social_group)
    social_group.add_to(m)

# ── Layer: NFIP claims circles ─────────────────────────────────────────────
if show_nfip and zip_claims:
    nfip_group = folium.FeatureGroup(name="NFIP Claims Density")
    for zipcode, count in zip_claims.items():
        centroid = ZIP_CENTROIDS.get(zipcode)
        if not centroid:
            continue
        ratio = count / max_claims
        color = "#ef4444" if ratio > 0.7 else "#f59e0b" if ratio > 0.4 else "#10b981"
        folium.Circle(
            location=centroid, radius=300 + ratio * 900,
            color=color, fill=True, fill_color=color, fill_opacity=0.28,
            popup=folium.Popup(f"<b>ZIP {zipcode}</b><br>NFIP Claims: {count}", max_width=180),
            tooltip=f"ZIP {zipcode} — {count} NFIP claims",
        ).add_to(nfip_group)
    nfip_group.add_to(m)

# ── Layer: SWBNO pump stations ─────────────────────────────────────────────
if show_pumps:
    pump_group = folium.FeatureGroup(name="SWBNO Pump Stations")
    for station in stations:
        coord = STATION_COORDS.get(station["id"])
        if not coord:
            continue
        color = STATUS_COLORS.get(station["status"], "#808080")
        elev = elevations.get(station["id"])
        elev_str = f"{elev:+.1f} ft AMSL" if elev is not None else "N/A"
        elev_warn = " ⚠️ Below sea level" if elev is not None and elev < 0 else ""
        popup_html = (
            f"<div style='font-family:sans-serif; min-width:200px;'>"
            f"<h4 style='margin:0 0 6px 0;'>{station['name']}</h4>"
            f"<b>Status:</b> <span style='color:{color}; font-weight:bold;'>{station['status']}</span><br>"
            f"<b>Capacity:</b> {station['capacity_cfs']:,} CFS<br>"
            f"<b>Operational:</b> {station['operational_pct']}%<br>"
            f"<b>Elevation:</b> {elev_str}"
            f"<span style='color:#ef4444;'>{elev_warn}</span></div>"
        )
        folium.CircleMarker(
            location=coord, radius=12, color=color, weight=2,
            fill=True, fill_color=color, fill_opacity=0.8,
            popup=folium.Popup(popup_html, max_width=250),
            tooltip=f"{station['name']} — {station['status']} | {elev_str}",
        ).add_to(pump_group)
    pump_group.add_to(m)

# ── Layer: USGS gauges ─────────────────────────────────────────────────────
if show_gauges:
    gauge_group = folium.FeatureGroup(name="USGS Water Gauges")
    river_gauge = data.get("river_gauge")
    pont_gauge  = data.get("pontchartrain_gauge")
    river_ft_str = f"{river_gauge['value_ft']:.2f} ft" if river_gauge else "N/A"
    pont_ft_str  = f"{pont_gauge['value_ft']:.2f} ft" if pont_gauge else "N/A"
    river_warn = " ⚠️ Above action stage (17 ft)" if river_gauge and river_gauge["value_ft"] > 17 else ""
    for loc, label, reading, warn in [
        ([29.9504,-90.0680], "Mississippi River at New Orleans", river_ft_str, river_warn),
        ([30.0271,-90.0784], "Lake Pontchartrain at Lakefront", pont_ft_str, ""),
    ]:
        folium.Marker(
            location=loc,
            popup=folium.Popup(
                f"<b>{label}</b><br>Level: {reading}<span style='color:#ef4444;'>{warn}</span>",
                max_width=240,
            ),
            tooltip=f"USGS: {label} — {reading}{warn}",
            icon=folium.DivIcon(
                html="<div style='width:14px;height:14px;background:#3b82f6;border-radius:2px;border:2px solid #fff;'></div>",
                icon_size=(14, 14), icon_anchor=(7, 7),
            ),
        ).add_to(gauge_group)
    gauge_group.add_to(m)

# ── Geocoded address pin ───────────────────────────────────────────────────
if geocode_result:
    folium.Marker(
        location=[geocode_result["lat"], geocode_result["lon"]],
        popup=folium.Popup(
            f"<b>Your Location</b><br>{geocode_result['display'][:80]}", max_width=260
        ),
        tooltip="📍 Your address",
        icon=folium.Icon(color="red", icon="home", prefix="fa"),
    ).add_to(m)
    m.location = [geocode_result["lat"], geocode_result["lon"]]
    m.zoom_start = 16

# ── Legend ─────────────────────────────────────────────────────────────────
legend_html = """
<div style='position:fixed; bottom:30px; right:10px; z-index:9999;
            background:rgba(15,23,42,0.94); padding:14px 18px;
            border-radius:10px; border:1px solid #334155;
            font-family:sans-serif; font-size:12px; color:#f1f5f9; line-height:1.8;'>
  <b style='font-size:13px; color:#f1f5f9;'>Street Flood Depth</b><br>
  <div style='margin:6px 0 4px 0;
              background:linear-gradient(to right,#10b981,#f59e0b,#f97316,#ef4444);
              height:10px; border-radius:5px; width:160px;'></div>
  <div style='display:flex; justify-content:space-between; width:160px;
              font-size:9px; color:#64748b; margin-bottom:4px;'>
    <span>Clear</span><span>Wet</span><span>Flooding</span><span>Severe</span>
  </div>
  <span style='font-size:10px; color:#64748b;'>Thicker line = deeper water</span><br>
  <br>
  <b style='color:#f1f5f9;'>Pump Stations</b><br>
  <span style='color:#10b981;'>⬤</span> <span style='color:#e2e8f0;'>PUMPING</span> &nbsp;
  <span style='color:#f59e0b;'>⬤</span> <span style='color:#e2e8f0;'>STANDBY</span><br>
  <span style='color:#ef4444;'>⬤</span> <span style='color:#e2e8f0;'>OFFLINE</span> &nbsp;
  <span style='color:#3b82f6;'>⬤</span> <span style='color:#e2e8f0;'>TESTING</span><br>
  <br>
  <b style='color:#f1f5f9;'>Reports</b><br>
  <span style='color:#a855f7;'>⬤</span> <span style='color:#e2e8f0;'>311 Official</span><br>
  <span style='background:#f97316;color:white;padding:1px 5px;border-radius:4px;font-size:10px;'>💬 Reddit</span>
  &nbsp;
  <span style='background:#0ea5e9;color:white;padding:1px 5px;border-radius:4px;font-size:10px;'>💬 News</span>
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))
folium.LayerControl(collapsed=True).add_to(m)

st_folium(m, width=None, height=640, returned_objects=[])

st.divider()

# ── Below-map tabs ─────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["🛣️ Street Risk Detail", "🏦 NFIP Claims", "📊 Station Elevations"])

with tab1:
    st.subheader(f"Street-Level Flood Risk — {neighborhood}")
    if street_scores:
        # Deduplicate by street name, keep highest-scoring segment per name
        _best_by_name: dict = {}
        for seg in street_scores:
            n = seg["name"]
            if n not in _best_by_name or seg["score"] > _best_by_name[n]["score"]:
                _best_by_name[n] = seg
        _unique = sorted(_best_by_name.values(), key=lambda s: s["score"], reverse=True)
        st.caption(f"{len(_unique)} named streets · {len(street_scores)} total OSM segments scored")
        for seg in _unique:
            depth_in    = seg.get("depth_in", 0.0)
            depth_label = seg.get("depth_label", "< 0.3 in — clear")
            passability = seg.get("passability", "🟢 Passable")
            if depth_in >= 6:     color = "#ef4444"
            elif depth_in >= 1:   color = "#f97316"
            elif depth_in >= 0.3: color = "#f59e0b"
            else:                 color = "#10b981"
            complaints_badge = (
                f" &nbsp;<span style='background:#a855f720; color:#a855f7; "
                f"padding:1px 6px; border-radius:4px; font-size:0.75rem;'>"
                f"⚠️ {seg['nearby_complaints']} complaint(s)</span>"
                if seg["nearby_complaints"] > 0 else ""
            )
            st.markdown(
                f"<div style='padding:10px 14px; margin-bottom:8px; background:#ffffff; border:1px solid #e2e8f0; "
                f"border-left:4px solid {color}; border-radius:0 8px 8px 0;'>"
                f"<b style='color:#0f172a;'>{seg['name']}</b>"
                f"<span style='color:{color}; font-weight:700; margin-left:10px;'>{depth_label}</span>"
                f"{complaints_badge}<br>"
                f"<span style='color:#64748b; font-size:0.82rem;'>"
                f"{passability} &nbsp;|&nbsp; "
                f"Elev: {seg['elevation_ft']:+.1f} ft &nbsp;|&nbsp; "
                f"Pump: {seg['pump_status']} &nbsp;|&nbsp; Score: {seg['score']}/100</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
    else:
        st.info(f"No street data available for {neighborhood} yet.")

    st.divider()
    st.subheader("Recent 311 Drainage Reports")
    if reports_311:
        for rep in reports_311[:10]:
            is_mock = rep.get("is_mock", False)
            reason  = rep.get("request_reason", "Drainage issue")
            date    = rep.get("date_created", "")[:10]
            svc_req = rep.get("service_request", "")
            lat     = rep.get("latitude", "")
            lon     = rep.get("longitude", "")
            loc_str = f"({float(lat):.4f}, {float(lon):.4f})" if lat and lon else "No coordinates"
            try:
                loc_str = f"({float(lat):.4f}, {float(lon):.4f})" if lat and lon else "No coordinates"
            except (ValueError, TypeError):
                loc_str = "No coordinates"
            st.markdown(
                f"<div style='padding:8px 12px; margin-bottom:6px; background:#ffffff; border:1px solid #e2e8f0; "
                f"border-left:3px solid #a855f7; border-radius:0 6px 6px 0;'>"
                f"<b style='color:#0f172a;'>{reason}</b> {'🔵 Demo' if is_mock else ''}<br>"
                f"<span style='color:#64748b; font-size:0.8rem;'>"
                f"#{svc_req} &nbsp;·&nbsp; {date} &nbsp;·&nbsp; 📍 {loc_str}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
    else:
        st.info("No recent 311 reports available.")

with tab2:
    if nfip_claims:
        df_nfip = pd.DataFrame(nfip_claims)
        df_nfip["amountPaidOnBuildingClaim"] = pd.to_numeric(
            df_nfip["amountPaidOnBuildingClaim"], errors="coerce"
        ).fillna(0)
        col_a, col_b = st.columns(2)
        with col_a:
            zip_summary = (
                df_nfip.groupby("reportedZipCode")
                .agg(claims=("yearOfLoss","count"), total_paid=("amountPaidOnBuildingClaim","sum"))
                .sort_values("claims", ascending=False).reset_index()
            )
            zip_summary["total_paid"] = zip_summary["total_paid"].map("${:,.0f}".format)
            zip_summary.columns = ["ZIP", "Claims", "Building Payouts"]
            st.dataframe(zip_summary, hide_index=True, use_container_width=True)
        with col_b:
            year_summary = (
                df_nfip.groupby("yearOfLoss").agg(claims=("reportedZipCode","count"))
                .sort_index(ascending=False).reset_index().head(12)
            )
            fig_yr = px.bar(year_summary, x="yearOfLoss", y="claims",
                            color="claims", color_continuous_scale=["#10b981","#f59e0b","#ef4444"],
                            title="Claims by Year")
            fig_yr.update_layout(paper_bgcolor="#ffffff", plot_bgcolor="#f8fafc",
                                  font_color="#0f172a", height=300, coloraxis_showscale=False)
            st.plotly_chart(fig_yr, use_container_width=True)
    else:
        st.warning("FEMA NFIP data unavailable.")

with tab3:
    elev_rows = []
    for s in stations:
        elev = elevations.get(s["id"])
        elev_rows.append({
            "Station": s["name"], "ID": s["id"],
            "Elevation (ft)": elev,
            "Below Sea Level": "⚠️ Yes" if elev is not None and elev < 0 else "No",
            "Status": s["status"],
        })
    df_elev = pd.DataFrame(elev_rows).sort_values("Elevation (ft)")
    fig_elev = px.bar(df_elev, x="Station", y="Elevation (ft)",
                      color="Elevation (ft)", color_continuous_scale=["#ef4444","#f59e0b","#10b981"],
                      title="Ground Elevation at Pump Stations (ft AMSL)", text="Elevation (ft)")
    fig_elev.add_hline(y=0, line_dash="dash", line_color="#64748b",
                       annotation_text="Sea level", annotation_position="right")
    fig_elev.update_layout(paper_bgcolor="#ffffff", plot_bgcolor="#f8fafc",
                            font_color="#0f172a", height=340, coloraxis_showscale=False)
    fig_elev.update_traces(texttemplate="%{text:+.1f} ft", textposition="outside")
    st.plotly_chart(fig_elev, use_container_width=True)
