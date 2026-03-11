import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

def app(data, fecha_inicio, fecha_fin, ciudad_filtro, autor_filtro):
    # Filtros aplicados
    df_ga = data['ga_diario'][(data['ga_diario']['date'] >= fecha_inicio) & 
                              (data['ga_diario']['date'] <= fecha_fin)]
    
    if ciudad_filtro != 'Todas':
        df_ga = df_ga[df_ga['city'] == ciudad_filtro]  # Ajusta merge si necesario
    
    st.header("📊 General Tráfico y Producción")
    
    # Métricas generales (3 columnas)
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Usuarios Activos", df_ga['activeUsers'].sum(), delta="10%")
    col2.metric("Usuarios Totales", df_ga['sessions'].sum())
    col3.metric("Vistas", df_ga['screenPageViews'].sum())
    col4.metric("Tiempo Promedio", f"{df_ga['userEngagementDuration'].mean():.0f}s")
    
    # Q1 Meta
    q1_usuarios = df_ga[df_ga['date'] <= '2026-03-31']['activeUsers'].sum()
    col5.metric("Status Q1 Meta", q1_usuarios, goal=750000, delta=f"{q1_usuarios/750000*100:.1f}%")
    
    st.subheader("Gráficos Detallados")
    
    # 1. Evolución usuarios vs vistas
    df_monthly = df_ga.groupby('year_month').agg({
        'activeUsers': 'sum', 'screenPageViews': 'sum'
    }).reset_index()
    fig1 = px.line(df_monthly, x='year_month', y=['activeUsers', 'screenPageViews'], 
                   title="Evolución Usuarios Activos vs Vistas")
    st.plotly_chart(fig1, use_container_width=True)
    
    # 2. Producción URLs (con tráfico unido)
    prod_trafico = data['produccion'].merge(df_ga, left_on='url', right_on='page_path', how='left')
    urls_con_trafico = prod_trafico[prod_trafico['screenPageViews'] > 0]['url'].nunique()
    st.metric("URLs con Tráfico", urls_con_trafico)
    
    # 3. Torta canales
    canales = data['ga_canales'].groupby('sessionDefaultChannelGroup').agg({
        'activeUsers': 'sum'
    }).reset_index()
    fig3 = px.pie(canales, names='sessionDefaultChannelGroup', values='activeUsers')
    st.plotly_chart(fig3)
    
    # 4-5. Mapas tráfico ciudad/país (usa choropleth si tienes coords)
    col1, col2 = st.columns(2)
    with col1:
        fig_city = px.bar(data['ga_ciudad'].groupby('city')['activeUsers'].sum().reset_index(),
                         x='city', y='activeUsers')
        st.plotly_chart(fig_city)
    with col2:
        fig_country = px.bar(data['ga_pais'].groupby('country')['activeUsers'].sum().reset_index(),
                           x='country', y='activeUsers')
        st.plotly_chart(fig_country)
    
    # 6. Tablas autores/URLs
    col1, col2 = st.columns(2)
    with col1:
        top_autores = prod_trafico.groupby('post_author_name')['screenPageViews'].sum().sort_values(ascending=False).head(10)
        st.dataframe(top_autores)
    with col2:
        top_urls = prod_trafico.nlargest(10, 'screenPageViews')[['post_title', 'post_author_name', 'screenPageViews']]
        st.dataframe(top_urls)
    
    # 7-9. Secciones, IA, Demografía
    col1, col2, col3 = st.columns(3)
    with col1:
        st.subheader("Edad")
        px.bar(data['ga_edad'].groupby('userAgeBracket')['activeUsers'].sum()).show()
    with col2:
        st.subheader("Dispositivo")
        px.bar(data['ga_device'].groupby('deviceCategory')['activeUsers'].sum()).show()
    with col3:
        st.subheader("Notas IA")
        top_ia = data['notas_ia'].groupby('post_author_name')['post_id'].count().sort_values(ascending=False)
        st.dataframe(top_ia)
