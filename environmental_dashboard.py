import streamlit as st
import pandas as pd
import json
from pathlib import Path

st.set_page_config(
    page_title="Ladywood Environmental Dashboard",
    page_icon="🌍",
    layout="wide"
)

DATA = Path(".")

st.title("🌍 Ladywood Environmental Dashboard")
st.caption("Air Quality • Brownfield Sites • Surface Water Flooding • Rainfall")

section = st.sidebar.radio(
    "Choose a section",
    ["Overview", "Air Quality", "Brownfield Sites", "Surface Water Flooding", "Rainfall"]
)

def find_file(possible_names):
    for name in possible_names:
        path = DATA / name
        if path.exists():
            return path
    return None

def safe_read_csv(path):
    if path is None:
        return pd.DataFrame()

    # Try normal CSV first, then try skipping extra header/comment lines.
    for skip in range(0, 30):
        try:
            df = pd.read_csv(path, skiprows=skip)
            df.columns = [str(c).strip() for c in df.columns]

            # Keep only real-looking tables.
            if df.shape[1] > 1 and len(df) > 0:
                # Drop fully empty columns and rows.
                df = df.dropna(axis=1, how="all").dropna(axis=0, how="all")
                if df.shape[1] > 1 and len(df) > 0:
                    return df
        except Exception:
            pass

    return pd.DataFrame()

def clean_numeric_columns(df):
    for col in df.columns:
        # Remove commas and spaces from possible numeric text.
        if df[col].dtype == "object":
            cleaned = df[col].astype(str).str.replace(",", "", regex=False).str.strip()
            converted = pd.to_numeric(cleaned, errors="coerce")
            if converted.notna().sum() > 0:
                df[col] = converted
        else:
            df[col] = pd.to_numeric(df[col], errors="ignore")
    return df

def show_dataframe(df, title):
    st.subheader(title)
    if df.empty:
        st.error("No data could be loaded for this section.")
        return
    st.write(f"Rows loaded: **{len(df)}**")
    st.dataframe(df, use_container_width=True)

brownfield_path = find_file(["brownfield.xlsx", "brownfield.csv", "Brownfield.xlsx", "Brownfield.csv"])
air_path = find_file(["air_quality_2026.csv", "air_quality.csv", "Air_Quality_2026.csv", "Air Quality 2026.csv"])
flood_path = find_file(["surface_water_flooding.json", "surface_water_flooding.geojson", "flooding.json", "Surface_Water_Flooding.json"])
rain_path = find_file(["rainfall.csv", "ladywood_rainfall_2025.csv", "Ladywood_Rainfall_2025.csv", "rain.csv"])

if section == "Overview":
    st.header("Overview")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Air Quality File", "Found" if air_path else "Missing")
    with col2:
        st.metric("Brownfield File", "Found" if brownfield_path else "Missing")
    with col3:
        st.metric("Flooding File", "Found" if flood_path else "Missing")
    with col4:
        st.metric("Rainfall File", "Found" if rain_path else "Missing")

    st.info("Use the sidebar to open each dataset. If a section says missing, upload that file to the main GitHub repo page.")

elif section == "Air Quality":
    st.header("Air Quality")

    air_df = clean_numeric_columns(safe_read_csv(air_path))

    if air_df.empty:
        st.error("Air quality data is missing or could not be read.")
        st.write("Expected file name: `air_quality_2026.csv`")
    else:
        show_dataframe(air_df, "Air Quality Data")

        numeric_cols = air_df.select_dtypes(include="number").columns.tolist()
        if numeric_cols:
            selected_col = st.selectbox("Choose a numeric column to chart", numeric_cols)
            st.line_chart(air_df[selected_col])
        else:
            st.warning("No numeric columns were found to chart.")

elif section == "Brownfield Sites":
    st.header("Brownfield Sites")

    if brownfield_path is None:
        st.error("Brownfield file is missing.")
        st.write("Expected file name: `brownfield.xlsx`")
    else:
        try:
            if brownfield_path.suffix.lower() == ".xlsx":
                brown_df = pd.read_excel(brownfield_path)
            else:
                brown_df = safe_read_csv(brownfield_path)

            brown_df.columns = [str(c).strip() for c in brown_df.columns]
            show_dataframe(brown_df, "Brownfield Sites Data")

            st.write("Column names found:")
            st.code(", ".join(brown_df.columns))

        except Exception as e:
            st.error("Brownfield file could not be read.")
            st.exception(e)

elif section == "Surface Water Flooding":
    st.header("Surface Water Flooding")

    if flood_path is None:
        st.error("Surface water flooding file is missing.")
        st.write("Expected file name: `surface_water_flooding.json`")
    else:
        try:
            with open(flood_path, "r", encoding="utf-8") as f:
                flood_data = json.load(f)

            st.success("Surface water flooding file loaded successfully.")

            if isinstance(flood_data, dict):
                st.write("Top-level keys:")
                st.code(", ".join(flood_data.keys()))

                if "features" in flood_data:
                    st.write(f"Number of flood features: **{len(flood_data['features'])}**")
                    rows = [feature.get("properties", {}) for feature in flood_data["features"][:1000]]
                    flood_df = pd.DataFrame(rows)

                    if not flood_df.empty:
                        st.dataframe(flood_df, use_container_width=True)
                    else:
                        st.warning("The flood file loaded, but no table properties were found.")
                else:
                    st.json(flood_data)
            else:
                st.json(flood_data)

        except Exception as e:
            st.error("Surface water flooding file could not be read.")
            st.exception(e)

elif section == "Rainfall":
    st.header("Rainfall")

    rain_df = clean_numeric_columns(safe_read_csv(rain_path))

    if rain_df.empty:
        st.error("Rainfall data is missing or could not be read.")
        st.write("Expected file name: `rainfall.csv`")
    else:
        show_dataframe(rain_df, "Rainfall Data")

        numeric_cols = rain_df.select_dtypes(include="number").columns.tolist()
        if numeric_cols:
            selected_col = st.selectbox("Choose a rainfall numeric column to chart", numeric_cols)
            st.line_chart(rain_df[selected_col])
        else:
            st.warning("No numeric rainfall columns were found to chart.")

st.markdown("---")
st.caption("Ladywood Environmental Dashboard")
