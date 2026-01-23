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

# =========================================================
# FUNGSI LOAD DATA
# =========================================================
@st.cache_data
def load_grid_data(file_path):
    gdf = gpd.read_file(file_path)
    if gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")
    
    # Hitung centroid
    gdf['lon'] = gdf.geometry.centroid.x
    gdf['lat'] = gdf.geometry.centroid.y
    
    return gdf

def get_retail_color(retail_class):
    """Generate RGB color based on retail class"""
    colors = {
        'High': [220, 38, 38, 200],      # Red
        'Medium': [245, 158, 11, 200],   # Orange
        'Low': [16, 185, 129, 200],      # Green
    }
    return colors.get(retail_class, [156, 163, 175, 150])  # Gray default

def get_color_scale(value, vmin, vmax):
    """Generate RGB color based on continuous value (Red-Yellow-Green)"""
    if pd.isna(value):
        return [200, 200, 200, 100]  # Gray untuk null
    
    # Normalize value to 0-1
    normalized = (value - vmin) / (vmax - vmin) if vmax > vmin else 0.5
    normalized = max(0, min(1, normalized))  # Clamp to 0-1
    
    # Red-Yellow-Green color scale
    if normalized < 0.5:
        # Red to Yellow
        r = 255
        g = int(normalized * 2 * 255)
        b = 0
    else:
        # Yellow to Green
        r = int(255 - (normalized - 0.5) * 2 * 255)
        g = 255
        b = 0
    
    alpha = int(150 + (normalized * 105))  # 150-255
    return [r, g, b, alpha]

# =========================================================
# SIDEBAR - DATA SELECTION
# =========================================================
st.sidebar.title("⚙️ Settings")

# List available datasets
data_files = {
    "OKU": "data/grid_retail_expansion_score_oku.gpkg",
    "Tangsel": "data/grid_retail_expansion_score_tangsel.gpkg"
}

# Dataset selector
selected_dataset = st.sidebar.selectbox(
    "Pilih Dataset:",
    options=list(data_files.keys())
)

# File upload option
uploaded_file = st.sidebar.file_uploader(
    "Atau Upload File (Optional)",
    type=['gpkg', 'shp', 'geojson']
)

if uploaded_file is not None:
    temp_path = Path("temp_upload")
    temp_path.parent.mkdir(exist_ok=True)
    
    if uploaded_file.name.endswith('.gpkg'):
        temp_file = temp_path.with_suffix('.gpkg')
    elif uploaded_file.name.endswith('.geojson'):
        temp_file = temp_path.with_suffix('.geojson')
    else:
        temp_file = temp_path.with_suffix('.shp')
    
    with open(temp_file, "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    try:
        gdf = load_grid_data(temp_file)
        st.sidebar.success(f"✅ File uploaded: {len(gdf):,} features")
        dataset_name = uploaded_file.name
    except Exception as e:
        st.error(f"Error loading file: {str(e)}")
        st.stop()
else:
    try:
        selected_path = data_files[selected_dataset]
        gdf = load_grid_data(selected_path)
        st.sidebar.info(f"📁 Dataset: {selected_dataset} ({len(gdf):,} features)")
        dataset_name = selected_dataset
    except Exception as e:
        st.error(f"Error loading {selected_dataset} data: {str(e)}")
        st.stop()

# Tentukan kolom landuse berdasarkan dataset
if 'Keterangan' in gdf.columns:
    landuse_col = 'Keterangan'
elif 'KELAS_2' in gdf.columns:
    landuse_col = 'KELAS_2'
else:
    landuse_col = None

# =========================================================
# FILTER
# =========================================================
st.sidebar.subheader("🔍 Filter Data")

# Filter retail_class
if 'retail_class' in gdf.columns:
    retail_options = ['All'] + sorted(gdf['retail_class'].dropna().unique().tolist())
    selected_retail = st.sidebar.selectbox("Filter Retail Class", retail_options)
    if selected_retail != 'All':
        gdf = gdf[gdf['retail_class'] == selected_retail]

# Filter flood_class
if 'flood_class' in gdf.columns:
    flood_options = ['All'] + sorted(gdf['flood_class'].dropna().unique().tolist())
    selected_flood = st.sidebar.selectbox("Filter Flood Class", flood_options)
    if selected_flood != 'All':
        gdf = gdf[gdf['flood_class'] == selected_flood]

# Filter landuse (KELAS_2 atau Keterangan)
if landuse_col:
    landuse_options = ['All'] + sorted(gdf[landuse_col].dropna().unique().tolist())
    selected_landuse = st.sidebar.selectbox(f"Filter {landuse_col}", landuse_options)
    if selected_landuse != 'All':
        gdf = gdf[gdf[landuse_col] == selected_landuse]

# Filter retail_score minimum
if 'retail_score' in gdf.columns:
    min_score = gdf['retail_score'].min()
    max_score = gdf['retail_score'].max()
    selected_min_score = st.sidebar.slider(
        "Retail Score Minimum",
        min_value=float(min_score),
        max_value=float(max_score),
        value=float(min_score),
        format="%.4f"
    )
    gdf = gdf[gdf['retail_score'] >= selected_min_score]

# =========================================================
# MAIN CONTENT
# =========================================================
st.title("🏪 Grid Retail Expansion Score Dashboard")
st.markdown("Dashboard untuk analisis potensi ekspansi retail berdasarkan grid dasymetric")
st.markdown("---")

# Metrics
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total Grid", f"{len(gdf):,}")

with col2:
    if 'retail_class' in gdf.columns:
        high_retail = (gdf['retail_class'] == 'High').sum()
        st.metric("Grid Retail Class: High", f"{high_retail:,}", 
                 delta=f"{high_retail/len(gdf)*100:.1f}%")

with col3:
    if 'pop_dasymetric' in gdf.columns:
        st.metric("Total Populasi", f"{gdf['pop_dasymetric'].sum():,.0f}")

with col4:
    if 'access_idx' in gdf.columns:
        akses = (gdf['access_idx'] == 1).sum()
        st.metric("Grid dgn Akses", f"{akses:,}")

st.markdown("---")

# =========================================================
# TABS
# =========================================================
tab1, tab2, tab3, tab4 = st.tabs([
    "🗺️ Peta Retail Class",
    "📊 Statistik",
    "📈 Charts",
    "📋 Data Table"
])

# =========================================================
# TAB 1: PETA POLYGON (PYDECK)
# =========================================================
with tab1:
    st.subheader("Peta Grid Retail Expansion Score")
    
    # Pilih mode visualisasi
    viz_mode = st.radio(
        "Mode Visualisasi:",
        ["Retail Class (Kategori)", "Retail Score (Continuous)"],
        horizontal=True
    )
    
    # Prepare data untuk pydeck
    gdf_plot = gdf.copy()
    
    if len(gdf_plot) > 0:
        # Convert geometries to GeoJSON
        gdf_plot['coordinates'] = gdf_plot.geometry.apply(
            lambda x: [[[coord[0], coord[1]] for coord in x.exterior.coords]]
        )
        
        # Add color column based on mode
        if viz_mode == "Retail Class (Kategori)" and 'retail_class' in gdf_plot.columns:
            gdf_plot = gdf_plot.dropna(subset=['retail_class'])
            gdf_plot['fill_color'] = gdf_plot['retail_class'].apply(get_retail_color)
            color_by = 'retail_class'
        else:
            if 'retail_score' in gdf_plot.columns:
                gdf_plot = gdf_plot.dropna(subset=['retail_score'])
                vmin = gdf_plot['retail_score'].min()
                vmax = gdf_plot['retail_score'].max()
                gdf_plot['fill_color'] = gdf_plot['retail_score'].apply(
                    lambda x: get_color_scale(x, vmin, vmax)
                )
                color_by = 'retail_score'
        
        # Calculate center
        center_lat = gdf_plot['lat'].mean()
        center_lon = gdf_plot['lon'].mean()
        
        # Create PyDeck layer
        polygon_layer = pdk.Layer(
            'PolygonLayer',
            data=gdf_plot,
            get_polygon='coordinates',
            get_fill_color='fill_color',
            get_line_color=[80, 80, 80, 150],
            get_line_width=10,
            pickable=True,
            auto_highlight=True,
            line_width_min_pixels=0.5
        )
        
        # Tooltip - tampilkan kolom penting
        tooltip_html = "<b>Grid ID:</b> {gid}<br/>"
        
        # Kolom yang akan ditampilkan di tooltip
        important_cols = ['retail_class', 'retail_score', landuse_col, 'pop_dasymetric', 
                         'flood_class', 'demand_idx', 'flood_risk_idx', 'access_idx',
                         'akses_jalan_utama', 'akses_jalan_arteri', 'akses_jalan_kolektor']
        
        # Filter kolom yang benar-benar ada
        important_cols = [col for col in important_cols if col and col in gdf_plot.columns]
        
        for col in important_cols:
            tooltip_html += f"<b>{col}:</b> {{{col}}}<br/>"
        
        tooltip = {
            "html": tooltip_html,
            "style": {
                "backgroundColor": "rgba(0, 0, 0, 0.8)",
                "color": "white",
                "fontSize": "11px",
                "padding": "8px",
                "borderRadius": "4px"
            }
        }
        
        # Create map
        view_state = pdk.ViewState(
            latitude=center_lat,
            longitude=center_lon,
            zoom=11,
            pitch=0,
            bearing=0
        )
        
        deck = pdk.Deck(
            layers=[polygon_layer],
            initial_view_state=view_state,
            tooltip=tooltip,
            map_style='mapbox://styles/mapbox/light-v10'
        )
        
        st.pydeck_chart(deck, use_container_width=True)
        
        # Legend
        st.markdown(f"**Legend:** {color_by}")
        
        if viz_mode == "Retail Class (Kategori)":
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                st.markdown("🔴 **High**: Potensi tinggi")
            with col_b:
                st.markdown("🟠 **Medium**: Potensi sedang")
            with col_c:
                st.markdown("🟢 **Low**: Potensi rendah")
        else:
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                st.metric("Min Score", f"{vmin:.4f}")
            with col_b:
                st.metric("Mean Score", f"{gdf_plot['retail_score'].mean():.4f}")
            with col_c:
                st.metric("Max Score", f"{vmax:.4f}")

# =========================================================
# TAB 2: STATISTIK
# =========================================================
with tab2:
    st.subheader("Statistik Deskriptif")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if 'retail_score' in gdf.columns:
            st.markdown("### Retail Score")
            retail_stats = gdf['retail_score'].describe()
            st.dataframe(retail_stats, use_container_width=True)
        
        if 'demand_idx' in gdf.columns:
            st.markdown("### Demand Index")
            demand_stats = gdf['demand_idx'].describe()
            st.dataframe(demand_stats, use_container_width=True)
    
    with col2:
        if 'pop_dasymetric' in gdf.columns:
            st.markdown("### Populasi")
            pop_stats = gdf['pop_dasymetric'].describe()
            st.dataframe(pop_stats, use_container_width=True)
        
        if 'flood_risk_idx' in gdf.columns:
            st.markdown("### Flood Risk Index")
            flood_stats = gdf['flood_risk_idx'].describe()
            st.dataframe(flood_stats, use_container_width=True)
    
    # Crosstab
    st.markdown("---")
    if 'retail_class' in gdf.columns and 'flood_class' in gdf.columns:
        st.markdown("### Crosstab: Retail Class vs Flood Class")
        crosstab = pd.crosstab(
            gdf['retail_class'].fillna('NULL'),
            gdf['flood_class'].fillna('No Flood'),
            margins=True
        )
        st.dataframe(crosstab, use_container_width=True)
    
    if 'retail_class' in gdf.columns and landuse_col:
        st.markdown(f"### Crosstab: Retail Class vs {landuse_col}")
        crosstab2 = pd.crosstab(
            gdf['retail_class'].fillna('NULL'),
            gdf[landuse_col].fillna('NULL'),
            margins=True
        )
        st.dataframe(crosstab2, use_container_width=True)

# =========================================================
# TAB 3: CHARTS
# =========================================================
with tab3:
    st.subheader("Visualisasi Charts")
    
    chart_col1, chart_col2 = st.columns(2)
    
    with chart_col1:
        if 'retail_class' in gdf.columns:
            retail_count = gdf['retail_class'].value_counts().reset_index()
            retail_count.columns = ['Retail Class', 'Count']
            
            fig_bar = px.bar(
                retail_count,
                x='Retail Class',
                y='Count',
                title="Distribusi Grid per Retail Class",
                color='Retail Class',
                color_discrete_map={'High': '#dc2626', 'Medium': '#f59e0b', 'Low': '#10b981'}
            )
            st.plotly_chart(fig_bar, use_container_width=True)
    
    with chart_col2:
        if 'retail_score' in gdf.columns:
            fig_hist = px.histogram(
                gdf,
                x='retail_score',
                nbins=50,
                title="Distribusi Retail Score",
                color_discrete_sequence=['#3b82f6']
            )
            st.plotly_chart(fig_hist, use_container_width=True)
    
    # Box plots
    chart_col3, chart_col4 = st.columns(2)
    
    with chart_col3:
        if 'retail_class' in gdf.columns and 'demand_idx' in gdf.columns:
            fig_box1 = px.box(
                gdf.dropna(subset=['retail_class']),
                x='retail_class',
                y='demand_idx',
                title="Demand Index per Retail Class",
                color='retail_class',
                color_discrete_map={'High': '#dc2626', 'Medium': '#f59e0b', 'Low': '#10b981'}
            )
            st.plotly_chart(fig_box1, use_container_width=True)
    
    with chart_col4:
        if 'retail_class' in gdf.columns and 'pop_dasymetric' in gdf.columns:
            fig_box2 = px.box(
                gdf.dropna(subset=['retail_class']),
                x='retail_class',
                y='pop_dasymetric',
                title="Populasi per Retail Class",
                color='retail_class',
                color_discrete_map={'High': '#dc2626', 'Medium': '#f59e0b', 'Low': '#10b981'}
            )
            st.plotly_chart(fig_box2, use_container_width=True)
    
    # Scatter plot
    if 'demand_idx' in gdf.columns and 'flood_risk_idx' in gdf.columns and 'retail_class' in gdf.columns:
        st.markdown("### Scatter Plot: Demand Index vs Flood Risk Index")
        
        # Siapkan hover data
        hover_data_cols = ['gid', 'retail_score']
        if landuse_col:
            hover_data_cols.append(landuse_col)
        
        fig_scatter = px.scatter(
            gdf.dropna(subset=['demand_idx', 'flood_risk_idx', 'retail_class']),
            x='demand_idx',
            y='flood_risk_idx',
            color='retail_class',
            title="Hubungan Demand Index dan Flood Risk Index",
            color_discrete_map={'High': '#dc2626', 'Medium': '#f59e0b', 'Low': '#10b981'},
            hover_data=hover_data_cols
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

# =========================================================
# TAB 4: DATA TABLE
# =========================================================
with tab4:
    st.subheader("Data Table")
    
    all_cols = [col for col in gdf.columns if col not in ['geometry', 'coordinates', 'fill_color', 'lon', 'lat']]
    
    # Default columns
    default_cols = ['gid', 'retail_class', 'retail_score', landuse_col, 'pop_dasymetric', 
                   'flood_class', 'demand_idx', 'flood_risk_idx', 'access_idx']
    default_cols = [col for col in default_cols if col and col in all_cols]
    
    display_cols = st.multiselect(
        "Pilih kolom untuk ditampilkan:",
        all_cols,
        default=default_cols
    )
    
    if display_cols:
        # Show data
        st.dataframe(
            gdf[display_cols].head(1000),
            use_container_width=True,
            height=400
        )
        
        st.info(f"Menampilkan {min(1000, len(gdf)):,} dari {len(gdf):,} baris")
        
        # Download button
        csv = gdf[display_cols].to_csv(index=False)
        st.download_button(
            label="📥 Download CSV",
            data=csv,
            file_name=f"retail_expansion_{dataset_name}.csv",
            mime="text/csv"
        )

# =========================================================
# FOOTER
# =========================================================
st.markdown("---")
st.markdown(
    f"""
    <div style='text-align: center'>
        <p><strong>Grid Retail Expansion Score Dashboard</strong> - {dataset_name}</p>
        <p style='font-size: 12px;'>Powered by PyDeck & Streamlit | Data: {len(gdf):,} grid features</p>
    </div>
    """,
    unsafe_allow_html=True
)