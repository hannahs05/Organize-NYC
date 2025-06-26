import streamlit as st
import pandas as pd
import plotly.express as px
import requests

# layout setup
st.set_page_config(page_title="OrganizeNYC", layout="wide")
st.title("🗳️ OrganizeNYC: Citywide Housing + Civic Data")

# load and clean live data
@st.cache_data
def load_live_data():
    complaints_url = "https://data.cityofnewyork.us/resource/cewg-5fre.json?$limit=10000&$where=complaint_type%20like%20%27%25HEAT%25%27"
    evictions_url = "https://data.cityofnewyork.us/resource/6z8x-wfk4.json?$limit=5000"

    complaints_response = requests.get(complaints_url)
    evictions_response = requests.get(evictions_url)

    df_311 = pd.DataFrame(complaints_response.json())
    df_evictions = pd.DataFrame(evictions_response.json())

    # zip filter
    df_311 = df_311[df_311['incident_zip'].notna()]
    complaints_by_zip = df_311.groupby("incident_zip").size().reset_index(name="Housing_Complaints")

    df_evictions = df_evictions[df_evictions['eviction_zip'].notna()]
    evictions_by_zip = df_evictions.groupby("eviction_zip").size().reset_index(name="Evictions")

    df = complaints_by_zip.merge(evictions_by_zip, left_on="incident_zip", right_on="eviction_zip", how="outer")
    df = df.rename(columns={"incident_zip": "ZIP"}).fillna(0)

    # zip to lat/lon/turnout/events
    zip_meta = {
        "10001": [40.7506, -73.9972, 41.2, 2],
        "10002": [40.7170, -73.9870, 43.8, 0],
        "10025": [40.7968, -73.9707, 44.5, 1],
        "11211": [40.7081, -73.9571, 36.9, 2],
        "11221": [40.6906, -73.9272, 31.4, 1],
        "11368": [40.7473, -73.8726, 29.2, 0],
        "11385": [40.7037, -73.8893, 30.0, 1],
        "10451": [40.8198, -73.9223, 27.3, 0],
        "10467": [40.8732, -73.8674, 25.6, 0],
        "10301": [40.6300, -74.0942, 39.7, 0],
        "10314": [40.6066, -74.1456, 41.1, 1],
        "11101": [40.7440, -73.9485, 38.2, 1],
        "11103": [40.7531, -73.9137, 40.1, 2],
        "11105": [40.7789, -73.9105, 41.3, 3],
    }

    df["Latitude"] = df["ZIP"].map(lambda x: zip_meta.get(x, [None, None, None, None])[0])
    df["Longitude"] = df["ZIP"].map(lambda x: zip_meta.get(x, [None, None, None, None])[1])
    df["Turnout_Percent"] = df["ZIP"].map(lambda x: zip_meta.get(x, [None, None, None, None])[2])
    df["Campaign_Events"] = df["ZIP"].map(lambda x: zip_meta.get(x, [None, None, None, None])[3])

    df["Priority_Score"] = (
        df["Housing_Complaints"] * (1 - df["Turnout_Percent"] / 100)
    ) / (df["Campaign_Events"] + 1)

    return df.dropna()

# load borough info
@st.cache_data
def load_borough_map():
    return pd.read_csv("borough_zip.csv")

# run it
df = load_live_data()
borough_df = load_borough_map()
df = df.merge(borough_df, on="ZIP", how="left")

# borough filter
st.sidebar.subheader("📍 filter by borough")
boroughs = df["Borough"].dropna().unique().tolist()
selected_borough = st.sidebar.selectbox("Choose a borough", ["All"] + sorted(boroughs))

if selected_borough != "All":
    df = df[df["Borough"] == selected_borough]

# show table
st.subheader("📊 Neighborhood Data")
st.dataframe(df[["ZIP", "Borough", "Housing_Complaints", "Evictions", "Turnout_Percent", "Campaign_Events", "Priority_Score"]])

# show map
st.subheader("🗺️ Housing & Civic Heatmap")
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

# show recs
st.subheader("✅ Top Areas to Prioritize")
top_zips = df.sort_values("Priority_Score", ascending=False).head(3)
for _, row in top_zips.iterrows():
    st.markdown(f"- **ZIP {row['ZIP']}** → Priority Score: {row['Priority_Score']:.1f}")
