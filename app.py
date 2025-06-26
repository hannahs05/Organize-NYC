import streamlit as st
import pandas as pd
import plotly.express as px
import requests

# set up page layout
st.set_page_config(page_title="OrganizeNYC", layout="wide")
st.title("📦 OrganizeNYC: citywide housing + civic data")

# load the zip to borough mapping live from nyc api
@st.cache_data
def load_borough_map():
    url = "https://data.cityofnewyork.us/resource/jp4d-irnc.json?$select=zip,boro"
    r = requests.get(url)
    records = r.json()

    df = pd.DataFrame(records)

    # log column names so we know what we're working with
    st.write("borough df columns:", df.columns.tolist())

    # make sure all lowercase
    df.columns = df.columns.str.lower()

    # rename to match merge expectations
    df = df.rename(columns={"zip": "ZIP", "boro": "Borough"})
    df["ZIP"] = df["ZIP"].astype(str).str.zfill(5)
    df["Borough"] = df["Borough"].map({
        "X": "Bronx", "M": "Manhattan", "K": "Brooklyn", "Q": "Queens", "R": "Staten Island"
    })

    return df.dropna()

# pull housing + eviction data live from nyc apis
@st.cache_data
def load_live_data():
    complaints_url = "https://data.cityofnewyork.us/resource/cewg-5fre.json?$limit=10000&$where=complaint_type%20like%20%27%25HEAT%25%27"
    evictions_url = "https://data.cityofnewyork.us/resource/6z8x-wfk4.json?$limit=5000"

    complaints = requests.get(complaints_url).json()
    evictions = requests.get(evictions_url).json()

    df_311 = pd.DataFrame(complaints)
    df_evictions = pd.DataFrame(evictions)

    df_311 = df_311[df_311['incident_zip'].notna()]
    complaints_by_zip = df_311.groupby("incident_zip").size().reset_index(name="Housing_Complaints")

    df_evictions = df_evictions[df_evictions['eviction_zip'].notna()]
    evictions_by_zip = df_evictions.groupby("eviction_zip").size().reset_index(name="Evictions")

    df = complaints_by_zip.merge(evictions_by_zip, left_on="incident_zip", right_on="eviction_zip", how="outer")
    df = df.rename(columns={"incident_zip": "ZIP"}).fillna(0)
    df["ZIP"] = df["ZIP"].astype(str)

    # mock turnout + events for now
    zip_meta = {
        "11101": [40.7440, -73.9485, 38.2, 1],
        "11102": [40.7760, -73.9235, 42.0, 0],
        "11103": [40.7531, -73.9137, 40.1, 2],
        "11104": [40.7450, -73.9191, 37.5, 1],
        "11105": [40.7789, -73.9105, 41.3, 3],
        "10451": [40.8198, -73.9222, 27.3, 0],
        "10467": [40.8702, -73.8663, 25.6, 0],
        "11211": [40.7099, -73.9543, 36.9, 2],
        "11221": [40.6911, -73.9272, 31.4, 1],
        "11368": [40.7498, -73.8625, 29.2, 0],
    }

    df["Latitude"] = df["ZIP"].map(lambda x: zip_meta.get(x, [None])[0])
    df["Longitude"] = df["ZIP"].map(lambda x: zip_meta.get(x, [None, None])[1])
    df["Turnout_Percent"] = df["ZIP"].map(lambda x: zip_meta.get(x, [None, None, None])[2])
    df["Campaign_Events"] = df["ZIP"].map(lambda x: zip_meta.get(x, [None, None, None, None])[3])

    df["Priority_Score"] = (
        df["Housing_Complaints"] * (1 - df["Turnout_Percent"] / 100)
    ) / (df["Campaign_Events"] + 1)

    return df.dropna()

# load both datasets
df = load_live_data()
borough_df = load_borough_map()

# make sure zip formats match
borough_df["ZIP"] = borough_df["ZIP"].astype(str)
df["ZIP"] = df["ZIP"].astype(str)

# merge in borough info
df = df.merge(borough_df, on="ZIP", how="left")

# sidebar filter
st.sidebar.header("📍 Filter by Borough")
selected_borough = st.sidebar.selectbox("Choose a borough", ["All"] + sorted(df["Borough"].dropna().unique().tolist()))
if selected_borough != "All":
    df = df[df["Borough"] == selected_borough]

# main table
st.subheader("📊 Neighborhood Data")
st.dataframe(df[["ZIP", "Borough", "Housing_Complaints", "Evictions", "Turnout_Percent", "Campaign_Events", "Priority_Score"]])

# map
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

# top zips
st.subheader("🔑 Top ZIP Codes to Prioritize")
top = df.sort_values("Priority_Score", ascending=False).head(3)
for _, row in top.iterrows():
    st.markdown(f"- **ZIP {row['ZIP']}** → Score: {row['Priority_Score']:.1f}")
