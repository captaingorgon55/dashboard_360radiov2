import os
import shutil
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="360Radio · Analytics",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

CACHE_DIR = Path(".parquet_cache")


def clear_all_cache():
    try:
        st.cache_data.clear()
    except Exception:
        pass

    try:
        st.cache_resource.clear()
    except Exception:
        pass

    try:
        if CACHE_DIR.exists():
            shutil.rmtree(CACHE_DIR, ignore_errors=True)
    except Exception:
        pass

    try:
        CACHE_DIR.mkdir(exist_ok=True)
    except Exception:
        pass


def _rows_count(obj):
    try:
        if isinstance(obj, pd.DataFrame):
            return len(obj)
        return len(obj)
    except Exception:
        return 0


def run_all_loaders():
    from data_loader import (
        load_ga4_general,
        load_ga4_city,
        load_ga4_country,
        load_ga4_channel,
        load_ga4_age,
        load_ga4_device,
        load_ga4_interests,
        load_ga4_urls,
        load_search_console,
        load_adsense,
        load_mgid,
        load_admanager,
        load_youtube,
        load_instagram_posts,
        load_instagram_stories,
        load_facebook,
        load_produccion_con_metricas,
        load_por_autor,
        load_por_categoria,
    )

    results = {}

    try:
        df = load_ga4_general()
        results["GA4 General"] = f"{_rows_count(df):,} filas"
    except Exception as e:
        results["GA4 General"] = f"ERROR: {e}"

    try:
        df = load_ga4_city()
        results["GA4 Ciudad"] = f"{_rows_count(df):,} filas"
    except Exception as e:
        results["GA4 Ciudad"] = f"ERROR: {e}"

    try:
        df = load_ga4_country()
        results["GA4 País"] = f"{_rows_count(df):,} filas"
    except Exception as e:
        results["GA4 País"] = f"ERROR: {e}"

    try:
        df = load_ga4_channel()
        results["GA4 Canal"] = f"{_rows_count(df):,} filas"
    except Exception as e:
        results["GA4 Canal"] = f"ERROR: {e}"

    try:
        df = load_ga4_age()
        results["GA4 Edad"] = f"{_rows_count(df):,} filas"
    except Exception as e:
        results["GA4 Edad"] = f"ERROR: {e}"

    try:
        df = load_ga4_device()
        results["GA4 Device"] = f"{_rows_count(df):,} filas"
    except Exception as e:
        results["GA4 Device"] = f"ERROR: {e}"

    try:
        df = load_ga4_interests()
        results["GA4 Interests"] = f"{_rows_count(df):,} filas"
    except Exception as e:
        results["GA4 Interests"] = f"ERROR: {e}"

    try:
        df = load_ga4_urls()
        results["GA4 URLs"] = f"{_rows_count(df):,} filas"
    except Exception as e:
        results["GA4 URLs"] = f"ERROR: {e}"

    try:
        sc = load_search_console()
        results["Search Console · daily"] = f"{_rows_count(sc.get('daily', pd.DataFrame())):,} filas"
        results["Search Console · queries"] = f"{_rows_count(sc.get('queries', pd.DataFrame())):,} filas"
        results["Search Console · pages"] = f"{_rows_count(sc.get('pages', pd.DataFrame())):,} filas"
        results["Search Console · country"] = f"{_rows_count(sc.get('country', pd.DataFrame())):,} filas"
        results["Search Console · device"] = f"{_rows_count(sc.get('device', pd.DataFrame())):,} filas"
    except Exception as e:
        results["Search Console"] = f"ERROR: {e}"

    try:
        df = load_adsense()
        results["AdSense"] = f"{_rows_count(df):,} filas"
    except Exception as e:
        results["AdSense"] = f"ERROR: {e}"

    try:
        df = load_mgid()
        results["MGID"] = f"{_rows_count(df):,} filas"
    except Exception as e:
        results["MGID"] = f"ERROR: {e}"

    try:
        gam = load_admanager()
        results["AdManager · diario"] = f"{_rows_count(gam.get('diario', pd.DataFrame())):,} filas"
        results["AdManager · mensual"] = f"{_rows_count(gam.get('mensual', pd.DataFrame())):,} filas"
        results["AdManager · formatos"] = f"{_rows_count(gam.get('formatos', pd.DataFrame())):,} filas"
        results["AdManager · devices"] = f"{_rows_count(gam.get('devices', pd.DataFrame())):,} filas"
        results["AdManager · fill"] = f"{_rows_count(gam.get('fill', pd.DataFrame())):,} filas"
        results["AdManager · orders"] = f"{_rows_count(gam.get('orders', pd.DataFrame())):,} filas"
    except Exception as e:
        results["AdManager"] = f"ERROR: {e}"

    try:
        yt = load_youtube()
        yt_tabla = yt.get("tabla", pd.DataFrame()) if isinstance(yt, dict) else pd.DataFrame()
        yt_grafico = yt.get("grafico", pd.DataFrame()) if isinstance(yt, dict) else pd.DataFrame()

        tabla_cols = ", ".join(list(yt_tabla.columns[:6])) if not yt_tabla.empty else "sin columnas"
        graf_cols = ", ".join(list(yt_grafico.columns[:6])) if not yt_grafico.empty else "sin columnas"

        results["YouTube · tabla"] = f"{_rows_count(yt_tabla):,} filas"
        results["YouTube · gráfico"] = f"{_rows_count(yt_grafico):,} filas"
        results["YouTube · cols tabla"] = tabla_cols
        results["YouTube · cols gráfico"] = graf_cols
    except Exception as e:
        results["YouTube"] = f"ERROR: {e}"

    try:
        df = load_instagram_posts()
        results["Instagram Posts"] = f"{_rows_count(df):,} filas"
    except Exception as e:
        results["Instagram Posts"] = f"ERROR: {e}"

    try:
        df = load_instagram_stories()
        results["Instagram Stories"] = f"{_rows_count(df):,} filas"
    except Exception as e:
        results["Instagram Stories"] = f"ERROR: {e}"

    try:
        df = load_facebook()
        results["Facebook"] = f"{_rows_count(df):,} filas"
    except Exception as e:
        results["Facebook"] = f"ERROR: {e}"

    try:
        df = load_produccion_con_metricas()
        results["Producción + métricas"] = f"{_rows_count(df):,} filas"
        if not df.empty:
            results["Producción · columnas"] = ", ".join(list(df.columns[:8]))
    except Exception as e:
        results["Producción + métricas"] = f"ERROR: {e}"

    try:
        df = load_por_autor()
        results["Producción · por autor"] = f"{_rows_count(df):,} filas"
    except Exception as e:
        results["Producción · por autor"] = f"ERROR: {e}"

    try:
        df = load_por_categoria()
        results["Producción · por categoría"] = f"{_rows_count(df):,} filas"
    except Exception as e:
        results["Producción · por categoría"] = f"ERROR: {e}"

    st.session_state["loader_results"] = results


st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=Inter:wght@300;400;500;600&display=swap');

/* ── Reset base ─────────────────────────────────────────────── */
html,body,[class*="css"]     { font-family:'Inter',sans-serif; }
h1,h2,h3,h4                  { font-family:'Syne',sans-serif; }

/* ── Ocultar navegación automática de Streamlit ─────────────── */
[data-testid="stSidebarNav"],
section[data-testid="stSidebarNav"],
.st-emotion-cache-1cypcdb,
ul[data-testid="stSidebarNavItems"]  { display:none !important; }

/* ── Sidebar ─────────────────────────────────────────────────── */
[data-testid="stSidebar"]            { background:#07071a !important; border-right:1px solid #18183a; width:220px !important; }
[data-testid="stSidebar"] *          { color:#b8c0e0 !important; }

/* Logo */
.sb-logo   { font-family:'Syne',sans-serif; font-size:1.45rem; font-weight:800;
             background:linear-gradient(135deg,#6366f1 30%,#06b6d4);
             -webkit-background-clip:text; -webkit-text-fill-color:transparent;
             line-height:1.2; }
.sb-sub    { font-size:0.63rem; color:#2e3460 !important; text-transform:uppercase;
             letter-spacing:0.14em; margin-top:2px; }
.sb-divider{ border:none; border-top:1px solid #18183a; margin:12px 0; }

/* Nav items — radio buttons disfrazados */
[data-testid="stSidebar"] .stRadio > div            { gap:2px; }
[data-testid="stSidebar"] .stRadio label            { display:flex; align-items:center;
    gap:10px; padding:9px 14px; border-radius:10px; cursor:pointer;
    font-size:0.82rem; font-weight:500; color:#7880a8 !important;
    transition:all .18s; border:1px solid transparent; }
[data-testid="stSidebar"] .stRadio label:hover      { background:#12123a; color:#c8d0f0 !important; border-color:#25254a; }
[data-testid="stSidebar"] .stRadio [data-checked="true"] ~ label,
[data-testid="stSidebar"] .stRadio input:checked + div label { background:#1a1a42; color:#a5b4fc !important;
    border-color:#4f46e5; font-weight:600; }
[data-testid="stSidebar"] .stRadio [data-baseweb="radio"] > div:first-child { display:none; }

/* ── Main ────────────────────────────────────────────────────── */
.main .block-container   { padding:1.4rem 2rem 2rem; max-width:1640px; }
.stApp                   { background:#080814; }

/* ── Metric cards ────────────────────────────────────────────── */
[data-testid="stMetric"]        { background:linear-gradient(145deg,#0f0f28,#141438);
    border:1px solid #20204a; border-radius:14px; padding:1rem 1.2rem; transition:.2s; }
[data-testid="stMetric"]:hover  { border-color:#4f46e5; box-shadow:0 0 0 1px #4f46e5; }
[data-testid="stMetricValue"]   { color:#e8ecff !important; font-family:'Syne',sans-serif;
    font-size:1.7rem !important; font-weight:700 !important; }
[data-testid="stMetricLabel"]   { color:#4a5280 !important; font-size:0.67rem !important;
    text-transform:uppercase; letter-spacing:.1em; }
[data-testid="stMetricDelta"]   { font-size:0.77rem !important; }

/* ── Section headers ─────────────────────────────────────────── */
.sec-hdr { font-family:'Syne',sans-serif; font-size:0.82rem; font-weight:700;
    color:#818cf8; border-left:3px solid #4f46e5; padding:1px 0 1px 10px;
    margin:1.4rem 0 0.7rem; letter-spacing:0.06em; text-transform:uppercase; }

/* ── Filter box ──────────────────────────────────────────────── */
.filter-box { background:#0c0c24; border:1px solid #1a1a36; border-radius:12px;
    padding:.9rem 1.1rem .4rem; margin-bottom:.9rem; }

/* ── Tabs ────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"]  { gap:2px; background:#0a0a1e; border-radius:10px;
    padding:3px; border:1px solid #181836; }
.stTabs [data-baseweb="tab"]       { border-radius:7px; color:#4a5280 !important;
    font-family:'Syne',sans-serif; font-weight:600; font-size:0.77rem; padding:6px 16px; }
.stTabs [aria-selected="true"]     { background:#4f46e5 !important; color:#fff !important; }

/* ── DataFrames ──────────────────────────────────────────────── */
[data-testid="stDataFrame"]       { border-radius:10px; overflow:hidden; border:1px solid #1a1a36; }

/* ── Progress ────────────────────────────────────────────────── */
.stProgress > div > div { background:linear-gradient(90deg,#4f46e5,#06b6d4); border-radius:4px; }

/* ── Alerts ──────────────────────────────────────────────────── */
.stAlert { border-radius:10px; }

.page-title    { font-family:'Syne',sans-serif; font-size:1.55rem; font-weight:800;
    color:#e8ecff; margin-bottom:.15rem; }
.page-subtitle { font-size:0.75rem; color:#3a4070; margin-bottom:1rem; letter-spacing:.06em; }

[data-testid="stSelectbox"] > div > div,
[data-testid="stDateInput"] input  { background:#0c0c24 !important; border-color:#20204a !important; }
hr { border-color:#181836 !important; margin:.8rem 0 !important; }

.stButton > button {
    width:100%;
    border-radius:10px;
    border:1px solid #25254a;
    background:#11112d;
    color:#dbe4ff !important;
    font-weight:600;
}
.stButton > button:hover {
    border-color:#4f46e5;
    background:#17173b;
    color:#ffffff !important;
}
</style>
""", unsafe_allow_html=True)

PAGES = {
    "🏠  General · Tráfico":   "views/general.py",
    "🔍  Search Console":      "views/search.py",
    "📱  Social Media":        "views/social.py",
    "💰  Ads y Monetización":  "views/ads.py",
    "📣  Pauta":               "views/pauta.py",
}

with st.sidebar:
    st.markdown('<div class="sb-logo">🎙️ 360Radio</div>', unsafe_allow_html=True)
    st.markdown('<div class="sb-sub">Analytics Dashboard</div>', unsafe_allow_html=True)
    st.markdown('<hr class="sb-divider">', unsafe_allow_html=True)

    selection = st.radio(
        "nav",
        list(PAGES.keys()),
        label_visibility="collapsed",
        key="main_nav"
    )

    st.markdown('<hr class="sb-divider">', unsafe_allow_html=True)

    if st.button("🧹 Limpiar caché", use_container_width=True):
        clear_all_cache()
        st.session_state["loader_results"] = {"Sistema": "Caché limpiada correctamente"}
        st.rerun()

    if st.button("🔄 Recargar todo", use_container_width=True):
        st.rerun()

    if st.button("▶️ Ejecutar todos los loads", use_container_width=True):
        run_all_loaders()

    if "loader_results" in st.session_state:
        st.markdown('<hr class="sb-divider">', unsafe_allow_html=True)
        st.markdown("**Estado de cargas**")

        for k, v in st.session_state["loader_results"].items():
            txt = f"{k}: {v}"
            if str(v).startswith("ERROR"):
                st.error(txt)
            elif str(v).startswith("0 filas") or str(v) == "sin columnas":
                st.warning(txt)
            else:
                st.success(txt)

    st.markdown('<hr class="sb-divider">', unsafe_allow_html=True)
    st.markdown(
        '<span style="font-size:.62rem;color:#1e2040">v3.2 · 360Radio Analytics</span>',
        unsafe_allow_html=True
    )

page_path = PAGES[selection]

if not os.path.exists(page_path):
    st.error(f"No se encontró la vista: {page_path}")
    st.stop()

with open(page_path, encoding="utf-8") as fh:
    exec(compile(fh.read(), page_path, "exec"), {"__name__": "__main__"})
