# FloodWatch NOLA

FloodWatch NOLA is a flood resilience intelligence platform for small businesses and renters in Orleans Parish, New Orleans. It combines live data from NOAA, USGS, and SWBNO into a composite risk score that goes beyond FEMA's static flood maps — the only platform that factors in real-time drainage pump station status when calculating risk.

Built for the Tulane University Freeman School of Business AI Innovation Challenge with BoodleBox (2026), the platform gives vulnerable communities actionable, personalized intelligence before, during, and after storm events. Features include an interactive risk map, SWBNO infrastructure deep-dive, an AI flood navigator (FloodBot), and downloadable resilience reports tailored to property type.

---

## How to Run

```bash
# 1. Clone / download the project
cd floodwatch-nola

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
.venv\Scripts\activate           # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. (Optional) Add your Anthropic API key — see section below

# 5. Launch the app
streamlit run app.py
```

The app opens at **http://localhost:8501**

---

## Adding the Anthropic API Key

Create `.streamlit/secrets.toml` (never commit this file):

```toml
ANTHROPIC_API_KEY = "sk-ant-api03-..."
```

Without the key, FloodBot runs in **Demo Mode** with curated educational responses covering the most common questions about NFIP policies, pump station impacts, and FEMA appeals.

---

## Deploy to Streamlit Community Cloud

1. Push your repo to GitHub (exclude `secrets.toml` via `.gitignore`)
2. Go to [share.streamlit.io](https://share.streamlit.io) and click **New app**
3. Select your repo, branch, and `app.py` as the entry point
4. Under **Advanced settings → Secrets**, paste your `secrets.toml` content
5. Click **Deploy** — the app is live in ~2 minutes

> Note: The free tier has resource limits. For a competition demo, it handles the load comfortably.

---

## Competitive Differentiation

- **Real-time infrastructure integration** — The only flood risk platform that ingests SWBNO pump station status into its scoring model. National platforms (First Street, FEMA) assume the drainage system operates at design capacity. We know when it doesn't.

- **Hyper-local risk for the underserved** — Tailored specifically for Orleans Parish small businesses and renters who lack access to the professional risk analytics available to large commercial real estate operators.

- **Action-oriented intelligence** — Every data point drives a specific, role-appropriate action checklist. Users don't just see a risk score — they know exactly what to do about it, in plain language.

---

## Data Sources

| Source | Data | URL |
|---|---|---|
| NOAA National Weather Service | Active alerts, hourly forecast | https://api.weather.gov |
| USGS National Water Information System | River/lake gauge readings | https://waterservices.usgs.gov/nwis/iv/ |
| SWBNO Pumping & Power Dashboard | Pump station status, system capacity | https://www.swbno.org/Projects/PumpingAndPower |
| NOLA Open Data Portal (Socrata) | 311 flood/drainage service requests | https://data.nola.gov |
| Anthropic Claude API | FloodBot AI navigator | https://api.anthropic.com |

NOAA and USGS are free with no API key. NOLA Open Data is public. SWBNO data is currently served from a demo dataset matching April 2026 dashboard state; a live scraper is in development.
