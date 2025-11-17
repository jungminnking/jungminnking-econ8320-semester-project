# streamlit_app.py — US Labor Dashboard (original data only; no derived series)
import pandas as pd
import streamlit as st
import plotly.express as px

# ───────────────────────────────────────────────────────────
# Page & Title
# ───────────────────────────────────────────────────────────
st.set_page_config(page_title="US Labor Dashboard", page_icon="📊", layout="wide")
st.title("US Labor Dashboard")
st.caption("BLS dashboard — original source data only (no derived series)")

# ───────────────────────────────────────────────────────────
# Simple data read (GitHub only)
# ───────────────────────────────────────────────────────────
CSV_URL = "https://github.com/jungminnking/jungminnking-econ8320-semester-project/raw/main/data/bls_timeseries.csv"

@st.cache_data(show_spinner=False)
def load_data(url: str) -> pd.DataFrame:
    df = pd.read_csv(url, parse_dates=["date"])
    df["series_id"] = df["series_id"].astype("string")
    return df

df_all = load_data(CSV_URL)

# Guard
if df_all.empty:
    st.error("The CSV loaded successfully but contains no rows.")
    st.stop()

# ───────────────────────────────────────────────────────────
# Series Catalog (must match your updater)
# ───────────────────────────────────────────────────────────
SERIES = {
    "LNS12000000": {"section": "Employment", "name": "Civilian Employment (Thousands, SA)", "freq": "M"},
    "CES0000000001": {"section": "Employment", "name": "Total Nonfarm Employment (Thousands, SA)", "freq": "M"},
    "LNS14000000": {"section": "Employment", "name": "Unemployment Rate (% SA)", "freq": "M"},
    "CES0500000002": {"section": "Employment", "name": "Avg Weekly Hours, Total Private (SA)", "freq": "M"},
    "CES0500000003": {"section": "Employment", "name": "Avg Hourly Earnings, Total Private ($, SA)", "freq": "M"},
    "PRS85006092": {"section": "Productivity", "name": "Output per Hour — Nonfarm Business (Q/Q %)", "freq": "Q"},
    "CUUR0000SA0": {"section": "Price Index", "name": "CPI-U All Items (NSA, 1982–84=100)", "freq": "M"},
    "CIU1010000000000A": {"section": "Compensation", "name": "ECI — Total Compensation, Private (12m % change, NSA)", "freq": "Q"},
}
SECTIONS = ["Employment", "Productivity", "Price Index", "Compensation"]

# ───────────────────────────────────────────────────────────
# Sidebar filters
# ───────────────────────────────────────────────────────────
section = st.sidebar.multiselect("Sections", SECTIONS, default=SECTIONS)
eligible = [sid for sid, meta in SERIES.items() if meta["section"] in section]

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
# Filter + coverage (original rows only)
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

# Optional: download filtered CSV (still original rows, just filtered)
st.download_button(
    "⬇️ Download filtered CSV",
    df.to_csv(index=False).encode("utf-8"),
    file_name="bls_timeseries_filtered.csv",
    mime="text/csv",
)

# ───────────────────────────────────────────────────────────
# Charts (tabs by section) — original series only
# ───────────────────────────────────────────────────────────
active_sections = section or SECTIONS
tabs = st.tabs(active_sections)
tab_by_section = dict(zip(active_sections, tabs))

for sec in active_sections:
    with tab_by_section[sec]:
        sub_ids = [sid for sid in pick if sid in SERIES and SERIES[sid]["section"] == sec]
        st.subheader(sec)

        if not sub_ids:
            st.info("No series selected for this section.")
            continue

        for sid in sub_ids:
            name = SERIES[sid]["name"]
            d = df[df.series_id == sid].sort_values("date")
            if d.empty:
                continue

            # Single chart per original series (no derived YoY/metrics)
            fig = px.line(
                d, x="date", y="value", title=name,
                labels={"value": "Value", "date": "Date"}
            )
            fig.update_traces(mode="lines+markers", hovertemplate="%{x|%Y-%m} — %{y:.2f}")
            st.plotly_chart(fig, use_container_width=True)

# ───────────────────────────────────────────────────────────
# Footer
# ───────────────────────────────────────────────────────────
st.write("---")
st.caption(f"Reading original source CSV from: {CSV_URL}")
