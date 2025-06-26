import streamlit as st
import pandas as pd
import plotly.express as px
import requests

# set up page layout
st.set_page_config(page_title="OrganizeNYC", layout="wide")
st.title("🗳️ OrganizeNYC: live housing + civic data for ny-36")

# pulling live data from nyc apis
@st.cache_data
def load_live_data():
    # grab 311 housing complaints (filtered for heat issues)
    complaints_url = "https://data.cityofnewyork.us/resource/cewg-5fre.json?$limit=10000&$where=complaint_type like '%HEAT%'"
    df_311 = pd.read_json(complaints_url)
    df_311 = df_311[df_311['incident_zip'].notna()]
    complaints_by_zip = df_311.groupby("incident_zip").size().reset_index(name="Housing_Complaints")

    # grab eviction filings
    evictions_url = "https://data.cityofnewyork.us/resource/6z8x-wfk4.json?$limit=5000"
    df_evictions = pd.read_json(evictions_url)
    df_evictions = df_evictions[df_evictions['eviction_zip'].notna()]
    evictions_by_zip = df_evictions.groupby("eviction_zip").size().reset_index(name="Evictions")

    # merge the two datasets together by zip
    df = complaints_by_zip.merge(evictions_by_zip, left_on="incident_zip", right_on="eviction_zip", how="outer")
    df = df.rename(columns={"incident_zip": "ZIP"}).fillna(0)

    # add some mock info like turnout, campaign events, and lat/lon
    zip_meta = {
        "11101": [40.7440, -73.9485, 38.2, 1],
        "11102": [40.7760, -73.9235, 42.0, 0],
        "11103": [40.7531, -73.9137, 40.1, 2],
        "11104": [40.7450, -73.9191, 37.5, 1],
        "11105": [40.7789, -73.9105, 41.3, 3],
    }

    df["Latitude"] = df["ZIP"].map(lambda x: zip_meta.get(x, [None, None, None, None])[0])
    df["Longitude"] = df["ZIP"].map(lambda x: zip_meta.get(x, [None, None, None, None])[1])
    df["Turnout_Percent"] = df["ZIP"].map(lambda x: zip_meta.get(x, [None, None, None, None])[2])
    df["Campaign_Events"] = df["ZIP"].map(lambda x: zip_meta.get(x, [None, None, None, None])[3])

    # calculate a basic priority score
    df["Priority_Score"] = (
        df["Housing_Complaints"] * (1 - df["Turnout_Percent"] / 100)
    ) / (df["Campaign_Events"] + 1)

    return df.dropna()

df = load_live_data()

# show the raw data
st.subheader("📊 neighborhood data")
st.dataframe(df[["ZIP", "Housing_Complaints", "Evictions", "Turnout_Percent", "Campaign_Events", "Priority_Score"]])

# show it on a map
st.subheader("🗺️ heatmap")
fig = px.scatter_mapbox(
    df,
    lat="Latitude",
    lon="Longitude",
    color="Priority_Score",
    size="Housing_Complaints",
    hover_name="ZIP",
    mapbox_style="carto-positron",
    zoom=11,
    height=500
)
st.plotly_chart(fig, use_container_width=True)

# show top recommended zip codes
st.subheader("📍top areas to prioritize")
top_zips = df.sort_values("Priority_Score", ascending=False).head(3)
for _, row in top_zips.iterrows():
    st.markdown(f"- **ZIP {row['ZIP']}** → Priority Score: {row['Priority_Score']:.1f}")