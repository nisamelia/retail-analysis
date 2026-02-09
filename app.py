import streamlit as st
import geopandas as gpd
import pandas as pd
import pydeck as pdk
from pathlib import Path

# =========================================================
# PAGE CONFIG (HARUS PALING ATAS)
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

st.markdown(
    "🔗 **Find out my CV:** "
    "[Nisa Amelia's CV]"
    "(https://drive.google.com/file/d/1sa14j-L3tioraYqTcS8n1wPE6pwv9D_A/view?usp=sharing)"
)

# =========================================================
# LOAD DATA (OPTIMIZED & DEPLOY-SAFE)
# =========================================================
@st.cache_data
def load_grid_data(file_path, simplify_tol):
    gdf = gpd.read_file(file_path)

    if gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")

    # Simplify geometry (IMPORTANT for performance)
    gdf["geometry"] = gdf.geometry.simplify(
        tolerance=simplify_tol,
        preserve_topology=True
    )

    # Representative point (faster than centroid)
    rp = gdf.geometry.representative_point()
    gdf["lon"] = rp.x
    gdf["lat"] = rp.y

    # Precompute polygon coordinates ONCE
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
    "Full Detail Geometry (Slower)",
    value=False
)

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
# FILTERS (DEFAULT: HIGH + LOW FLOOD + PERMUKIMAN)
# =========================================================
st.sidebar.subheader("🔍 Filters")

# Retail Class
if "retail_class" in gdf.columns:
    rc_options = ["All"] + sorted(gdf["retail_class"].dropna().unique())
    default_rc = "High" if "High" in rc_options else "All"

    selected_rc = st.sidebar.selectbox(
        "Retail Class",
        rc_options,
        index=rc_options.index(default_rc)
    )

    if selected_rc != "All":
        gdf = gdf[gdf["retail_class"] == selected_rc]

# Flood Class
if "flood_class" in gdf.columns:
    fc_options = ["All"] + sorted(gdf["flood_class"].dropna().unique())

    if "Low" in fc_options:
        default_fc = "Low"
    elif "Rendah" in fc_options:
        default_fc = "Rendah"
    else:
        default_fc = "All"

    selected_fc = st.sidebar.selectbox(
        "Flood Class",
        fc_options,
        index=fc_options.index(default_fc)
    )

    if selected_fc != "All":
        gdf = gdf[gdf["flood_class"] == selected_fc]

# Landuse / Keterangan
if landuse_col:
    lu_options = ["All"] + sorted(gdf[landuse_col].dropna().unique())

    if "Permukiman" in lu_options:
        default_lu = "Permukiman"
    elif "Perumahan" in lu_options:
        default_lu = "Perumahan"
    else:
        default_lu = "All"

    selected_lu = st.sidebar.selectbox(
        landuse_col,
        lu_options,
        index=lu_options.index(default_lu)
    )

    if selected_lu != "All":
        gdf = gdf[gdf[landuse_col] == selected_lu]

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
    col2.metric("Retail High", f"{(gdf['retail_class']=='High').sum():,}")

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

# Tooltip (FULL INFO)
tooltip_html = "<b>Grid ID:</b> {gid}<br/>"
tooltip_cols = [
    "retail_class", "retail_score", landuse_col,
    "pop_dasymetric", "flood_class",
    "demand_idx", "flood_risk_idx", "access_idx"
]
tooltip_cols = [c for c in tooltip_cols if c and c in gdf_plot.columns]

for c in tooltip_cols:
    tooltip_html += f"<b>{c}:</b> {{{c}}}<br/>"

layer = pdk.Layer(
    "PolygonLayer",
    data=gdf_plot,
    get_polygon="coordinates",
    get_fill_color="fill_color",
    stroked=True,
    filled=True,
    pickable=True
)

view = pdk.ViewState(
    latitude=gdf_plot["lat"].mean(),
    longitude=gdf_plot["lon"].mean(),
    zoom=10
)

deck = pdk.Deck(
    layers=[layer],
    initial_view_state=view,
    map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",  # ← OpenStreetMap default (NO TOKEN)
    tooltip={"html": tooltip_html}
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
