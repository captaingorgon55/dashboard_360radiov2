import streamlit as st

st.set_page_config(
    page_title="360Radio · Analytics",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CSS global ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}
h1, h2, h3, .stMetric label {
    font-family: 'Syne', sans-serif;
}

/* sidebar */
[data-testid="stSidebar"] {
    background: #0d0d0d;
}
[data-testid="stSidebar"] * {
    color: #e8e8e8 !important;
}
[data-testid="stSidebar"] .stRadio label {
    font-size: 0.9rem;
}

/* metric cards */
[data-testid="stMetric"] {
    background: #1a1a2e;
    border: 1px solid #2a2a4a;
    border-radius: 12px;
    padding: 1rem 1.2rem;
}
[data-testid="stMetricValue"] {
    color: #e0e7ff !important;
    font-family: 'Syne', sans-serif;
    font-size: 1.8rem !important;
    font-weight: 700;
}
[data-testid="stMetricLabel"] {
    color: #8892b0 !important;
    font-size: 0.75rem !important;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}
[data-testid="stMetricDelta"] {
    font-size: 0.8rem !important;
}

/* dataframes */
[data-testid="stDataFrame"] {
    border-radius: 8px;
    overflow: hidden;
}

/* tabs */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    background: #111;
    border-radius: 8px;
    padding: 4px;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 6px;
    color: #888;
    font-family: 'Syne', sans-serif;
    font-weight: 600;
    font-size: 0.85rem;
}
.stTabs [aria-selected="true"] {
    background: #4f46e5 !important;
    color: white !important;
}

/* progress bar */
.stProgress > div > div {
    background-color: #4f46e5;
}

/* section headers */
.section-header {
    font-family: 'Syne', sans-serif;
    font-size: 1.1rem;
    font-weight: 700;
    color: #c7d2fe;
    border-left: 3px solid #4f46e5;
    padding-left: 10px;
    margin: 1.5rem 0 0.8rem;
}
</style>
""", unsafe_allow_html=True)

pages = {
    "🏠 General · Tráfico y Producción": "pages/general.py",
    "🔍 Search Console":                 "pages/search.py",
    "📱 Social Media":                   "pages/social.py",
    "💰 Ads y Monetización":             "pages/ads.py",
    "📣 Pauta":                          "pages/pauta.py",
}

with st.sidebar:
    st.markdown("## 🎙️ **360Radio**")
    st.markdown("### Analytics Dashboard")
    st.markdown("---")
    selection = st.radio("Sección", list(pages.keys()), label_visibility="collapsed")
    st.markdown("---")
    st.caption("v2.0 · Datos actualizados")

# Ejecutar la página seleccionada
page_path = pages[selection]

with open(page_path, encoding="utf-8") as f:
    exec(compile(f.read(), page_path, "exec"), {"__name__": "__main__"})
