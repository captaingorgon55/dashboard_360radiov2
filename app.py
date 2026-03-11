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

/* ── Base ─────────────────────────────────────────── */
html, body, [class*="css"]          { font-family: 'Inter', sans-serif; }
h1,h2,h3,h4,.stMetric label         { font-family: 'Syne', sans-serif; }

/* ── Sidebar ──────────────────────────────────────── */
[data-testid="stSidebar"]           { background: #080812 !important; border-right: 1px solid #1e1e3a; }
[data-testid="stSidebar"] *         { color: #c8cedc !important; }
[data-testid="stSidebar"] hr        { border-color: #1e1e3a !important; }

/* logo sidebar */
.sidebar-logo {
    font-family: 'Syne', sans-serif;
    font-size: 1.4rem;
    font-weight: 800;
    background: linear-gradient(135deg, #6366f1, #06b6d4);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    letter-spacing: -0.5px;
    margin-bottom: 4px;
}
.sidebar-sub {
    font-size: 0.7rem;
    color: #4a5078 !important;
    text-transform: uppercase;
    letter-spacing: 0.12em;
}

/* ── Main content ─────────────────────────────────── */
.main .block-container     { padding: 1.5rem 2rem 2rem; max-width: 1600px; }
.stApp                     { background: #0a0a14; }

/* ── Metric cards ────────────────────────────────── */
[data-testid="stMetric"] {
    background: linear-gradient(145deg, #12122a 0%, #161630 100%);
    border: 1px solid #252550;
    border-radius: 14px;
    padding: 1.1rem 1.3rem;
    transition: border-color .2s;
}
[data-testid="stMetric"]:hover    { border-color: #4f46e5; }
[data-testid="stMetricValue"]     { color: #e8ecff !important; font-family:'Syne',sans-serif; font-size:1.75rem !important; font-weight:700; }
[data-testid="stMetricLabel"]     { color: #5c6490 !important; font-size:0.7rem !important; text-transform:uppercase; letter-spacing:.1em; }
[data-testid="stMetricDelta"]     { font-size:0.78rem !important; }

/* ── Section header ─────────────────────────────── */
.sec-hdr {
    font-family: 'Syne', sans-serif;
    font-size: 0.95rem;
    font-weight: 700;
    color: #a5b4fc;
    border-left: 3px solid #6366f1;
    padding: 2px 0 2px 10px;
    margin: 1.6rem 0 0.8rem;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}

/* ── Filtros box ─────────────────────────────────── */
.filter-box {
    background: #0f0f22;
    border: 1px solid #1e1e3a;
    border-radius: 12px;
    padding: 1rem 1.2rem 0.5rem;
    margin-bottom: 1rem;
}

/* ── Tabs ────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    gap: 3px;
    background: #0d0d1e;
    border-radius: 10px;
    padding: 4px;
    border: 1px solid #1a1a30;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 7px;
    color: #5c6490 !important;
    font-family: 'Syne', sans-serif;
    font-weight: 600;
    font-size: 0.8rem;
    padding: 6px 14px;
    transition: all .2s;
}
.stTabs [aria-selected="true"] {
    background: #4f46e5 !important;
    color: #ffffff !important;
}

/* ── DataFrames ──────────────────────────────────── */
[data-testid="stDataFrame"]        { border-radius: 10px; overflow: hidden; border: 1px solid #1e1e3a; }
[data-testid="stDataFrame"] table  { background: #0d0d1e !important; }
[data-testid="stDataFrame"] th     { background: #161630 !important; color: #8892b0 !important; font-size:0.72rem; text-transform:uppercase; }
[data-testid="stDataFrame"] td     { color: #c8cedc !important; font-size:0.83rem; }

/* ── Progress bar ────────────────────────────────── */
.stProgress > div > div            { background: linear-gradient(90deg,#4f46e5,#06b6d4); border-radius:4px; }

/* ── Selectbox / date input ──────────────────────── */
[data-testid="stSelectbox"] > div,
[data-testid="stDateInput"] > div  { background: #0f0f22 !important; border: 1px solid #252550 !important; border-radius: 8px !important; }

/* ── Info / warning boxes ───────────────────────── */
.stAlert                           { border-radius: 10px; border-left-width: 4px; }

/* ── Divider ─────────────────────────────────────── */
hr                                 { border-color: #1a1a30 !important; margin: 1rem 0 !important; }

/* ── Page title ──────────────────────────────────── */
.page-title {
    font-family: 'Syne', sans-serif;
    font-size: 1.6rem;
    font-weight: 800;
    color: #e8ecff;
    margin-bottom: 0.2rem;
}
.page-subtitle {
    font-size: 0.8rem;
    color: #4a5078;
    margin-bottom: 1.2rem;
    letter-spacing: 0.05em;
}
</style>
""", unsafe_allow_html=True)

# ── Navegación sidebar ─────────────────────────────────────────────────────────
PAGES = {
    "🏠  General · Tráfico":     "pages/general.py",
    "🔍  Search Console":         "pages/search.py",
    "📱  Social Media":           "pages/social.py",
    "💰  Ads y Monetización":     "pages/ads.py",
    "📣  Pauta":                  "pages/pauta.py",
}

with st.sidebar:
    st.markdown('<div class="sidebar-logo">🎙️ 360Radio</div>', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-sub">Analytics Dashboard</div>', unsafe_allow_html=True)
    st.markdown("---")
    selection = st.radio("", list(PAGES.keys()), label_visibility="collapsed")
    st.markdown("---")
    st.markdown('<span style="font-size:.68rem;color:#2e3155">v2.1 · Datos en tiempo real</span>', unsafe_allow_html=True)

page_path = PAGES[selection]
with open(page_path, encoding="utf-8") as f:
    exec(compile(f.read(), page_path, "exec"), {"__name__": "__main__"})
