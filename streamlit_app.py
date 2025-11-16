# streamlit_app.py — US Labor Dashboard (reads CSV written by bls_update.py)

from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime

import pandas as pd
import streamlit as st
import plotly.express as px

# ---------------------------------------------------------------------
# Page & Paths (path-safe: resolve relative to this file)
# ---------------------------------------------------------------------
st.set_page_config(page_title="US Labor Dashboard", page_icon="📊", layout="wide")
st.title("US Labor Dashboard")
st.caption("Auto-updating BLS dashboard (Econ 8320 project)")

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(st.secrets.get("LABOR_DASH_DATA_DIR", BASE_DIR / "data"))
CSV_PATH = DATA_DIR / "bls_timeseries.csv"
META_PATH = DATA_DIR / "meta.json"

# ---------------------------------------------------------------------
# Series Catalog (must match bls_update.py)
# ---------------------------------------------------------------------
SERIES = {
    "LNS12000000": {"section": "Employment", "name": "Civilian Employment (Thousands, SA)", "freq": "M"},
    "CES0000000001": {"section": "Employment", "name": "Total Nonfarm Employment (Thousands, SA)", "freq": "M"},
    "LNS14000000": {"section": "Employment", "name": "Unemployment Rate (% SA)", "freq": "M"},
    "CES0500000002": {"section": "Employment", "name": "Avg Weekly Hours, Total Private (SA)", "freq": "M"},
    "CES0500000003": {"section": "Employment", "name": "Avg Hourly Earnings, Total Private ($, SA)", "freq": "M"},
    "PRS85006093": {"section": "Productivity", "name": "Output per Hour — Nonfarm Business (Q/Q %)", "freq": "Q"},
    "CUUR0000SA0": {"section": "Price Index", "name": "CPI-U All Items (NSA, 1982–84=100)", "freq": "M"},
    "CIU1010000000000I": {"section": "Compensation", "name": "ECI — Total Compensation, Private (Index, NSA)", "freq": "Q"},
    "CIU1010000000000A": {"section": "Compensation", "name": "ECI — Total Compensation, Private (12m % change, NSA)", "freq": "Q"},
}
SECTIONS = ["Employment", "Productivity", "Price Index", "Compensation"]

# NBER recession shading since 2006 (approx monthly spans)
RECESSIONS = [
    (pd.Timestamp(2007, 12, 1), pd.Timestamp(2009, 6, 1)),
    (pd.Timestamp(2020, 2, 1), pd.Timestamp(2020, 4, 1)),
]

def add_recession_shading(fig):
    for start, end in RECESSIONS:
        fig.add_vrect(x0=start, x1=end, fillcolor="gray", opacity=0.15, line_width=0)
    return fig

@st.cache_data
def load_data(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path, parse_dates=["date"])
    df["series_id"] = df["series_id"].astype("string")
    return df

def yoy_from_level(df: pd.DataFrame, sid: str) -> pd.DataFrame:
    """YoY % from level series. Lag=12 for M, 4 for Q."""
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

# ---------------------------------------------------------------------
# About / Meta
# ---------------------------------------------------------------------
with st.expander("About & rubric alignment", expanded=False):
    st.markdown(
        "- Data is fetched by **bls_update.py** (locally or via GitHub Actions) and saved to `data/`.\n"
        "- This app only reads the CSV; it does **not** call the API.\n"
        "- Required labor series included; supports filters for section/series & year range; YoY views for CPI, wages, and ECI index."
    )

if META_PATH.exists():
    try:
        meta = json.loads(META_PATH.read_text())
        st.caption(f"Last updated (UTC): {meta.get('last_updated_utc', 'unknown')}")
    except Exception:
        pass

# Guard: CSV must exist
if not CSV_PATH.exists():
    st.error(
        "Data file not found. Run `python bls_update.py` once, "
        "or let the GitHub Action populate `data/bls_timeseries.csv`."
    )
    st.stop()

# ---------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------
section = st.sidebar.multiselect("Sections", SECTIONS, default=SECTIONS)
eligible = [sid for sid, m in SERIES.items() if m["section"] in section]
pick = st.sidebar.multiselect(
    "Series",
    eligible,
    default=eligible,
    format_func=lambda sid: f"{SERIES[sid]['section']} — {SERIES[sid]['name']}",
)
year_min_default, year_max_default = 2006, datetime.utcnow().year
year_min, year_max = st.sidebar.slider(
    "Year range", min_value=2006, max_value=year_max_default,
    value=(year_min_default, year_max_default)
)

# ---------------------------------------------------------------------
# Load, filter, and show coverage
# ---------------------------------------------------------------------
df = load_data(CSV_PATH)
if pick:
    df = df[df["series_id"].isin(pick)]
df = df[(df["date"].dt.year >= year_min) & (df["date"].dt.year <= year_max)]

st.subheader("Data coverage")
coverage = (
    df.groupby("series_id")["date"]
    .agg(["min", "max", "count"])
    .rename_axis("series_id")
    .reset_index()
)
coverage["series_name"] = coverage["series_id"].map(lambda sid: SERIES.get(sid, {}).get("name", sid))
coverage = coverage[["series_id", "series_name", "min", "max", "count"]]
st.dataframe(coverage, use_container_width=True)

# Downloads
c1, c2 = st.columns(2)
with c1:
    st.download_button("⬇️ Download full CSV", CSV_PATH.read_bytes(), file_name="bls_timeseries.csv", mime="text/csv")
with c2:
    st.download_button(
        "⬇️ Download filtered CSV",
        df.to_csv(index=False).encode("utf-8"),
        file_name="bls_timeseries_filtered.csv",
        mime="text/csv",
    )

# ---------------------------------------------------------------------
# Charts (levels + optional YoY for selected level series)
# ---------------------------------------------------------------------
for sec in SECTIONS:
    sub_ids = [sid for sid in pick if SERIES[sid]["section"] == sec]
    if not sub_ids:
        continue

    st.subheader(sec)
    for sid in sub_ids:
        name = SERIES[sid]["name"]
        d = df[df.series_id == sid].sort_values("date")
        if d.empty:
            continue

        # Level / % level chart
        fig = px.line(d, x="date", y="value", title=name, labels={"value": "Value", "date": "Date"})
        fig.update_traces(mode="lines+markers", hovertemplate="%{x|%Y-%m} — %{y:.2f}")
        add_recession_shading(fig)
        st.plotly_chart(fig, use_container_width=True)

        # Extra YoY for level-type series
        if sid in ["CUUR0000SA0", "CES0500000003", "CIU1010000000000I"]:
            yoy = yoy_from_level(df, sid).dropna()
            yoy = yoy[(yoy["date"].dt.year >= year_min) & (yoy["date"].dt.year <= year_max)]
            if not yoy.empty:
                fig2 = px.line(
                    yoy, x="date", y="YoY %", title=f"{name} — YoY %",
                    labels={"date": "Date", "YoY %": "YoY %"}
                )
                fig2.update_traces(mode="lines+markers", hovertemplate="%{x|%Y-%m} — %{y:.2f}%")
                add_recession_shading(fig2)
                st.plotly_chart(fig2, use_container_width=True)

st.write("---")
st.caption(
    f"Data path: `{CSV_PATH}` • CPI is NSA • Productivity is Q/Q % • "
    "ECI shows official YoY (A series) and YoY computed from the index (I series)."
)