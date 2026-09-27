from pathlib import Path
import json
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Ladywood Environmental Dashboard", layout="wide")

st.markdown("""
<style>
.stApp { background-color:#050A14; color:#EAF2FF; }
h1,h2,h3 { color:#4DA3FF; }
[data-testid="stSidebar"] { background-color:#07111F; }
[data-testid="stMetric"] {
    background-color:#071827;
    border:1px solid #145DA0;
    border-radius:14px;
    padding:15px;
}
.info-card {
    background-color:#071827;
    border:1px solid #145DA0;
    border-radius:14px;
    padding:18px;
    margin-bottom:16px;
}
</style>
""", unsafe_allow_html=True)

st.title("Ladywood Environmental Dashboard")
st.markdown(
    "<div class='info-card'><b>MIIN Group 37 FEBE1004A</b><br>"
    "This Interactive Dashboard reads the brownfield, flooding, air quaility and rainfall data from files stored in your GitHub repository."
    """Members: 
    Sanelisiwe Ntshangase;  
    Christopher Matsimela; 
    Slindelokuhle Hlatshwayo; </div>""",
    unsafe_allow_html=True
)

DATA = Path(".")
BROWNFIELD_FILE = DATA / "brownfield.xlsx"
AIR_FILE = DATA / "air_quality_2026.csv"
FLOOD_FILE = DATA / "surface_water_flooding.json"

YEARS = [2026, 2025, 2024, 2023, 2022]

def clean_cols(df):
    df = df.copy()
    df.columns = df.columns.astype(str).str.replace("\xa0", " ", regex=False).str.strip()
    return df

def find_col(df, words):
    for col in df.columns:
        low = str(col).lower()
        if any(w in low for w in words):
            return col
    return None

def search_rows(df, text):
    if not text:
        return df
    mask = df.astype(str).apply(lambda r: r.str.contains(text, case=False, na=False).any(), axis=1)
    return df[mask]

def filter_ladywood(df):
    if df.empty:
        return df
    mask = df.astype(str).apply(lambda r: r.str.contains("Ladywood", case=False, na=False).any(), axis=1)
    result = df[mask]
    return result if not result.empty else df

def filter_year(df, year):
    if df.empty:
        return df
    candidates = [c for c in df.columns if any(w in str(c).lower() for w in ["year","date","time","updated","added","permission"])]
    for c in candidates:
        dates = pd.to_datetime(df[c], errors="coerce", dayfirst=True)
        if dates.notna().sum() and (dates.dt.year == year).sum():
            return df[dates.dt.year == year]
        text = df[c].astype(str).str.contains(str(year), na=False)
        if text.sum():
            return df[text]
    return df

def map_if_possible(df):
    lat = find_col(df, ["lat", "latitude"])
    lon = find_col(df, ["lon", "lng", "longitude"])
    if not lat or not lon:
        st.info("No latitude/longitude columns detected for a map.")
        return
    m = df.copy()
    m[lat] = pd.to_numeric(m[lat], errors="coerce")
    m[lon] = pd.to_numeric(m[lon], errors="coerce")
    m = m.dropna(subset=[lat, lon])
    if not m.empty:
        st.map(m.rename(columns={lat:"lat", lon:"lon"})[["lat","lon"]])
    else:
        st.info("Coordinate columns were found, but no valid points could be mapped.")

@st.cache_data(ttl=3600)
def load_brownfield():
    return clean_cols(pd.read_excel(BROWNFIELD_FILE))

@st.cache_data(ttl=3600)
def load_air():
    try:
        return clean_cols(pd.read_csv(AIR_FILE, skiprows=4))
    except Exception:
        return clean_cols(pd.read_csv(AIR_FILE))

@st.cache_data(ttl=3600)
def load_flood():
    with open(FLOOD_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def first_coord(geom):
    if not geom:
        return None
    cur = geom.get("coordinates")
    try:
        while isinstance(cur, list):
            if len(cur) >= 2 and isinstance(cur[0], (int,float)) and isinstance(cur[1], (int,float)):
                return cur[1], cur[0]
            cur = cur[0]
    except Exception:
        return None
    return None

def flood_table(js):
    rows = []
    for i, feat in enumerate(js.get("features", []), start=1):
        row = {"feature_number": i, "feature_id": feat.get("id", "")}
        row.update(feat.get("properties", {}))
        pt = first_coord(feat.get("geometry", {}))
        if pt:
            row["lat"], row["lon"] = pt
        rows.append(row)
    return pd.DataFrame(rows)

section = st.sidebar.radio("Section", ["Overview", "Brownfield", "Air Quality", "Surface-Water Flooding", "Data Sources"])
year = st.sidebar.selectbox("Year", YEARS)

errors = []
try:
    brown_all = load_brownfield()
    brown_lady = filter_ladywood(brown_all)
    brown_year = filter_year(brown_lady, year)
except Exception as e:
    brown_all = brown_lady = brown_year = pd.DataFrame()
    errors.append(("Brownfield", e))

try:
    air = load_air()
    air_year = filter_year(air, year)
except Exception as e:
    air = air_year = pd.DataFrame()
    errors.append(("Air Quality", e))

try:
    flood = flood_table(load_flood())
    flood_year = filter_year(flood, year)
except Exception as e:
    flood = flood_year = pd.DataFrame()
    errors.append(("Surface-Water Flooding", e))

if section == "Overview":
    st.header("Overview")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Selected year", year)
    c2.metric("Ladywood brownfield records", len(brown_year))
    c3.metric("Air-quality records", len(air_year if not air_year.empty else air))
    c4.metric("Flooding features", len(flood_year if not flood_year.empty else flood))
    for name, e in errors:
        st.error(f"{name} could not be loaded.")
        st.exception(e)

elif section == "Brownfield":
    st.header("Brownfield")
    q = st.text_input("Search brownfield records", "")
    df = search_rows(brown_year, q)
    c1, c2, c3 = st.columns(3)
    c1.metric("All Birmingham records", len(brown_all))
    c2.metric("Ladywood records", len(brown_lady))
    c3.metric("Shown", len(df))
    st.dataframe(df, use_container_width=True)
    map_if_possible(df)

elif section == "Air Quality":
    st.header("Air Quality")
    q = st.text_input("Search air-quality records", "")
    df = search_rows(air_year if not air_year.empty else air, q)
    st.metric("Records shown", len(df))
    nums = df.select_dtypes(include="number").columns.tolist()
    if nums:
        st.line_chart(df[nums[:1]])
    st.dataframe(df, use_container_width=True)

elif section == "Surface-Water Flooding":
    st.header("Surface-Water Flooding")
    q = st.text_input("Search flooding records", "")
    df = search_rows(flood_year if not flood_year.empty else flood, q)
    st.metric("Features shown", len(df))
    st.dataframe(df, use_container_width=True)
    map_if_possible(df)

else:
    st.header("Data Sources")
    st.dataframe(pd.DataFrame([
        {"Dataset":"Brownfield", "File":"data/brownfield.xlsx"},
        {"Dataset":"Air Quality", "File":"data/air_quality_2026.csv"},
        {"Dataset":"Surface-Water Flooding", "File":"data/surface_water_flooding.json"},
    ]), use_container_width=True)
