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

import streamlit as st
from streamlit.logger import get_logger

LOGGER = get_logger(__name__)


def run():
    st.set_page_config(
        page_title="Hello",
        page_icon="👋",
    )

    st.write("# Welcome to Streamlit! 👋")

    st.sidebar.success("Select a demo above.")

    st.markdown(
        """
        Streamlit is an open-source app framework built specifically for
        Machine Learning and Data Science projects.
        **👈 Select a demo from the sidebar** to see some examples
        of what Streamlit can do!
        ### Want to learn more?
        - Check out [streamlit.io](https://streamlit.io)
        - Jump into our [documentation](https://docs.streamlit.io)
        - Ask a question in our [community
          forums](https://discuss.streamlit.io)
        ### See more complex demos
        - Use a neural net to [analyze the Udacity Self-driving Car Image
          Dataset](https://github.com/streamlit/demo-self-driving)
        - Explore a [New York City rideshare dataset](https://github.com/streamlit/demo-uber-nyc-pickups)
    """
    )


if __name__ == "__main__":
    run()




import pandas as pd
import requests
import matplotlib.pyplot as plt
from datetime import datetime
from pathlib import Path

%matplotlib inline
plt.rcParams['figure.figsize'] = (10, 5)
plt.rcParams['axes.grid'] = True
print('Pandas:', pd.__version__)

def series_to_frame(series_payload):
    rows = []
    sid = series_payload["seriesID"]
    for item in series_payload["data"]:
        period = item.get("period")
        if not period or not period.startswith('M') or period == 'M13':
            continue
        year = int(item["year"]) 
        month = int(period[1:])
        date = pd.Timestamp(year=year, month=month, day=1)
        value = float(item["value"])
        rows.append({"series_id": sid, "date": date, "value": value})
    return pd.DataFrame(rows).sort_values("date")

# Take the first series from the API result and preview
first_series = api["Results"]["series"][0]
df_test = series_to_frame(first_series)
df_test.head()


plt.figure()
plt.plot(df_test['date'], df_test['value'], marker='o')
plt.title(f"{df_test['series_id'].iloc[0]} — sample from BLS API")
plt.xlabel('Date')
plt.ylabel('Value')
plt.show()

def fetch_census_data(year, month):
    url = "https://api.census.gov/data/"
    
    https://api.bls.gov/publicAPI/v2/timeseries/data/

    year_inp = f"{year}/"
    data_set = "cps/basic/"
    month_inp = f"{month}"
    info_grab = "?get=CBSA,PEERNLAB,HEFAMINC,HETENURE,HRHTYPE,PEEDUCA,PRFTLF,PTERNH1O"
    full_url = url + year_inp + data_set + month_inp + info_grab
    response = requests.get(full_url)
    print(full_url)
    if response.status_code == 200:
        data = response.json()
        if data:
            columns = data[0]
            rows = data[1:]
            df = pd.DataFrame(rows, columns=columns)
            df['Year'] = year
            df['Month'] = month

            # Drop rows with missing values in the 'CBSA' column
            df = df.dropna(subset=['CBSA'])

            # Convert 'CBSA' column to float
            df = df[df['CBSA'].astype(str).str.strip().replace('', '0').astype(float) > 10000]

            # Map CBSA codes to metro area names
            df["Metro Area"] = df["CBSA"].map(metro_area_mapping)

            # Rename 'CBSA' column to 'GTCBSA'
            df.rename(columns={'CBSA': 'GTCBSA'}, inplace=True)
            df['PTERNH1O'] = pd.to_numeric(df['PTERNH1O'], errors='coerce')
            df = df[df["PEERNLAB"] != -1]
            df = df[df["PTERNH1O"].between(0.0, 99.99)]  # Filtering within the specified range
            return df
        else:
            print("No data found for", year, month)
            return None
    else:
        print("Failed to fetch data for", year, month)
        return None

def update_data(csv_path):
    latest_year = 0
    latest_month = 0
#check the csv for the latest month and year
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path)
        latest_year = df['Year'].max()
        latest_month = df[df['Year'] == latest_year]['Month'].max()

    print("Latest Year:", latest_year)
    print("Latest Month:", latest_month)
#pull current month and year
    now = datetime.now()
    current_year = now.year
    current_month = now.strftime("%b").lower()
#compare csv month and year with latest month and year
    for year in range(latest_year, current_year + 1):
        start_month = latest_month if year == latest_year else "jan"
        end_month = current_month if year == current_year else "dec"
        for month in get_months(start_month, end_month):
            df = fetch_census_data(year, month)
            if df is not None: #if the check pulled a year and month then proceed
                with open(csv_path, 'a') as f:
                    df.to_csv(f, header=f.tell()==0, index=False)
                print(f"Data for {year}-{month} fetched and CSV updated successfully!")
            else:
                print(f"Failed to fetch data for {year}-{month}")

def get_months(start_month, end_month):
    months = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
    start_index = months.index(start_month)
    end_index = months.index(end_month)
    return months[start_index:end_index+1]

def main():
    csv_path = "CENSUS_CPS_DATA.csv"
    update_data(csv_path)

if __name__ == "__main__":
    main()


{
   "status":"REQUEST_SUCCEEDED",
   "responseTime":253,
   "message":[],
   "Results": {
      "series": [
         {
            "seriesID":"LAUCN040010000000005",
            "data":[
             {
                "year": "2013",
                "period": "M11",
                "periodName": "November",
                "latest": "true",
                "value": "16393",
                "footnotes": [
                   {
                     "code": "P",
                     "text": "Preliminary."
                   }
                ]
            }]
      ]
   }
}
    