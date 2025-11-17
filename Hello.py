# -*- coding: utf-8 -*-
"""US Labor Dashboard — Exploration (v2)
Author: Jungmin Hwang

This Streamlit app mirrors the *format/style* of the CPS/Union dashboard
(shared earlier) while preserving the BLS-focused *content* here:
- Pulls BLS series via API (monthly + quarterly mapped to Mar/Jun/Sep/Dec)
- Builds a unified dataset and interactive figures
- Sections/Tabs echo the original app's layout

Run with:  streamlit run app.py
"""

import os
import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

# ===========================================================
# Page & Intro
# ===========================================================
st.set_page_config(page_title="US Labor Dashboard — Exploration (v2)", layout="wide")

st.write("# US Labor Dashboard — Exploration (v2)")

st.markdown(
    """
    This dashboard explores **U.S. labor market indicators** fetched directly from the
    **Bureau of Labor Statistics (BLS) API**. It keeps quarterly data and maps them to
    months (Q1→Mar, Q2→Jun, Q3→Sep, Q4→Dec), and visualizes:

    - Employment (levels, hours, earnings, unemployment rate)
    - Productivity (Output per Hour — Nonfarm Business)
    - Prices (CPI-U All Items)
    - Compensation (ECI — Private Industry)

    **Instructions**
    - Use the controls in the left sidebar to set the time range and toggle series.
    - Each chart supports zoom and legend interaction; double-click to reset.
    - Use the *Download* buttons to export the unified dataset.

    *Note:* CPI is **NSA**; some series are **SA**. Quarterly series are shown at
    Mar/Jun/Sep/Dec. API key is optional (public rate limits may apply).
    """
)

# ===========================================================
# Config & Constants
# ===========================================================
START_YEAR_DEFAULT = 2006
END_YEAR_DEFAULT = datetime.utcnow().year

SERIES = {
    # Employment (Monthly)
    "LNS12000000": {"section": "Employment", "name": "Civilian Employment (Thousands, SA)", "freq": "M", "units": "Thousands"},
    "CES0000000001": {"section": "Employment", "name": "Total Nonfarm Employment (Thousands, SA)", "freq": "M", "units": "Thousands"},
    "LNS14000000": {"section": "Employment", "name": "Unemployment Rate (% SA)", "freq": "M", "units": "%"},
    "CES0500000002": {"section": "Employment", "name": "Avg Weekly Hours, Total Private (SA)", "freq": "M", "units": "Hours"},
    "CES0500000003": {"section": "Employment", "name": "Avg Hourly Earnings, Total Private ($, SA)", "freq": "M", "units": "$"},

    # Productivity (Quarterly, SA — Q/Q %)
    "PRS85006093": {"section": "Productivity", "name": "Output per Hour — Nonfarm Business (Q/Q %)", "freq": "Q", "units": "% Q/Q"},

    # Price Index (Monthly, NSA)
    "CUUR0000SA0": {"section": "Price Index", "name": "CPI-U All Items (NSA, 1982–84=100)", "freq": "M", "units": "Index"},

    # Compensation (Quarterly, NSA)
    "CIU1010000000000I": {"section": "Compensation", "name": "ECI — Total Compensation, Private Industry (12m % chg)", "freq": "Q", "units": "% YoY"},
}
ALL_SERIES = list(SERIES.keys())

BLS_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"

# ===========================================================
# Sidebar Controls
# ===========================================================
st.sidebar.header("Controls")
api_key = st.sidebar.text_input("BLS API Key (optional)", value=os.getenv("BLS_API_KEY", ""), type="password")

min_year = st.sidebar.number_input("Start Year", min_value=1940, max_value=END_YEAR_DEFAULT, value=START_YEAR_DEFAULT, step=1)
max_year = st.sidebar.number_input("End Year", min_value=min_year, max_value=END_YEAR_DEFAULT, value=END_YEAR_DEFAULT, step=1)

section = st.sidebar.radio("Section", options=["Employment", "Productivity", "Price Index", "Compensation", "All"], index=4)

# Allow custom series selection (especially useful in All mode)
available_series = [sid for sid, meta in SERIES.items() if section == "All" or meta["section"] == section]
sel_series = st.sidebar.multiselect("Series to display", options=available_series, default=available_series)

show_yoy = st.sidebar.checkbox("Show YoY % (where applicable)", value=False, help="Uses 12-month change for monthly series; 4-quarter change for quarterly series.")

# ===========================================================
# Helpers
# ===========================================================
@st.cache_data(show_spinner=True)
def fetch_bls_timeseries(series_ids, start_year, end_year, api_key_val):
    payload = {
        "seriesid": series_ids,
        "startyear": str(start_year),
        "endyear": str(end_year),
    }
    if api_key_val:
        payload["registrationkey"] = api_key_val

    r = requests.post(BLS_URL, json=payload, timeout=60)
    r.raise_for_status()
    data = r.json()
    if data.get("status") != "REQUEST_SUCCEEDED":
        raise RuntimeError(f"BLS API error: {json.dumps(data)[:300]}")
    return data


def _q_to_month(q: int) -> int:
    return {1: 3, 2: 6, 3: 9, 4: 12}[q]


def series_payload_to_rows(series_json):
    sid = series_json["seriesID"]
    rows = []
    for item in series_json.get("data", []):
        period = item.get("period")
        if not period or period == "M13":
            continue  # skip annual average
        year = int(item["year"])
        if period.startswith("M"):
            month = int(period[1:])
        elif period.startswith("Q"):
            month = _q_to_month(int(period[1:]))
        else:
            continue
        dt = pd.Timestamp(year=year, month=month, day=1)
        try:
            val = float(item["value"])  # ensure numeric
        except Exception:
            continue
        rows.append({"series_id": sid, "date": dt, "value": val})
    return rows


def build_dataframe(series_ids, start_year, end_year, api_key_val):
    api = fetch_bls_timeseries(series_ids, start_year, end_year, api_key_val)
    rows = []
    for s in api["Results"]["series"]:
        rows.extend(series_payload_to_rows(s))
    df = pd.DataFrame(rows).sort_values(["series_id", "date"]).reset_index(drop=True)
    return df


def add_yoy(df_long, sid):
    freq = SERIES.get(sid, {}).get("freq", "M").upper()
    lag = 4 if freq.startswith("Q") else 12
    d = (
        df_long[df_long.series_id == sid]
        .set_index("date")
        .sort_index()[["value"]]
        .copy()
    )
    d["YoY %"] = d["value"].pct_change(lag) * 100
    d["series_id"] = sid
    return d.reset_index()


# ===========================================================
# Data Pull
# ===========================================================
with st.spinner("Fetching data from BLS API…"):
    try:
        df = build_dataframe(sel_series, min_year, max_year, api_key)
    except Exception as e:
        st.error(f"Failed to fetch data. {e}")
        st.stop()

if df.empty:
    st.warning("No data returned for the selected series/time range.")
    st.stop()

# Provide download of unified CSV
csv_bytes = df.to_csv(index=False).encode("utf-8")
st.download_button("Download unified CSV", data=csv_bytes, file_name="bls_timeseries.csv", mime="text/csv")

# Coverage summary
with st.expander("Show data coverage summary"):
    coverage = (
        df.groupby("series_id")["date"].agg(["min", "max", "count"]).rename_axis("series_id").reset_index()
    )
    st.dataframe(coverage, use_container_width=True)

# ===========================================================
# Layout Tabs (mirrors style of the CPS app)
# ===========================================================
sections = [
    ("Employment", [sid for sid in sel_series if SERIES[sid]["section"] == "Employment"]),
    ("Productivity", [sid for sid in sel_series if SERIES[sid]["section"] == "Productivity"]),
    ("Price Index", [sid for sid in sel_series if SERIES[sid]["section"] == "Price Index"]),
    ("Compensation", [sid for sid in sel_series if SERIES[sid]["section"] == "Compensation"]),
]

# Create pairs of tabs where it makes sense (e.g., raw vs YoY)
emp_tab, prod_tab, cpi_tab, eci_tab = st.tabs(["Employment", "Productivity", "Price Index", "Compensation"])

# ---------------- Employment ----------------
with emp_tab:
    subs = [sid for sid, meta in SERIES.items() if meta["section"] == "Employment" and sid in sel_series]
    if not subs:
        st.info("No employment series selected.")
    else:
        # One combined wide-format line chart with multiple series
        wide = df[df.series_id.isin(subs)].pivot(index="date", columns="series_id", values="value")
        # Relabel columns to human-readable names
        newcols = {sid: SERIES[sid]["name"] for sid in wide.columns}
        wide = wide.rename(columns=newcols)
        fig = px.line(wide, x=wide.index, y=wide.columns, title="Employment Indicators")
        fig.update_layout(legend_title_text="Series")
        st.plotly_chart(fig, use_container_width=True)

# ---------------- Productivity ----------------
with prod_tab:
    subs = [sid for sid, meta in SERIES.items() if meta["section"] == "Productivity" and sid in sel_series]
    if not subs:
        st.info("No productivity series selected.")
    else:
        sub_df = df[df.series_id.isin(subs)].copy()
        # Quarter-over-quarter % is already the unit for PRS85006093
        name_map = {sid: SERIES[sid]["name"] for sid in subs}
        fig = px.line(sub_df, x="date", y="value", color="series_id", title="Productivity",
                      labels={"value": "%", "series_id": "Series"})
        fig.for_each_trace(lambda t: t.update(name=name_map.get(t.name, t.name)))
        st.plotly_chart(fig, use_container_width=True)

# ---------------- Price Index (CPI) ----------------
with cpi_tab:
    subs = [sid for sid, meta in SERIES.items() if meta["section"] == "Price Index" and sid in sel_series]
    if not subs:
        st.info("No price index series selected.")
    else:
        sub_df = df[df.series_id.isin(subs)].copy()
        name_map = {sid: SERIES[sid]["name"] for sid in subs}

        if show_yoy:
            yoy_parts = [add_yoy(df, sid) for sid in subs]
            cpi_y = pd.concat(yoy_parts, ignore_index=True)
            fig = px.line(cpi_y, x="date", y="YoY %", color="series_id", title="CPI — 12-month % change",
                          labels={"YoY %": "YoY %", "series_id": "Series"})
            fig.for_each_trace(lambda t: t.update(name=name_map.get(t.name, t.name)))
        else:
            fig = px.line(sub_df, x="date", y="value", color="series_id", title=name_map.get(subs[0], "CPI"),
                          labels={"value": "Index", "series_id": "Series"})
            fig.for_each_trace(lambda t: t.update(name=name_map.get(t.name, t.name)))

        st.plotly_chart(fig, use_container_width=True)

# ---------------- Compensation (ECI) ----------------
with eci_tab:
    subs = [sid for sid, meta in SERIES.items() if meta["section"] == "Compensation" and sid in sel_series]
    if not subs:
        st.info("No compensation series selected.")
    else:
        sub_df = df[df.series_id.isin(subs)].copy()
        name_map = {sid: SERIES[sid]["name"] for sid in subs}
        # ECI series is already 12m % change per BLS definition
        fig = px.line(sub_df, x="date", y="value", color="series_id", title="Employment Cost Index",
                      labels={"value": "%", "series_id": "Series"})
        fig.for_each_trace(lambda t: t.update(name=name_map.get(t.name, t.name)))
        st.plotly_chart(fig, use_container_width=True)

# ===========================================================
# Data Viewer (Optional, like a final tab in the CPS app)
# ===========================================================
st.markdown("---")
st.subheader("Data Preview")
st.dataframe(df.sort_values(["series_id", "date"]).tail(500), use_container_width=True, height=360)

st.caption(
    """
    **Series IDs used**: LNS12000000, CES0000000001, LNS14000000, CES0500000002, CES0500000003,
    PRS85006093, CUUR0000SA0, CIU1010000000000I.
    Quarterly points are placed at Mar/Jun/Sep/Dec. CPI series is NSA; others
    are noted above. For heavier use, provide a BLS API key to avoid rate limits.
    """
)

