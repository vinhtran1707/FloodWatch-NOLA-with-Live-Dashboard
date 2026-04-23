from __future__ import annotations

import concurrent.futures
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

import requests
import streamlit as st

from .swbno_data import get_swbno_status

_HEADERS = {"User-Agent": "Waterline/1.0 (tulane.edu competition)"}
_TIMEOUT = 10

_MOCK_311 = [
    {
        "service_request": "2026-001234",
        "request_type": "Drainage",
        "request_reason": "Catch Basin Not Draining",
        "date_created": "2026-04-22T08:15:00.000",
        "latitude": "29.9720",
        "longitude": "-90.0712",
        "is_mock": True,
    },
    {
        "service_request": "2026-001198",
        "request_type": "Drainage",
        "request_reason": "Catch Basin Frame and Cover Missing or Damaged",
        "date_created": "2026-04-22T07:45:00.000",
        "latitude": "29.9340",
        "longitude": "-90.0844",
        "is_mock": True,
    },
    {
        "service_request": "2026-001155",
        "request_type": "Roads/Drainage",
        "request_reason": "Street Flooding",
        "date_created": "2026-04-22T06:30:00.000",
        "latitude": "29.9668",
        "longitude": "-90.0866",
        "is_mock": True,
    },
    {
        "service_request": "2026-000987",
        "request_type": "Drainage",
        "request_reason": "Flooded Road - Impassable",
        "date_created": "2026-04-21T22:10:00.000",
        "latitude": "29.9584",
        "longitude": "-90.0971",
        "is_mock": True,
    },
    {
        "service_request": "2026-000901",
        "request_type": "Drainage",
        "request_reason": "Standing Water / Pooling",
        "date_created": "2026-04-21T19:55:00.000",
        "latitude": "29.9897",
        "longitude": "-90.0567",
        "is_mock": True,
    },
]


@st.cache_data(ttl=300, show_spinner=False)
def get_noaa_alerts() -> list[dict] | None:
    try:
        r = requests.get(
            "https://api.weather.gov/alerts/active",
            params={"area": "LA"},
            headers=_HEADERS,
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        features = r.json().get("features", [])
        actual = [
            f for f in features
            if f.get("properties", {}).get("status") == "Actual"
        ]
        return actual[:10]
    except Exception:
        return None


@st.cache_data(ttl=300, show_spinner=False)
def get_noaa_forecast() -> dict | None:
    try:
        r1 = requests.get(
            "https://api.weather.gov/points/29.9511,-90.0715",
            headers=_HEADERS,
            timeout=_TIMEOUT,
        )
        r1.raise_for_status()
        hourly_url = r1.json()["properties"]["forecastHourly"]
        r2 = requests.get(hourly_url, headers=_HEADERS, timeout=_TIMEOUT)
        r2.raise_for_status()
        periods = r2.json()["properties"]["periods"]
        return periods[0] if periods else None
    except Exception:
        return None


@st.cache_data(ttl=300, show_spinner=False)
def get_noaa_hourly_12() -> list[dict] | None:
    """Return next 12 hourly forecast periods for the 12-hour strip."""
    try:
        r1 = requests.get(
            "https://api.weather.gov/points/29.9511,-90.0715",
            headers=_HEADERS, timeout=_TIMEOUT,
        )
        r1.raise_for_status()
        hourly_url = r1.json()["properties"]["forecastHourly"]
        r2 = requests.get(hourly_url, headers=_HEADERS, timeout=_TIMEOUT)
        r2.raise_for_status()
        periods = r2.json()["properties"]["periods"][:12]
        return [
            {
                "hour": p["startTime"][11:16],
                "shortForecast": p.get("shortForecast", ""),
                "precip": (p.get("probabilityOfPrecipitation") or {}).get("value") or 0,
                "temp": p.get("temperature", ""),
                "windSpeed": p.get("windSpeed", ""),
            }
            for p in periods
        ]
    except Exception:
        return None


@st.cache_data(ttl=600, show_spinner=False)
def geocode_address(address: str) -> dict | None:
    """Geocode a free-text address via Nominatim. Returns {lat, lon, display}."""
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": address, "format": "json", "limit": 1,
                    "countrycodes": "us", "viewbox": "-90.14,29.86,-89.94,30.07",
                    "bounded": 1},
            headers=_HEADERS,
            timeout=10,
        )
        if r.ok and r.json():
            res = r.json()[0]
            return {
                "lat": float(res["lat"]),
                "lon": float(res["lon"]),
                "display": res.get("display_name", address),
            }
    except Exception:
        pass
    return None


@st.cache_data(ttl=300, show_spinner=False)
def get_usgs_gauge(site_id: str) -> dict | None:
    try:
        r = requests.get(
            "https://waterservices.usgs.gov/nwis/iv/",
            params={
                "sites": site_id,
                "format": "json",
                "parameterCd": "00065",
                "siteStatus": "active",
            },
            headers=_HEADERS,
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        ts = r.json()["value"]["timeSeries"]
        if not ts:
            return None
        entry = ts[0]["values"][0]["value"][0]
        return {
            "value_ft": float(entry["value"]),
            "datetime": entry["dateTime"],
            "site_id": site_id,
        }
    except Exception:
        return None


@st.cache_data(ttl=300, show_spinner=False)
def get_nola_311(limit: int = 20) -> list[dict] | None:
    # Dataset: 311 OPCD Calls (2012-Present) — resource 2jgv-pqrq
    params = {
        "$where": (
            "request_type='Drainage' "
            "OR request_type='Roads/Drainage' "
            "OR request_reason like '%flood%' "
            "OR request_reason like '%drain%'"
        ),
        "$limit": limit,
        "$order": "date_created DESC",
    }
    try:
        r = requests.get(
            "https://data.nola.gov/resource/2jgv-pqrq.json",
            params=params,
            headers=_HEADERS,
            timeout=_TIMEOUT,
        )
        if r.status_code == 200:
            data = r.json()
            # Normalize lat/lon from geocoded_column if top-level fields are missing
            for rec in data:
                if not rec.get("latitude") and rec.get("geocoded_column"):
                    rec["latitude"] = rec["geocoded_column"].get("latitude", "")
                    rec["longitude"] = rec["geocoded_column"].get("longitude", "")
            return data if data else []
    except Exception:
        pass
    return _MOCK_311


@st.cache_data(ttl=3600, show_spinner=False)
def get_311_history() -> list[dict] | None:
    """Year-by-year drainage complaint volume from NOLA 311 (2019–present)."""
    try:
        r = requests.get(
            "https://data.nola.gov/resource/2jgv-pqrq.json",
            params={
                "$select": "date_trunc_y(date_created) as year, count(*) as complaints",
                "$where": "request_type='Drainage' OR request_type='Roads/Drainage'",
                "$group": "year",
                "$order": "year DESC",
                "$limit": 20,
            },
            headers=_HEADERS,
            timeout=_TIMEOUT,
        )
        if r.status_code == 200:
            rows = r.json()
            return [
                {"year": int(row["year"][:4]), "complaints": int(row["complaints"])}
                for row in rows
                if row.get("year") and row.get("complaints")
            ]
    except Exception:
        pass
    # Fallback: hardcoded from last validated pull
    return [
        {"year": 2026, "complaints": 512},
        {"year": 2025, "complaints": 3107},
        {"year": 2024, "complaints": 5479},
        {"year": 2023, "complaints": 3281},
        {"year": 2022, "complaints": 4834},
        {"year": 2021, "complaints": 9302},
        {"year": 2020, "complaints": 7960},
        {"year": 2019, "complaints": 55801},
    ]


@st.cache_data(ttl=86400, show_spinner=False)
def get_nfip_claims() -> list[dict] | None:
    """FEMA OpenFEMA NFIP claims for Orleans Parish (countyCode 22071)."""
    try:
        r = requests.get(
            "https://www.fema.gov/api/open/v2/FimaNfipClaims",
            params={
                "$filter": "countyCode eq '22071'",
                "$select": (
                    "reportedZipCode,yearOfLoss,"
                    "amountPaidOnBuildingClaim,"
                    "amountPaidOnContentsClaim,"
                    "waterDepth,floodEvent"
                ),
                "$top": 1000,
                "$orderby": "yearOfLoss desc",
            },
            headers=_HEADERS,
            timeout=30,
        )
        if r.status_code == 200:
            return r.json().get("FimaNfipClaims", [])
    except Exception:
        pass
    return None


@st.cache_data(ttl=86400, show_spinner=False)
def get_station_elevations() -> dict[str, float]:
    """USGS EPQS elevation (ft) for each SWBNO pump station coordinate."""
    coords = {
        "DPS-02": (29.9720, -90.0851),
        "DPS-07": (30.0045, -90.1068),
        "DPS-12": (29.9897, -90.0567),
        "DPS-19": (29.9542, -90.1012),
        "DPS-24": (29.9514, -90.0459),
        "DPS-31": (29.9653, -90.0712),
        "DPS-38": (29.9268, -90.0598),
        "SFC2":   (29.9654, -90.0771),
    }
    results = {}
    for station_id, (lat, lon) in coords.items():
        try:
            r = requests.get(
                "https://epqs.nationalmap.gov/v1/json",
                params={"x": lon, "y": lat, "units": "Feet", "includeDate": "false"},
                headers=_HEADERS,
                timeout=10,
            )
            if r.ok:
                results[station_id] = round(float(r.json()["value"]), 1)
        except Exception:
            pass
    # Fallback values from last validated pull (April 2026)
    fallback = {
        "DPS-02": -0.2, "DPS-07": -5.7, "DPS-12": -5.6,
        "DPS-19": -1.9, "DPS-24": +4.5, "DPS-31": -0.9,
        "DPS-38": +1.0, "SFC2":   +0.3,
    }
    for sid, val in fallback.items():
        results.setdefault(sid, val)
    return results


_FLOOD_KEYWORDS = {
    "flood", "flooding", "flooded", "drainage", "drain", "pump",
    "swbno", "water", "ponding", "impassable", "street water",
}

_RSS_FEEDS = [
    ("NOLA.com Flood", "https://www.nola.com/search/?q=flood+new+orleans&format=rss"),
    ("WWL-TV Weather", "https://www.wwltv.com/feeds/rss/news/local/weather/"),
    ("NOLA.com Weather", "https://www.nola.com/weather/?format=rss"),
]

_MOCK_NEWS = [
    {
        "source": "NOLA.com",
        "title": "Heavy rain causes street flooding in Mid-City and Lakeview",
        "published": "2026-04-22T08:00:00",
        "link": "",
        "is_mock": True,
    },
    {
        "source": "WWL-TV",
        "title": "SWBNO pump station offline ahead of Thursday storm system",
        "published": "2026-04-21T17:30:00",
        "link": "",
        "is_mock": True,
    },
    {
        "source": "Reddit r/NewOrleans",
        "title": "Anyone else seeing massive puddles on Canal St near Carrollton?",
        "published": "2026-04-22T07:12:00",
        "link": "",
        "is_mock": True,
    },
    {
        "source": "NOLA.com",
        "title": "City issues flood watch for Orleans Parish — 2 to 3 inches expected",
        "published": "2026-04-21T14:00:00",
        "link": "",
        "is_mock": True,
    },
]

_REDDIT_SEARCH_URL = "https://www.reddit.com/search.json"
_REDDIT_SUBREDDITS = ["NewOrleans", "Louisiana"]


@st.cache_data(ttl=600, show_spinner=False)
def get_news_rss() -> list[dict]:
    """Fetch flood-relevant headlines from the past 24 hours via local news RSS feeds."""
    results = []
    cutoff = datetime.utcnow() - timedelta(hours=24)
    for source_name, url in _RSS_FEEDS:
        try:
            r = requests.get(url, headers=_HEADERS, timeout=10)
            if not r.ok:
                continue
            root = ET.fromstring(r.text)
            items = root.findall(".//item")
            for item in items[:50]:
                title = (item.findtext("title") or "").strip()
                pub_raw = (item.findtext("pubDate") or "").strip()
                link  = (item.findtext("link") or "")
                # Parse RFC 2822 pubDate; skip if older than 24 h
                pub_dt = None
                for fmt in (
                    "%a, %d %b %Y %H:%M:%S %z",
                    "%a, %d %b %Y %H:%M:%S GMT",
                    "%a, %d %b %Y %H:%M:%S +0000",
                ):
                    try:
                        pub_dt = datetime.strptime(pub_raw[:31], fmt)
                        if pub_dt.tzinfo is not None:
                            pub_dt = pub_dt.replace(tzinfo=None) - pub_dt.utcoffset()
                        break
                    except ValueError:
                        continue
                if pub_dt is None or pub_dt < cutoff:
                    continue
                if any(kw in title.lower() for kw in _FLOOD_KEYWORDS):
                    results.append({
                        "source": source_name,
                        "title": title,
                        "published": pub_dt.isoformat(),
                        "link": link,
                        "is_mock": False,
                    })
        except Exception:
            continue
    return results or []


@st.cache_data(ttl=600, show_spinner=False)
def get_reddit_flood_posts() -> list[dict]:
    """Search Reddit public JSON API for flood/drainage posts in NOLA subreddits."""
    results = []
    headers = {**_HEADERS, "Accept": "application/json"}
    for sub in _REDDIT_SUBREDDITS:
        try:
            r = requests.get(
                f"https://www.reddit.com/r/{sub}/search.json",
                params={
                    "q": "flood OR flooding OR drainage OR pump OR SWBNO OR ponding",
                    "sort": "new",
                    "restrict_sr": "1",
                    "limit": 25,
                    "t": "day",
                },
                headers=headers,
                timeout=10,
            )
            if not r.ok:
                continue
            posts = r.json().get("data", {}).get("children", [])
            cutoff = datetime.utcnow() - timedelta(hours=24)
            for p in posts:
                d = p.get("data", {})
                title = d.get("title", "")
                created_dt = datetime.utcfromtimestamp(d.get("created_utc", 0))
                if created_dt < cutoff:
                    continue
                permalink = "https://reddit.com" + d.get("permalink", "")
                score = d.get("score", 0)
                if any(kw in title.lower() for kw in _FLOOD_KEYWORDS):
                    results.append({
                        "source": f"Reddit r/{sub}",
                        "title": title,
                        "published": created_dt.isoformat(),
                        "link": permalink,
                        "score": score,
                        "is_mock": False,
                    })
        except Exception:
            continue
    return results or []


NEIGHBORHOOD_BBOX: dict[str, tuple[float, float, float, float]] = {
    # (south, west, north, east)
    "Mid-City":             (29.955, -90.102, 29.982, -90.072),
    "Lakeview":             (29.990, -90.130, 30.018, -90.092),
    "Broadmoor":            (29.938, -90.118, 29.965, -90.090),
    "Gentilly":             (29.975, -90.075, 29.998, -90.038),
    "Bywater":              (29.938, -90.060, 29.960, -90.028),
    "Tremé":                (29.954, -90.083, 29.975, -90.058),
    "Algiers":              (29.912, -90.078, 29.938, -90.042),
    "Garden District":      (29.916, -90.108, 29.940, -90.078),
    "Uptown":               (29.916, -90.130, 29.948, -90.085),
    "CBD / French Quarter": (29.940, -90.083, 29.965, -90.055),
}

_HIGHWAY_PRIORITY = {
    "primary": 0, "primary_link": 0,
    "secondary": 1, "secondary_link": 1,
    "tertiary": 2, "tertiary_link": 2,
    "residential": 3,
    "unclassified": 4,
    "living_street": 5,
}


@st.cache_data(ttl=3600, show_spinner=False)
def get_osm_streets(neighborhood: str) -> list[dict]:
    """Fetch actual OSM street geometry for a neighborhood via Overpass API."""
    bbox = NEIGHBORHOOD_BBOX.get(neighborhood)
    if not bbox:
        return []
    south, west, north, east = bbox
    query = (
        f"[out:json][timeout:25];"
        f'way["highway"~"^(primary|primary_link|secondary|secondary_link|tertiary|tertiary_link|residential|unclassified)$"]["name"]'
        f"({south},{west},{north},{east});"
        f"out geom;"
    )
    try:
        r = requests.get(
            "https://overpass-api.de/api/interpreter",
            params={"data": query},
            headers={**_HEADERS, "Accept": "application/json"},
            timeout=30,
        )
        if not r.ok:
            return []
        elements = r.json().get("elements", [])
        streets = []
        for el in elements:
            if el.get("type") != "way":
                continue
            geometry = el.get("geometry", [])
            if len(geometry) < 2:
                continue
            coords = [[pt["lat"], pt["lon"]] for pt in geometry]
            tags = el.get("tags", {})
            name = tags.get("name") or tags.get("ref") or "Unnamed Road"
            highway = tags.get("highway", "residential")
            streets.append({
                "name": name,
                "coords": coords,
                "way_id": el.get("id"),
                "highway": highway,
            })
        streets.sort(key=lambda s: _HIGHWAY_PRIORITY.get(s["highway"], 99))
        return streets
    except Exception:
        return []


@st.cache_data(ttl=86400, show_spinner=False)
def get_elevation_grid(neighborhood: str, grid_size: int = 20) -> dict | None:
    """Fetch SRTM 30m elevation grid from open-topo-data (no API key required).

    Returns {"dem": [[float,...]], "lats": [float,...], "lons": [float,...]}
    with dem shaped [grid_size, grid_size], values in metres above sea level.
    """
    bbox = NEIGHBORHOOD_BBOX.get(neighborhood)
    if not bbox:
        return None
    south, west, north, east = bbox

    lats = [south + (north - south) * i / (grid_size - 1) for i in range(grid_size)]
    lons = [west  + (east  - west)  * j / (grid_size - 1) for j in range(grid_size)]
    locations = [(lat, lon) for lat in lats for lon in lons]

    elevations: list[float] = []
    for i in range(0, len(locations), 100):
        batch = locations[i:i + 100]
        loc_str = "|".join(f"{la},{lo}" for la, lo in batch)
        try:
            r = requests.get(
                "https://api.opentopodata.org/v1/srtm30m",
                params={"locations": loc_str},
                headers=_HEADERS,
                timeout=20,
            )
            if not r.ok:
                return None
            for res in r.json().get("results", []):
                elevations.append(float(res["elevation"] or 0))
        except Exception:
            return None

    if len(elevations) != grid_size * grid_size:
        return None

    dem = [elevations[i * grid_size:(i + 1) * grid_size] for i in range(grid_size)]
    return {"dem": dem, "lats": lats, "lons": lons}


def get_social_feed() -> list[dict]:
    """Merge news RSS + Reddit posts, sorted newest first. Falls back to mock if empty."""
    rss   = get_news_rss()
    reddit = get_reddit_flood_posts()
    combined = rss + reddit
    combined.sort(key=lambda x: x.get("published", ""), reverse=True)
    return combined[:15] if combined else _MOCK_NEWS


def _fetch_all_raw() -> dict:
    """Parallel-fetch all live data sources."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        f_alerts   = pool.submit(get_noaa_alerts)
        f_forecast = pool.submit(get_noaa_forecast)
        f_hourly   = pool.submit(get_noaa_hourly_12)
        f_river    = pool.submit(get_usgs_gauge, "07374000")
        f_pont     = pool.submit(get_usgs_gauge, "073802516")
        f_311      = pool.submit(get_nola_311, 20)
        f_history  = pool.submit(get_311_history)
        f_nfip     = pool.submit(get_nfip_claims)
        f_elev     = pool.submit(get_station_elevations)
        f_social   = pool.submit(get_social_feed)

        alerts              = f_alerts.result()
        forecast            = f_forecast.result()
        hourly_12           = f_hourly.result()
        river_gauge         = f_river.result()
        pontchartrain_gauge = f_pont.result()
        reports_311         = f_311.result()
        history_311         = f_history.result()
        nfip_claims         = f_nfip.result()
        station_elevations  = f_elev.result()
        social_feed         = f_social.result()

    return {
        "alerts":              alerts,
        "forecast":            forecast,
        "hourly_12":           hourly_12,
        "river_gauge":         river_gauge,
        "pontchartrain_gauge": pontchartrain_gauge,
        "reports_311":         reports_311,
        "history_311":         history_311,
        "nfip_claims":         nfip_claims,
        "station_elevations":  station_elevations,
        "social_feed":         social_feed,
        "swbno":               get_swbno_status(),
        "fetch_time":          datetime.now().isoformat(),
    }


def get_all_data() -> dict:
    return _fetch_all_raw()
