# organize-nyc app with zip-level choropleth + scorecard + filters
import streamlit as st
import pandas as pd
import plotly.express as px
import json
import requests

# set up page
st.set_page_config(page_title="OrganizeNYC", layout="wide")
st.title("🗳️ OrganizeNYC: Housing Distress & Civic Data in NYC")

st.markdown("""
This tool helps visualize areas in NYC with high housing complaints and low voter turnout.
I'm a fan of Zohran Mamdani’s work and wanted to build a public resource that could support grassroots organizing.
""")

# load housing complaint + eviction data from NYC open data
@st.cache_data
def load_data():
    complaints_url = "https://data.cityofnewyork.us/resource/cewg-5fre.json?$limit=10000&$where=complaint_type%20like%20%27%25HEAT%25%27"
    evictions_url = "https://data.cityofnewyork.us/resource/6z8x-wfk4.json?$limit=5000"

    complaints = pd.DataFrame(requests.get(complaints_url).json())
    evictions = pd.DataFrame(requests.get(evictions_url).json())

    complaints = complaints[complaints['incident_zip'].notna()]
    evictions = evictions[evictions['eviction_zip'].notna()]

    c_by_zip = complaints.groupby("incident_zip").size().reset_index(name="Housing_Complaints")
    e_by_zip = evictions.groupby("eviction_zip").size().reset_index(name="Evictions")

    df = pd.merge(c_by_zip, e_by_zip, left_on="incident_zip", right_on="eviction_zip", how="outer")
    df = df.rename(columns={"incident_zip": "ZIP"})
    df = df.drop(columns=["eviction_zip"])
    df = df.fillna(0)
    df["ZIP"] = df["ZIP"].astype(str).str.zfill(5)

    return df

# load zip-to-borough-turnout-event info
@st.cache_data
def load_zip_meta():
    # load csv of zip → borough + neighborhood
    df = pd.read_csv("nyc-zip-codes.csv")

    # make sure the zip code is a string + zero-padded to 5 digits
    df["ZIP"] = df["ZipCode"].astype(str).str.zfill(5)

    return df[["ZIP", "Borough", "Neighborhood"]]
    
# load geojson
@st.cache_data
def load_geojson():
    url = "https://raw.githubusercontent.com/OpenDataDE/State-zip-code-GeoJSON/main/ny_new_york_zip_codes_geo.min.json"
    return requests.get(url).json()

# pull data
df_data = load_data()
df_meta = load_zip_meta()
geojson = load_geojson()

# combine
df = pd.merge(df_data, df_meta, on="ZIP", how="left")
df = df.dropna(subset=["Borough"])
df["Turnout_Percent"] = df["Turnout_Percent"].astype(float)
df["Campaign_Events"] = df["Campaign_Events"].astype(int)

# priority score
df["Priority_Score"] = (
    df["Housing_Complaints"] * (1 - df["Turnout_Percent"] / 100)
) / (df["Campaign_Events"] + 1)

# filters
st.sidebar.subheader("Filter ZIPs")
boroughs = st.sidebar.multiselect("Borough", sorted(df["Borough"].unique()), default=list(df["Borough"].unique()))
min_turnout = st.sidebar.slider("Max Turnout %", 0, 100, 50)
show_top = st.sidebar.checkbox("Show only top 10 ZIPs", False)

filtered = df[df["Borough"].isin(boroughs)]
filtered = filtered[filtered["Turnout_Percent"] <= min_turnout]
if show_top:
    filtered = filtered.sort_values("Priority_Score", ascending=False).head(10)

# scorecard
st.subheader("📍ZIP-Level Scorecard")
st.dataframe(filtered[["ZIP", "Borough", "Housing_Complaints", "Evictions", "Turnout_Percent", "Campaign_Events", "Priority_Score"]].sort_values("Priority_Score", ascending=False))

# map
st.subheader("🗺️ Priority Heatmap by ZIP")
fig = px.choropleth_mapbox(
    filtered,
    geojson=geojson,
    locations="ZIP",
    color="Priority_Score",
    featureidkey="properties.ZCTA5CE10",
    mapbox_style="carto-positron",
    zoom=9,
    center={"lat": 40.7128, "lon": -74.0060},
    opacity=0.6,
    hover_data=["ZIP", "Housing_Complaints", "Evictions", "Turnout_Percent", "Campaign_Events"]
)
st.plotly_chart(fig, use_container_width=True)

# footer
st.markdown("---")
st.markdown("""
Built with ❤️ using [NYC Open Data](https://opendata.cityofnewyork.us/). Not affiliated with any official campaign.
""")
