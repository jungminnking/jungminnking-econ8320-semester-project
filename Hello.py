# Copyright (c) Streamlit Inc. (2018-2022) Snowflake Inc. (2022)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# ================================================================
# US Labor Statistics Dashboard — Jungmin Hwang (Semester Project)
# ================================================================

import os
from pathlib import Path
from datetime import datetime
import pandas as pd
import streamlit as st
import plotly.express as px
from streamlit.logger import get_logger

LOGGER = get_logger(__name__)

# -----------------------------
# Data file configuration
# -----------------------------
DATA_PATH = Path("data") / "bls_timeseries.csv"
META_PATH = Path("data") / "_meta.txt"

# -----------------------------
# BLS Series Configuration
# -----------------------------
SERIES = {
    # Employment (Monthly, SA)
    "LNS12000000": {"section": "Employment", "name": "Civilian Employment (Thousands, SA)", "freq": "M"},
    "CES0000000001": {"section": "Employment", "name": "Total Nonfarm Employment (Thousands, SA)", "freq": "M"},
    "LNS14000000": {"section": "Employment", "name": "Unemployment Rate (% SA)", "freq": "M"},
    "CES0500000002": {"section": "Employment", "name": "Avg Weekly Hours, Total Private (SA)", "freq": "M"},
    "CES0500000003": {"section": "Employment", "name": "Avg Hourly Earnings, Total Private ($, SA)", "freq": "M"},

    # Productivity (Quarterly)
    # Corrected ID (previously PRS85006092 -> PRS85006093)
    "PRS85006093": {"section": "Productivity", "name": "Output per Hour — Nonfarm Business Productivity (Q/Q %)", "freq": "Q"},

    # Price Index (Monthly, NSA)
    "CUUR0000SA0": {"section": "Price Index", "name": "CPI-U All Items (NSA, 1982–84=100)", "freq": "M"},

    # Compensation (Quarterly, NSA)
    # Corrected ID (previously CIU1010000000000A -> CIU1010000000000I)
    "CIU1010000000000I": {"section": "Compensation", "name": "Employment Cost Index — Total Compensation, Private Industry (12m % chg)", "freq": "Q"},
}

SECTIONS = ["Employment", "Productivity", "Price Index", "Compensation"]


# -----------------------------
# Helper functions
# -----------------------------
@st.cache_data
def load_data() -> pd.DataFrame:
    """Load pre-collected dataset."""
    if not DATA_PATH.exists():
        return pd.DataFrame(columns=["series_id", "date", "value", "footnotes"])
    df = pd.read_csv(DATA_PATH, parse_dates=["date"])
    df = df[df["series_id"].isin(SERIES.keys())]
    return df

@st.cache_data
def load_meta() -> dict:
    """Read metadata from _meta.txt."""
    meta = {"last_updated_utc": "unknown"}
    if META_PATH.exists():
        with open(META_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line:
                    k, v = line.strip().split("=", 1)
                    meta[k] = v
    return meta

def kpi(df: pd.DataFrame, sid: str, label: str, fmt: str):
    """Display KPI metric for latest vs previous period."""
    s = df[df.series_id == sid].sort_values("date")
    if s.empty:
        st.metric(label, "—")
        return
    last = s.iloc[-1]
    prev = s.iloc[-2] if len(s) > 1 else None
    delta = (last.value - prev.value) if prev is not None else None
    st.metric(label, fmt.format(last.value), None if delta is None else fmt.format(delta))

def plot_lines(df: pd.DataFrame, sids: list[str], title: str, ylab: str = None, years_back: int = 5):
    """Plot multiple time series lines."""
    if df.empty or not sids:
        st.info("No data to plot yet.")
        return
    min_date = pd.Timestamp.today() - pd.DateOffset(years=years_back)
    dfp = df[df.series_id.isin(sids)].copy()
    dfp = dfp[dfp["date"] >= min_date]
    dfp["series_name"] = dfp.series_id.map(lambda x: SERIES.get(x, {}).get("name", x))

    fig = px.line(dfp, x="date", y="value", color="series_name", markers=False, title=title)
    if ylab:
        fig.update_yaxes(title_text=ylab)
    fig.update_layout(height=480, legend_title_text="Series")
    st.plotly_chart(fig, use_container_width=True)


# -----------------------------
# Streamlit app
# -----------------------------
def run():
    st.set_page_config(page_title="US Labor Statistics Dashboard", page_icon="📊", layout="wide")
    st.title("US Labor Statistics Dashboard — U.S. Bureau of Labor Statistics")

    st.sidebar.success("Use the tabs to explore data.")
    st.sidebar.caption("Data source: BLS Public API • Updates monthly via GitHub Actions")

    df = load_data()
    meta = load_meta()

    st.caption(f"**Last dataset update (UTC):** {meta.get('last_updated_utc', 'unknown')}")

    if df.empty:
        st.warning("⚠️ No dataset found. Run `python src/update_dataset.py` or trigger GitHub Action to create `data/bls_timeseries.csv`.")
        st.stop()

    # -----------------------------
    # Headline KPIs (Employment)
    # -----------------------------
    st.subheader("Key Employment Indicators")
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1: kpi(df, "CES0000000001", "Nonfarm Payrolls (k)", "{:,.0f}")
    with col2: kpi(df, "LNS14000000", "Unemployment Rate (%)", "{:.1f}")
    with col3: kpi(df, "LNS12000000", "Civilian Employment (k)", "{:,.0f}")
    with col4: kpi(df, "CES0500000002", "Avg Weekly Hours", "{:.1f}")
    with col5: kpi(df, "CES0500000003", "Avg Hourly Earnings ($)", "{:.2f}")

    # Tabs by section
    tabs = st.tabs(SECTIONS)

    # Employment
    with tabs[0]:
        st.subheader("Employment Trends")
        years = st.slider("Show last N years", 1, 15, 5, key="years_emp")
        sids = ["LNS12000000", "CES0000000001", "LNS14000000", "CES0500000002", "CES0500000003"]
        plot_lines(df, sids, "Employment Indicators", years_back=years)

    # Productivity
    with tabs[1]:
        st.subheader("Productivity (Quarterly)")
        years = st.slider("Show last N years", 1, 15, 10, key="years_prod")
        plot_lines(df, ["PRS85006093"], "Output per Hour — Nonfarm Business (Q/Q %)", "Q/Q %", years_back=years)

    # Price Index
    with tabs[2]:
        st.subheader("Price Index — CPI-U")
        years = st.slider("Show last N years", 1, 20, 10, key="years_cpi")
        plot_lines(df, ["CUUR0000SA0"], "CPI-U All Items (NSA, 1982–84=100)", "Index", years_back=years)

        cpi = df[df.series_id == "CUUR0000SA0"].set_index("date").sort_index()
        cpi["YoY %"] = cpi["value"].pct_change(12) * 100
        cpi = cpi.reset_index()
        cpi = cpi[cpi["date"] >= (pd.Timestamp.today() - pd.DateOffset(years=years))]
        fig = px.line(cpi, x="date", y="YoY %", title="CPI-U — 12-Month % Change")
        st.plotly_chart(fig, use_container_width=True)

    # Compensation
    with tabs[3]:
        st.subheader("Compensation (ECI)")
        years = st.slider("Show last N years", 1, 20, 10, key="years_eci")
        plot_lines(df, ["CIU1010000000000I"], "Employment Cost Index — Total Compensation (12m % chg)", "%", years_back=years)

    st.caption("Built with Streamlit • Data via BLS API • Updated automatically once per month.")

# -----------------------------
# Entrypoint
# -----------------------------
if __name__ == "__main__":
    run()
