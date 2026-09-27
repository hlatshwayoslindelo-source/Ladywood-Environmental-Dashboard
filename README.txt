LADYWOOD BLACK AND BLUE ENVIRONMENTAL DASHBOARD

This is a simple black-and-blue interactive Streamlit dashboard.

It includes:

1. Brownfield
2. Air Quality
3. Surface-Water Flooding
4. One Year dropdown

MAIN FILE

environmental_dashboard.py

HOW TO RUN

1. Open Command Prompt in this folder.
2. Install packages:

   pip install -r requirements.txt

3. Run:

   streamlit run environmental_dashboard.py

DESIGN

- Black background
- Blue accent cards
- Simple layout
- One Year dropdown
- Interactive tables, charts, metrics, and maps

WHAT IS ALREADY CONNECTED

Brownfield:
- Birmingham City Council Brownfield Register URL is already included.

Air Quality:
- DEFRA UK-AIR Birmingham Ladywood station code BMLD is already included.
- The year dropdown changes the air-quality URL automatically.

Surface-Water Flooding:
- Paste a public GeoJSON/API URL into SURFACE_FLOODING_URL in environmental_dashboard.py.

YEAR DROPDOWN

Edit AVAILABLE_YEARS in environmental_dashboard.py if you want more or fewer year options:

AVAILABLE_YEARS = [2026, 2025, 2024, 2023, 2022]
