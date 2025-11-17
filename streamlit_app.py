# streamlit_app.py — Simplified US Labor Dashboard (tabs only, no section/series pickers)
import pandas as pd
import streamlit as st
import plotly.express as px

# ───────────────────────────────────────────────────────────
# Page & Title
# ───────────────────────────────────────────────────────────
st.set_page_config(page_title="US Labor Dashboard", page_icon="📊", layout="wide")
st.title("US Labor Dashboard")
st.caption("BLS dashboard — original source data only (tabs by section)")

# ───────────────────────────────────────────────────────────
# Load CSV directly from GitHub
# ───────────────────────────────────────────────────────────
CSV_URL = "https://github.com/jungminnking/jungminnking-econ8320-semester-project/raw/main/data/bls_timeseries.csv"

@st.cache_data(show_spinner=False)
def load_data(url: str) -> pd.DataFrame:
    df = pd.read_csv(url, parse_dates=["date"])
    df["series_id"] = df["series_id"].astype("string")
    return df

df_all = load_data(CSV_URL)

if df_all.empty:
    st.error("The CSV loaded successfully but contains no rows.")
    st.stop()

# ───────────────────────────────────────────────────────────
# Series Catalog (matches your repo)
# ───────────────────────────────────────────────────────────
SERIES = {
    "LNS12000000": {"section": "Employment", "name": "Civilian Employment (Thousands, SA)"},
    "CES0000000001": {"section": "Employment", "name": "Total Nonfarm Employment (Thousands, SA)"},
    "LNS14000000": {"section": "Employment", "name": "Unemployment Rate (% SA)"},
    "CES0500000002": {"section": "Employment", "name": "Avg Weekly Hours, Total Private (SA)"},
    "CES0500000003": {"section": "Employment", "name": "Avg Hourly Earnings, Total Private ($, SA)"},
    "PRS85006092": {"section": "Productivity", "name": "Output per Hour — Nonfarm Business (Q/Q %)"},
    "CUUR0000SA0": {"section": "Price Index", "name": "CPI-U All Items (NSA, 1982–84=100)"},
    "CIU1010000000000A": {"section": "Compensation", "name": "ECI — Total Compensation, Private (12m % change, NSA)"},
}
SECTIONS = ["Employment", "Productivity", "Price Index", "Compensation"]

# ───────────────────────────────────────────────────────────
# Sidebar — only year range filter
# ───────────────────────────────────────────────────────────
min_year = int(df_all["date"].dt.year.min())
max_year = int(df_all["date"].dt.year.max())

year_min, year_max = st.sidebar.slider(
    "Year range", min_value=min_year, max_value=max_year, value=(min_year, max_year)
)

# ───────────────────────────────────────────────────────────
# Filter data
# ───────────────────────────────────────────────────────────
df = df_all[(df_all["date"].dt.year >= year_min) & (df_all["date"].dt.year <= year_max)]

st.subheader("Data coverage")
coverage = (
    df.groupby("series_id")["date"]
    .agg(["min", "max", "count"])
    .rename_axis("series_id")
    .reset_index()
)
coverage["series_name"] = coverage["series_id"].map(lambda sid: SERIES.get(sid, {}).get("name", sid))
st.caption(f"Rows: {len(df):,} • Min date: {df['date'].min().date()} • Max date: {df['date'].max().date()}")
st.dataframe(coverage[["series_id", "series_name", "min", "max", "count"]], use_container_width=True)

# Download filtered CSV
st.download_button(
    "⬇️ Download filtered CSV",
    df.to_csv(index=False).encode("utf-8"),
    file_name="bls_timeseries_filtered.csv",
    mime="text/csv",
)

# ───────────────────────────────────────────────────────────
# Charts in tabs (one tab per section)
# ───────────────────────────────────────────────────────────
tabs = st.tabs(SECTIONS)

for sec, tab in zip(SECTIONS, tabs):
    with tab:
        st.subheader(sec)
        sub_ids = [sid for sid, meta in SERIES.items() if meta["section"] == sec]

        for sid in sub_ids:
            name = SERIES[sid]["name"]
            d = df[df.series_id == sid].sort_values("date")
            if d.empty:
                continue

            fig = px.line(d, x="date", y="value", title=name, labels={"value": "Value", "date": "Date"})
            fig.update_traces(mode="lines+markers", hovertemplate="%{x|%Y-%m} — %{y:.2f}")
            st.plotly_chart(fig, use_container_width=True)

# ───────────────────────────────────────────────────────────
# Footer
# ───────────────────────────────────────────────────────────
st.write("---")
st.caption(f"Reading data directly from: {CSV_URL}")

