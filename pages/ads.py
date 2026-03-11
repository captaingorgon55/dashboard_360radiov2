import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

def app(data, fecha_inicio, fecha_fin):
    st.header("💰 Ads y Monetización")
    
    # Cargar datos ads
    adsense = data['adsense']
    admanager = data['admanager']
    mgid = data['mgid']
    
    # Filtros
    col1, col2, col3 = st.columns(3)
    with col1: plataforma = st.selectbox("Plataforma", ['Todas', 'Adsense', 'AdManager', 'MGID'])
    with col2: fecha_inicio_ads = st.date_input("Fecha Ads", value=fecha_inicio)
    
    # Métricas generales
    revenue_total = adsense['Estimated earnings (USD)'].sum() + admanager['AD_SERVER_CPM_AND_CPC_REVENUE'].sum()
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Revenue Total", f"${revenue_total:.2f}")
    col2.metric("CPM Promedio", f"${admanager['AD_SERVER_WITHOUT_CPD_AVERAGE_ECPM'].mean():.2f}")
    col3.metric("CTR", f"{admanager['AD_SERVER_CTR'].mean():.2%}")
    col4.metric("Impresiones Ads", admanager['AD_SERVER_IMPRESSIONS'].sum())
    col5.metric("Clicks Totales", admanager['AD_SERVER_CLICKS'].sum())
    
    # Gráficos
    # 1. Evolución impresiones
    fig1 = make_subplots(specs=[[{"secondary_y": True}]])
    fig1.add_trace(go.Scatter(x=admanager['DATE'], y=admanager['AD_SERVER_IMPRESSIONS'], name="Impresiones"), secondary_y=False)
    fig1.add_trace(go.Scatter(x=admanager['DATE'], y=admanager['TOTAL_LINE_ITEM_LEVEL_IMPRESSIONS'], name="Sin Rellenar"), secondary_y=True)
    st.plotly_chart(fig1)
    
    # 2. Barras + Torta por plataforma
    col1, col2 = st.columns(2)
    with col1:
        plataformas = pd.DataFrame({
            'Plataforma': ['Adsense', 'AdManager', 'MGID'],
            'Revenue': [adsense['Estimated earnings (USD)'].sum(), admanager['AD_SERVER_CPM_AND_CPC_REVENUE'].sum(), mgid['Revenue'].sum()]
        })
        fig_bar = px.bar(plataformas, x='Plataforma', y='Revenue')
        st.plotly_chart(fig_bar)
    
    with col2:
        fig_pie = px.pie(plataformas, names='Plataforma', values='Revenue')
        st.plotly_chart(fig_pie)
    
    # 3. Tabla formatos
    formatos = admanager[admanager['CREATIVE_SIZE'].notna()][['CREATIVE_SIZE', 'AD_SERVER_IMPRESSIONS', 'AD_SERVER_WITHOUT_CPD_AVERAGE_ECPM', 'AD_SERVER_CPM_AND_CPC_REVENUE']]
    st.dataframe(formatos.head(10))
