from __future__ import annotations

import os
import sys
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.data_fetchers import get_all_data, get_osm_streets, get_elevation_grid
from utils.risk_engine import (
    compute_risk_score,
    score_neighborhood_streets,
    neighborhood_plain_language,
    NEIGHBORHOOD_STREETS,
    NEIGHBORHOOD_STATION,
)
from utils.swbno_data import STATUS_COLORS

st.set_page_config(
    page_title="waterline",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded",
)

_css_path = os.path.join(os.path.dirname(__file__), "assets", "style.css")
with open(_css_path) as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


# ── Session state init ─────────────────────────────────────────────────────
for key, default in [
    ("user_type", "Small Business Owner"),
    ("address", "New Orleans, LA"),
    ("neighborhood", "Mid-City"),
]:
    if key not in st.session_state:
        st.session_state[key] = default


# ── Data fetch ─────────────────────────────────────────────────────────────
def _load_data():
    with st.spinner("Fetching live data from NOAA, USGS, SWBNO…"):
        st.session_state["data"] = get_all_data()


if "data" not in st.session_state:
    _load_data()

data = st.session_state["data"]
_fetch_dt = datetime.fromisoformat(data["fetch_time"])
_age_min = (datetime.now() - _fetch_dt).total_seconds() / 60
if _age_min > 30:
    _load_data()
    data = st.session_state["data"]
    _age_min = 0

risk       = compute_risk_score(data)
swbno      = data.get("swbno", {})
hourly_12  = data.get("hourly_12") or []
forecast   = data.get("forecast") or {}
reports_311 = data.get("reports_311") or []
neighborhood = st.session_state["neighborhood"]

_osm_raw   = get_osm_streets(neighborhood)
_elev_grid = get_elevation_grid(neighborhood)
_streets_to_score = _osm_raw[:300] if _osm_raw else None
street_scores = score_neighborhood_streets(
    neighborhood, swbno, risk["precip_pct"], reports_311,
    streets=_streets_to_score, elev_grid=_elev_grid,
)
# Deduplicate by name for the dashboard panel (keep highest-scoring segment per name)
_best_by_name: dict = {}
for _seg in street_scores:
    _n = _seg["name"]
    if _n not in _best_by_name or _seg["score"] > _best_by_name[_n]["score"]:
        _best_by_name[_n] = _seg
street_scores = sorted(_best_by_name.values(), key=lambda s: s["score"], reverse=True)


# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        "<div style='text-align:center; padding:0.75rem 0;'>"
        "<div style='font-size:1.9rem; font-weight:900;'>🌊 waterline</div>"
        "<div style='font-size:0.8rem; color:#64748b; margin-top:0.2rem;'>"
        "Orleans Parish Resilience Platform</div></div>",
        unsafe_allow_html=True,
    )
    st.divider()

    user_type = st.selectbox(
        "I am a…",
        ["Small Business Owner", "Renter / Tenant", "Property Manager", "Community Member"],
        index=["Small Business Owner", "Renter / Tenant", "Property Manager", "Community Member"]
        .index(st.session_state["user_type"]),
    )
    st.session_state["user_type"] = user_type

    address = st.text_input("My address or intersection", value=st.session_state["address"])
    st.session_state["address"] = address

    neighborhood = st.selectbox(
        "My neighborhood",
        ["Mid-City", "Lakeview", "Gentilly", "Broadmoor", "Bywater",
         "Tremé", "Algiers", "Garden District", "Uptown", "CBD / French Quarter"],
        index=["Mid-City", "Lakeview", "Gentilly", "Broadmoor", "Bywater",
               "Tremé", "Algiers", "Garden District", "Uptown", "CBD / French Quarter"]
        .index(st.session_state["neighborhood"]),
    )
    st.session_state["neighborhood"] = neighborhood

    st.divider()
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.session_state.pop("data", None)
        get_all_data.clear() if hasattr(get_all_data, "clear") else None
        st.rerun()

    st.caption("NOAA NWS · USGS NWIS · SWBNO · NOLA Open Data · FEMA OpenFEMA")
    st.caption("Built at Tulane University Freeman School of Business")


# ── Header ─────────────────────────────────────────────────────────────────
col_title, col_live = st.columns([3, 1])
with col_title:
    st.markdown("<div style='font-size:0.8rem; color:#64748b;'>🌊 waterline</div>",
                unsafe_allow_html=True)
    st.title("New Orleans Flood Risk Dashboard")
with col_live:
    indicator = "🟢 Live" if _age_min <= 10 else "🟠 Stale"
    ind_color  = "#10b981" if _age_min <= 10 else "#f59e0b"
    st.markdown(
        f"<div style='text-align:right; padding-top:2rem;'>"
        f"<span style='color:{ind_color}; font-weight:700;'>{indicator}</span><br>"
        f"<span style='font-size:0.75rem; color:#64748b;'>Updated {int(_age_min)}m ago</span>"
        f"</div>",
        unsafe_allow_html=True,
    )


# ── Risk score banner ──────────────────────────────────────────────────────
score     = risk["score"]
level     = risk["level"]
risk_color = risk["color"]

st.markdown(
    f"<div style='background:{risk_color}18; border:1px solid {risk_color}50; "
    f"border-radius:12px; padding:1.25rem; margin-bottom:0.75rem;'>"
    f"<div style='display:flex; align-items:center; gap:1.5rem;'>"
    f"<div style='text-align:center; min-width:110px;'>"
    f"<div style='font-size:4.5rem; font-weight:900; color:{risk_color}; line-height:1;'>{score}</div>"
    f"<div style='font-size:1.1rem; font-weight:700; color:{risk_color};'>{level} RISK</div>"
    f"<div style='font-size:0.7rem; color:#64748b;'>/100 composite</div>"
    f"</div>"
    f"<div style='flex:1; color:#64748b; font-size:0.85rem;'>"
    f"Primary signal: <b style='color:#0f172a;'>{risk['components']['infrastructure']['label']}</b>"
    f"</div></div></div>",
    unsafe_allow_html=True,
)

col_prog, col_comp = st.columns([2, 1])
with col_prog:
    st.progress(score / 100, text=f"Composite Risk: {score}/100")
    for action in risk.get("recommended_actions", []):
        st.markdown(f"• {action}")
with col_comp:
    for comp_name, comp in risk["components"].items():
        label = comp_name.replace("_", " ").title()
        st.markdown(
            f"<div style='font-size:0.72rem; color:#64748b; margin-top:0.4rem;'>"
            f"<b>{label}</b> ({int(comp['weight']*100)}%) — {comp['label']}</div>",
            unsafe_allow_html=True,
        )
        st.progress(comp["score"] / 100)

st.divider()


# ── Live weather card + 12-hour strip ─────────────────────────────────────
weather_col, strip_col = st.columns([1, 2])

with weather_col:
    st.subheader("🌤️ Current Conditions")
    temp    = forecast.get("temperature", "—")
    unit    = forecast.get("temperatureUnit", "F")
    wind    = forecast.get("windSpeed", "—")
    wdir    = forecast.get("windDirection", "")
    short_fc = forecast.get("shortForecast", "Unavailable")
    river_ft = risk["river_ft"]
    river_color = "#ef4444" if river_ft > 17 else "#f59e0b" if river_ft > 14 else "#10b981"
    river_label = "Above action stage" if river_ft > 17 else "Elevated" if river_ft > 14 else "Normal"

    st.markdown(
        f"<div style='background:#ffffff; border:1px solid #e2e8f0; border-radius:10px; padding:1rem; box-shadow:0 1px 2px rgba(15,23,42,0.03);'>"
        f"<div style='font-size:2.5rem; font-weight:900; color:#0f172a;'>{temp}°{unit}</div>"
        f"<div style='color:#64748b;'>{short_fc}</div>"
        f"<div style='color:#64748b; margin-top:0.5rem; font-size:0.85rem;'>"
        f"💨 Wind: {wind} {wdir}<br>"
        f"🌧️ Precip: {int(risk['precip_pct'])}%<br>"
        f"<span style='color:{river_color};'>🌊 River: {river_ft:.1f} ft — {river_label}</span>"
        f"</div></div>",
        unsafe_allow_html=True,
    )
    st.caption("Source: NOAA NWS · USGS NWIS")

with strip_col:
    st.subheader("⏱️ 12-Hour Precipitation Forecast")
    if hourly_12:
        hours   = [h["hour"] for h in hourly_12]
        precips = [h["precip"] for h in hourly_12]
        colors  = ["#ef4444" if p >= 60 else "#f59e0b" if p >= 30 else "#3b82f6" for p in precips]
        fig_strip = go.Figure(go.Bar(
            x=hours, y=precips, marker_color=colors,
            text=[f"{p}%" for p in precips], textposition="outside",
            hovertemplate="%{x} — %{y}% chance of rain<extra></extra>",
        ))
        fig_strip.add_hline(y=60, line_dash="dash", line_color="#ef4444",
                            annotation_text="High risk", annotation_position="right")
        fig_strip.update_layout(
            paper_bgcolor="#ffffff", plot_bgcolor="#f8fafc",
            font_color="#0f172a", height=200,
            margin=dict(l=10, r=80, t=10, b=20),
            yaxis_range=[0, 115], yaxis_title="Precip %",
            xaxis_title="Hour (local)", showlegend=False,
        )
        st.plotly_chart(fig_strip, use_container_width=True)
    else:
        st.warning("12-hour forecast unavailable.")

st.divider()


# ── Metrics row ────────────────────────────────────────────────────────────
pumps_available = swbno.get("pumps_available", 0)
pumps_total     = swbno.get("pumps_total", 0)
pumps_offline   = swbno.get("pumps_offline", 0)
flood_count     = risk["flood_alerts_count"]
precip_pct      = risk["precip_pct"]
river_ft        = risk["river_ft"]

mc1, mc2, mc3, mc4 = st.columns(4)
with mc1:
    st.metric("Pumps Online", f"{pumps_available}/{pumps_total}",
              delta=f"-{pumps_offline} offline" if pumps_offline > 0 else "All operational",
              delta_color="inverse" if pumps_offline > 0 else "normal")
with mc2:
    st.metric("Flood Alerts", flood_count,
              delta="Active NWS alerts" if flood_count > 0 else "None active",
              delta_color="inverse" if flood_count > 0 else "normal")
with mc3:
    st.metric("Precip. Probability", f"{int(precip_pct)}%",
              delta="Above threshold" if precip_pct > 50 else "Below threshold",
              delta_color="inverse" if precip_pct > 50 else "normal")
with mc4:
    st.metric("River Level", f"{river_ft:.1f} ft" if river_ft else "N/A",
              delta="⚠️ Above action stage (17 ft)" if river_ft > 17 else "Below action stage",
              delta_color="inverse" if river_ft > 17 else "normal")

st.divider()


# ── Neighborhood street outlook ────────────────────────────────────────────
st.subheader(f"🛣️ Street Risk — {neighborhood}")
outlook = neighborhood_plain_language(
    neighborhood, risk, swbno, street_scores, reports_311, hourly_12
)
_risk_color = risk["color"]
st.markdown(
    f"<div style='background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:1rem 1.25rem; "
    f"color:#0f172a; border-left:4px solid {_risk_color}; margin-bottom:0.75rem;'>{outlook}</div>",
    unsafe_allow_html=True,
)

if street_scores:
    _sorted_segs = sorted(street_scores, key=lambda s: s.get("depth_in", 0), reverse=True)
    _total = len(_sorted_segs)
    for seg in _sorted_segs[:10]:
        depth_in    = seg.get("depth_in", 0.0)
        depth_label = seg.get("depth_label", "< 0.3 in — clear")
        passability = seg.get("passability", "🟢 Passable")
        if depth_in >= 6:    c = "#ef4444"
        elif depth_in >= 1:  c = "#f97316"
        elif depth_in >= 0.3: c = "#f59e0b"
        else:                 c = "#10b981"
        badge = (
            f" <span style='background:#a855f720; color:#a855f7; "
            f"padding:1px 5px; border-radius:4px; font-size:0.72rem;'>"
            f"⚠️ {seg['nearby_complaints']} complaint(s)</span>"
            if seg["nearby_complaints"] > 0 else ""
        )
        st.markdown(
            f"<div style='padding:8px 12px; margin-bottom:5px; background:#ffffff; border:1px solid #e2e8f0; "
            f"border-left:4px solid {c}; border-radius:0 6px 6px 0;'>"
            f"<b style='color:#0f172a;'>{seg['name']}</b> "
            f"<span style='color:{c}; font-weight:700;'>{depth_label}</span>{badge}<br>"
            f"<span style='color:#64748b; font-size:0.78rem;'>"
            f"{passability} &nbsp;·&nbsp; Elev: {seg['elevation_ft']:+.1f} ft &nbsp;·&nbsp; Score: {seg['score']}/100"
            f"</span></div>",
            unsafe_allow_html=True,
        )
    if _total > 10:
        st.caption(f"Showing 10 of {_total} streets — see full map on Risk Map page.")

st.divider()


# ── Two-column: infrastructure + 311 reports ──────────────────────────────
col_left, col_right = st.columns([1.2, 0.8])

with col_left:
    st.subheader("⚙️ Infrastructure Status")
    stations = swbno.get("stations", [])
    if stations:
        df = pd.DataFrame(stations)

        def _style_status(val):
            colors = {
                "PUMPING": "background-color:#10b981; color:#fff; border-radius:4px; padding:2px 6px;",
                "STANDBY": "background-color:#f59e0b; color:#000; border-radius:4px; padding:2px 6px;",
                "OFFLINE": "background-color:#ef4444; color:#fff; border-radius:4px; padding:2px 6px;",
                "TESTING": "background-color:#3b82f6; color:#fff; border-radius:4px; padding:2px 6px;",
            }
            return colors.get(val, "")

        styled = df[["id","neighborhood","status","capacity_cfs","operational_pct"]].style.map(
            _style_status, subset=["status"]
        )
        st.dataframe(
            styled,
            column_config={
                "id": st.column_config.TextColumn("ID"),
                "neighborhood": st.column_config.TextColumn("Neighborhood"),
                "status": st.column_config.TextColumn("Status"),
                "capacity_cfs": st.column_config.NumberColumn("Capacity", format="%d CFS"),
                "operational_pct": st.column_config.ProgressColumn("Operational", min_value=0, max_value=100),
            },
            use_container_width=True, hide_index=True,
        )

    st.caption("🔵 Demo Data · SWBNO Pumping & Power Dashboard · Live scraper in development")

with col_right:
    alerts = data.get("alerts") or []
    st.subheader("⚠️ Active NWS Alerts")
    if alerts:
        for alert in alerts[:4]:
            props = alert.get("properties", {})
            event = props.get("event", "Unknown Event")
            area  = props.get("areaDesc", "")
            if "flood" in event.lower():
                st.error(f"**{event}** — {area[:55]}")
            else:
                st.warning(f"**{event}** — {area[:55]}")
    elif data.get("alerts") is None:
        st.warning("NWS alerts API unreachable")
    else:
        st.success("No active weather alerts for Orleans Parish")

    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("📞 311 Drainage Reports")
    has_mock = any(r.get("is_mock") for r in reports_311)
    if has_mock:
        st.caption("🔵 Demo Data — 311 API fallback")

    for rep in reports_311[:6]:
        is_mock = rep.get("is_mock", False)
        reason  = rep.get("request_reason", "Drainage issue")
        req_type = rep.get("request_type", "Drainage")
        date    = rep.get("date_created", "")[:10]
        svc_req = rep.get("service_request", "")
        try:
            lat = float(rep.get("latitude") or 0)
            lon = float(rep.get("longitude") or 0)
            loc_str = f"{lat:.4f}, {lon:.4f}" if lat and lon else "No GPS"
        except (ValueError, TypeError):
            loc_str = "No GPS"
        st.markdown(
            f"<div style='padding:7px 10px; margin-bottom:5px; background:#ffffff; border:1px solid #e2e8f0; "
            f"border-left:3px solid #a855f7; border-radius:0 6px 6px 0; font-size:0.85rem;'>"
            f"<b style='color:#0f172a;'>{reason[:50]}</b> {'🔵' if is_mock else ''}<br>"
            f"<span style='color:#64748b;'>#{svc_req} · {date} · 📍 {loc_str}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

st.divider()


# ── Social / News feed ────────────────────────────────────────────────────
social_feed = data.get("social_feed") or []
with st.expander("📰 Live Flood Reports — News & Social Media", expanded=False):
    if social_feed:
        has_mock = any(p.get("is_mock") for p in social_feed)
        if has_mock:
            st.caption("🔵 Demo posts shown — live scrape returned no results")
        for post in social_feed[:10]:
            src      = post.get("source", "")
            title    = post.get("title", "")
            pub      = post.get("published", "")[:16].replace("T", " ")
            link     = post.get("link", "")
            is_mock  = post.get("is_mock", False)
            score    = post.get("score")

            if "reddit" in src.lower():
                icon = "🟠"
            elif "nola.com" in src.lower():
                icon = "📰"
            elif "wwl" in src.lower():
                icon = "📺"
            else:
                icon = "🔗"

            score_badge = f" · ⬆️ {score}" if score is not None else ""
            mock_badge  = " 🔵" if is_mock else ""
            link_html   = f"<a href='{link}' target='_blank' style='color:#38bdf8;'>→ Read</a>" if link else ""

            st.markdown(
                f"<div style='padding:8px 12px; margin-bottom:6px; background:#ffffff; border:1px solid #e2e8f0; "
                f"border-left:3px solid #38bdf8; border-radius:0 6px 6px 0; font-size:0.85rem;'>"
                f"{icon} <b style='color:#0f172a;'>{title[:90]}</b>{mock_badge}<br>"
                f"<span style='color:#64748b;'>{src} · {pub}{score_badge}</span>"
                f"{'&nbsp;&nbsp;' + link_html if link_html else ''}"
                f"</div>",
                unsafe_allow_html=True,
            )
    else:
        st.info("No flood-related posts found in the past 7 days.")
    st.caption("Sources: NOLA.com RSS · WWL-TV RSS · Reddit r/NewOrleans · Reddit r/Louisiana")


# ── Actions panel ─────────────────────────────────────────────────────────
user_label = st.session_state["user_type"]
with st.expander(f"📋 Recommended Actions for {user_label}", expanded=True):
    ac1, ac2 = st.columns(2)
    with ac1:
        st.markdown("**For Small Business Owners**")
        for i, action in enumerate(risk.get("smb_actions", [])):
            st.checkbox(action, key=f"smb_{i}")
    with ac2:
        st.markdown("**For Renters / Tenants**")
        for i, action in enumerate(risk.get("renter_actions", [])):
            st.checkbox(action, key=f"rent_{i}")


# ── Partial data warning ───────────────────────────────────────────────────
missing = [src for src, key in [("NWS Alerts","alerts"),("NOAA Forecast","forecast"),("USGS Gauge","river_gauge")]
           if data.get(key) is None]
if missing:
    st.warning(f"Some live data unavailable — showing demo fallbacks. Missing: {', '.join(missing)}")
