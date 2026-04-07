import streamlit as st

st.set_page_config(
    page_title="360Radio · Analytics",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

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
/* Punto activo */
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

/* ── Page title ──────────────────────────────────────────────── */
.page-title    { font-family:'Syne',sans-serif; font-size:1.55rem; font-weight:800;
    color:#e8ecff; margin-bottom:.15rem; }
.page-subtitle { font-size:0.75rem; color:#3a4070; margin-bottom:1rem; letter-spacing:.06em; }

/* ── Selectbox / inputs ──────────────────────────────────────── */
[data-testid="stSelectbox"] > div > div,
[data-testid="stDateInput"] input  { background:#0c0c24 !important; border-color:#20204a !important; }
hr { border-color:#181836 !important; margin:.8rem 0 !important; }
</style>
""", unsafe_allow_html=True)

# ── Páginas ────────────────────────────────────────────────────────────────────
PAGES = {
    "🏠  General · Tráfico":   "views/general.py",
    "🔍  Search Console":       "views/search.py",
    "📱  Social Media":         "views/social.py",
    "💰  Ads y Monetización":   "views/ads.py",
    "📣  Pauta":                "views/pauta.py",
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
    st.markdown('<span style="font-size:.62rem;color:#1e2040">v3.0 · 360Radio Analytics</span>',
                unsafe_allow_html=True)

page_path = PAGES[selection]
with open(page_path, encoding="utf-8") as fh:
    exec(compile(fh.read(), page_path, "exec"), {"__name__": "__main__"})
