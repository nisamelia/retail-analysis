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

# Repo link (biar langsung kelihatan)
st.markdown(
    "🔗 **Source code:** "
    "[github.com/nisamelia/retail-expansion]"
    "(https://github.com/nisamelia/retail-expansion)"
)

# =========================================================
# LOAD DATA (OPTIMIZED)
# =========================================================
@st.cache_data
def load_grid_data(file_path, simplify_tol):
    gdf = gpd.read_file(file_path)

    if gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")

    # Simplify geometry (speed-up rendering)
    gdf["geometry"] = gdf.geometry.simplify(
        tolerance=simplify_tol,
        preserve_topology=True
    )

    # Representative point (lebih cepat dari centroid)
    rp = gdf.geometry.representative_point()
    gdf["lon"] = rp.x
    gdf["lat"] = rp.y

    # Precompute polygon coordinates (PyDeck friendly)
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
# FILTERS (DEFAULT: HIGH + LOW FLOOD)
# =========================================================
st.sidebar.subheader("🔍 Filters")

# Retail class
if "retail_class" in gdf.columns:
    rc_options = sorted(gdf["retail_class"].dropna().unique())
    selected_rc = st.sidebar.selectbox(
        "Retail Class",
        rc_options,
        index=rc_options.index("High") if "High" in rc_options else 0
    )
    gdf = gdf[gdf["retail_class"] == selected_rc]

# Flood class
if "flood_class" in gdf.columns:
    fc_options = sorted(gdf["flood_class"].dropna().unique())
    default_fc = "Low" if "Low" in fc_options else fc_options[0]
    selected_fc = st.sidebar.selectbox(
        "Flood Class",
        fc_options,
        index=fc_options.index(default_fc)
    )
    gdf = gdf[gdf["flood_class"] == selected_fc]

# Landuse
if landuse_col:
    lu_options = ["All"] + sorted(gdf[landuse_col].dropna().unique())
    sel_lu = st.sidebar.selectbox(landuse_col, lu_options)
    if sel_lu != "All":
        gdf = gdf[gdf[landuse_col] == sel_lu]

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
    col2.metric("Retail High", f"{high:,}")

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

if viz_mode == "Retail Class" and "retail_class" in gdf_plot.columns:
    gdf_plot["fill_color"] = gdf_plot["retail_class"].apply(get_retail_color)
else:
    vmin, vmax = gdf_plot["retail_score"].min(), gdf_plot["retail_score"].max()
    gdf_plot["fill_color"] = gdf_plot["retail_score"].apply(
        lambda x: get_color_scale(x, vmin, vmax)
    )

# Tooltip lengkap
tooltip_html = "<b>Grid ID:</b> {gid}<br/>"
important_cols = [
    "retail_class", "retail_score", landuse_col,
    "pop_dasymetric", "flood_class",
    "demand_idx", "flood_risk_idx", "access_idx",
    "akses_jalan_utama", "akses_jalan_arteri", "akses_jalan_kolektor"
]
important_cols = [c for c in important_cols if c and c in gdf_plot.columns]

for col in important_cols:
    tooltip_html += f"<b>{col}:</b> {{{col}}}<br/>"

layer = pdk.Layer(
    "PolygonLayer",
    data=gdf_plot,
    get_polygon="coordinates",
    get_fill_color="fill_color",
    stroked=False,
    filled=True,
    extruded=False,
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
    map_style="carto-positron",  # 🔥 NO TOKEN
    tooltip={
        "html": tooltip_html,
        "style": {
            "backgroundColor": "rgba(0,0,0,0.8)",
            "color": "white",
            "fontSize": "11px",
            "padding": "8px",
            "borderRadius": "4px"
        }
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
