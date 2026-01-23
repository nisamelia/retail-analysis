import streamlit as st
import geopandas as gpd
import pandas as pd
import pydeck as pdk
import plotly.express as px
from pathlib import Path

# =========================================================
# CONFIG
# =========================================================
st.set_page_config(
    page_title="Retail Expansion Score Dashboard",
    page_icon="🏪",
    layout="wide"
    
)

st.markdown(
    "🔗 **Source code:** "
    "[github.com/nisamelia/retail-expansion]"
    "(https://github.com/nisamelia/retail-expansion)"
)

# =========================================================
# LOAD DATA (OPTIMIZED, SAFE)
# =========================================================
@st.cache_data
def load_grid_data(file_path, simplify_tol):
    gdf = gpd.read_file(file_path)

    if gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")

    # 🔥 Geometry simplify (KEY PERFORMANCE)
    gdf["geometry"] = gdf.geometry.simplify(
        tolerance=simplify_tol,
        preserve_topology=True
    )

    # Representative point (faster than centroid)
    rp = gdf.geometry.representative_point()
    gdf["lon"] = rp.x
    gdf["lat"] = rp.y

    # Precompute polygon coordinates (ONCE)
    gdf["coordinates"] = gdf.geometry.apply(
        lambda geom: [[[x, y] for x, y in geom.exterior.coords]]
    )

    return gdf


# =========================================================
# COLOR FUNCTIONS
# =========================================================
def get_retail_color(retail_class):
    return {
        "High": [220, 38, 38, 160],
        "Medium": [245, 158, 11, 160],
        "Low": [16, 185, 129, 160],
    }.get(retail_class, [160, 160, 160, 120])


def get_color_scale(value, vmin, vmax):
    if pd.isna(value):
        return [200, 200, 200, 80]

    norm = (value - vmin) / (vmax - vmin) if vmax > vmin else 0.5
    norm = max(0, min(1, norm))

    if norm < 0.5:
        r, g = 255, int(norm * 2 * 255)
    else:
        r, g = int(255 - (norm - 0.5) * 2 * 255), 255

    return [r, g, 0, int(120 + norm * 100)]


# =========================================================
# SIDEBAR
# =========================================================
st.sidebar.title("⚙️ Settings")

data_files = {
    "OKU": "data/grid_retail_expansion_score_oku.gpkg",
    "Tangsel": "data/grid_retail_expansion_score_tangsel.gpkg"
}

selected_dataset = st.sidebar.selectbox(
    "Select Dataset",
    list(data_files.keys())
)

full_detail = st.sidebar.checkbox(
    "Full Detail Mode (Slower)",
    value=False
)

# Geometry tolerance control
simplify_tol = 0.0001 if full_detail else 0.0003

uploaded_file = st.sidebar.file_uploader(
    "Or upload your own file",
    type=["gpkg", "geojson", "shp"]
)

if uploaded_file:
    temp = Path("temp_upload.gpkg")
    with open(temp, "wb") as f:
        f.write(uploaded_file.getbuffer())
    gdf = load_grid_data(temp, simplify_tol)
    dataset_name = uploaded_file.name
else:
    gdf = load_grid_data(data_files[selected_dataset], simplify_tol)
    dataset_name = selected_dataset

# Detect landuse column
if "Keterangan" in gdf.columns:
    landuse_col = "Keterangan"
elif "KELAS_2" in gdf.columns:
    landuse_col = "KELAS_2"
else:
    landuse_col = None

# =========================================================
# FILTERS
# =========================================================
st.sidebar.subheader("🔍 Filters")

if "retail_class" in gdf.columns:
    rc = ["All"] + sorted(gdf["retail_class"].dropna().unique())
    sel = st.sidebar.selectbox("Retail Class", rc)
    if sel != "All":
        gdf = gdf[gdf["retail_class"] == sel]

if "flood_class" in gdf.columns:
    fc = ["All"] + sorted(gdf["flood_class"].dropna().unique())
    sel = st.sidebar.selectbox("Flood Class", fc)
    if sel != "All":
        gdf = gdf[gdf["flood_class"] == sel]

if landuse_col:
    lu = ["All"] + sorted(gdf[landuse_col].dropna().unique())
    sel = st.sidebar.selectbox(landuse_col, lu)
    if sel != "All":
        gdf = gdf[gdf[landuse_col] == sel]

# =========================================================
# MAIN
# =========================================================
st.title("🏪 Grid Retail Expansion Score Dashboard")
st.markdown(
    "Grid-based retail expansion analysis using dasymetric population modeling"
)
st.markdown("---")

# =========================================================
# METRICS
# =========================================================
col1, col2, col3, col4 = st.columns(4)

col1.metric("Total Grids", f"{len(gdf):,}")

if "retail_class" in gdf.columns:
    high = (gdf["retail_class"] == "High").sum()
    col2.metric("Retail High", f"{high:,}", f"{high/len(gdf)*100:.1f}%")

if "pop_dasymetric" in gdf.columns:
    col3.metric("Total Population", f"{gdf['pop_dasymetric'].sum():,.0f}")

if "access_idx" in gdf.columns:
    col4.metric("Grid with Access", f"{(gdf['access_idx']==1).sum():,}")

st.markdown("---")

# =========================================================
# MAP
# =========================================================
st.subheader("🗺️ Retail Expansion Map")


viz_mode = st.radio(
    "Visualization Mode",
    ["Retail Class", "Retail Score"],
    horizontal=True
)

gdf_plot = gdf.copy()

# Coloring
if viz_mode == "Retail Class" and "retail_class" in gdf_plot.columns:
    gdf_plot["fill_color"] = gdf_plot["retail_class"].apply(get_retail_color)
else:
    vmin, vmax = gdf_plot["retail_score"].min(), gdf_plot["retail_score"].max()
    gdf_plot["fill_color"] = gdf_plot["retail_score"].apply(
        lambda x: get_color_scale(x, vmin, vmax)
    )

# PyDeck Polygon Layer (ULTRA LIGHT)
layer = pdk.Layer(
    "PolygonLayer",
    data=gdf_plot,
    get_polygon="coordinates",
    get_fill_color="fill_color",
    stroked=False,        # 🔥 NO BORDER
    filled=True,
    extruded=False,
    pickable=True,
    auto_highlight=False
)

view = pdk.ViewState(
    latitude=gdf_plot["lat"].mean(),
    longitude=gdf_plot["lon"].mean(),
    zoom=10
)

deck = pdk.Deck(
    layers=[layer],
    initial_view_state=view,
    map_style="mapbox://styles/mapbox/light-v10",
    tooltip={
        "html": "<b>ID:</b> {gid}<br><b>Score:</b> {retail_score:.3f}"
    }
)

st.pydeck_chart(deck, use_container_width=True)

# =========================================================
# FOOTER
# =========================================================
st.markdown("---")
st.markdown(
    f"""
    <div style="text-align:center; font-size:12px;">
        <strong>Grid Retail Expansion Score Dashboard</strong><br>
        Dataset: {dataset_name}<br>
        Powered by Streamlit & PyDeck
    </div>
    """,
    unsafe_allow_html=True
)