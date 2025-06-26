import streamlit as st
import pandas as pd
import plotly.express as px
import requests

# set up page layout
st.set_page_config(page_title="OrganizeNYC", layout="wide")
st.title("🗳️ OrganizeNYC: Live Housing + Civic Data for NYC")

# pull + merge live data with borough info
@st.cache_data
def load_data():
    # load zip to borough mapping
    borough_df = pd.read_csv("borough_zip.csv")

    # get 311 heat complaints
    complaints_url = "https://data.cityofnewyork.us/resource/cewg-5fre.json?$limit=50000&$where=complaint_type%20like%20%27%25HEAT%25%27"
    evictions_url = "https://data.cityofnewyork.us/resource/6z8x-wfk4.json?$limit=20000"

    complaints_response = requests.get(complaints_url)
    evictions_response = requests.get(evictions_url)

    df_311 = pd.DataFrame(complaints_response.json())
    df_evictions = pd.DataFrame(evictions_response.json())

    # process 311 data
    df_311 = df_311[df_311['incident_zip'].notna()]
    complaints_by_zip = df_311.groupby("incident_zip").size().reset_index(name="Housing_Complaints")

    # process evictions
    df_evictions = df_evictions[df_evictions['eviction_zip'].notna()]
    evictions_by_zip = df_evictions.groupby("eviction_zip").size().reset_index(name="Evictions")

    # merge datasets
    df = complaints_by_zip.merge(evictions_by_zip, left_on="incident_zip", right_on="eviction_zip", how="outer")
    df = df.rename(columns={"incident_zip": "ZIP"}).fillna(0)

    # bring in borough info
    df = df.merge(borough_df, on="ZIP", how="left")

    # mock lat/lon, turnout, events for demo zip codes
    zip_meta = {
        "11101": [40.7440, -73.9485, 38.2, 1],
        "11102": [40.7760, -73.9235, 42.0, 0],
        "11368": [40.7473, -73.8726, 34.5, 1],
        "11377": [40.7427, -73.9047, 36.8, 0],
        "11201": [40.6943, -73.9918, 43.1, 2],
        "11211": [40.7081, -73.9571, 35.6, 2],
        "10001": [40.7506, -73.9972, 39.0, 1],
        "10002": [40.7170, -73.9870, 41.4, 0],
        "10451": [40.8198, -73.9223, 31.2, 0],
        "10301": [40.6300, -74.0942, 47.5, 0]
    }

    df["Latitude"] = df["ZIP"].map(lambda x: zip_meta.get(x, [None, None, None, None])[0])
    df["Longitude"] = df["ZIP"].map(lambda x: zip_meta.get(x, [None, None, None, None])[1])
    df["Turnout_Percent"] = df["ZIP"].map(lambda x: zip_meta.get(x, [None, None, None, None])[2])
    df["Campaign_Events"] = df["ZIP"].map(lambda x: zip_meta.get(x, [None, None, None, None])[3])

    # score
    df["Priority_Score"] = (
        df["Housing_Complaints"] * (1 - df["Turnout_Percent"] / 100)
    ) / (df["Campaign_Events"] + 1)

    return df.dropna()

df = load_data()

# borough filter
boroughs = df["Borough"].dropna().unique()
selected = st.sidebar.selectbox("Filter by Borough", options=["All"] + sorted(boroughs.tolist()))

if selected != "All":
    df = df[df["Borough"] == selected]

# display data
st.subheader("📊 Neighborhood Data")
st.dataframe(df[["Borough", "ZIP", "Housing_Complaints", "Evictions", "Turnout_Percent", "Campaign_Events", "Priority_Score"]])

st.subheader("🗺️ Heatmap")
fig = px.scatter_mapbox(
    df,
    lat="Latitude",
    lon="Longitude",
    color="Priority_Score",
    size="Housing_Complaints",
    hover_name="ZIP",
    mapbox_style="carto-positron",
    zoom=10,
    height=500
)
st.plotly_chart(fig, use_container_width=True)

st.subheader("📍Top Areas to Prioritize")
top_zips = df.sort_values("Priority_Score", ascending=False).head(5)
for _, row in top_zips.iterrows():
    st.markdown(f"- **ZIP {row['ZIP']}** ({row['Borough']}) → Priority Score: {row['Priority_Score']:.1f}")
