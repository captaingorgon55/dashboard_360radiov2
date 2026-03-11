import streamlit as st
import plotly.express as px
import pandas as pd

def app(data, fecha_inicio, fecha_fin):
    st.header("🔍 Search Console")
    
    sc_diario = data['sc_queries'][(data['sc_queries']['date'] >= fecha_inicio) & 
                                  (data['sc_queries']['date'] <= fecha_fin)]
    
    # Métricas generales (último informe)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Queries Totales", sc_diario['query'].nunique())
    col2.metric("Impresiones Totales", sc_diario['impressions'].sum())
    col3.metric("URLs con Tráfico", sc_diario['page'].nunique())
    col4.metric("CTR Promedio", f"{sc_diario['ctr'].mean():.2%}")
    
    col1, col2 = st.columns(2)
    with col1:
        # Top queries
        top_queries = sc_diario.groupby('query')['clicks'].sum().sort_values(ascending=False).head(10)
        fig = px.bar(x=top_queries.index, y=top_queries.values, title="Top Queries")
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Top páginas
        top_paginas = sc_diario.groupby('page')['impressions'].sum().sort_values(ascending=False).head(10)
        st.dataframe(top_paginas)
    
    st.subheader("Tráfico por País")
    pais_trafico = sc_diario.groupby('country')['clicks'].sum().sort_values(ascending=False).head(10)
    fig_pais = px.bar(x=pais_trafico.index, y=pais_trafico.values)
    st.plotly_chart(fig_pais)
