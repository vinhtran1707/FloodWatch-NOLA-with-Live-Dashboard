from __future__ import annotations

import os
import sys
from datetime import datetime

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.data_fetchers import get_all_data
from utils.risk_engine import compute_risk_score

st.set_page_config(
    page_title="My Report — Crest",
    page_icon="📄",
    layout="wide",
)

_css_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "style.css")
with open(_css_path) as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

if "data" not in st.session_state:
    with st.spinner("Fetching data…"):
        st.session_state["data"] = get_all_data()

data = st.session_state["data"]
risk = compute_risk_score(data)
swbno = data.get("swbno", {})
forecast = data.get("forecast") or {}
river_gauge = data.get("river_gauge")

st.markdown(
    "<div style='font-size:0.8rem; color:#64748b;'>🌊 Crest</div>",
    unsafe_allow_html=True,
)
st.title("📄 My Resilience Report")
st.markdown(
    "Generate a personalized flood resilience report you can save to your phone "
    "or print before a storm."
)
st.divider()

# ── Input form ─────────────────────────────────────────────────────────────
with st.form("report_form"):
    fc1, fc2 = st.columns(2)
    with fc1:
        biz_name = st.text_input("Business / Property Name", placeholder="My Business or Property")
        address = st.text_input(
            "Address",
            value=st.session_state.get("address", "New Orleans, LA"),
        )
        property_type = st.selectbox(
            "Property Type",
            ["Restaurant", "Retail", "Office", "Residential Rental", "Other"],
        )
    with fc2:
        contact_name = st.text_input("Primary Contact Name")
        contact_info = st.text_input("Phone / Email")
        nfip_policy = st.text_input(
            "NFIP Policy Number (optional — for your reference only)",
            placeholder="e.g. 00XXXXXXXX",
        )

    submitted = st.form_submit_button("🔄 Generate My Report", use_container_width=True)


# ── Report content builders ────────────────────────────────────────────────
def _nfip_coverage(prop_type: str) -> tuple[str, str]:
    covers = {
        "Restaurant": (
            "Building structure, permanently installed equipment (ovens, walk-in coolers), "
            "electrical/plumbing systems, and contents up to $500K.",
            "Business interruption/lost revenue, outdoor signage, cash on hand, "
            "vehicles, landscaping, and basement-level contents.",
        ),
        "Retail": (
            "Building structure, inventory on shelves above ground level (if insured), "
            "fixtures, and electrical systems.",
            "Business interruption, cash, outdoor property, vehicles, and underground items.",
        ),
        "Office": (
            "Building structure, permanently installed items, electrical and HVAC systems.",
            "Business interruption, electronic data, vehicles, and temporary locations.",
        ),
        "Residential Rental": (
            "Building structure and permanently installed appliances (building policy). "
            "Tenants need renters insurance for their own contents.",
            "Loss of rental income, tenant belongings (without renters policy), "
            "landscaping, and vehicles.",
        ),
        "Other": (
            "Building structure, permanently installed equipment, and general contents "
            "up to policy limits.",
            "Business interruption, vehicles, outdoor property, and cash.",
        ),
    }
    return covers.get(prop_type, covers["Other"])


def _pre_event_checklist(prop_type: str) -> str:
    base = [
        "- [ ] Back up all critical data and documents to cloud storage",
        "- [ ] Photograph/video all property and inventory for insurance documentation",
        "- [ ] Elevate electrical equipment, computers, and inventory off the floor",
        "- [ ] Move vehicles to upper-level or covered parking",
        "- [ ] Check SWBNO pump status at swbno.org and on Crest",
        "- [ ] Review your NFIP policy limits and deductibles",
        "- [ ] Notify staff / tenants of flood risk level",
        "- [ ] Confirm emergency contacts are reachable",
    ]
    if prop_type == "Restaurant":
        base += [
            "- [ ] Move perishable inventory to highest shelves or off-site storage",
            "- [ ] Turn off gas at the main valve if flooding is imminent",
            "- [ ] Unplug and elevate kitchen equipment where possible",
        ]
    elif prop_type in ("Retail", "Office"):
        base += [
            "- [ ] Move display merchandise and equipment above flood line",
            "- [ ] Secure or remove outdoor furniture and signage",
        ]
    elif prop_type == "Residential Rental":
        base += [
            "- [ ] Notify tenants to activate personal flood preparedness plans",
            "- [ ] Document building condition with timestamped photos",
        ]
    return "\n".join(base)


def _during_event_checklist() -> str:
    return """- [ ] Do NOT enter flooded areas — 6 inches of moving water can knock you down
- [ ] Monitor NOAA weather radio or the Crest app
- [ ] Call SWBNO Emergency Line if you observe pump failure: **(504) 529-2837**
- [ ] Report flooding to 311 (non-emergency line)
- [ ] Stay off roads — turn around, don't drown
- [ ] If evacuating: take documents, medications, charger, 3 days of cash"""


def _post_event_checklist(prop_type: str) -> str:
    base = [
        "- [ ] Document ALL damage with photos/video before cleanup — this is critical for your claim",
        "- [ ] Contact your NFIP insurer within 24 hours of flood event",
        "- [ ] File a Proof of Loss within 60 days of the event",
        "- [ ] Keep all damaged property until adjuster inspects — do not discard",
        "- [ ] Obtain at least 2 contractor repair estimates in writing",
        "- [ ] Track all expenses (hotel, meals, equipment rental) with receipts",
        "- [ ] Request FEMA disaster registration if declared: DisasterAssistance.gov",
    ]
    if prop_type == "Restaurant":
        base.append(
            "- [ ] Contact Louisiana Restaurant Association for recovery resources"
        )
    return "\n".join(base)


def _generate_report(
    biz_name: str,
    address: str,
    prop_type: str,
    contact_name: str,
    contact_info: str,
    nfip_policy: str,
) -> str:
    now = datetime.now()
    fetch_time = data.get("fetch_time", now.isoformat())
    score = risk["score"]
    level = risk["level"]
    precip = int(risk["precip_pct"])
    river_ft = risk["river_ft"]

    forecast_summary = "NOAA forecast unavailable"
    if forecast:
        short_fc = forecast.get("shortForecast", "")
        temp = forecast.get("temperature", "")
        temp_unit = forecast.get("temperatureUnit", "F")
        forecast_summary = f"{short_fc} | {temp}°{temp_unit} | Precipitation: {precip}%"

    river_str = f"{river_ft:.1f} ft" if river_ft else "Data unavailable"
    river_status = "Normal" if river_ft and river_ft < 14 else ("Elevated" if river_ft and river_ft < 17 else "Action Stage")

    nearest_station = "Mid-City Station (DPS-02) — PUMPING"
    neighborhood = st.session_state.get("neighborhood", "New Orleans")
    for s in swbno.get("stations", []):
        if s["neighborhood"].lower() in neighborhood.lower():
            nearest_station = f"{s['name']} ({s['id']}) — {s['status']}"
            break

    covers, not_covers = _nfip_coverage(prop_type)
    pre_check = _pre_event_checklist(prop_type)
    during_check = _during_event_checklist()
    post_check = _post_event_checklist(prop_type)

    nfip_line = f"**NFIP Policy:** {nfip_policy}" if nfip_policy else "**NFIP Policy:** Not provided"

    report = f"""# Crest — Resilience Report
**{biz_name or 'My Property'}** | {address}
**Contact:** {contact_name or '—'} | {contact_info or '—'}
**Generated:** {now.strftime("%B %d, %Y at %I:%M %p")}
{nfip_line}

---

## Section 1: Property Risk Summary

| Field | Value |
|---|---|
| **Composite Risk Score** | **{score}/100 — {level}** |
| **Assessment Date** | {now.strftime("%B %d, %Y")} |
| **Data Current As Of** | {fetch_time} |
| **Neighborhood** | {neighborhood} |
| **Nearest Drainage Station** | {nearest_station} |
| **Flood Alerts** | {risk["flood_alerts_count"]} active NWS alerts |

**NOAA Forecast:** {forecast_summary}

**Water Levels:**
- Mississippi River at New Orleans: {river_str} (Action stage: 17 ft — Status: {river_status})
- Precipitation probability: {precip}%

**SWBNO System:** {swbno.get("pumps_available", "?")} of {swbno.get("pumps_total", "?")} pumps operational | System capacity: {swbno.get("system_capacity_pct", "?")}%

---

## Section 2: NFIP Policy Quick Reference

**Property Type:** {prop_type}

**Risk Rating 2.0 Impact:**
FEMA's Risk Rating 2.0 (effective Oct 2021) calculates your premium based on rebuilding
cost, distance to water, flood frequency, and flood types — not just your flood zone.
Premiums may increase up to 18% per year until reaching actuarial rates. Properties
under $250K replacement cost typically saw smaller increases. Ask your agent to review
your specific RR 2.0 factors.

**What NFIP Covers for {prop_type}:**
{covers}

**What NFIP Does NOT Cover:**
{not_covers}

**Key Phone Numbers:**
- NFIP Direct: **1-800-427-4661**
- Louisiana Department of Insurance: **1-800-259-5300**
- FEMA Flood Map Service Center: **1-877-336-2627**
- FEMA Disaster Assistance: **1-800-621-3362** | DisasterAssistance.gov

---

## Section 3: Protective Action Checklist

### Pre-Event (24–48 Hours Before Storm)
{pre_check}

### During Event
{during_check}

### Post-Event Documentation
{post_check}

---

## Section 4: Emergency Contacts

| Service | Contact |
|---|---|
| SWBNO Emergency Line | **(504) 529-2837** |
| NOLA Office of Homeland Security | **(504) 658-8700** |
| Non-Emergency City Services | **311** |
| American Red Cross | **1-800-RED-CROSS** (1-800-733-2767) |
| SBA Disaster Loan Line | **1-800-659-2955** |
| NFIP Direct | **1-800-427-4661** |
| Louisiana DOI | **1-800-259-5300** |
| Entergy New Orleans | **1-800-ENTERGY** |

---

## Section 5: Data Sources

| Source | URL | Last Fetched |
|---|---|---|
| NOAA NWS Alerts | api.weather.gov/alerts | {fetch_time} |
| NOAA Hourly Forecast | api.weather.gov/points | {fetch_time} |
| USGS National Water Info | waterservices.usgs.gov | {fetch_time} |
| SWBNO Dashboard | swbno.org/Projects/PumpingAndPower | {fetch_time} |
| NOLA Open Data 311 | data.nola.gov | {fetch_time} |

---

*Generated by Crest — Educational purposes only.*
*Not an insurance advisory service.*
*Built at Tulane University A.B. Freeman School of Business.*
*Freeman AI Innovation Challenge with BoodleBox, 2026.*
"""
    return report


# ── Render report on submit ────────────────────────────────────────────────
if submitted:
    report_md = _generate_report(
        biz_name, address, property_type, contact_name, contact_info, nfip_policy
    )

    st.divider()
    st.subheader("Your Resilience Report")

    st.download_button(
        label="⬇️ Download Report (.txt)",
        data=report_md.encode("utf-8"),
        file_name=f"Crest_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
        mime="text/plain",
        use_container_width=False,
    )

    st.markdown(report_md)

    st.divider()
    st.info(
        "💡 **Tip:** This report is for your personal preparedness records. "
        "Store it in your phone's camera roll or email it to yourself before a storm "
        "when internet connectivity may be lost."
    )
else:
    st.markdown(
        """
        <div style='text-align:center; padding:3rem; color:#64748b;'>
          <div style='font-size:3rem;'>📄</div>
          <div style='font-size:1.1rem; margin-top:1rem;'>
            Fill out the form above and click <b>Generate My Report</b><br>
            to create your personalized flood resilience report.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
