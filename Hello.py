# %run "C:/Users/jungm/Documents/GitHub/jungminnking-econ8320-semester-project/Hello.py"
# Hello.py — Fetch BLS time series and save into your GitHub repo's /data folder

import os
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any

import requests
import pandas as pd

# ===========================================================
# 1) CONFIG — API, years, and series list
# ===========================================================
BLS_URL: str = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
START_YEAR: int = 2006
END_YEAR: int = datetime.now(timezone.utc).year  # current year

# Series: (ID, section, name, frequency)
SERIES = [
    ("LNS12000000", "Employment", "Civilian Employment (Thousands, SA)", "M"),
    ("CES0000000001", "Employment", "Total Nonfarm Employment (Thousands, SA)", "M"),
    ("LNS14000000", "Employment", "Unemployment Rate (% SA)", "M"),
    ("CES0500000002", "Employment", "Avg Weekly Hours, Total Private (SA)", "M"),
    ("CES0500000003", "Employment", "Avg Hourly Earnings, Total Private ($, SA)", "M"),
    ("PRS85006092", "Productivity", "Output per Hour — Nonfarm Business (Q/Q %)", "Q"),
    ("CUUR0000SA0", "Price Index", "CPI-U All Items (NSA, 1982–84=100)", "M"),
    ("CIU1010000000000A", "Compensation", "ECI — Total Compensation, Private (12m % change, NSA)", "Q"),
]

# ===========================================================
# 2) PATHS — point to your local GitHub repo folder
# ===========================================================
# ⚠️ Replace this path with where your repo is cloned locally.
# The repo link (https://github.com/...) itself is just the remote.
REPO_DIR: Path = Path(r"C:/Users/jungm/Documents/GitHub/jungminnking-econ8320-semester-project")
DATA_DIR: Path = REPO_DIR / "data"
CSV_PATH: Path = DATA_DIR / "bls_timeseries.csv"
META_PATH: Path = DATA_DIR / "meta.json"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ===========================================================
# 3) ERROR CLASS
# ===========================================================
class BLSError(Exception):
    """Raised for HTTP or logical errors from the BLS API."""
    pass

# ===========================================================
# 4) API FETCH FUNCTION
# ===========================================================
def bls_timeseries(series_ids: List[str], start_year: int, end_year: int) -> Dict[str, Any]:
    """Fetch multiple BLS time series in one API call."""
    payload = {"seriesid": series_ids, "startyear": str(start_year), "endyear": str(end_year)}
    key = os.getenv("BLS_API_KEY")
    if key:
        payload["registrationkey"] = key
    r = requests.post(BLS_URL, json=payload, timeout=60)
    if r.status_code != 200:
        raise BLSError(f"HTTP {r.status_code}: {r.text[:200]}")
    data = r.json()
    if data.get("status") != "REQUEST_SUCCEEDED":
        raise BLSError(f"BLS error: {json.dumps(data)[:300]}")
    return data

# ===========================================================
# 5) PARSING FUNCTIONS
# ===========================================================
def _q_to_month(q: int) -> int:
    """Map quarter number to representative month."""
    return {1: 3, 2: 6, 3: 9, 4: 12}[q]

def series_payload_to_rows(series_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Convert one series’ JSON to tidy rows."""
    sid = series_json["seriesID"]
    rows = []
    for item in series_json.get("data", []):
        period = item.get("period")
        if not period or period == "M13":
            continue
        year = int(item["year"])
        if period.startswith("M"):
            month = int(period[1:])
        elif period.startswith("Q"):
            month = _q_to_month(int(period[1:]))
        else:
            continue
        dt = pd.Timestamp(year=year, month=month, day=1)
        val = float(item["value"])
        rows.append({"series_id": sid, "date": dt, "value": val})
    return rows

# ===========================================================
# 6) CSV LOAD + MERGE
# ===========================================================
def load_existing() -> pd.DataFrame:
    """Load existing CSV (if any)."""
    if CSV_PATH.exists():
        return pd.read_csv(CSV_PATH, parse_dates=["date"])
    return pd.DataFrame(columns=["series_id", "date", "value"])

def union_and_dedupe(df_old: pd.DataFrame, df_new: pd.DataFrame) -> pd.DataFrame:
    """Combine old + new, drop duplicates by (series_id, date)."""
    df = pd.concat([df_old, df_new], ignore_index=True)
    df = df.drop_duplicates(subset=["series_id", "date"], keep="last")
    return df.sort_values(["series_id", "date"]).reset_index(drop=True)

# ===========================================================
# 7) MAIN FUNCTION
# ===========================================================
def run_full_or_incremental() -> pd.DataFrame:
    """Fetch BLS data and save to your GitHub repo’s data folder."""
    df_old = load_existing()
    if df_old.empty:
        start = START_YEAR
    else:
        last_date = df_old["date"].max()
        start = max(START_YEAR, (last_date - pd.DateOffset(months=24)).year)

    series_ids = [sid for sid, *_ in SERIES]
    api = bls_timeseries(series_ids, start, END_YEAR)
    rows = [r for s in api["Results"]["series"] for r in series_payload_to_rows(s)]
    df_new = pd.DataFrame(rows)
    df_out = union_and_dedupe(df_old, df_new)

    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    df_out.to_csv(CSV_PATH, index=False)
    META_PATH.write_text(json.dumps({"last_updated_utc": datetime.now(timezone.utc).isoformat()}, indent=2))

    print(f"✅ Saved {len(df_out):,} rows to {CSV_PATH.resolve()}")
    print("\nCoverage:")
    print(df_out.groupby("series_id")["date"].agg(["min", "max", "count"]))
    print("\nNext steps:")
    print(f"  cd \"{REPO_DIR}\"")
    print("  git add data/bls_timeseries.csv data/meta.json")
    print("  git commit -m \"Update BLS data\"")
    print("  git push")
    return df_out

# ===========================================================
# 8) ENTRY POINT
# ===========================================================
if __name__ == "__main__":
    run_full_or_incremental()
