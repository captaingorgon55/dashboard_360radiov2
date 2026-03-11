import streamlit as st
import pandas as pd
from data_loader import load_all_data
import pages.general as general
import pages.search as search
import pages.social as social
import pages.ads as ads
import pages.pauta as pauta

st.set_page_config(page_title="Dashboard 360Radio", layout="wide", page_icon="📊")

@st.cache_data
def load_data():
    return load_all_data()

data = load_data()

# Sidebar filtros globales
st.sidebar.title("🔧 Filtros Globales")
fecha_inicio = st.sidebar.date_input("Fecha inicio", value=pd.to_datetime('2025-01-01'))
fecha_fin = st.sidebar.date_input("Fecha fin", value=pd.to_datetime('today'))

# Navegación principal
page = st.sidebar.selectbox("📂 Navegación", [
    "📊 General Tráfico y Producción",
    "🔍 Search Console", 
    "📱 Social Media",
    "💰 Ads y Monetización",
    "📢 Pauta"
])

if page == "📊 General Tráfico y Producción":
    general.app(data, fecha_inicio, fecha_fin, 'Todas', 'Todos')
elif page == "🔍 Search Console":
    search.app(data, fecha_inicio, fecha_fin)
elif page == "📱 Social Media":
    social.app(data, fecha_inicio, fecha_fin)
elif page == "💰 Ads y Monetización":
    ads.app(data, fecha_inicio, fecha_fin)
elif page == "📢 Pauta":
    pauta.app(data, fecha_inicio, fecha_fin)

# Footer
st.markdown("---")
st.markdown("**Dashboard 360Radio** | Desarrollado con Streamlit | Marzo 2026")
