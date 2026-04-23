from __future__ import annotations

import os
import sys
from datetime import datetime

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.data_fetchers import get_all_data
from utils.risk_engine import compute_risk_score

st.set_page_config(
    page_title="FloodBot — FloodWatch NOLA",
    page_icon="🤖",
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

# ── Anthropic client setup ─────────────────────────────────────────────────
_api_key = None
_demo_mode = False
try:
    _api_key = st.secrets["ANTHROPIC_API_KEY"]
    import anthropic
    _client = anthropic.Anthropic(api_key=_api_key)
except Exception:
    _demo_mode = True
    _client = None

# ── Demo canned responses ──────────────────────────────────────────────────
_CANNED = {
    "business interruption": (
        "**NFIP & Business Interruption:** Standard NFIP commercial policies do **not** "
        "cover business interruption losses. NFIP covers only direct physical damage to "
        "your building and contents.\n\n"
        "For business interruption protection during flood events, you need:\n"
        "- A commercial property policy with a **flood endorsement**\n"
        "- A **surplus lines flood policy** through an admitted carrier\n"
        "- A separate **business income** rider\n\n"
        "For specific policy advice, contact a licensed insurance producer or the "
        "Louisiana Department of Insurance at **1-800-259-5300**."
    ),
    "broadmoor": (
        "**DPS-19 Broadmoor Offline — Impact Assessment:**\n\n"
        "The Broadmoor drainage pump station (870 CFS capacity) being **OFFLINE** "
        "means your neighborhood has significantly reduced drainage capacity. "
        "During moderate rainfall (1–2 inches/hr), water that would normally drain "
        "in 1–2 hours may sit for 4–6+ hours.\n\n"
        "**Recommended actions:**\n"
        "- Move vehicles to elevated ground or covered parking\n"
        "- Elevate ground-floor inventory above 18 inches\n"
        "- Monitor SWBNO updates at swbno.org\n"
        "- Document any pre-existing water damage for insurance\n\n"
        "For specific policy advice, contact a licensed insurance producer or the "
        "Louisiana Department of Insurance at **1-800-259-5300**."
    ),
    "appeal": (
        "**Appealing an Underpaid Flood Claim:**\n\n"
        "If you believe your NFIP claim was underpaid, you have several options:\n\n"
        "1. **Request Re-inspection** — Contact your WYO carrier within 60 days of "
        "the denial/underpayment letter and request a re-inspection\n"
        "2. **Submit Proof of Loss** — File a signed Proof of Loss within 60 days "
        "of the flood event (extensions available)\n"
        "3. **Invoke Appraisal** — Either party may request appraisal under the "
        "Standard Flood Insurance Policy terms\n"
        "4. **Contact FEMA NFIP** — Call 1-800-427-4661 for claim status and escalation\n"
        "5. **File with Louisiana DOI** — The Department of Insurance can intervene "
        "at 1-800-259-5300\n"
        "6. **SBA Disaster Loan** — If federally declared disaster, apply at 1-800-659-2955\n\n"
        "For specific policy advice, contact a licensed insurance producer or the "
        "Louisiana Department of Insurance at **1-800-259-5300**."
    ),
    "risk rating 2.0": (
        "**FEMA Risk Rating 2.0 in Louisiana:**\n\n"
        "Risk Rating 2.0 (effective Oct 2021) fundamentally changed NFIP premium calculations:\n\n"
        "| Old Method | New Method (RR 2.0) |\n"
        "|---|---|\n"
        "| Flood zone + elevation cert | Rebuilding cost + flood frequency + distance to water |\n"
        "| Flat rates by zone | Property-specific actuarial rates |\n\n"
        "**Louisiana impacts:**\n"
        "- Premiums can increase up to **18% per year** until actuarially sound\n"
        "- Properties with replacement costs under $250K often saw smaller increases\n"
        "- Coastal/low-lying properties saw the largest increases\n"
        "- New policyholders pay full actuarial rate immediately\n\n"
        "**What to do:**\n"
        "- Ask your agent to review your property's specific RR 2.0 factors\n"
        "- Explore mitigation discounts (elevate utilities, flood-proof openings)\n"
        "- Consider Increased Cost of Compliance coverage\n\n"
        "For specific policy advice, contact a licensed insurance producer or the "
        "Louisiana Department of Insurance at **1-800-259-5300**."
    ),
    "default": (
        "I'm **FloodBot**, your flood risk navigator for Orleans Parish. I can help with:\n\n"
        "- NFIP policy questions (coverage, exclusions, appeals)\n"
        "- Protective actions before, during, and after flood events\n"
        "- SWBNO pump system status and its impact on your risk\n"
        "- FEMA Risk Rating 2.0 and premium questions\n\n"
        "What would you like to know? Use the suggested questions below to get started."
    ),
}


def _demo_response(message: str) -> str:
    msg_lower = message.lower()
    for keyword, response in _CANNED.items():
        if keyword in msg_lower:
            return response
    return _CANNED["default"]


def _build_system_prompt(data: dict, risk: dict) -> str:
    swbno = data.get("swbno", {})
    stations = swbno.get("stations", [])
    offline = [s["name"] for s in stations if s.get("status") == "OFFLINE"]
    offline_str = ", ".join(offline) if offline else "None"

    forecast = data.get("forecast") or {}
    precip = (forecast.get("probabilityOfPrecipitation") or {}).get("value", 0)
    river_gauge = data.get("river_gauge")
    river_ft = river_gauge["value_ft"] if river_gauge else "N/A"

    data_context = (
        f"Current risk score: {risk['score']}/100 ({risk['level']})\n"
        f"Flood alerts: {risk['flood_alerts_count']} active NWS alerts\n"
        f"SWBNO: {swbno.get('pumps_available', '?')}/{swbno.get('pumps_total', '?')} pumps operational\n"
        f"Offline stations: {offline_str}\n"
        f"Precipitation probability: {precip}%\n"
        f"Mississippi River: {river_ft} ft\n"
        f"System capacity: {swbno.get('system_capacity_pct', '?')}%"
    )

    return f"""You are FloodBot, an AI flood risk navigator for Orleans Parish, New Orleans. \
You serve small business owners and renters with free educational guidance about flood risk, \
NFIP policies, and protective actions.

You have access to the following live data context:
{data_context}

Your role:
- Explain flood risk in plain language
- Help users understand their NFIP policy documents
- Provide general guidance on protective actions before, during, and after flood events
- Explain the SWBNO pump system and why it matters
- Help users navigate the FEMA appeals process (general steps only)
- Explain Risk Rating 2.0 premium impacts in Louisiana

You are NOT:
- A licensed insurance producer or advisor
- A claims adjuster
- A substitute for professional legal or insurance counsel

Always end responses about insurance decisions with:
'For specific policy advice, contact a licensed insurance producer or the Louisiana Department \
of Insurance at 1-800-259-5300.'

Keep responses concise (under 200 words unless detail is needed). \
Use bullet points for action lists. Be warm and direct."""


def _stream_response(messages: list[dict], system: str):
    """Generator that yields text chunks from Anthropic streaming API."""
    try:
        with _client.messages.stream(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=system,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                yield text
    except Exception as e:
        yield f"\n\n⚠️ AI response error. Please try again. ({type(e).__name__})"


# ── Page layout ────────────────────────────────────────────────────────────
st.markdown(
    "<div style='font-size:0.8rem; color:#64748b;'>🌊 FloodWatch NOLA</div>",
    unsafe_allow_html=True,
)
st.title("🤖 FloodBot — AI Flood Navigator")

if _demo_mode:
    st.warning(
        "**Demo Mode:** Anthropic API key not found. FloodBot is running with "
        "canned educational responses.\n\n"
        "To enable live AI responses, add your key to `.streamlit/secrets.toml`:\n"
        "```toml\nANTHROPIC_API_KEY = 'sk-ant-...'\n```"
    )

# Sidebar data snapshot
with st.sidebar:
    st.markdown("### 📊 Current Data Snapshot")
    st.markdown(f"**Risk Score:** `{risk['score']}/100` — **{risk['level']}**")
    st.markdown(f"**Flood Alerts:** {risk['flood_alerts_count']} active")
    st.markdown(
        f"**Pumps:** {swbno.get('pumps_available', '?')}/{swbno.get('pumps_total', '?')} online"
    )
    st.markdown(f"**Precipitation:** {int(risk['precip_pct'])}%")
    st.markdown(
        f"**River Level:** {risk['river_ft']:.1f} ft"
        if risk["river_ft"] else "**River Level:** N/A"
    )
    st.divider()
    if st.button("🗑️ Clear Chat"):
        st.session_state["messages"] = []
        st.rerun()

# ── Chat state init ────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state["messages"] = []

# Welcome message on first load
if not st.session_state["messages"]:
    welcome = (
        "👋 Hello! I'm **FloodBot**, your AI flood risk navigator for Orleans Parish.\n\n"
        f"**Current risk level:** {risk['level']} ({risk['score']}/100)\n"
        f"**Active flood alerts:** {risk['flood_alerts_count']}\n\n"
        "I can help with NFIP policy questions, pump station impacts, protective "
        "actions, and FEMA appeals. What's on your mind?"
    )
    st.session_state["messages"].append({"role": "assistant", "content": welcome})

# ── Suggested questions (shown when only welcome message exists) ───────────
SUGGESTED_QUESTIONS = [
    "Does my NFIP policy cover business interruption losses?",
    "Pump DPS-19 in Broadmoor is offline — how does that affect my risk?",
    "How do I appeal if I think my flood claim was underpaid?",
    "What's Risk Rating 2.0 and how does it affect my premium?",
]

if len(st.session_state["messages"]) <= 1:
    st.markdown("**Suggested questions:**")
    q_cols = st.columns(2)
    for i, q in enumerate(SUGGESTED_QUESTIONS):
        with q_cols[i % 2]:
            if st.button(q, key=f"sq_{i}", use_container_width=True):
                st.session_state["messages"].append({"role": "user", "content": q})
                if _demo_mode:
                    response = _demo_response(q)
                    st.session_state["messages"].append(
                        {"role": "assistant", "content": response}
                    )
                st.rerun()

# ── Chat history ───────────────────────────────────────────────────────────
for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ── Chat input ─────────────────────────────────────────────────────────────
if prompt := st.chat_input("Ask FloodBot anything about flood risk or NFIP…"):
    st.session_state["messages"].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        if _demo_mode:
            response_text = _demo_response(prompt)
            st.markdown(response_text)
            st.session_state["messages"].append(
                {"role": "assistant", "content": response_text}
            )
        else:
            system_prompt = _build_system_prompt(data, risk)
            api_messages = [
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state["messages"]
                if m["role"] in ("user", "assistant")
            ]
            full_response = st.write_stream(
                _stream_response(api_messages, system_prompt)
            )
            st.session_state["messages"].append(
                {"role": "assistant", "content": full_response}
            )

# ── Legal disclaimer ───────────────────────────────────────────────────────
st.divider()
st.caption(
    "⚖️ **Educational Navigator Disclaimer:** FloodBot provides general educational "
    "information only. It is not a licensed insurance producer, claims adjuster, or "
    "legal advisor. For policy-specific advice, contact a licensed insurance producer "
    "or the **Louisiana Department of Insurance at 1-800-259-5300**. "
    "In emergencies, call 911."
)
