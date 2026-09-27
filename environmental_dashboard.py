from io import BytesIO, StringIO
import re

import pandas as pd
import requests
import streamlit as st


# ============================================================
# LADYWOOD BLACK & BLUE ENVIRONMENTAL DASHBOARD
# ============================================================
# A simple, clean, interactive Streamlit dashboard for:
# - Brownfield
# - Air Quality
# - Surface-Water Flooding
#
# Design:
# - Black background
# - Blue accents
# - One main Year dropdown
# - Interactive tables, charts, metrics, and maps
# ============================================================


st.set_page_config(
    page_title="Ladywood Environmental Dashboard",
    layout="wide"
)


# ============================================================
# BLACK + BLUE DASHBOARD STYLE
# ============================================================

st.markdown(
    """
    <style>
    .stApp {
        background-color: #050A14;
        color: #EAF2FF;
    }

    h1, h2, h3 {
        color: #4DA3FF;
        font-weight: 700;
    }

    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }

    [data-testid="stSidebar"] {
        background-color: #07111F;
        border-right: 1px solid #12355B;
    }

    [data-testid="stMetric"] {
        background-color: #071827;
        border: 1px solid #145DA0;
        border-radius: 14px;
        padding: 15px;
        box-shadow: 0px 0px 12px rgba(77, 163, 255, 0.10);
    }

    [data-testid="stMetricLabel"] {
        color: #9ECFFF;
    }

    [data-testid="stMetricValue"] {
        color: #FFFFFF;
    }

    div.stButton > button {
        background-color: #145DA0;
        color: white;
        border-radius: 10px;
        border: none;
        padding: 0.6rem 1rem;
    }

    div.stButton > button:hover {
        background-color: #1F8BFF;
        color: white;
    }

    .info-card {
        background-color: #071827;
        border: 1px solid #145DA0;
        border-radius: 14px;
        padding: 18px;
        margin-bottom: 16px;
    }

    .small-muted {
        color: #9ECFFF;
        font-size: 0.9rem;
    }
    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# ONLINE DATA SOURCES
# ============================================================

BROWNFIELD_URL = "https://www.birmingham.gov.uk/downloads/file/9037/brownfield_register"

# DEFRA UK-AIR Birmingham Ladywood station
UK_AIR_SITE_ID = "BMLD"

# The dropdown uses these years.
# Add more years here later if you want.
AVAILABLE_YEARS = [2026, 2025, 2024, 2023, 2022]

# Surface-water flooding public GeoJSON/API link.
# Paste the public flooding link here when you have it.
SURFACE_FLOODING_URL = ""

CACHE_SECONDS = 3600


# ============================================================
# HEADER
# ============================================================

st.title("Ladywood Environmental Dashboard")
st.markdown(
    """
    <div class="info-card">
        <b>Simple black-and-blue interactive dashboard</b><br>
        Brownfield, air quality, and surface-water flooding data for Ladywood.
        Use the year dropdown to update the Ladywood data views.
    </div>
    """,
    unsafe_allow_html=True
)


# ============================================================
# HELPERS
# ============================================================

def clean_columns(df):
    df = df.copy()
    df.columns = (
        df.columns.astype(str)
        .str.replace("\xa0", " ", regex=False)
        .str.strip()
    )
    return df


def find_column(df, words):
    for col in df.columns:
        low = str(col).lower()
        if any(word.lower() in low for word in words):
            return col
    return None


def search_rows(df, text):
    if not text:
        return df

    mask = df.astype(str).apply(
        lambda row: row.str.contains(text, case=False, na=False).any(),
        axis=1
    )
    return df[mask]


def filter_by_year(df, year):
    """
    Finds likely date/year columns and filters records by the selected year.
    If no useful year/date column exists, it returns the original dataframe.
    """
    if df.empty:
        return df

    df = df.copy()

    likely_year_cols = [
        col for col in df.columns
        if "year" in str(col).lower()
        or "date" in str(col).lower()
        or "time" in str(col).lower()
        or "added" in str(col).lower()
        or "updated" in str(col).lower()
        or "permission" in str(col).lower()
    ]

    for col in likely_year_cols:
        # Direct numeric year column
        numeric = pd.to_numeric(df[col], errors="coerce")
        if numeric.notna().sum() > 0:
            mask = numeric.astype("Int64", errors="ignore") == year
            if mask.sum() > 0:
                return df[mask]

        # Date-like column
        dates = pd.to_datetime(df[col], errors="coerce", dayfirst=True)
        if dates.notna().sum() > 0:
            mask = dates.dt.year == year
            if mask.sum() > 0:
                return df[mask]

        # Text containing year
        text_mask = df[col].astype(str).str.contains(str(year), na=False)
        if text_mask.sum() > 0:
            return df[text_mask]

    return df


def make_map_if_possible(df, title):
    lat_col = find_column(df, ["lat", "latitude"])
    lon_col = find_column(df, ["lon", "lng", "longitude"])

    if not lat_col or not lon_col:
        st.info("No latitude/longitude columns detected for this table.")
        return

    map_df = df.copy()
    map_df[lat_col] = pd.to_numeric(map_df[lat_col], errors="coerce")
    map_df[lon_col] = pd.to_numeric(map_df[lon_col], errors="coerce")
    map_df = map_df.dropna(subset=[lat_col, lon_col])

    if map_df.empty:
        st.info("Coordinates were detected, but none could be mapped.")
        return

    st.subheader(title)
    st.map(map_df.rename(columns={lat_col: "lat", lon_col: "lon"})[["lat", "lon"]])


# ============================================================
# DATA LOADERS
# ============================================================

@st.cache_data(ttl=CACHE_SECONDS)
def load_brownfield(url):
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    df = pd.read_excel(BytesIO(response.content))
    return clean_columns(df)


@st.cache_data(ttl=CACHE_SECONDS)
def load_air_quality(site_id, year):
    url = f"https://uk-air.defra.gov.uk/datastore/data_files/site_data/{site_id}_{year}.csv?v=1"
    response = requests.get(url, timeout=60)
    response.raise_for_status()

    text = response.text
    lines = text.splitlines()

    # Try to find the real CSV header row.
    header_index = 0
    for i, line in enumerate(lines):
        lower = line.lower()
        if (
            ("date" in lower or "time" in lower)
            and "," in line
        ):
            header_index = i
            break

    df = pd.read_csv(StringIO("\n".join(lines[header_index:])))
    return clean_columns(df), url


@st.cache_data(ttl=CACHE_SECONDS)
def load_surface_flooding(url):
    if not url:
        return None

    response = requests.get(url, timeout=60)
    response.raise_for_status()
    return response.json()


def filter_ladywood(df):
    if df.empty:
        return df

    mask = df.astype(str).apply(
        lambda row: row.str.contains("Ladywood", case=False, na=False).any(),
        axis=1
    )
    filtered = df[mask]

    # If the source already only represents Ladywood, do not accidentally return empty.
    if filtered.empty:
        return df

    return filtered


def extract_first_coordinate(geometry):
    if not geometry:
        return None

    try:
        current = geometry.get("coordinates")

        if geometry.get("type") == "Point":
            lon, lat = current
            return lat, lon

        while isinstance(current, list):
            if (
                len(current) >= 2
                and isinstance(current[0], (int, float))
                and isinstance(current[1], (int, float))
            ):
                lon, lat = current[0], current[1]
                return lat, lon
            current = current[0]
    except Exception:
        return None

    return None


def geojson_to_table(geojson_data):
    if not geojson_data:
        return pd.DataFrame()

    rows = []
    features = geojson_data.get("features", [])

    for i, feature in enumerate(features, start=1):
        props = feature.get("properties", {})
        geom = feature.get("geometry", {})
        point = extract_first_coordinate(geom)

        row = {
            "feature_number": i,
            "feature_id": feature.get("id", "")
        }

        for key, value in props.items():
            row[key] = value

        if point:
            lat, lon = point
            row["lat"] = lat
            row["lon"] = lon

        rows.append(row)

    return pd.DataFrame(rows)


def numeric_columns(df):
    if df.empty:
        return []

    temp = df.copy()

    for col in temp.columns:
        temp[col] = pd.to_numeric(temp[col], errors="ignore")

    nums = temp.select_dtypes(include="number").columns.tolist()
    return nums


def chart_numeric(df, title):
    nums = numeric_columns(df)

    if not nums:
        st.info("No numeric columns available for a chart.")
        return

    selected = st.selectbox(f"Choose chart field for {title}", nums)

    plot_df = df.copy()
    plot_df[selected] = pd.to_numeric(plot_df[selected], errors="coerce")
    plot_df = plot_df.dropna(subset=[selected])

    date_col = find_column(plot_df, ["date", "time"])
    if date_col:
        plot_df[date_col] = pd.to_datetime(plot_df[date_col], errors="coerce", dayfirst=True)
        plot_df = plot_df.dropna(subset=[date_col]).sort_values(date_col)
        if not plot_df.empty:
            plot_df = plot_df.set_index(date_col)

    if not plot_df.empty:
        st.line_chart(plot_df[[selected]])
    else:
        st.info("There is no valid numeric data to chart.")


# ============================================================
# SIDEBAR CONTROLS
# ============================================================

st.sidebar.header("Controls")

selected_year = st.sidebar.selectbox(
    "Year",
    AVAILABLE_YEARS,
    index=0
)

section = st.sidebar.radio(
    "Section",
    ["Overview", "Brownfield", "Air Quality", "Surface-Water Flooding", "Data Sources"]
)

st.sidebar.markdown(
    f"""
    <div class="info-card">
        <b>Selected year:</b> {selected_year}<br>
        <span class="small-muted">Theme: black + blue</span>
    </div>
    """,
    unsafe_allow_html=True
)


# ============================================================
# LOAD DATA
# ============================================================

brownfield_error = None
air_error = None
flood_error = None

try:
    brownfield_all = load_brownfield(BROWNFIELD_URL)
    brownfield_ladywood = filter_ladywood(brownfield_all)
    brownfield_year = filter_by_year(brownfield_ladywood, selected_year)
except Exception as error:
    brownfield_error = error
    brownfield_all = pd.DataFrame()
    brownfield_ladywood = pd.DataFrame()
    brownfield_year = pd.DataFrame()

try:
    air_quality, air_url = load_air_quality(UK_AIR_SITE_ID, selected_year)
except Exception as error:
    air_error = error
    air_quality = pd.DataFrame()
    air_url = f"https://uk-air.defra.gov.uk/datastore/data_files/site_data/{UK_AIR_SITE_ID}_{selected_year}.csv?v=1"

try:
    flood_json = load_surface_flooding(SURFACE_FLOODING_URL)
    flood_table = geojson_to_table(flood_json)
    flood_year = filter_by_year(flood_table, selected_year)
except Exception as error:
    flood_error = error
    flood_json = None
    flood_table = pd.DataFrame()
    flood_year = pd.DataFrame()


# ============================================================
# OVERVIEW
# ============================================================

if section == "Overview":
    st.header("Overview")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Selected year", selected_year)
    col2.metric("Ladywood brownfield records", len(brownfield_year))
    col3.metric("Air-quality records", len(air_quality))
    col4.metric("Flooding features", len(flood_year) if not flood_year.empty else len(flood_table))

    st.markdown(
        """
        <div class="info-card">
            This dashboard is interactive. Use the Year dropdown in the sidebar.
            The brownfield table, air-quality data, and any year-based flooding data
            will update based on that selected year.
        </div>
        """,
        unsafe_allow_html=True
    )

    if brownfield_error:
        st.error("Brownfield data could not be loaded.")
        st.exception(brownfield_error)

    if air_error:
        st.error("Air-quality data could not be loaded for the selected year.")
        st.exception(air_error)

    if flood_error:
        st.error("Surface-water flooding data could not be loaded.")
        st.exception(flood_error)


# ============================================================
# BROWNFIELD
# ============================================================

elif section == "Brownfield":
    st.header("Brownfield")

    if brownfield_error:
        st.error("Brownfield data could not be loaded.")
        st.exception(brownfield_error)
        st.stop()

    search = st.text_input("Search brownfield records", value="")
    display = search_rows(brownfield_year, search)

    col1, col2, col3 = st.columns(3)
    col1.metric("All Birmingham records", len(brownfield_all))
    col2.metric("Ladywood records", len(brownfield_ladywood))
    col3.metric(f"Shown for {selected_year}", len(display))

    st.subheader("Brownfield Table")
    st.dataframe(display, use_container_width=True)

    make_map_if_possible(display, "Brownfield Map")


# ============================================================
# AIR QUALITY
# ============================================================

elif section == "Air Quality":
    st.header("Air Quality")

    if air_error:
        st.error(f"Air-quality data could not be loaded for {selected_year}.")
        st.write("Try another year from the dropdown.")
        st.exception(air_error)
        st.stop()

    search = st.text_input("Search air-quality records", value="")
    display = search_rows(air_quality, search)

    col1, col2, col3 = st.columns(3)
    col1.metric("Station", UK_AIR_SITE_ID)
    col2.metric("Year", selected_year)
    col3.metric("Records shown", len(display))

    st.subheader("Air Quality Chart")
    chart_numeric(display, "air quality")

    st.subheader("Air Quality Table")
    st.dataframe(display, use_container_width=True)


# ============================================================
# SURFACE-WATER FLOODING
# ============================================================

elif section == "Surface-Water Flooding":
    st.header("Surface-Water Flooding")

    if not SURFACE_FLOODING_URL:
        st.warning("Surface-water flooding URL has not been added yet.")
        st.markdown(
            """
            <div class="info-card">
                Paste a public GeoJSON/API link into <b>SURFACE_FLOODING_URL</b>
                near the top of the Python file. After that, this section will show
                a flood-risk table and map.
            </div>
            """,
            unsafe_allow_html=True
        )
        st.code('SURFACE_FLOODING_URL = "PASTE_PUBLIC_GEOJSON_OR_API_LINK_HERE"')
        st.stop()

    if flood_error:
        st.error("Surface-water flooding data could not be loaded.")
        st.exception(flood_error)
        st.stop()

    display = flood_year if not flood_year.empty else flood_table
    search = st.text_input("Search flooding records", value="")
    display = search_rows(display, search)

    col1, col2 = st.columns(2)
    col1.metric("Flooding features shown", len(display))
    col2.metric("Selected year", selected_year)

    st.subheader("Surface-Water Flooding Table")
    st.dataframe(display, use_container_width=True)

    make_map_if_possible(display, "Surface-Water Flooding Map")


# ============================================================
# DATA SOURCES
# ============================================================

elif section == "Data Sources":
    st.header("Data Sources")

    sources = pd.DataFrame([
        {
            "Dataset": "Brownfield",
            "Source": "Birmingham City Council Brownfield Register",
            "URL": BROWNFIELD_URL
        },
        {
            "Dataset": "Air Quality",
            "Source": f"DEFRA UK-AIR Birmingham Ladywood station {UK_AIR_SITE_ID}",
            "URL": air_url
        },
        {
            "Dataset": "Surface-Water Flooding",
            "Source": "Public GeoJSON/API link",
            "URL": SURFACE_FLOODING_URL if SURFACE_FLOODING_URL else "Not added yet"
        }
    ])

    st.dataframe(sources, use_container_width=True)

    st.markdown(
        """
        <div class="info-card">
            The dashboard pulls data from online sources.
            The selected Year dropdown changes the views where the data supports year filtering.
        </div>
        """,
        unsafe_allow_html=True
    )
