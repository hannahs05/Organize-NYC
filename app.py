import streamlit as st
import pandas as pd
import plotly.express as px
import requests

# set up the layout
st.set_page_config(page_title="OrganizeNYC", layout="wide")
st.title("OrganizeNYC: Citywide Housing + Civic Data")

# load borough data from the local csv
@st.cache_data
def load_borough_map():
    df = pd.read_csv("nyc-zip-codes.csv")
    df["ZipCode"] = df["ZipCode"].astype(str).str.zfill(5)
    return df.rename(columns={"ZipCode": "ZIP"})

# pull and process live housing + eviction data
@st.cache_data
def load_live_data():
    # 311 complaints api (filtering for heat complaints as proxy for housing issues)
    complaints_url = "https://data.cityofnewyork.us/resource/cewg-5fre.json?$limit=10000&$where=complaint_type%20like%20%27%25HEAT%25%27"
    evictions_url = "https://data.cityofnewyork.us/resource/6z8x-wfk4.json?$limit=5000"

    complaints_resp = requests.get(complaints_url)
    evictions_resp = requests.get(evictions_url)

    df_311 = pd.DataFrame(complaints_resp.json())
    df_evictions = pd.DataFrame(evictions_resp.json())

    df_311 = df_311[df_311['incident_zip'].notna()]
    df_evictions = df_evictions[df_evictions['eviction_zip'].notna()]

    complaints_by_zip = df_311.groupby("incident_zip").size().reset_index(name="Housing_Complaints")
    evictions_by_zip = df_evictions.groupby("eviction_zip").size().reset_index(name="Evictions")

    df = complaints_by_zip.merge(evictions_by_zip, left_on="incident_zip", right_on="eviction_zip", how="outer")
    df = df.rename(columns={"incident_zip": "ZIP"}).fillna(0)

    # mock values for turnout and campaign events
    df["ZIP"] = df["ZIP"].astype(str).str.zfill(5)
    df["Turnout_Percent"] = 35 + (df.index % 15)
    df["Campaign_Events"] = df.index % 4

    df["Priority_Score"] = (df["Housing_Complaints"] * (1 - df["Turnout_Percent"] / 100)) / (df["Campaign_Events"] + 1)

    return df

# load and merge all data
df_main = load_live_data()
borough_df = load_borough_map()
df = df_main.merge(borough_df[["ZIP", "Borough"]], on="ZIP", how="left")

# sidebar filter
st.sidebar.markdown("📍 **filter by borough**")
boroughs = ["All"] + sorted(df["Borough"].dropna().unique())
selected_borough = st.sidebar.selectbox("Choose a borough", boroughs)

if selected_borough != "All":
    df = df[df["Borough"] == selected_borough]

# show data
st.subheader("📊 Neighborhood Data")
st.dataframe(df[["ZIP", "Borough", "Housing_Complaints", "Evictions", "Turnout_Percent", "Campaign_Events", "Priority_Score"]])

# placeholder coordinates for map
df["Latitude"] = 40.7 + (df.index % 10) * 0.01
df["Longitude"] = -73.9 + (df.index % 10) * 0.01

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

# top zip codes to focus on
st.subheader("📌 Top Areas to Prioritize")
top_zips = df.sort_values("Priority_Score", ascending=False).head(3)
for _, row in top_zips.iterrows():
    st.markdown(f"- **ZIP {row['ZIP']} ({row['Borough']})** → Priority Score: {row['Priority_Score']:.1f}")
