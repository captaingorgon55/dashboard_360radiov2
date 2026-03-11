import pandas as pd
import streamlit as st

@st.cache_data
def load_all_data():
    # GA4
    ga_diario = pd.read_excel('data/ga4_360radio_completo.xlsx', sheet_name='📊_General_Diario')
    ga_canales = pd.read_excel('data/ga4_360radio_completo.xlsx', sheet_name='📈_General_x_Canal')
    ga_ciudad = pd.read_excel('data/ga4_360radio_completo.xlsx', sheet_name='🏙️_General_x_Ciudad')
    ga_pais = pd.read_excel('data/ga4_360radio_completo.xlsx', sheet_name='🌎_General_x_Pais')
    ga_edad = pd.read_excel('data/ga4_360radio_completo.xlsx', sheet_name='👤_General_x_Edad')
    ga_device = pd.read_excel('data/ga4_360radio_completo.xlsx', sheet_name='📱_General_x_Device')
    
    # Producción + unir con GA4 para tráfico
    produccion = pd.read_csv('data/Produccion.csv')
    # Asumimos que tienes page_path en GA4 o extraes de URL en Produccion
    # Merge por URL/post_id (ajusta según tu estructura real)
    ga_paginas = pd.read_excel('data/ga4_360radio_completo.xlsx', sheet_name='📊_General_Diario')  # Ajusta si tienes sheet de páginas
    
    # Search Console
    sc_queries = pd.read_excel('data/search_console_360radio.xlsx', sheet_name='🔍_GSC_Queries')
    sc_paginas = pd.read_excel('data/search_console_360radio.xlsx', sheet_name='🌐_GSC_Paginas')
    
    # Ads
    adsense = pd.read_csv('data/Adsense.csv')
    admanager_diario = pd.read_excel('data/admanager_360radio.xlsx', sheet_name='GAM_Diario')
    mgid = pd.read_csv('data/MGID.csv')
    
    # Social (simplificado - procesa fechas)
    fb_posts = pd.read_csv('data/Post Facebook.csv')
    ig_posts = pd.read_csv('data/Post Instagram.csv')
    yt_data = pd.read_excel('data/Youtube histórico.xlsx', sheet_name='Datos de la tabla')
    
    # Notas IA: filtrar tags síntesis en Produccion
    notas_ia = produccion[produccion['tags'].str.contains('síntesis', na=False)]
    
    return {
        'ga_diario': ga_diario, 'ga_canales': ga_canales, 'ga_ciudad': ga_ciudad,
        'ga_pais': ga_pais, 'ga_edad': ga_edad, 'ga_device': ga_device,
        'produccion': produccion, 'notas_ia': notas_ia,
        'sc_queries': sc_queries, 'sc_paginas': sc_paginas,
        'adsense': adsense, 'admanager': admanager_diario, 'mgid': mgid,
        'social': {'fb': fb_posts, 'ig': ig_posts, 'yt': yt_data}
    }
