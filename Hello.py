# %run "C:/Users/jungm/Documents/GitHub/jungminnking-econ8320-semester-project/Hello.py"
import os
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any
import requests
import pandas as pd
# API
BLS_URL: str = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
START_YEAR: int = 2006
END_YEAR: int = datetime.now(timezone.utc).year 

# Series
SERIES = [
    ("LNS12000000", "Employment", "Civilian Employment (Thousands, SA)", "M"),
    ("CES0000000001", "Employment", "Total Nonfarm Employment (Thousands, SA)", "M"),
    ("LNS14000000", "Employment", "Unemployment Rate (% SA)", "M"),
    ("CES0500000002", "Employment", "Avg Weekly Hours, Total Private (SA)", "M"),
    ("CES0500000003", "Employment", "Avg Hourly Earnings, Total Private ($, SA)", "M"),
    ("PRS85006092", "Productivity", "Output per Hour — Nonfarm Business (Q/Q %)", "Q"),
    ("CUUR0000SA0", "Price Index", "CPI-U All Items (NSA, Basis: 1982–84)", "M"),
    ("CIU1010000000000A", "Compensation", "ECI — Total Compensation, Private (12m % change, NSA)", "Q"),
]

# Path
REPO_DIR: Path = Path(r"C:/Users/jungm/Documents/GitHub/jungminnking-econ8320-semester-project")
DATA_DIR: Path = REPO_DIR / "data"
CSV_PATH: Path = DATA_DIR / "bls_timeseries.csv"
META_PATH: Path = DATA_DIR / "meta.json"
DATA_DIR.mkdir(parents=True, exist_ok=True)


# Fetching
def bls_timeseries(series_ids: List[str], start_year: int, end_year: int) -> Dict[str, Any]:
    """Fetch multiple BLS time series in one API call."""
    payload = {"seriesid": series_ids, "startyear": str(start_year), "endyear": str(end_year)}
    key = os.getenv("BLS_API_KEY")
    if key:
        payload["registrationkey"] = key
    r = requests.post(BLS_URL, json=payload, timeout=60)
    r.raise_for_status() 
    data = r.json()
    if data.get("status") != "REQUEST_SUCCEEDED":
        raise RuntimeError(f"BLS API error: {json.dumps(data)[:300]}")
    return data

# Parsing 
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

# CSV loading 
def load_existing() -> pd.DataFrame:
    if CSV_PATH.exists():
        return pd.read_csv(CSV_PATH, parse_dates=["date"])
    return pd.DataFrame(columns=["series_id", "date", "value"])

def union_and_dedupe(df_old: pd.DataFrame, df_new: pd.DataFrame) -> pd.DataFrame:
    df = pd.concat([df_old, df_new], ignore_index=True)
    df = df.drop_duplicates(subset=["series_id", "date"], keep="last")
    return df.sort_values(["series_id", "date"]).reset_index(drop=True)

# Main
def run_full_or_incremental() -> pd.DataFrame:
    df_old = load_existing()
    series_ids = [sid for sid, *_ in SERIES]
    api = bls_timeseries(series_ids, START_YEAR, END_YEAR)
    rows = [r for s in api["Results"]["series"] for r in series_payload_to_rows(s)]
    df_new = pd.DataFrame(rows)
    df_out = union_and_dedupe(df_old, df_new)
    allowed = set(series_ids)
    df_out = df_out[df_out["series_id"].isin(allowed)].sort_values(["series_id", "date"]).reset_index(drop=True)
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    df_out.to_csv(CSV_PATH, index=False)
    META_PATH.write_text(json.dumps({"last_updated_utc": datetime.now(timezone.utc).isoformat()}, indent=2))
    return df_out
if __name__ == "__main__":
    df_out = run_full_or_incremental()

    print(f"✅ Saved {len(df_out):,} rows to {CSV_PATH.resolve()}")
    print("\nCoverage:")