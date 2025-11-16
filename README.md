# US Labor Dashboard (Econ 8320) — Revised

This project meets the rubric and your proposal:
- BLS API ingestion to CSV (not re-fetched on app load)
- Required series (Nonfarm, Unemployment) + additional sections
- Streamlit interactive dashboard with filters and recession shading
- GitHub Actions scheduled twice monthly to append new releases

## Local run
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python bls_update.py              # builds data/bls_timeseries.csv
streamlit run streamlit_app.py
```

## Deploy on Streamlit Community Cloud
- App file: `streamlit_app.py`
- Include `requirements.txt`
- Ensure `data/bls_timeseries.csv` exists in the repo (created by `bls_update.py`)

## Automation (GitHub Actions)
- Add secret `BLS_API_KEY` (optional) in repo settings
- Workflow `.github/workflows/update.yml` runs on the 5th and 15th (UTC)
