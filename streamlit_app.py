# streamlit_app.py — US Labor Dashboard (reads CSV from GitHub raw or local)

import json
import hashlib
from pathlib import Path
from datetime import datetime

import pandas as pd
import streamlit as st
import plotly.express as px
import requests

# ───────────────────────────────────────────────────────────
# Page & Title
# ───────────────────────────────────────────────────────────
st.set_page_config(page_title="US Labor Dashboard", page_icon="📊", layout="wide")
st.title("US Labor Dashboard")
st.caption("Auto-updating BLS dashboard (Econ 8320 project)")

# ───────────────────────────────────────────────────────────
# Data source configuration
# ───────────────────────────────────────────────────────────
# Default to GitHub raw (no local clone required)
OWNER = "jungminnking"
REPO = "jungminnking-econ8320-semester-project"
BRANCH = "main"
CSV_REPO_PATH = "data/bls_timeseries.csv"
META_REPO_PATH = "data/meta.json"

RAW_CSV_URL = f"https://raw.githubusercontent.com/{OWNER}/{REPO}/{BRANCH}/{CSV_REPO_PATH}"
RAW_META_URL = f"https://raw.githubusercontent.com/{OWNER}/{REPO}/{BRANCH}/{META_REPO_PATH}"

# If you prefer a local folder during development, put this in .streamlit/secrets.toml:
# LABOR_DASH_DATA_DIR = "C:/Users/you/Documents/GitHub/jungminnking-econ8320-semester-project/data"
local_dir = st.secrets.get("LABOR_DASH_DATA_DIR", "")
USE_LOCAL = bool(local_dir)

if USE_LOCAL:
    DATA_DIR = Path(local_dir)
    CSV_PATH = DATA_DIR / "bls_timeseries.csv"
    META_PATH = DATA_DIR / "meta.json"
else:
    CSV_PATH = None
    META_PATH = None

# ───────────────────────────────────────────────────────────
# Series Catalog (must match updater)
# ───────────────────────────────────────────────────────────
SERIES = {
    # Employment — monthly, SA
    "LNS12000000": {"section": "Employment", "name": "Civilian Employment (Thousands, SA)", "freq": "M"},
    "CES0000000001": {"section": "Employment", "name": "Total Nonfarm Employment (Thousands, SA)", "freq": "M"},
    "LNS14000000": {"section": "Employment", "name": "Unemployment Rate (% SA)", "freq": "M"},
    "CES0500000002": {"section": "Employment", "name": "Avg Weekly Hours, Total Private (SA)", "freq": "M"},
    "CES0500000003": {"section": "Employment", "name": "Avg Hourly Earnings, Total Private ($, SA)", "freq": "M"},
    # Productivity — quarterly, SA
    "PRS85006093": {"section": "Productivity", "name": "Output per Hour — Nonfarm Business (Q/Q %)", "freq": "Q"},
    # Price Index — monthly, NSA
    "CUUR0000SA0": {"section": "Price Index", "name": "CPI-U All Items (NSA, 1982–84=100)", "freq": "M"},
    # Compensation — quarterly, NSA
    "CIU1010000000000A": {"section": "Compensation", "name": "ECI — Total Compensation, Private (12m % change, NSA)", "freq": "Q"},
    # If you also export the index series, you can enable YoY-from-level:
    # "CIU1010000000000I": {"section": "Compensation", "name": "ECI — Total Compensation, Private (Index, NSA)", "freq": "Q"},
}
SECTIONS = ["Employment", "Productivity", "Price Index", "Compensation"]

# ───────────────────────────────────────────────────────────
# Helpers: cached fetchers (GitHub or local)
# ───────────────────────────────────────────────────────────
def _etag_or_last_modified(url: str) -> str:
    """Fetch HEAD and return a stable cache key based on ETag/Last-Modified/URL."""
    try:
        r = requests.head(url, timeout=10)
        tag = r.headers.get("ETag") or r.headers.get("Last-Modified") or ""
        if tag:
            return tag
    except Exception:
        pass
    # Fallback to URL hash if no headers or HEAD blocked
    return hashlib.sha256(url.encode("utf-8")).hexdigest()

@st.cache_data(show_spinner=False)
def load_csv_from_github(url: str, cache_buster: str) -> pd.DataFrame:
    # cache_buster ensures cache invalidates when ETag/Last-Modified changes
    return pd.read_csv(url, parse_dates=["date"]).assign(series_id=lambda d: d["series_id"].astype("string"))

@st.cache_data(show_spinner=False)
def load_meta_from_github(url: str, cache_buster: str) -> dict:
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return {}

@st.cache_data(show_spinner=False)
def load_csv_local(path: str, mtime: float) -> pd.DataFrame:
    return pd.read_csv(path, parse_dates=["date"]).assign(series_id=lambda d: d["series_id"].astype("string"))

@st.cache_data(show_spinner=False)
def load_meta_local(path: str, mtime: float) -> dict:
    try:
        return json.loads(Path(path).read_text())
    except Exception:
        return {}

def yoy_from_level(df: pd.DataFrame, sid: str) -> pd.DataFrame:
    """Compute YoY % for level series. Lag=12 for M, 4 for Q."""
    freq = SERIES.get(sid, {}).get("freq", "M").upper()
    lag = 4 if freq.startswith("Q") else 12
    d = (
        df[df.series_id == sid][["date", "value"]]
        .sort_values("date")
        .set_index("date")
        .copy()
    )
    d["YoY %"] = d["value"].pct_change(lag) * 100.0
    d = d.reset_index()
    d["series_id"] = sid
    return d

# ───────────────────────────────────────────────────────────
# About & metadata
# ───────────────────────────────────────────────────────────
with st.expander("About & rubric alignment", expanded=False):
    st.markdown(
        "- Data is fetched by **Hello.py** (locally or via GitHub Actions) and saved under `data/` in the repo.\n"
        "- This app reads the CSV **from GitHub raw** by default; you can override with a local data folder via `LABOR_DASH_DATA_DIR`.\n"
        "- Includes Employment, Productivity, CPI (NSA), and ECI YoY views."
    )

# ───────────────────────────────────────────────────────────
# Load data (GitHub raw by default; local if configured)
# ───────────────────────────────────────────────────────────
if USE_LOCAL:
    if not (CSV_PATH.exists() and CSV_PATH.is_file()):
        st.error(f"Local CSV not found at: {CSV_PATH}")
        st.stop()
    csv_mtime = CSV_PATH.stat().st_mtime
    df_all = load_csv_local(str(CSV_PATH), csv_mtime)
    meta = load_meta_local(str(META_PATH), META_PATH.stat().st_mtime) if META_PATH.exists() else {}
else:
    # Use ETag/Last-Modified to bust cache when GitHub updates the file
    cache_key = _etag_or_last_modified(RAW_CSV_URL)
    df_all = load_csv_from_github(RAW_CSV_URL, cache_key)
    meta = load_meta_from_github(RAW_META_URL, _etag_or_last_modified(RAW_META_URL))

# show last updated if available
if meta:
    st.caption(f"Last updated (UTC): {meta.get('last_updated_utc', 'unknown')}")

# guard
if df_all.empty:
    st.error("The CSV loaded successfully but contains no rows.")
    st.stop()

# ───────────────────────────────────────────────────────────
# Sidebar – cache control + filters
# ───────────────────────────────────────────────────────────
if st.sidebar.button("🔄 Reload data"):
    st.cache_data.clear()
    st.experimental_rerun()

section = st.sidebar.multiselect("Sections", SECTIONS, default=SECTIONS)
eligible = [sid for sid, m in SERIES.items() if m["section"] in section]

# Compute year bounds *from the data* so 2025 appears if present
min_year = int(df_all["date"].dt.year.min())
max_year = int(df_all["date"].dt.year.max())

pick = st.sidebar.multiselect(
    "Series",
    eligible,
    default=eligible,
    format_func=lambda sid: f"{SERIES[sid]['section']} — {SERIES[sid]['name']}",
)
year_min, year_max = st.sidebar.slider(
    "Year range", min_value=min_year, max_value=max_year, value=(min_year, max_year)
)

# ───────────────────────────────────────────────────────────
# Filter + coverage
# ───────────────────────────────────────────────────────────
df = df_all[df_all["series_id"].isin(pick)] if pick else df_all.iloc[0:0]
df = df[(df["date"].dt.year >= year_min) & (df["date"].dt.year <= year_max)]

st.subheader("Data coverage")
if df.empty:
    st.info("No rows match the current filters.")
else:
    coverage = (
        df.groupby("series_id")["date"]
        .agg(["min", "max", "count"])
        .rename_axis("series_id")
        .reset_index()
    )
    coverage["series_name"] = coverage["series_id"].map(lambda sid: SERIES.get(sid, {}).get("name", sid))
    st.caption(f"Rows: {len(df):,} • Min date: {df['date'].min().date()} • Max date: {df['date'].max().date()}")
    st.dataframe(coverage[["series_id", "series_name", "min", "max", "count"]], use_container_width=True)

# Downloads
c1, c2 = st.columns(2)
with c1:
    if USE_LOCAL:
        st.download_button("⬇️ Download full CSV", Path(CSV_PATH).read_bytes(), file_name="bls_timeseries.csv", mime="text/csv")
    else:
        # Download from GitHub raw
        try:
            raw_bytes = requests.get(RAW_CSV_URL, timeout=20).content
            st.download_button("⬇️ Download full CSV", raw_bytes, file_name="bls_timeseries.csv", mime="text/csv")
        except Exception:
            st.info("Could not fetch CSV bytes for download button (network).")

with c2:
    st.download_button(
        "⬇️ Download filtered CSV",
        df.to_csv(index=False).encode("utf-8"),
        file_name="bls_timeseries_filtered.csv",
        mime="text/csv",
    )

# ───────────────────────────────────────────────────────────
# Charts
# ───────────────────────────────────────────────────────────
for sec in SECTIONS:
    sub_ids = [sid for sid in pick if sid in SERIES and SERIES[sid]["section"] == sec]
    if not sub_ids:
        continue
    st.subheader(sec)
    for sid in sub_ids:
        name = SERIES[sid]["name"]
        d = df[df.series_id == sid].sort_values("date")
        if d.empty:
            continue

        # Level chart
        fig = px.line(d, x="date", y="value", title=name, labels={"value": "Value", "date": "Date"})
        fig.update_traces(mode="lines+markers", hovertemplate="%{x|%Y-%m} — %{y:.2f}")
        st.plotly_chart(fig, use_container_width=True)

        # YoY chart for level series where it makes sense
        if sid in {"CUUR0000SA0", "CES0500000003"} or sid.endswith("I"):
            yoy = yoy_from_level(df_all, sid).dropna()
            yoy = yoy[(yoy["date"].dt.year >= year_min) & (yoy["date"].dt.year <= year_max)]
            if not yoy.empty:
                fig2 = px.line(
                    yoy, x="date", y="YoY %", title=f"{name} — YoY %",
                    labels={"date": "Date", "YoY %": "YoY %"}
                )
                fig2.update_traces(mode="lines+markers", hovertemplate="%{x|%Y-%m} — %{y:.2f}%")
                st.plotly_chart(fig2, use_container_width=True)

st.write("---")
if USE_LOCAL:
    st.caption(f"Reading from local: `{CSV_PATH}`")
else:
    st.caption(f"Reading from GitHub raw: `{RAW_CSV_URL}`")
