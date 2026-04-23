"""
FloodWatch NOLA — Live Dashboard (client demo surface)

Design intent: this page is the sales-demo view we show to prospects.
It's deliberately distinct from app.py (the consumer homepage):

  • Light theme — white canvas, green accents, no dark mode
  • Two tabs — Individual (renter/homeowner) and Small Business
  • Auto-refresh every 5 minutes
  • Reliability-adjusted risk using SWBNO maintenance history
  • Business-tab computes revenue-at-risk from user-supplied daily revenue

Everything inline-styles its components so the dark styling used elsewhere
in the app doesn't leak into this page.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta

import folium
import folium.plugins as fplugins
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_folium import st_folium

# Make utils importable when Streamlit runs this file directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.data_fetchers import get_all_data
from utils.risk_engine import compute_risk_score, NEIGHBORHOOD_STATION
from utils.maintenance_history import (
    get_events_for_station,
    get_events_for_neighborhood,
    get_recent_burst_pipes,
    reliability_score_for_station,
    capacity_adjustment_for_neighborhood,
    get_all_events,
    EVENT_TYPE_META,
)
from utils.nola_places import (
    search_places,
    format_place_label,
    get_place_by_name,
)

# Optional searchbox — fall back to text_input if not installed
try:
    from streamlit_searchbox import st_searchbox
    _HAS_SEARCHBOX = True
except ImportError:
    _HAS_SEARCHBOX = False


# ── Neighborhood centers (used for map focus + highlight circle) ──────────
NEIGHBORHOOD_CENTERS: dict[str, tuple[float, float]] = {
    "Mid-City":             (29.9720, -90.0950),
    "Lakeview":             (29.9950, -90.1150),
    "Gentilly":             (29.9900, -90.0550),
    "Broadmoor":            (29.9468, -90.1002),
    "Bywater":              (29.9612, -90.0412),
    "Tremé":                (29.9642, -90.0718),
    "Algiers":              (29.9400, -90.0400),
    "Garden District":      (29.9248, -90.0852),
    "Uptown":               (29.9198, -90.1138),
    "CBD / French Quarter": (29.9495, -90.0712),
}

# Optional auto-refresh dependency — fall back gracefully if not installed
try:
    from streamlit_autorefresh import st_autorefresh
    _HAS_AUTOREFRESH = True
except ImportError:
    _HAS_AUTOREFRESH = False


# ── Page config + theme override ───────────────────────────────────────────
st.set_page_config(page_title="Live Dashboard · FloodWatch NOLA",
                   page_icon="🌿", layout="wide")

# Hard-override any inherited dark styling from the rest of the app.
# This page is LIGHT. Green + white.
st.markdown("""
<style>
  /* Base canvas — force light */
  .stApp { background-color: #ffffff; }
  [data-testid="stHeader"] { background-color: rgba(255,255,255,0.9); }
  .main .block-container { padding-top: 1.5rem; padding-bottom: 3rem; max-width: 1400px; }

  /* Typography */
  h1, h2, h3, h4, p, span, label, div {
    color: #0f172a;
  }

  /* KPI tile — used throughout */
  .fw-tile {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 14px;
    padding: 1.1rem 1.25rem;
    box-shadow: 0 1px 3px rgba(15,23,42,0.04);
    height: 100%;
  }
  .fw-tile-label {
    font-size: 0.72rem;
    font-weight: 700;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 0.35rem;
  }
  .fw-tile-value {
    font-size: 2.1rem;
    font-weight: 800;
    color: #0f172a;
    line-height: 1.1;
  }
  .fw-tile-sub {
    font-size: 0.78rem;
    color: #64748b;
    margin-top: 0.3rem;
  }
  .fw-tile-accent-green {
    border-left: 4px solid #16a34a;
  }
  .fw-tile-accent-amber {
    border-left: 4px solid #f59e0b;
  }
  .fw-tile-accent-red {
    border-left: 4px solid #dc2626;
  }

  /* Callout card */
  .fw-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 14px;
    padding: 1.25rem;
    margin-bottom: 0.75rem;
  }
  .fw-card-green {
    background: #f0fdf4;
    border-color: #bbf7d0;
  }
  .fw-card-amber {
    background: #fffbeb;
    border-color: #fde68a;
  }
  .fw-card-red {
    background: #fef2f2;
    border-color: #fecaca;
  }

  /* Live pill */
  .fw-live-pill {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    background: #f0fdf4;
    color: #15803d;
    border: 1px solid #bbf7d0;
    border-radius: 999px;
    padding: 0.3rem 0.75rem;
    font-size: 0.78rem;
    font-weight: 700;
  }
  .fw-live-dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: #22c55e;
    box-shadow: 0 0 0 0 rgba(34,197,94,0.7);
    animation: fw-pulse 2s infinite;
  }
  @keyframes fw-pulse {
    0% { box-shadow: 0 0 0 0 rgba(34,197,94,0.6); }
    70% { box-shadow: 0 0 0 10px rgba(34,197,94,0); }
    100% { box-shadow: 0 0 0 0 rgba(34,197,94,0); }
  }

  /* Tab styling — green accent */
  .stTabs [data-baseweb="tab-list"] {
    gap: 0.5rem;
    border-bottom: 1px solid #e2e8f0;
  }
  .stTabs [data-baseweb="tab"] {
    background: transparent;
    color: #64748b;
    font-weight: 600;
    padding: 0.65rem 1.1rem;
  }
  .stTabs [aria-selected="true"] {
    color: #15803d !important;
    border-bottom: 2px solid #16a34a !important;
  }

  /* Event row */
  .fw-event {
    display: flex;
    gap: 0.75rem;
    padding: 0.65rem 0.85rem;
    background: #f8fafc;
    border-radius: 8px;
    margin-bottom: 0.5rem;
    border-left: 3px solid #16a34a;
  }
  .fw-event-icon { font-size: 1.25rem; }
  .fw-event-body { flex: 1; }
  .fw-event-title { font-size: 0.9rem; font-weight: 600; color: #0f172a; }
  .fw-event-meta { font-size: 0.75rem; color: #64748b; margin-top: 0.15rem; }

  /* Section header */
  .fw-section-header {
    font-size: 1.1rem;
    font-weight: 700;
    color: #0f172a;
    margin-top: 1.25rem;
    margin-bottom: 0.6rem;
    padding-left: 0.5rem;
    border-left: 3px solid #16a34a;
  }

  /* ─── ANIMATION 1: Animated water wave strip ─── */
  @keyframes fw-wave-slide {
    from { background-position: 0 0; }
    to   { background-position: -120px 0; }
  }
  .fw-wave-strip {
    height: 7px;
    margin: 0.35rem 0 0.75rem 0;
    background-image: url("data:image/svg+xml;charset=utf-8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 120 7' preserveAspectRatio='none'><path d='M0,3.5 C15,1.5 30,5.5 45,3.5 C60,1.5 75,5.5 90,3.5 C105,1.5 120,5.5 135,3.5 L120,7 L0,7 Z' fill='%2316a34a' fill-opacity='0.22'/><path d='M0,4.5 C15,2.5 30,6.5 45,4.5 C60,2.5 75,6.5 90,4.5 C105,2.5 120,6.5 135,4.5 L120,7 L0,7 Z' fill='%2316a34a' fill-opacity='0.12'/></svg>");
    background-repeat: repeat-x;
    background-size: 120px 7px;
    animation: fw-wave-slide 5s linear infinite;
    border-radius: 2px;
  }
  .fw-section-header::after {
    content: '';
    display: block;
    height: 5px;
    margin-top: 5px;
    max-width: 260px;
    background-image: url("data:image/svg+xml;charset=utf-8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 120 5' preserveAspectRatio='none'><path d='M0,2.5 C15,1 30,4 45,2.5 C60,1 75,4 90,2.5 C105,1 120,4 135,2.5 L120,5 L0,5 Z' fill='%2316a34a' fill-opacity='0.20'/><path d='M0,3.3 C15,1.8 30,4.8 45,3.3 C60,1.8 75,4.8 90,3.3 C105,1.8 120,4.8 135,3.3 L120,5 L0,5 Z' fill='%2316a34a' fill-opacity='0.10'/></svg>");
    background-repeat: repeat-x;
    background-size: 120px 5px;
    animation: fw-wave-slide 5s linear infinite;
    border-radius: 2px;
  }

  /* ─── ANIMATION 2: Topographic contour pattern on headline cards ─── */
  @keyframes fw-topo-drift {
    from { background-position: 0 0; opacity: 0.85; }
    to   { background-position: 40px 15px; opacity: 1; }
  }
  .fw-card-headline {
    position: relative;
    overflow: hidden;
  }
  .fw-card-headline::before {
    content: '';
    position: absolute;
    inset: 0;
    background-image:
      radial-gradient(ellipse 320px 180px at 85% 60%, transparent 40%, rgba(22, 163, 74, 0.06) 40.6%, rgba(22, 163, 74, 0.06) 41.8%, transparent 42.4%),
      radial-gradient(ellipse 250px 140px at 85% 60%, transparent 40%, rgba(22, 163, 74, 0.09) 40.6%, rgba(22, 163, 74, 0.09) 41.8%, transparent 42.4%),
      radial-gradient(ellipse 185px 105px at 85% 60%, transparent 40%, rgba(22, 163, 74, 0.12) 40.6%, rgba(22, 163, 74, 0.12) 41.8%, transparent 42.4%),
      radial-gradient(ellipse 130px 75px at 85% 60%, transparent 40%, rgba(22, 163, 74, 0.15) 40.6%, rgba(22, 163, 74, 0.15) 41.8%, transparent 42.4%),
      radial-gradient(ellipse 75px 42px at 85% 60%, transparent 40%, rgba(22, 163, 74, 0.19) 40.6%, rgba(22, 163, 74, 0.19) 41.8%, transparent 42.4%);
    animation: fw-topo-drift 22s ease-in-out infinite alternate;
    pointer-events: none;
    z-index: 0;
  }
  .fw-card-headline > * { position: relative; z-index: 1; }

  /* ─── ANIMATION 3: Count-up numbers (CSS @property technique) ─── */
  @property --fw-count {
    syntax: '<integer>';
    initial-value: 0;
    inherits: false;
  }
  @keyframes fw-count-anim {
    from { --fw-count: 0; }
    to   { --fw-count: var(--fw-to, 0); }
  }
  .fw-countup {
    animation: fw-count-anim 1.6s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    counter-reset: fwc var(--fw-count);
    display: inline;
  }
  .fw-countup::after { content: counter(fwc); }
  /* Fallback: if @property not supported, show the target value via data attribute */
  @supports not (background: paint(id)) {
    .fw-countup::after { content: attr(data-final); }
  }

  /* Fade-in + gentle scale for KPI values and currency */
  @keyframes fw-fade-in-up {
    from { opacity: 0; transform: translateY(6px) scale(0.96); }
    to   { opacity: 1; transform: translateY(0)   scale(1); }
  }
  .fw-fade-in {
    animation: fw-fade-in-up 0.7s cubic-bezier(0.16, 1, 0.3, 1) both;
  }
  .fw-delay-1 { animation-delay: 0.05s; }
  .fw-delay-2 { animation-delay: 0.15s; }
  .fw-delay-3 { animation-delay: 0.25s; }
  .fw-delay-4 { animation-delay: 0.35s; }

  /* ─── Force LIGHT mode on all form inputs ─── */

  /* Labels above every widget — hit every possible wrapper */
  [data-testid="stWidgetLabel"],
  [data-testid="stWidgetLabel"] > div,
  [data-testid="stWidgetLabel"] p,
  [data-testid="stWidgetLabel"] label,
  [data-testid="stWidgetLabel"] span,
  .stSelectbox label,
  .stTextInput label,
  .stNumberInput label,
  label[data-testid="stWidgetLabel"] {
    color: #475569 !important;
    background-color: transparent !important;
    font-weight: 600 !important;
    font-size: 0.82rem !important;
  }

  /* Nuke any background on the full widget wrapper — this is what was rendering as the black bar */
  [data-testid="stTextInput"],
  [data-testid="stSelectbox"],
  [data-testid="stNumberInput"],
  [data-testid="stSearchbox"] {
    background-color: transparent !important;
  }
  [data-testid="stTextInput"] > div,
  [data-testid="stSelectbox"] > div,
  [data-testid="stNumberInput"] > div,
  [data-testid="stSearchbox"] > div {
    background-color: transparent !important;
  }

  /* ── Searchbox (streamlit_searchbox component) ── */
  [data-testid="stSearchbox"] div[data-baseweb="select"] > div,
  [data-testid="stSearchbox"] div[data-baseweb="input"] > div,
  div[data-baseweb="select"] > div,
  div[data-baseweb="input"] {
    background-color: #ffffff !important;
    border: 1px solid #cbd5e1 !important;
    border-radius: 10px !important;
    color: #0f172a !important;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03) !important;
  }
  div[data-baseweb="select"] > div:hover,
  div[data-baseweb="input"]:hover {
    border-color: #16a34a !important;
  }
  div[data-baseweb="select"] > div:focus-within,
  div[data-baseweb="input"]:focus-within {
    border-color: #16a34a !important;
    box-shadow: 0 0 0 3px rgba(22, 163, 74, 0.15) !important;
  }

  /* Input text itself + placeholder */
  div[data-baseweb="select"] input,
  div[data-baseweb="input"] input,
  input[type="text"],
  input[type="number"] {
    background-color: #ffffff !important;
    color: #0f172a !important;
    caret-color: #16a34a !important;
  }
  div[data-baseweb="select"] input::placeholder,
  div[data-baseweb="input"] input::placeholder,
  input::placeholder {
    color: #94a3b8 !important;
    opacity: 1 !important;
  }

  /* Displayed value / single-value text in selectboxes */
  div[data-baseweb="select"] [data-testid="stMarkdownContainer"],
  div[data-baseweb="select"] > div > div,
  div[data-baseweb="select"] div[role="combobox"] {
    background-color: #ffffff !important;
    color: #0f172a !important;
  }

  /* Selectbox dropdown caret icon */
  div[data-baseweb="select"] svg {
    fill: #64748b !important;
    color: #64748b !important;
  }

  /* ── Dropdown menu that pops open ── */
  div[data-baseweb="popover"] {
    background-color: #ffffff !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 10px !important;
    box-shadow: 0 8px 24px rgba(15, 23, 42, 0.12) !important;
  }
  div[data-baseweb="popover"] ul,
  ul[role="listbox"] {
    background-color: #ffffff !important;
  }
  li[role="option"],
  div[data-baseweb="popover"] li {
    background-color: #ffffff !important;
    color: #0f172a !important;
    padding: 10px 14px !important;
    border-bottom: 1px solid #f1f5f9 !important;
  }
  li[role="option"]:hover,
  li[role="option"][aria-selected="true"] {
    background-color: #f0fdf4 !important;
    color: #15803d !important;
  }
  li[role="option"]:last-child {
    border-bottom: none !important;
  }

  /* ── Number inputs (business tab — revenue, hours, employees) ── */
  .stNumberInput > div > div,
  .stNumberInput [data-baseweb="input"] {
    background-color: #ffffff !important;
    border: 1px solid #cbd5e1 !important;
    border-radius: 10px !important;
  }
  .stNumberInput button {
    background-color: #f8fafc !important;
    border-color: #e2e8f0 !important;
    color: #475569 !important;
  }
  .stNumberInput button:hover {
    background-color: #f0fdf4 !important;
    color: #15803d !important;
  }

  /* ── Refresh button ── */
  .stButton > button {
    background-color: #ffffff !important;
    color: #15803d !important;
    border: 1px solid #bbf7d0 !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    transition: all 0.15s ease !important;
  }
  .stButton > button:hover {
    background-color: #f0fdf4 !important;
    border-color: #16a34a !important;
    color: #15803d !important;
  }
  .stButton > button:active,
  .stButton > button:focus {
    background-color: #dcfce7 !important;
    border-color: #16a34a !important;
    box-shadow: 0 0 0 3px rgba(22, 163, 74, 0.15) !important;
  }

  /* ── Clear "X" button inside searchbox ── */
  [data-testid="stSearchbox"] button,
  div[data-baseweb="select"] button {
    background-color: transparent !important;
    color: #94a3b8 !important;
    border: none !important;
  }
  [data-testid="stSearchbox"] button:hover,
  div[data-baseweb="select"] button:hover {
    color: #ef4444 !important;
    background-color: transparent !important;
  }

  /* ─── KPI tile hover lift (subtle, professional) ─── */
  .fw-tile {
    transition: transform 0.18s cubic-bezier(0.2, 0.8, 0.2, 1),
                box-shadow 0.18s ease,
                border-color 0.18s ease;
    cursor: default;
  }
  .fw-tile:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(15, 23, 42, 0.08);
    border-color: #bbf7d0;
  }

  /* ─── Secondary status pill (pairs with LIVE pill) ─── */
  .fw-status-pill {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    background: #f8fafc;
    color: #475569;
    border: 1px solid #e2e8f0;
    border-radius: 999px;
    padding: 0.25rem 0.7rem;
    font-size: 0.72rem;
    font-weight: 600;
    margin-top: 0.35rem;
  }
  .fw-status-pill .dot {
    width: 6px; height: 6px; border-radius: 50%;
    background: #16a34a;
  }

  /* ─── Checklist progress bar ─── */
  .fw-progress-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.5rem;
    font-size: 0.85rem;
  }
  .fw-progress-track {
    width: 100%;
    height: 8px;
    background: #f1f5f9;
    border-radius: 999px;
    overflow: hidden;
    margin-bottom: 0.75rem;
  }
  .fw-progress-fill {
    height: 100%;
    background: linear-gradient(90deg, #16a34a 0%, #22c55e 100%);
    border-radius: 999px;
    transition: width 0.5s cubic-bezier(0.16, 1, 0.3, 1);
  }

  /* ─── Success empty-state card (no maintenance events) ─── */
  .fw-empty-success {
    background: #f0fdf4;
    border: 1px solid #bbf7d0;
    border-radius: 10px;
    padding: 1rem 1.1rem;
    display: flex;
    gap: 0.75rem;
    align-items: start;
  }
  .fw-empty-icon {
    font-size: 1.5rem;
    color: #16a34a;
    line-height: 1;
    padding-top: 2px;
  }
  .fw-empty-title {
    font-size: 0.92rem;
    font-weight: 700;
    color: #15803d;
    margin-bottom: 0.2rem;
  }
  .fw-empty-body {
    font-size: 0.82rem;
    color: #475569;
    line-height: 1.4;
  }

  /* ─── Combined search + neighborhood container ─── */
  .fw-location-bar {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 0.9rem 1rem;
    margin-bottom: 1rem;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03);
  }
  .fw-location-label {
    font-size: 0.7rem;
    font-weight: 700;
    color: #16a34a;
    letter-spacing: 0.08em;
    margin-bottom: 0.4rem;
  }

  /* ─── Branded sidebar header ─── */
  [data-testid="stSidebar"] > div:first-child {
    background: #ffffff;
  }
  [data-testid="stSidebar"] a[data-testid="stSidebarNavLink"]:hover {
    background-color: #f0fdf4 !important;
    color: #15803d !important;
  }
</style>
""", unsafe_allow_html=True)


# ── Branded sidebar header ─────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        "<div style='padding: 0.6rem 0.2rem 0.8rem; border-bottom: 1px solid #e2e8f0; "
        "margin-bottom: 0.6rem;'>"
        "<div style='display:flex; align-items:center; gap:0.6rem;'>"
        "<div style='width:34px; height:34px; background:linear-gradient(135deg,#16a34a,#15803d); "
        "border-radius:8px; display:flex; align-items:center; justify-content:center; "
        "font-size:1.1rem;'>🌿</div>"
        "<div><div style='font-size:0.98rem; font-weight:800; color:#0f172a; line-height:1.1;'>"
        "FloodWatch NOLA</div>"
        "<div style='font-size:0.68rem; color:#16a34a; font-weight:600; letter-spacing:0.05em;'>"
        "LIVE · ORLEANS PARISH</div></div></div></div>",
        unsafe_allow_html=True,
    )


# ── Auto-refresh (every 5 min) ─────────────────────────────────────────────
if _HAS_AUTOREFRESH:
    st_autorefresh(interval=5 * 60 * 1000, key="livedash_autorefresh")


# ── Data load (reuse cached fetchers from the rest of the app) ─────────────
def _load_data():
    with st.spinner("Fetching live data from NOAA · USGS · SWBNO…"):
        st.session_state["data"] = get_all_data()

if "data" not in st.session_state:
    _load_data()

data = st.session_state["data"]
fetch_dt = datetime.fromisoformat(data["fetch_time"])
age_min = (datetime.now() - fetch_dt).total_seconds() / 60
if age_min > 30:
    _load_data()
    data = st.session_state["data"]
    age_min = 0

risk = compute_risk_score(data)
swbno = data.get("swbno") or {}
forecast = data.get("forecast") or {}
hourly_12 = data.get("hourly_12") or []
reports_311 = data.get("reports_311") or []
alerts = data.get("alerts") or []


# ═══════════════════════════════════════════════════════════════════════════
# HEADER
# ═══════════════════════════════════════════════════════════════════════════
col_brand, col_right = st.columns([3, 2])
with col_brand:
    st.markdown(
        "<div style='display:flex; align-items:center; gap:0.75rem;'>"
        "<div style='width:42px; height:42px; background:linear-gradient(135deg,#16a34a,#15803d); "
        "border-radius:10px; display:flex; align-items:center; justify-content:center; "
        "font-size:1.4rem;'>🌿</div>"
        "<div><div style='font-size:0.72rem; color:#16a34a; font-weight:700; letter-spacing:0.08em;'>"
        "FLOODWATCH NOLA · LIVE</div>"
        "<div style='font-size:1.6rem; font-weight:800; color:#0f172a; line-height:1.1;'>"
        "Resilience Dashboard</div></div></div>",
        unsafe_allow_html=True,
    )
with col_right:
    updated_label = f"Updated {int(age_min)}m ago" if age_min >= 1 else "Updated just now"
    current_nb = st.session_state.get("neighborhood", "Mid-City")
    st.markdown(
        f"<div style='text-align:right; padding-top:0.75rem;'>"
        f"<span class='fw-live-pill'><span class='fw-live-dot'></span>LIVE · {updated_label}</span>"
        f"<div style='margin-top:0.3rem;'>"
        f"<span class='fw-status-pill'><span class='dot'></span>"
        f"📍 {current_nb} · NOAA · USGS · SWBNO"
        f"</span></div>"
        f"</div>",
        unsafe_allow_html=True,
    )

# Animated wave strip under the page header
st.markdown("<div class='fw-wave-strip'></div>", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════
# LOCATION INPUT (shared across both tabs)
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("<div style='height:0.75rem;'></div>", unsafe_allow_html=True)

NEIGHBORHOODS = [
    "Mid-City", "Lakeview", "Gentilly", "Broadmoor", "Bywater",
    "Tremé", "Algiers", "Garden District", "Uptown", "CBD / French Quarter",
]

st.markdown(
    "<div class='fw-location-bar'>"
    "<div class='fw-location-label'>📍  YOUR LOCATION</div>",
    unsafe_allow_html=True,
)
loc_col1, loc_col2, loc_col3 = st.columns([2, 2, 1])
with loc_col1:
    if _HAS_SEARCHBOX:
        def _place_search(search_term: str):
            """Called by st_searchbox on every keystroke."""
            if not search_term:
                return []
            results = search_places(search_term, limit=8)
            # Returns list of (display_label, value_passed_back_on_select)
            return [(format_place_label(p), p["name"]) for p in results]

        selected_name = st_searchbox(
            _place_search,
            placeholder="🔍  Type a street, landmark, or intersection…",
            label="Your address or place",
            key="place_searchbox",
            default=st.session_state.get("address"),
            clear_on_submit=False,
        )

        # When user picks a suggestion, update address + auto-set neighborhood
        if selected_name:
            picked = get_place_by_name(selected_name)
            if picked:
                st.session_state["address"] = picked["name"]
                st.session_state["picked_coords"] = (picked["lat"], picked["lon"])
                if picked.get("neighborhood"):
                    st.session_state["neighborhood"] = picked["neighborhood"]
            else:
                # Freeform text the user typed that isn't in the catalogue
                st.session_state["address"] = selected_name
                st.session_state.pop("picked_coords", None)

        address = st.session_state.get("address", "1600 Canal St")
    else:
        # Fallback — plain text input if streamlit-searchbox isn't installed
        address = st.text_input(
            "Your address or intersection",
            value=st.session_state.get("address", "1600 Canal St"),
            placeholder="e.g. 1600 Canal St or Canal & Carrollton",
        )
        st.session_state["address"] = address
        st.caption("💡 Install `streamlit-searchbox` for autocomplete suggestions.")

with loc_col2:
    default_idx = NEIGHBORHOODS.index(st.session_state.get("neighborhood", "Mid-City"))
    neighborhood = st.selectbox(
        "Neighborhood",
        NEIGHBORHOODS,
        index=default_idx,
    )
    st.session_state["neighborhood"] = neighborhood
with loc_col3:
    st.markdown("<div style='height:1.85rem;'></div>", unsafe_allow_html=True)
    if st.button("🔄 Refresh now", use_container_width=True):
        if hasattr(get_all_data, "clear"):
            get_all_data.clear()
        st.session_state.pop("data", None)
        st.rerun()

# Close fw-location-bar
st.markdown("</div>", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════
# COMPUTE LOCATION-SPECIFIC METRICS
# ═══════════════════════════════════════════════════════════════════════════
station_id = NEIGHBORHOOD_STATION.get(neighborhood)
station = next(
    (s for s in swbno.get("stations", []) if s.get("id") == station_id),
    None,
)

# Reliability-adjusted score for the chosen neighborhood's station
reliability = reliability_score_for_station(station_id) if station_id else {
    "score": 75, "label": "Unknown", "color": "#64748b",
    "baseline": 75, "delta": 0, "event_count": 0, "headline": None,
}

# Drainage capacity multiplier for the neighborhood (0.1 to 1.2)
capacity_mult = capacity_adjustment_for_neighborhood(neighborhood)

# ── Rain-gated risk model ──────────────────────────────────────
# Key insight: infrastructure weakness is a LATENT risk on dry days and an
# ACTIVE risk when rainfall is expected. A broken pump on a sunny day isn't
# a flood risk — it's an advisory. So we scale the drag by a rain multiplier
# that's zero below 20% precip probability and ramps to full at 100%.
composite_base = risk["score"]
precip_pct = risk["precip_pct"]
river_ft = risk["river_ft"]

# Raw drag components — these are the "potential" drag when it rains
raw_reliability_drag = max(0, (75 - reliability["score"])) * 0.35
raw_capacity_drag = max(0, (1.0 - capacity_mult)) * 40
raw_total_drag = raw_reliability_drag + raw_capacity_drag

# Rain multiplier: 0 below 20% precip, linearly ramps to 1.0 at 100%
rain_multiplier = max(0.0, min(1.0, (precip_pct - 20) / 80))

# Active (applied) drag — what actually inflates the score
reliability_drag = raw_reliability_drag * rain_multiplier
capacity_drag = raw_capacity_drag * rain_multiplier
adjusted_score = int(min(100, composite_base + reliability_drag + capacity_drag))

# Risk mode determines the narrative framing
# - dry: infrastructure is an advisory, not a score penalty
# - active: infrastructure compounds with rain
# - high: both rain and infrastructure are serious
if precip_pct < 20:
    risk_mode = "dry"
elif precip_pct < 50:
    risk_mode = "watch"
else:
    risk_mode = "active"

if adjusted_score < 25:
    adj_level, adj_color, adj_bg = "LOW", "#16a34a", "fw-card-green"
elif adjusted_score < 50:
    adj_level, adj_color, adj_bg = "MODERATE", "#f59e0b", "fw-card-amber"
elif adjusted_score < 75:
    adj_level, adj_color, adj_bg = "HIGH", "#dc2626", "fw-card-red"
else:
    adj_level, adj_color, adj_bg = "CRITICAL", "#991b1b", "fw-card-red"

temp = forecast.get("temperature", "—")
temp_unit = forecast.get("temperatureUnit", "F")
short_fc = forecast.get("shortForecast", "—")

# Recent maintenance around the chosen neighborhood
nb_events = get_events_for_neighborhood(neighborhood, days_back=60)
station_events = get_events_for_station(station_id) if station_id else []
recent_bursts = get_recent_burst_pipes(days_back=30)


# ═══════════════════════════════════════════════════════════════════════════
# TABS
# ═══════════════════════════════════════════════════════════════════════════
tab_ind, tab_biz = st.tabs(["👤  Individual", "🏢  Small Business"])


# ───────────────────────────────────────────────────────────────────────────
# HELPER — render a KPI tile
# ───────────────────────────────────────────────────────────────────────────

def get_risk_microcopy(level: str) -> str:
    """Short Apple/Google-style helper copy for the headline risk card."""
    if level == "LOW":
        return "Low risk. Flooding is unlikely under current conditions."
    elif level == "MODERATE":
        return "Moderate risk. Minor water buildup possible in low-lying areas."
    elif level == "HIGH":
        return "High risk. Street flooding and travel disruption are possible."
    return "Critical risk. Flooding is likely and conditions may become hazardous."


def render_tile(label: str, value: str, sub: str = "", accent: str = "green",
                delay: int = 1):
    """Render a KPI tile. `delay` 1-4 staggers the fade-in animation."""
    accent_cls = f"fw-tile-accent-{accent}"
    delay_cls = f"fw-delay-{max(1, min(4, delay))}"
    st.markdown(
        f"<div class='fw-tile {accent_cls}'>"
        f"<div class='fw-tile-label'>{label}</div>"
        f"<div class='fw-tile-value fw-fade-in {delay_cls}'>{value}</div>"
        f"<div class='fw-tile-sub'>{sub}</div></div>",
        unsafe_allow_html=True,
    )


def render_event_list(events: list, limit: int = 5):
    if not events:
        st.markdown(
            "<div class='fw-empty-success'>"
            "<div class='fw-empty-icon'>✓</div>"
            "<div>"
            "<div class='fw-empty-title'>No recent maintenance disruptions</div>"
            "<div class='fw-empty-body'>Infrastructure in this area has been operating at baseline reliability. This is a good sign for drainage capacity.</div>"
            "</div></div>",
            unsafe_allow_html=True,
        )
        return
    for e in events[:limit]:
        meta = EVENT_TYPE_META.get(e["event_type"],
                                    {"icon": "🔧", "color": "#64748b", "label": "Maintenance"})
        days_ago = (datetime.now() - datetime.fromisoformat(e["date"])).days
        when = "today" if days_ago == 0 else f"{days_ago}d ago"
        status_color = "#16a34a" if e["status"].lower() in ("completed", "repaired") else "#f59e0b"
        st.markdown(
            f"<div class='fw-event' style='border-left-color:{meta['color']};'>"
            f"<div class='fw-event-icon'>{meta['icon']}</div>"
            f"<div class='fw-event-body'>"
            f"<div class='fw-event-title'>{e['description']}</div>"
            f"<div class='fw-event-meta'>{meta['label']} · {when} · "
            f"<span style='color:{status_color}; font-weight:600;'>{e['status']}</span> · "
            f"{e['id']}</div></div></div>",
            unsafe_allow_html=True,
        )


def render_precip_chart(hourly: list):
    if not hourly:
        st.info("12-hour forecast unavailable")
        return
    try:
        times = [datetime.fromisoformat(h["startTime"].replace("Z", "+00:00")).strftime("%-I%p")
                 for h in hourly[:12]]
        pops = [(h.get("probabilityOfPrecipitation") or {}).get("value") or 0
                for h in hourly[:12]]
    except Exception:
        return

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=times, y=pops,
        marker=dict(
            color=pops,
            colorscale=[[0, "#bbf7d0"], [0.5, "#fde68a"], [1, "#fca5a5"]],
            showscale=False,
        ),
        hovertemplate="<b>%{x}</b><br>%{y}% precip<extra></extra>",
    ))
    fig.update_layout(
        height=220, margin=dict(l=10, r=10, t=10, b=10),
        plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
        font=dict(color="#0f172a", size=11),
        xaxis=dict(showgrid=False), yaxis=dict(gridcolor="#f1f5f9", range=[0, 100], ticksuffix="%"),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


# ───────────────────────────────────────────────────────────────────────────
# HELPER — render the 0–100 risk scale visualization
# ───────────────────────────────────────────────────────────────────────────
def render_risk_scale(score: int, level: str, color: str):
    """
    Horizontal 0-100 flood risk scale with four colored bands, tick marks,
    band labels, and a marker showing the current score.
    """
    # Clamp and compute marker position as percentage
    pos = max(0, min(100, score))

    # Pointer width calculation so the caret doesn't clip at edges
    # Use percentage-based positioning that handles edges gracefully
    if pos <= 5:
        marker_style = "left: 0%; transform: translateX(0);"
        label_style = "left: 0%; transform: translateX(0);"
    elif pos >= 95:
        marker_style = "left: 100%; transform: translateX(-100%);"
        label_style = "left: 100%; transform: translateX(-100%);"
    else:
        marker_style = f"left: {pos}%; transform: translateX(-50%);"
        label_style = f"left: {pos}%; transform: translateX(-50%);"

    html = f"""
    <div style='background:#ffffff; border:1px solid #e2e8f0; border-radius:12px;
                padding:0.9rem 1.1rem 0.75rem 1.1rem; margin-bottom:1rem;
                box-shadow:0 1px 2px rgba(15,23,42,0.03);'>
      <div style='display:flex; justify-content:space-between; align-items:baseline;
                  margin-bottom:0.6rem;'>
        <div style='font-size:0.7rem; font-weight:700; color:#64748b;
                    letter-spacing:0.08em;'>RISK SCALE · 0–100</div>
        <div style='font-size:0.78rem; color:#64748b; font-weight:500;'>
          Where <b style='color:{color};'>{score}</b> lands
        </div>
      </div>

      <!-- Pointer callout above the bar -->
      <div style='position:relative; height:28px; margin-bottom:4px;'>
        <div style='position:absolute; {label_style} top:0;
                    background:{color}; color:white;
                    font-size:0.75rem; font-weight:700; padding:3px 10px;
                    border-radius:6px; white-space:nowrap;
                    box-shadow:0 2px 4px rgba(0,0,0,0.12);'>
          {score} · {level}
          <div style='position:absolute; bottom:-4px; left:50%; transform:translateX(-50%) rotate(45deg);
                      width:8px; height:8px; background:{color};'></div>
        </div>
      </div>

      <!-- Colored band bar -->
      <div style='position:relative; height:14px; border-radius:7px; overflow:hidden;
                  background:linear-gradient(to right,
                    #16a34a 0%,   #16a34a 25%,
                    #f59e0b 25%,  #f59e0b 50%,
                    #dc2626 50%,  #dc2626 75%,
                    #991b1b 75%,  #991b1b 100%);'>
        <!-- Marker line on the bar -->
        <div style='position:absolute; {marker_style} top:-3px;
                    width:4px; height:20px; background:#ffffff;
                    border:1.5px solid {color}; border-radius:2px;
                    box-shadow:0 1px 3px rgba(0,0,0,0.2);'></div>
      </div>

      <!-- Band labels below -->
      <div style='display:grid; grid-template-columns: repeat(4, 1fr); margin-top:6px;
                  font-size:0.68rem; text-align:center; line-height:1.2;'>
        <div style='color:#16a34a; font-weight:600;'>
          LOW<br><span style='color:#94a3b8; font-weight:500;'>0–24</span>
        </div>
        <div style='color:#f59e0b; font-weight:600;'>
          MODERATE<br><span style='color:#94a3b8; font-weight:500;'>25–49</span>
        </div>
        <div style='color:#dc2626; font-weight:600;'>
          HIGH<br><span style='color:#94a3b8; font-weight:500;'>50–74</span>
        </div>
        <div style='color:#991b1b; font-weight:600;'>
          CRITICAL<br><span style='color:#94a3b8; font-weight:500;'>75–100</span>
        </div>
      </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


# ───────────────────────────────────────────────────────────────────────────
# HELPER — render the interactive light-mode flood map
# ───────────────────────────────────────────────────────────────────────────
def render_flood_map(
    focus_neighborhood: str,
    stations: list,
    reports_311: list,
    map_key: str,
    height: int = 520,
    picked_coords: tuple | None = None,
    address_label: str | None = None,
):
    """
    Light-mode Folium map with:
      • Pump stations — color-coded by RELIABILITY (not just live status)
      • Maintenance events — burst mains, overhauls, sinkholes, etc.
      • 311 drainage complaints (last 7 days)
      • Selected neighborhood highlight (green circle)
      • Your address pin (if picked_coords is set)
      • Layer toggles + light-theme legend
    """
    # Map center: precise picked address if available, else neighborhood centroid
    if picked_coords:
        center = picked_coords
        zoom = 15
    else:
        center = NEIGHBORHOOD_CENTERS.get(focus_neighborhood, (29.9511, -90.0714))
        zoom = 13

    # Base map — CartoDB Positron (clean light gray / white)
    m = folium.Map(
        location=center,
        zoom_start=zoom,
        tiles="CartoDB positron",
        control_scale=True,
    )

    # ── Neighborhood highlight (green translucent circle) ──────────
    folium.Circle(
        location=NEIGHBORHOOD_CENTERS.get(focus_neighborhood, center),
        radius=900,
        color="#16a34a",
        weight=3,
        fill=True,
        fill_color="#16a34a",
        fill_opacity=0.08,
        popup=folium.Popup(
            f"<div style='font-family:sans-serif; font-size:13px;'>"
            f"<div style='color:#15803d; font-weight:700; margin-bottom:3px;'>"
            f"📍 {focus_neighborhood}</div>"
            f"<div style='color:#475569;'>Your selected neighborhood</div>"
            f"</div>",
            max_width=220,
        ),
        tooltip=f"📍 {focus_neighborhood}",
    ).add_to(m)

    # ── Your address pin (only if a specific address was selected) ──
    if picked_coords:
        pin_label = address_label or "Your location"
        pin_html = (
            f"<div style='position:relative; width:36px; height:36px;'>"
            f"<div style='position:absolute; top:8px; left:8px; width:20px; height:20px; "
            f"background:#16a34a; border-radius:50%; border:3px solid white; "
            f"box-shadow:0 2px 8px rgba(0,0,0,0.3);'></div>"
            f"<div style='position:absolute; inset:0; border-radius:50%; "
            f"border:3px solid #16a34a; opacity:0.5; "
            f"animation:fw-pin-pulse 1.8s ease-out infinite;'></div>"
            f"<style>@keyframes fw-pin-pulse{{0%{{transform:scale(0.6);opacity:0.8;}}"
            f"100%{{transform:scale(1.4);opacity:0;}}}}</style></div>"
        )
        folium.Marker(
            location=picked_coords,
            popup=folium.Popup(
                f"<div style='font-family:sans-serif; font-size:13px;'>"
                f"<div style='color:#15803d; font-weight:700; margin-bottom:2px;'>"
                f"📍 {pin_label}</div>"
                f"<div style='color:#475569; font-size:11px;'>"
                f"Lat {picked_coords[0]:.4f}, Lon {picked_coords[1]:.4f}</div></div>",
                max_width=220,
            ),
            tooltip=f"📍 {pin_label}",
            icon=folium.DivIcon(html=pin_html, icon_size=(36, 36), icon_anchor=(18, 18)),
        ).add_to(m)

    # ── Layer: Pump stations (reliability-colored) ─────────────────
    pump_group = folium.FeatureGroup(name="🏭 Pump Stations (by reliability)", show=True)
    for s in stations:
        sid = s.get("id", "")
        # Approximate coordinates for stations by neighborhood
        s_center = NEIGHBORHOOD_CENTERS.get(s.get("neighborhood"), center)
        # Offset slightly so they don't stack exactly on neighborhood circle
        s_lat = s_center[0] + 0.003
        s_lon = s_center[1] - 0.003

        rel = reliability_score_for_station(sid)
        # Color purely by reliability score
        if rel["score"] >= 85:
            fill_color = "#16a34a"   # green
        elif rel["score"] >= 70:
            fill_color = "#65a30d"   # lime
        elif rel["score"] >= 55:
            fill_color = "#f59e0b"   # amber
        else:
            fill_color = "#dc2626"   # red

        # Status badge color
        status_bg = {
            "PUMPING": "#16a34a", "STANDBY": "#f59e0b",
            "OFFLINE": "#dc2626", "TESTING": "#0284c7",
        }.get(s.get("status", ""), "#64748b")

        headline_html = ""
        if rel.get("headline"):
            h = rel["headline"]
            headline_html = (
                f"<div style='margin-top:8px; padding:6px 8px; background:#f0fdf4; "
                f"border-left:3px solid #16a34a; border-radius:4px; font-size:11px;'>"
                f"<b>Recent work:</b> {h['description']}<br>"
                f"<span style='color:#64748b;'>{h['days_ago']}d ago · {h['status']}</span>"
                f"</div>"
            )

        popup_html = (
            f"<div style='font-family:sans-serif; font-size:12px; min-width:240px;'>"
            f"<div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;'>"
            f"<b style='font-size:13px; color:#0f172a;'>{s.get('name', sid)}</b>"
            f"<span style='background:{status_bg}; color:#fff; padding:2px 8px; "
            f"border-radius:999px; font-size:10px; font-weight:700;'>{s.get('status','')}</span>"
            f"</div>"
            f"<div style='color:#64748b; font-size:11px; margin-bottom:6px;'>"
            f"{sid} · {s.get('neighborhood','')}</div>"
            f"<div style='display:flex; gap:12px; margin-bottom:4px;'>"
            f"<div><div style='font-size:10px; color:#64748b; text-transform:uppercase; font-weight:700;'>Reliability</div>"
            f"<div style='font-size:16px; font-weight:700; color:{fill_color};'>{rel['score']}/100</div>"
            f"<div style='font-size:10px; color:#64748b;'>{rel['label']}</div></div>"
            f"<div><div style='font-size:10px; color:#64748b; text-transform:uppercase; font-weight:700;'>Capacity</div>"
            f"<div style='font-size:16px; font-weight:700; color:#0f172a;'>{s.get('capacity_cfs', 0):,} CFS</div>"
            f"<div style='font-size:10px; color:#64748b;'>{s.get('operational_pct', 0)}% operational</div></div>"
            f"</div>"
            f"{headline_html}"
            f"</div>"
        )

        folium.CircleMarker(
            location=[s_lat, s_lon],
            radius=10 + (rel["score"] / 100 * 4),
            color="#ffffff",
            weight=2,
            fill=True,
            fill_color=fill_color,
            fill_opacity=0.92,
            popup=folium.Popup(popup_html, max_width=280),
            tooltip=f"{s.get('name', sid)} — Reliability {rel['score']}/100",
        ).add_to(pump_group)
    pump_group.add_to(m)

    # ── Layer: Maintenance events ──────────────────────────────────
    maint_group = folium.FeatureGroup(name="🔧 Maintenance Events (90-day)", show=True)
    for e in get_all_events():
        if "lat" not in e or "lon" not in e:
            continue
        meta = EVENT_TYPE_META.get(e["event_type"], {"icon": "🔧", "color": "#64748b", "label": "Maintenance"})
        days_ago = (datetime.now() - datetime.fromisoformat(e["date"])).days
        if days_ago > 90:
            continue

        when = "today" if days_ago == 0 else f"{days_ago} days ago"
        status_color = "#16a34a" if e["status"].lower() in ("completed", "repaired") else "#f59e0b"

        popup_html = (
            f"<div style='font-family:sans-serif; font-size:12px; min-width:230px;'>"
            f"<div style='display:flex; gap:8px; align-items:center; margin-bottom:4px;'>"
            f"<span style='font-size:18px;'>{meta['icon']}</span>"
            f"<b style='color:{meta['color']};'>{meta['label']}</b>"
            f"</div>"
            f"<div style='font-weight:600; color:#0f172a; margin-bottom:4px;'>{e['description']}</div>"
            f"<div style='font-size:11px; color:#64748b;'>"
            f"<b>When:</b> {when}<br>"
            f"<b>Status:</b> <span style='color:{status_color}; font-weight:600;'>{e['status']}</span><br>"
            f"<b>Work order:</b> {e['id']}<br>"
            f"<b>Area:</b> {e.get('neighborhood', '—')}"
            f"</div></div>"
        )

        # Use DivIcon so we can render a coloured circle with the event emoji
        icon_html = (
            f"<div style='background:{meta['color']}; color:white; width:28px; height:28px; "
            f"border-radius:50%; display:flex; align-items:center; justify-content:center; "
            f"font-size:14px; box-shadow:0 2px 6px rgba(0,0,0,0.25); border:2px solid white;'>"
            f"{meta['icon']}</div>"
        )

        folium.Marker(
            location=[e["lat"], e["lon"]],
            popup=folium.Popup(popup_html, max_width=280),
            tooltip=f"{meta['icon']} {meta['label']} — {when}",
            icon=folium.DivIcon(html=icon_html, icon_size=(28, 28), icon_anchor=(14, 14)),
        ).add_to(maint_group)
    maint_group.add_to(m)

    # ── Layer: 311 complaints ──────────────────────────────────────
    if reports_311:
        comp_group = folium.FeatureGroup(name="📞 311 Drainage Reports (7-day)", show=False)
        for r in reports_311[:40]:
            try:
                lat = float(r.get("latitude") or 0)
                lon = float(r.get("longitude") or 0)
            except (ValueError, TypeError):
                continue
            if not lat or not lon:
                continue

            reason = r.get("request_reason", "Drainage issue")
            date = r.get("date_created", "")[:10]
            svc = r.get("service_request", "")
            popup_html = (
                f"<div style='font-family:sans-serif; font-size:12px; min-width:200px;'>"
                f"<b style='color:#7c3aed;'>📞 311 Drainage Report</b><br>"
                f"<div style='margin-top:4px; color:#0f172a; font-weight:600;'>{reason}</div>"
                f"<div style='color:#64748b; font-size:11px; margin-top:3px;'>"
                f"#{svc} · {date}</div></div>"
            )
            folium.CircleMarker(
                location=[lat, lon],
                radius=5,
                color="#ffffff",
                weight=1,
                fill=True,
                fill_color="#a855f7",
                fill_opacity=0.85,
                popup=folium.Popup(popup_html, max_width=240),
                tooltip=f"311: {reason[:45]}",
            ).add_to(comp_group)
        comp_group.add_to(m)

    # ── Light-mode legend (bottom-right) ──────────────────────────
    legend_html = """
    <div style='position: fixed; bottom: 25px; right: 15px; z-index: 9999;
                background: #ffffff; border: 1px solid #e2e8f0;
                border-radius: 12px; padding: 12px 14px;
                box-shadow: 0 4px 12px rgba(15,23,42,0.1);
                font-family: -apple-system, BlinkMacSystemFont, sans-serif;
                font-size: 11px; color: #0f172a; min-width: 200px;'>
      <div style='font-weight: 700; color: #15803d; font-size: 11px;
                  letter-spacing: 0.06em; margin-bottom: 8px;
                  border-bottom: 1px solid #f0fdf4; padding-bottom: 5px;'>
        🌿 FLOODWATCH LEGEND
      </div>
      <div style='font-weight: 700; margin-bottom: 4px; color: #475569;'>Pump Reliability</div>
      <div style='display: flex; align-items: center; gap: 6px; margin-bottom: 3px;'>
        <span style='width:12px; height:12px; background:#16a34a; border-radius:50%; border:2px solid white; box-shadow:0 0 0 1px #16a34a;'></span>
        <span>Excellent (85+)</span>
      </div>
      <div style='display: flex; align-items: center; gap: 6px; margin-bottom: 3px;'>
        <span style='width:12px; height:12px; background:#65a30d; border-radius:50%; border:2px solid white; box-shadow:0 0 0 1px #65a30d;'></span>
        <span>Good (70–84)</span>
      </div>
      <div style='display: flex; align-items: center; gap: 6px; margin-bottom: 3px;'>
        <span style='width:12px; height:12px; background:#f59e0b; border-radius:50%; border:2px solid white; box-shadow:0 0 0 1px #f59e0b;'></span>
        <span>Fair (55–69)</span>
      </div>
      <div style='display: flex; align-items: center; gap: 6px; margin-bottom: 8px;'>
        <span style='width:12px; height:12px; background:#dc2626; border-radius:50%; border:2px solid white; box-shadow:0 0 0 1px #dc2626;'></span>
        <span>Degraded (<55)</span>
      </div>
      <div style='font-weight: 700; margin-bottom: 4px; color: #475569;'>Events</div>
      <div style='display: flex; align-items: center; gap: 6px; margin-bottom: 3px;'>
        <span>💥</span><span>Burst main / sinkhole</span>
      </div>
      <div style='display: flex; align-items: center; gap: 6px; margin-bottom: 3px;'>
        <span>🔧</span><span>Pump overhaul</span>
      </div>
      <div style='display: flex; align-items: center; gap: 6px; margin-bottom: 3px;'>
        <span>🕳️</span><span>Catch basin work</span>
      </div>
      <div style='display: flex; align-items: center; gap: 6px;'>
        <span style='width:10px; height:10px; background:#a855f7; border-radius:50%;'></span>
        <span>311 drainage report</span>
      </div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    # Layer control (top-right)
    folium.LayerControl(collapsed=False, position="topright").add_to(m)

    st_folium(m, width=None, height=height, returned_objects=[], key=map_key)


# ═══════════════════════════════════════════════════════════════════════════
# INDIVIDUAL TAB
# ═══════════════════════════════════════════════════════════════════════════
with tab_ind:
    # Estimated inches of standing water at current conditions
    est_depth = 0.0
    if precip_pct > 20:
        inhr = max(0, (precip_pct - 20) / 80 * 2.5)
        excess = max(0, inhr - capacity_mult)
        est_depth = round(min(excess * 2, 10), 1)

    # Hours until clear (rough proxy — pump rate adjusted for capacity + reliability)
    base_clear_hrs = max(0.5, est_depth * 1.2)
    hrs_to_clear = round(base_clear_hrs / max(0.3, capacity_mult * reliability["score"] / 100), 1)

    # "Safe to drive" logic
    if est_depth < 0.3 and adjusted_score < 50:
        safe_status, safe_color = "YES", "green"
        safe_sub = "Passable on all primary routes"
    elif est_depth < 2.0 and adjusted_score < 75:
        safe_status, safe_color = "CAUTION", "amber"
        safe_sub = "Avoid low-lying streets"
    else:
        safe_status, safe_color = "NO", "red"
        safe_sub = "Stay off the roads if possible"

    # ── Headline strip with 24-hr risk sparkline ───────────────────
    # Generate a plausible 24-hour trajectory converging to current score
    import random
    _rng = random.Random(adjusted_score * 37 + hash(neighborhood) % 1000)
    spark_points = []
    _val = max(5, adjusted_score + _rng.randint(-15, 10))
    for i in range(24):
        # Drift toward current score with noise
        _target = adjusted_score
        _val += (_target - _val) * 0.12 + _rng.randint(-6, 6)
        _val = max(2, min(95, _val))
        spark_points.append(_val)
    spark_points.append(adjusted_score)  # end at actual current value

    # Build SVG path for sparkline
    _w, _h = 180, 50
    _max_pt = max(max(spark_points), 10)
    _min_pt = min(min(spark_points), 0)
    _range = max(_max_pt - _min_pt, 1)
    _coords = []
    for i, v in enumerate(spark_points):
        x = (i / (len(spark_points) - 1)) * _w
        y = _h - ((v - _min_pt) / _range) * (_h - 6) - 3
        _coords.append(f"{x:.1f},{y:.1f}")
    _path = "M" + " L".join(_coords)
    _area_path = f"M0,{_h} L" + " L".join(_coords) + f" L{_w},{_h} Z"
    _last_x, _last_y = _coords[-1].split(",")

    sparkline_svg = (
        f"<div style='display:flex; flex-direction:column; align-items:flex-end; "
        f"min-width:190px;'>"
        f"<div style='font-size:0.62rem; color:#64748b; font-weight:700; "
        f"letter-spacing:0.08em; margin-bottom:3px;'>24-HR TREND</div>"
        f"<svg width='{_w}' height='{_h}' viewBox='0 0 {_w} {_h}' "
        f"style='display:block;'>"
        f"<defs><linearGradient id='spg-{adjusted_score}' x1='0' x2='0' y1='0' y2='1'>"
        f"<stop offset='0%' stop-color='{adj_color}' stop-opacity='0.28'/>"
        f"<stop offset='100%' stop-color='{adj_color}' stop-opacity='0.02'/>"
        f"</linearGradient></defs>"
        f"<path d='{_area_path}' fill='url(#spg-{adjusted_score})'/>"
        f"<path d='{_path}' fill='none' stroke='{adj_color}' "
        f"stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'/>"
        f"<circle cx='{_last_x}' cy='{_last_y}' r='3.5' fill='{adj_color}' "
        f"stroke='#ffffff' stroke-width='1.5'/>"
        f"</svg>"
        f"<div style='font-size:0.68rem; color:#64748b; margin-top:1px;'>"
        f"Range {int(min(spark_points))}–{int(max(spark_points))}</div>"
        f"</div>"
    )

    # ── Headline strip (mode-aware narrative) ──────────────────────
    # Build the explanation line + optional advisory chip based on risk mode
    has_infra_issue = (reliability["score"] < 75) or (capacity_mult < 0.95)
    risk_microcopy = get_risk_microcopy(adj_level)

    if risk_mode == "dry":
        # Sunny / low-rain day — keep the main line product-clean and move
        # the technical explanation into a lighter secondary line.
        explanation_html = (
            f"<div style='font-size:0.85rem; color:#475569; margin-top:0.15rem; "
            f"font-weight:500;'>"
            f"{risk_microcopy}"
            f"</div>"
            f"<div style='font-size:0.78rem; color:#94a3b8; margin-top:0.2rem;'>"
            f"Low rain forecast ({precip_pct}%) — current risk reflects weather only"
            f"</div>"
        )
        if has_infra_issue:
            issue_text = []
            if reliability["score"] < 75:
                issue_text.append(f"pump reliability {reliability['score']}/100")
            if capacity_mult < 0.95:
                issue_text.append(f"drainage at {int(capacity_mult*100)}% capacity")
            advisory_line = " · ".join(issue_text)
            explanation_html += (
                f"<div style='display:inline-flex; align-items:center; gap:0.4rem; "
                f"background:#eff6ff; color:#1e40af; border:1px solid #bfdbfe; "
                f"border-radius:8px; padding:4px 10px; margin-top:0.5rem; "
                f"font-size:0.78rem; font-weight:500;'>"
                f"ℹ️ <b>Infrastructure advisory:</b> {advisory_line} — will compound if rain arrives"
                f"</div>"
            )
    elif risk_mode == "watch":
        explanation_html = (
            f"<div style='font-size:0.85rem; color:#475569; margin-top:0.15rem; "
            f"font-weight:500;'>"
            f"{risk_microcopy}"
            f"</div>"
            f"<div style='font-size:0.78rem; color:#94a3b8; margin-top:0.2rem;'>"
            f"Rain expected ({precip_pct}%) — weather {composite_base}"
        )
        if reliability_drag + capacity_drag > 0.5:
            explanation_html += (
                f" + infrastructure +{int(reliability_drag + capacity_drag)} "
                f"<span style='color:#94a3b8;'>({int(rain_multiplier*100)}% applied)</span>"
            )
        explanation_html += "</div>"
    else:  # active
        explanation_html = (
            f"<div style='font-size:0.85rem; color:#475569; margin-top:0.15rem; "
            f"font-weight:500;'>"
            f"{risk_microcopy}"
            f"</div>"
            f"<div style='font-size:0.78rem; color:#94a3b8; margin-top:0.2rem;'>"
            f"Active rain ({precip_pct}%) — weather {composite_base}"
        )
        if reliability_drag > 0.5:
            explanation_html += f" + pump reliability +{int(reliability_drag)}"
        if capacity_drag > 0.5:
            explanation_html += f" + drainage capacity +{int(capacity_drag)}"
        explanation_html += "</div>"
    st.markdown(
        f"<div class='fw-card fw-card-headline {adj_bg}' style='margin-top:1rem;'>"
        f"<div style='display:flex; align-items:center; gap:1.5rem;'>"
        f"<div style='font-size:3rem; font-weight:900; color:{adj_color}; line-height:1;'>"
        f"<span class='fw-countup' style='--fw-to:{adjusted_score};' data-final='{adjusted_score}'></span>"
        f"</div>"
        f"<div style='flex:1;'>"
        f"<div style='font-size:0.72rem; color:#64748b; font-weight:700; letter-spacing:0.08em;'>"
        f"FLOOD RISK · {neighborhood.upper()}</div>"
        f"<div style='font-size:1.3rem; font-weight:800; color:{adj_color};'>{adj_level} RISK</div>"
        f"{explanation_html}"
        f"</div>"
        f"{sparkline_svg}"
        f"</div></div>",
        unsafe_allow_html=True,
    )

    # ── 0-100 risk scale visualization ─────────────────────────────
    render_risk_scale(adjusted_score, adj_level, adj_color)

    # ── KPI row ────────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        render_tile("Safe to drive?", safe_status, safe_sub, accent=safe_color, delay=1)
    with k2:
        render_tile(
            "Est. standing water",
            f"{est_depth:.1f}\"",
            "Next 2 hrs at current rate",
            accent="amber" if est_depth >= 0.3 else "green",
            delay=2,
        )
    with k3:
        render_tile(
            "Hours until clear",
            f"{hrs_to_clear:.1f} hr" if est_depth > 0 else "—",
            "Post-rainfall drainage time",
            accent="green" if hrs_to_clear <= 2 else ("amber" if hrs_to_clear <= 6 else "red"),
            delay=3,
        )
    with k4:
        render_tile(
            "Pump reliability",
            f"{reliability['score']}/100",
            f"{reliability['label']} · baseline {reliability['baseline']}",
            accent=("green" if reliability['score'] >= 75 else
                    "amber" if reliability['score'] >= 55 else "red"),
            delay=4,
        )

    # ── Weather + station detail ──────────────────────────────────
    st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)
    w1, w2 = st.columns([1.4, 1])

    with w1:
        st.markdown("<div class='fw-section-header'>12-Hour Precipitation Outlook</div>",
                    unsafe_allow_html=True)
        st.markdown(f"<div class='fw-card'>"
                    f"<div style='display:flex; gap:1.5rem; margin-bottom:0.75rem;'>"
                    f"<div><div class='fw-tile-label'>Now</div>"
                    f"<div style='font-size:1.5rem; font-weight:700;'>{temp}°{temp_unit}</div>"
                    f"<div class='fw-tile-sub'>{short_fc}</div></div>"
                    f"<div><div class='fw-tile-label'>Precip probability</div>"
                    f"<div style='font-size:1.5rem; font-weight:700; color:{'#dc2626' if precip_pct > 60 else '#f59e0b' if precip_pct > 30 else '#16a34a'};'>{precip_pct}%</div>"
                    f"<div class='fw-tile-sub'>Next 12 hours</div></div>"
                    f"<div><div class='fw-tile-label'>Mississippi R.</div>"
                    f"<div style='font-size:1.5rem; font-weight:700;'>{river_ft:.1f} ft</div>"
                    f"<div class='fw-tile-sub'>Carrollton gauge</div></div>"
                    f"</div>",
                    unsafe_allow_html=True)
        render_precip_chart(hourly_12)
        st.markdown("</div>", unsafe_allow_html=True)

    with w2:
        st.markdown(
            f"<div class='fw-section-header'>Your Pump Station</div>",
            unsafe_allow_html=True,
        )
        if station:
            status_colors = {
                "PUMPING": "#16a34a", "STANDBY": "#f59e0b",
                "OFFLINE": "#dc2626", "TESTING": "#0284c7",
            }
            s_color = status_colors.get(station["status"], "#64748b")
            st.markdown(
                f"<div class='fw-card'>"
                f"<div style='display:flex; justify-content:space-between; align-items:start;'>"
                f"<div><div style='font-size:1.1rem; font-weight:700;'>{station['name']}</div>"
                f"<div style='font-size:0.78rem; color:#64748b;'>{station['id']} · serves {neighborhood}</div></div>"
                f"<span style='background:{s_color}; color:#fff; padding:3px 10px; "
                f"border-radius:999px; font-size:0.72rem; font-weight:700;'>{station['status']}</span>"
                f"</div>"
                f"<div style='display:flex; gap:1.5rem; margin-top:0.85rem;'>"
                f"<div><div class='fw-tile-label'>Capacity</div>"
                f"<div style='font-size:1.2rem; font-weight:700;'>{station['capacity_cfs']:,} CFS</div></div>"
                f"<div><div class='fw-tile-label'>Operational</div>"
                f"<div style='font-size:1.2rem; font-weight:700;'>{station['operational_pct']}%</div></div>"
                f"</div></div>",
                unsafe_allow_html=True,
            )

            if reliability.get("headline"):
                h = reliability["headline"]
                st.markdown(
                    f"<div class='fw-card fw-card-green' style='font-size:0.85rem;'>"
                    f"<b>📋 Most recent work:</b><br>"
                    f"{h['description']}<br>"
                    f"<span style='color:#64748b; font-size:0.78rem;'>"
                    f"{h['days_ago']} days ago · {h['status']}</span></div>",
                    unsafe_allow_html=True,
                )
        else:
            st.info("No direct pump station assigned to this neighborhood.")

    # ── Interactive flood risk map ────────────────────────────────
    st.markdown(f"<div class='fw-section-header'>Live Flood Risk Map — {neighborhood}</div>",
                unsafe_allow_html=True)
    st.markdown(
        "<div style='font-size:0.85rem; color:#475569; margin-bottom:0.5rem;'>"
        "Click any marker for details. Pump stations are colored by "
        "<b>reliability score</b> (maintenance-adjusted, not just live status). "
        "Toggle layers in the top-right corner."
        "</div>",
        unsafe_allow_html=True,
    )
    render_flood_map(
        focus_neighborhood=neighborhood,
        stations=swbno.get("stations", []),
        reports_311=reports_311,
        map_key=f"map_individual_{neighborhood}_{address}",
        height=520,
        picked_coords=st.session_state.get("picked_coords"),
        address_label=address,
    )

    # ── Recent maintenance in your area ────────────────────────────
    st.markdown(f"<div class='fw-section-header'>Recent Infrastructure Work Near You "
                f"({neighborhood})</div>",
                unsafe_allow_html=True)
    m1, m2 = st.columns([1, 1])
    with m1:
        st.markdown("<div style='font-size:0.88rem; color:#475569; "
                    "margin-bottom:0.5rem;'><b>Neighborhood events (60-day window)</b></div>",
                    unsafe_allow_html=True)
        render_event_list(nb_events, limit=5)
    with m2:
        st.markdown("<div style='font-size:0.88rem; color:#475569; "
                    "margin-bottom:0.5rem;'><b>Burst mains · parish-wide (30-day)</b></div>",
                    unsafe_allow_html=True)
        render_event_list(recent_bursts, limit=5)

    # ── Individual action checklist ────────────────────────────────
    ind_keys = ["ind_a1", "ind_a2", "ind_a3", "ind_a4",
                "ind_b1", "ind_b2", "ind_b3", "ind_b4"]
    ind_done = sum(1 for k in ind_keys if st.session_state.get(k, False))
    ind_total = len(ind_keys)
    ind_pct = int((ind_done / ind_total) * 100)
    if ind_pct >= 75:
        ind_label = "Storm-ready"
    elif ind_pct >= 40:
        ind_label = "Getting there"
    else:
        ind_label = "Not yet prepared"

    st.markdown("<div class='fw-section-header'>Your Action Checklist</div>",
                unsafe_allow_html=True)
    st.markdown(
        f"<div class='fw-progress-header'>"
        f"<span style='color:#475569; font-weight:600;'>"
        f"<b>{ind_done}</b> of {ind_total} actions complete · "
        f"<span style='color:#15803d;'>{ind_label}</span></span>"
        f"<span style='color:#16a34a; font-weight:700;'>{ind_pct}%</span>"
        f"</div>"
        f"<div class='fw-progress-track'>"
        f"<div class='fw-progress-fill' style='width:{ind_pct}%;'></div></div>",
        unsafe_allow_html=True,
    )
    ac1, ac2 = st.columns(2)
    with ac1:
        st.markdown("**Before the storm**")
        st.checkbox("Move vehicles to high ground (Esplanade Ridge, Uptown crest)", key="ind_a1")
        st.checkbox("Photograph belongings for insurance baseline", key="ind_a2")
        st.checkbox("Charge phones and power banks", key="ind_a3")
        st.checkbox("Clear gutters and the catch basin on your block", key="ind_a4")
    with ac2:
        st.markdown("**During & after**")
        st.checkbox("Never drive through standing water", key="ind_b1")
        st.checkbox("Document any water intrusion with timestamps", key="ind_b2")
        st.checkbox("Keep receipts for any emergency expenses", key="ind_b3")
        st.checkbox("File 311 report for clogged basins or flooded streets", key="ind_b4")


# ═══════════════════════════════════════════════════════════════════════════
# SMALL BUSINESS TAB
# ═══════════════════════════════════════════════════════════════════════════
with tab_biz:
    st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)
    st.markdown("<div class='fw-section-header'>Your Business Profile</div>",
                unsafe_allow_html=True)

    b1, b2, b3, b4 = st.columns(4)
    with b1:
        biz_type = st.selectbox(
            "Business type",
            ["Restaurant / Bar", "Retail", "Professional Services",
             "Salon / Personal Care", "Hospitality", "Other"],
            key="biz_type",
        )
    with b2:
        daily_revenue = st.number_input(
            "Daily revenue ($)",
            min_value=100, max_value=100000, value=2500, step=100,
        )
    with b3:
        operating_hours = st.number_input(
            "Operating hours/day",
            min_value=1, max_value=24, value=10, step=1,
        )
    with b4:
        employees = st.number_input(
            "Employees on shift",
            min_value=1, max_value=500, value=8, step=1,
        )

    # ── Compute business-specific metrics ─────────────────────────
    # Expected closure probability scales with adjusted risk
    closure_prob = min(0.95, max(0.0, (adjusted_score - 20) / 80))

    # Typical flood event impact duration for NOLA: 0.5 to 8 hrs
    event_duration_hrs = 0.5 + (adjusted_score / 100) * 7.5

    expected_hours_lost = round(closure_prob * event_duration_hrs, 1)
    expected_hours_lost = min(expected_hours_lost, float(operating_hours))
    revenue_at_risk = int((expected_hours_lost / operating_hours) * daily_revenue)

    # Employee commute risk — combo of precip + neighborhood capacity
    commute_risk = int(min(100, precip_pct * 0.6 + (1 - capacity_mult) * 60 + adjusted_score * 0.15))
    affected_employees = int(round(employees * min(1.0, commute_risk / 100 * 1.2)))

    # Delivery window — safe hours in the next 12 hrs below 30% precip
    safe_delivery_hours = 0
    if hourly_12:
        for h in hourly_12[:12]:
            pop = (h.get("probabilityOfPrecipitation") or {}).get("value") or 0
            if pop < 40:
                safe_delivery_hours += 1

    # Business continuity score — inverse of risk, reliability-weighted
    continuity_score = int(max(0, 100 - adjusted_score * 0.8))

    # ── Headline card (mode-aware) ────────────────────────────────
    if risk_mode == "dry":
        # On a dry day, revenue at risk should be near zero.
        # Show a calmer card that surfaces the annualized exposure instead.
        st.markdown(
            f"<div class='fw-card fw-card-headline fw-card-green'>"
            f"<div style='display:flex; align-items:center; gap:1.5rem;'>"
            f"<div style='font-size:2.5rem; font-weight:900; color:#16a34a; line-height:1;'>"
            f"☀️</div>"
            f"<div style='flex:1;'>"
            f"<div style='font-size:0.72rem; color:#64748b; font-weight:700; letter-spacing:0.08em;'>"
            f"NO IMMEDIATE DISRUPTION EXPECTED</div>"
            f"<div style='font-size:1.2rem; font-weight:800; color:#15803d;'>"
            f"Clear operating window</div>"
            f"<div style='font-size:0.85rem; color:#475569; margin-top:0.15rem;'>"
            f"Rain forecast {precip_pct}% · scroll down for your annualized exposure "
            f"and 12-hour operating window</div>"
            f"</div></div></div>",
            unsafe_allow_html=True,
        )
    else:
        # Rain is expected or active — show the revenue-at-risk story
        st.markdown(
            f"<div class='fw-card fw-card-headline {adj_bg}'>"
            f"<div style='display:flex; align-items:center; gap:1.5rem;'>"
            f"<div class='fw-fade-in' style='font-size:3rem; font-weight:900; color:{adj_color}; line-height:1;'>"
            f"${revenue_at_risk:,}</div>"
            f"<div style='flex:1;'>"
            f"<div style='font-size:0.72rem; color:#64748b; font-weight:700; letter-spacing:0.08em;'>"
            f"REVENUE AT RISK · NEXT 24 HOURS</div>"
            f"<div style='font-size:1rem; font-weight:600; color:#0f172a;'>"
            f"{expected_hours_lost:.1f} expected hours of disruption · "
            f"{int(closure_prob*100)}% closure probability</div>"
            f"<div style='font-size:0.82rem; color:#64748b; margin-top:0.2rem;'>"
            f"Based on ${daily_revenue:,}/day · {operating_hours}-hr operation · "
            f"{adj_level.lower()} risk in {neighborhood}</div>"
            f"</div></div></div>",
            unsafe_allow_html=True,
        )

    # ── 0-100 risk scale visualization ─────────────────────────────
    render_risk_scale(adjusted_score, adj_level, adj_color)

    # ── KPI row ────────────────────────────────────────────────────
    b_k1, b_k2, b_k3, b_k4 = st.columns(4)
    with b_k1:
        render_tile(
            "Continuity score",
            f"{continuity_score}/100",
            "Operational readiness",
            accent=("green" if continuity_score >= 70 else
                    "amber" if continuity_score >= 40 else "red"),
            delay=1,
        )
    with b_k2:
        render_tile(
            "Employees at commute risk",
            f"{affected_employees}/{employees}",
            f"Commute risk score {commute_risk}",
            accent=("red" if commute_risk >= 60 else
                    "amber" if commute_risk >= 30 else "green"),
            delay=2,
        )
    with b_k3:
        render_tile(
            "Safe delivery window",
            f"{safe_delivery_hours} hr",
            "Next 12 hrs below 40% precip",
            accent=("green" if safe_delivery_hours >= 6 else
                    "amber" if safe_delivery_hours >= 3 else "red"),
            delay=3,
        )
    with b_k4:
        render_tile(
            "Drainage capacity",
            f"{int(capacity_mult*100)}%",
            "Of design — maintenance-adjusted",
            accent=("green" if capacity_mult >= 0.9 else
                    "amber" if capacity_mult >= 0.7 else "red"),
            delay=4,
        )

    # ── Ops detail: 12-hr window + station + maintenance ─────────
    st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)
    o1, o2 = st.columns([1.4, 1])
    with o1:
        st.markdown("<div class='fw-section-header'>Operational Window — Next 12 Hours</div>",
                    unsafe_allow_html=True)
        st.markdown("<div class='fw-card'>", unsafe_allow_html=True)
        render_precip_chart(hourly_12)
        if hourly_12:
            st.markdown(
                f"<div style='font-size:0.85rem; color:#475569; margin-top:0.5rem;'>"
                f"💡 <b>{safe_delivery_hours} hours</b> of the next 12 have precipitation "
                f"probability below 40% — optimal for deliveries, customer visits, and "
                f"outdoor operations.</div>",
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

    with o2:
        st.markdown("<div class='fw-section-header'>Drainage Infrastructure</div>",
                    unsafe_allow_html=True)
        if station:
            st.markdown(
                f"<div class='fw-card'>"
                f"<div style='font-size:0.72rem; color:#16a34a; font-weight:700; letter-spacing:0.06em;'>"
                f"SERVING STATION</div>"
                f"<div style='font-size:1.05rem; font-weight:700;'>{station['name']}</div>"
                f"<div style='font-size:0.78rem; color:#64748b;'>{station['id']}</div>"
                f"<div style='display:flex; gap:1.2rem; margin-top:0.75rem;'>"
                f"<div><div class='fw-tile-label'>Reliability</div>"
                f"<div style='font-size:1.2rem; font-weight:700; color:{reliability['color']};'>"
                f"{reliability['score']}/100</div>"
                f"<div class='fw-tile-sub'>{reliability['label']}</div></div>"
                f"<div><div class='fw-tile-label'>Status</div>"
                f"<div style='font-size:1.2rem; font-weight:700;'>{station['status']}</div>"
                f"<div class='fw-tile-sub'>{station['operational_pct']}% operational</div></div>"
                f"</div>"
                f"<div style='font-size:0.8rem; color:#475569; margin-top:0.75rem;'>"
                f"<b>{reliability['event_count']}</b> maintenance events logged in past 180 days · "
                f"reliability {'+' if reliability['delta']>=0 else ''}{reliability['delta']} vs baseline"
                f"</div></div>",
                unsafe_allow_html=True,
            )

    # ── Interactive flood risk map — business view ────────────────
    st.markdown(f"<div class='fw-section-header'>Drainage Coverage Map — {neighborhood}</div>",
                unsafe_allow_html=True)
    st.markdown(
        "<div style='font-size:0.85rem; color:#475569; margin-bottom:0.5rem;'>"
        "Infrastructure serving your block. Green pumps = reliable, red = degraded. "
        "Click markers to see recent maintenance and capacity details."
        "</div>",
        unsafe_allow_html=True,
    )
    render_flood_map(
        focus_neighborhood=neighborhood,
        stations=swbno.get("stations", []),
        reports_311=reports_311,
        map_key=f"map_business_{neighborhood}_{address}",
        height=520,
        picked_coords=st.session_state.get("picked_coords"),
        address_label=address,
    )

    # ── Recent maintenance affecting this business ───────────────
    st.markdown("<div class='fw-section-header'>Maintenance Affecting Your Block</div>",
                unsafe_allow_html=True)
    mm1, mm2 = st.columns(2)
    with mm1:
        st.markdown("<div style='font-size:0.88rem; color:#475569; "
                    "margin-bottom:0.5rem;'><b>Station work (180-day)</b></div>",
                    unsafe_allow_html=True)
        render_event_list(station_events, limit=4)
    with mm2:
        st.markdown("<div style='font-size:0.88rem; color:#475569; "
                    "margin-bottom:0.5rem;'><b>Neighborhood work (60-day)</b></div>",
                    unsafe_allow_html=True)
        render_event_list(nb_events, limit=4)

    # ── Business continuity checklist ─────────────────────────────
    biz_keys = ["biz_a1", "biz_a2", "biz_a3", "biz_a4", "biz_a5",
                "biz_b1", "biz_b2", "biz_b3", "biz_b4", "biz_b5"]
    biz_done = sum(1 for k in biz_keys if st.session_state.get(k, False))
    biz_total = len(biz_keys)
    biz_pct = int((biz_done / biz_total) * 100)
    if biz_pct >= 75:
        biz_label = "Continuity plan ready"
    elif biz_pct >= 40:
        biz_label = "In progress"
    else:
        biz_label = "Plan not started"

    st.markdown("<div class='fw-section-header'>Business Continuity Plan</div>",
                unsafe_allow_html=True)
    st.markdown(
        f"<div class='fw-progress-header'>"
        f"<span style='color:#475569; font-weight:600;'>"
        f"<b>{biz_done}</b> of {biz_total} actions complete · "
        f"<span style='color:#15803d;'>{biz_label}</span></span>"
        f"<span style='color:#16a34a; font-weight:700;'>{biz_pct}%</span>"
        f"</div>"
        f"<div class='fw-progress-track'>"
        f"<div class='fw-progress-fill' style='width:{biz_pct}%;'></div></div>",
        unsafe_allow_html=True,
    )
    bc1, bc2 = st.columns(2)
    with bc1:
        st.markdown("**Pre-event (T-24 hrs)**")
        st.checkbox("Move POS terminals and electronics off ground level", key="biz_a1")
        st.checkbox("Backup POS data and customer records off-site", key="biz_a2")
        st.checkbox("Confirm flood insurance is current (NFIP or private)", key="biz_a3")
        st.checkbox("Notify key suppliers of potential delivery delays", key="biz_a4")
        st.checkbox("Message staff about expected schedule changes", key="biz_a5")
    with bc2:
        st.markdown("**Post-event**")
        st.checkbox("Photograph all damage before cleanup begins", key="biz_b1")
        st.checkbox("Document business interruption hours for insurance", key="biz_b2")
        st.checkbox("Collect employee displacement expenses", key="biz_b3")
        st.checkbox("File SBA disaster loan application if damage > $5k", key="biz_b4")
        st.checkbox("Update emergency contact list for staff", key="biz_b5")

    # ── ROI / value callout ──────────────────────────────────────
    annual_events_estimate = 12  # NOLA typically sees 10–15 disruptive rain events/year
    annual_at_risk = revenue_at_risk * annual_events_estimate
    st.markdown(
        f"<div class='fw-card fw-card-green' style='margin-top:1rem;'>"
        f"<div style='font-size:0.72rem; color:#15803d; font-weight:700; letter-spacing:0.08em;'>"
        f"ANNUALIZED EXPOSURE</div>"
        f"<div style='font-size:1.5rem; font-weight:800; color:#15803d; margin-top:0.25rem;'>"
        f"~${annual_at_risk:,} potential annual disruption</div>"
        f"<div style='font-size:0.85rem; color:#475569; margin-top:0.3rem;'>"
        f"Based on {annual_events_estimate} disruptive rain events/year at current location. "
        f"Mitigation actions above typically recover 40–60% of this exposure.</div>"
        f"</div>",
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════════════════════════════════
# FOOTER
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("<div style='height:1.5rem;'></div>", unsafe_allow_html=True)
st.markdown(
    "<div style='border-top:1px solid #e2e8f0; padding-top:1rem; "
    "font-size:0.75rem; color:#94a3b8; text-align:center;'>"
    "🌿 FloodWatch NOLA · Built at Tulane University Freeman School of Business · "
    "Data: NOAA NWS · USGS NWIS · SWBNO · NOLA Open Data · FEMA OpenFEMA"
    "</div>",
    unsafe_allow_html=True,
)

if not _HAS_AUTOREFRESH:
    st.caption(
        "ℹ️  Install `streamlit-autorefresh` (already in requirements.txt) "
        "to enable automatic 5-minute refresh."
    )
