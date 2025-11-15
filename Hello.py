# ===========================================================
# US Labor Dashboard — Exploration (v2)
# ===========================================================
# Jungmin Hwang
# -----------------------------------------------------------
# Features:
# - Correct BLS series IDs (PRS85006093, CIU1010000000000I)
# - Keeps quarterly data (M03/M06/M09/M12)
# - Fetches data from BLS API
# - Saves unified CSV for Streamlit dashboard
# - Visualizes Employment, Productivity, CPI, and ECI
# ===========================================================

import os
import json
import requests
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from pathlib import Path

# Plot settings
%matplotlib inline
plt.rcParams["figure.figsize"] = (11, 5)
plt.rcParams["axes.grid"] = True
pd.set_option("display.float_format", lambda x: f"{x:,.3f}")

START_YEAR = 2006
END_YEAR = datetime.utcnow().year
print("Pandas", pd.__version__, "| Years", START_YEAR, "→", END_YEAR)

# ===========================================================
# 1. BLS Series Configuration
# ===========================================================
SERIES = {
    # Employment (Monthly)
    "LNS12000000": {"section": "Employment", "name": "Civilian Employment (Thousands, SA)", "freq": "M"},
    "CES0000000001": {"section": "Employment", "name": "Total Nonfarm Employment (Thousands, SA)", "freq": "M"},
    "LNS14000000": {"section": "Employment", "name": "Unemployment Rate (% SA)", "freq": "M"},
    "CES0500000002": {"section": "Employment", "name": "Avg Weekly Hours, Total Private (SA)", "freq": "M"},
    "CES0500000003": {"section": "Employment", "name": "Avg Hourly Earnings, Total Private ($, SA)", "freq": "M"},

    # Productivity (Quarterly, SA)
    "PRS85006093": {"section": "Productivity", "name": "Output per Hour — Nonfarm Business (Q/Q %)", "freq": "Q"},

    # Price Index (Monthly, NSA)
    "CUUR0000SA0": {"section": "Price Index", "name": "CPI-U All Items (NSA, 1982–84=100)", "freq": "M"},

    # Compensation (Quarterly, NSA)
    "CIU1010000000000I": {"section": "Compensation", "name": "ECI — Total Compensation, Private Industry (12m % chg)", "freq": "Q"},
}

# ===========================================================
# 2. Fetch from BLS API
# ===========================================================
BLS_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"

class BLSError(Exception):
    pass

def fetch_bls_timeseries(series_ids, start_year, end_year):
    """Fetch data from BLS API for multiple series."""
    payload = {
        "seriesid": series_ids,
        "startyear": str(start_year),
        "endyear": str(end_year),
    }
    key = os.getenv("BLS_API_KEY")
    if key:
        payload["registrationkey"] = key

    r = requests.post(BLS_URL, json=payload, timeout=60)
    if r.status_code != 200:
        raise BLSError(f"HTTP {r.status_code}: {r.text[:200]}")
    data = r.json()
    if data.get("status") != "REQUEST_SUCCEEDED":
        raise BLSError(f"BLS API error: {json.dumps(data)[:300]}")
    return data


def series_payload_to_rows(series_json):
    """Flatten each BLS series JSON into rows of date, value."""
    sid = series_json["seriesID"]
    rows = []
    for item in series_json["data"]:
        p = item.get("period")
        if not p or p == "M13":
            continue  # drop annual averages
        if not p.startswith("M"):
            continue
        year = int(item["year"])
        month = int(p[1:])
        dt = pd.Timestamp(year=year, month=month, day=1)
        rows.append({
            "series_id": sid,
            "date": dt,
            "value": float(item["value"]),
        })
    return rows


# ===========================================================
# 3. Download & Save Unified Dataset
# ===========================================================
data_dir = Path("data")
data_dir.mkdir(parents=True, exist_ok=True)

print("Fetching data from BLS API...")
api = fetch_bls_timeseries(list(SERIES.keys()), START_YEAR, END_YEAR)
rows = []
for s in api["Results"]["series"]:
    rows.extend(series_payload_to_rows(s))

df = pd.DataFrame(rows).sort_values(["series_id", "date"]).reset_index(drop=True)
df.to_csv(data_dir / "bls_timeseries.csv", index=False)
print(f"✅ Saved {len(df)} rows to {data_dir / 'bls_timeseries.csv'}")

# Show data coverage summary
display(df.groupby("series_id")["date"].agg(["min", "max", "count"]))


# ===========================================================
# 4. Helper Functions
# ===========================================================
def plot_series(df_long, series_ids, title=None, ylabel=None, since=None):
    """Plot each series with Matplotlib."""
    sub = df_long[df_long.series_id.isin(series_ids)].copy()
    if since is not None:
        sub = sub[sub.date >= pd.to_datetime(since)]
    present = sorted(sub["series_id"].unique())
    missing = [sid for sid in series_ids if sid not in present]
    if missing:
        print("⚠️ No data for:", ", ".join(missing))
    for sid in present:
        name = SERIES.get(sid, {}).get("name", sid)
        d = sub[sub.series_id == sid]
        plt.figure()
        plt.plot(d["date"], d["value"], marker="o")
        plt.title(name if title is None else title)
        plt.xlabel("Date")
        plt.ylabel(ylabel or "Value")
        plt.show()


def yoy(df_long, sid):
    """Compute year-over-year percentage change."""
    d = df_long[df_long.series_id == sid].set_index("date").sort_index()[["value"]].copy()
    d["YoY %"] = d["value"].pct_change(12) * 100
    return d


# ===========================================================
# 5. Visualizations by Section
# ===========================================================

# --- Employment ---
employment_ids = ["LNS12000000", "CES0000000001", "LNS14000000", "CES0500000002", "CES0500000003"]
plot_series(df, employment_ids, title="Employment Indicators", since=f"{START_YEAR}-01-01")

# --- Productivity ---
plot_series(df, ["PRS85006093"], title="Output per Hour — Nonfarm Business (Q/Q %)", ylabel="Q/Q %", since=f"{START_YEAR}-01-01")

# --- Price Index (CPI) ---
plot_series(df, ["CUUR0000SA0"], title="CPI-U All Items (NSA, 1982–84=100)", ylabel="Index", since=f"{START_YEAR}-01-01")

cpi_y = yoy(df, "CUUR0000SA0")
plt.figure()
plt.plot(cpi_y.index, cpi_y["YoY %"])
plt.title("CPI-U — 12-month % change")
plt.xlabel("Date")
plt.ylabel("YoY %")
plt.show()

# --- Compensation (ECI) ---
plot_series(df, ["CIU1010000000000I"], title="Employment Cost Index (12m % chg)", ylabel="%", since=f"{START_YEAR}-01-01")

print("✅ All plots generated successfully!")
