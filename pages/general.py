import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from data_loader import (
    load_ga4_general, load_ga4_city, load_ga4_country, load_ga4_channel,
    load_ga4_age, load_ga4_device, load_ga4_interests,
    load_search_console, load_produccion_con_metricas, load_ga4_urls_daily,
    filter_by_date, fmt_number, safe_sum
)

# ── Paleta ──────────────────────────────────────────────────────────────────
COLORS = ["#4f46e5","#06b6d4","#10b981","#f59e0b","#ef4444","#8b5cf6","#ec4899","#14b8a6"]
DARK_BG = "#0f0f1a"
CARD_BG = "#1a1a2e"

def dark_chart(fig, height=340):
    fig.update_layout(
        height=height,
        paper_bgcolor=DARK_BG,
        plot_bgcolor=DARK_BG,
        font=dict(family="DM Sans", color="#cdd6f4"),
        margin=dict(l=10, r=10, t=36, b=10),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=11)),
        xaxis=dict(gridcolor="#1e2040", zerolinecolor="#1e2040"),
        yaxis=dict(gridcolor="#1e2040", zerolinecolor="#1e2040"),
    )
    return fig

# ── Título ──────────────────────────────────────────────────────────────────
st.markdown("# 🏠 General · Tráfico y Producción")

# ── Carga de datos ───────────────────────────────────────────────────────────
ga4       = load_ga4_general()
ga4_city  = load_ga4_city()
ga4_cntry = load_ga4_country()
ga4_chan  = load_ga4_channel()
ga4_age   = load_ga4_age()
ga4_dev   = load_ga4_device()
ga4_urls  = load_ga4_urls_daily()
sc        = load_search_console()
prod      = load_produccion_con_metricas()

# ── Filtros ──────────────────────────────────────────────────────────────────
st.markdown("### ⚙️ Filtros")
col1, col2, col3, col4 = st.columns([2, 2, 2, 2])

# Rango de fechas
if not ga4.empty and "date" in ga4.columns:
    min_date = ga4["date"].dropna().min().date()
    max_date = ga4["date"].dropna().max().date()
else:
    min_date = date(2024, 1, 1)
    max_date = date.today()

with col1:
    start_date = st.date_input("Desde", value=max_date - timedelta(days=90), min_value=min_date, max_value=max_date)
with col2:
    end_date = st.date_input("Hasta", value=max_date, min_value=min_date, max_value=max_date)

# Filtro ciudad
cities = ["Todas"]
if not ga4_city.empty and "city" in ga4_city.columns:
    cities += sorted(ga4_city["city"].dropna().unique().tolist())[:30]
with col3:
    selected_city = st.selectbox("Ciudad", cities)

# Filtro autor
authors = ["Todos"]
if not prod.empty and "post_author_name" in prod.columns:
    authors += sorted(prod["post_author_name"].dropna().unique().tolist())
with col4:
    selected_author = st.selectbox("Autor", authors)

# Aplicar filtros de fecha
ga4_f     = filter_by_date(ga4,      "date", start_date, end_date)
ga4_city_f= filter_by_date(ga4_city, "date", start_date, end_date)
ga4_cntry_f=filter_by_date(ga4_cntry,"date", start_date, end_date)
ga4_chan_f = filter_by_date(ga4_chan, "date", start_date, end_date)
ga4_age_f  = filter_by_date(ga4_age, "date", start_date, end_date)
ga4_dev_f  = filter_by_date(ga4_dev, "date", start_date, end_date)
ga4_urls_f = filter_by_date(ga4_urls,"date", start_date, end_date)
sc_f       = {k: filter_by_date(v, "date", start_date, end_date) for k, v in sc.items()}

# Produccion filtro
prod_f = prod.copy()
if not prod_f.empty and "post_date" in prod_f.columns:
    prod_f = filter_by_date(prod_f, "post_date", start_date, end_date)
if selected_author != "Todos" and "post_author_name" in prod_f.columns:
    prod_f = prod_f[prod_f["post_author_name"] == selected_author]

# Ciudad
if selected_city != "Todas" and not ga4_city_f.empty:
    ga4_city_f = ga4_city_f[ga4_city_f["city"] == selected_city]

# ── Métricas generales ───────────────────────────────────────────────────────
st.markdown("---")
st.markdown('<div class="section-header">📊 Métricas Generales</div>', unsafe_allow_html=True)

m1, m2, m3, m4, m5, m6, m7 = st.columns(7)

active_users  = int(safe_sum(ga4_f, "activeUsers"))
total_views   = int(safe_sum(ga4_f, "screenPageViews"))
total_sessions= int(safe_sum(ga4_f, "sessions"))
avg_duration  = ga4_f["userEngagementDuration"].mean() if not ga4_f.empty and "userEngagementDuration" in ga4_f.columns else 0
sc_daily      = sc_f["daily"]
total_queries = int(safe_sum(sc_f["queries"], "clicks"))
total_impr    = int(safe_sum(sc_daily, "impressions"))
total_urls    = ga4_urls_f["pagePath"].nunique() if not ga4_urls_f.empty and "pagePath" in ga4_urls_f.columns else 0

m1.metric("👤 Usuarios Activos", fmt_number(active_users))
m2.metric("👥 Sesiones", fmt_number(total_sessions))
m3.metric("📄 Vistas", fmt_number(total_views))
m4.metric("⏱ Tiempo Promedio", f"{avg_duration/60:.1f} min" if avg_duration else "—")
m5.metric("🔍 Clicks Search", fmt_number(total_queries))
m6.metric("👁 Impresiones GSC", fmt_number(total_impr))
m7.metric("🔗 URLs con Tráfico", fmt_number(total_urls))

# ── Meta Q1 ──────────────────────────────────────────────────────────────────
META_Q1 = 750_000
st.markdown('<div class="section-header">🎯 Meta Q1 · 750,000 usuarios activos</div>', unsafe_allow_html=True)

# Usuarios activos del Q1 (ene-mar)
q1_start = date(end_date.year, 1, 1)
q1_end   = date(end_date.year, 3, 31)
ga4_q1   = filter_by_date(ga4, "date", q1_start, q1_end)
q1_users = int(safe_sum(ga4_q1, "activeUsers"))
pct_meta = min(q1_users / META_Q1, 1.0)

c1, c2 = st.columns([3, 1])
with c1:
    st.progress(pct_meta, text=f"{fmt_number(q1_users)} / {fmt_number(META_Q1)} · {pct_meta*100:.1f}%")
with c2:
    remaining = max(META_Q1 - q1_users, 0)
    st.metric("Faltan", fmt_number(remaining), delta=f"{(pct_meta-1)*100:.1f}%" if pct_meta < 1 else "✅ Meta alcanzada")

# ── Gráficos ─────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown('<div class="section-header">📈 Evolución Temporal</div>', unsafe_allow_html=True)

# 1 · Usuarios activos vs vistas por mes
if not ga4_f.empty and "date" in ga4_f.columns:
    ga4_f_c = ga4_f.copy()
    ga4_f_c["mes"] = ga4_f_c["date"].dt.to_period("M").astype(str)
    monthly = ga4_f_c.groupby("mes").agg(
        activeUsers=("activeUsers", "sum"),
        screenPageViews=("screenPageViews", "sum")
    ).reset_index()

    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(x=monthly["mes"], y=monthly["activeUsers"],
        name="Usuarios Activos", line=dict(color=COLORS[0], width=2.5), mode="lines+markers"))
    fig1.add_trace(go.Bar(x=monthly["mes"], y=monthly["screenPageViews"],
        name="Vistas", marker_color=COLORS[1], opacity=0.55, yaxis="y2"))
    fig1.update_layout(
        title="Usuarios Activos vs Vistas por Mes",
        yaxis2=dict(overlaying="y", side="right", showgrid=False),
        barmode="overlay"
    )
    dark_chart(fig1)
    st.plotly_chart(fig1, use_container_width=True)

# 2 · Producción total de URLs por mes
if not prod_f.empty and "post_date" in prod_f.columns:
    prod_f_c = prod_f.copy()
    prod_f_c["mes"] = prod_f_c["post_date"].dt.to_period("M").astype(str)
    prod_monthly = prod_f_c.groupby("mes").size().reset_index(name="publicaciones")

    fig2 = px.area(prod_monthly, x="mes", y="publicaciones",
        title="Evolución de Producción Total de URLs",
        color_discrete_sequence=[COLORS[2]])
    fig2.update_traces(fill="tozeroy", fillcolor="rgba(16,185,129,0.15)")
    dark_chart(fig2)
    st.plotly_chart(fig2, use_container_width=True)

# 3 · Canales de tráfico
st.markdown('<div class="section-header">📡 Canales de Tráfico</div>', unsafe_allow_html=True)
c1, c2 = st.columns([1, 2])
if not ga4_chan_f.empty and "sessionDefaultChannelGroup" in ga4_chan_f.columns:
    chan_agg = ga4_chan_f.groupby("sessionDefaultChannelGroup").agg(
        activeUsers=("activeUsers","sum"),
        screenPageViews=("screenPageViews","sum"),
        sessions=("sessions","sum")
    ).reset_index().sort_values("activeUsers", ascending=False)

    with c1:
        fig3a = px.pie(chan_agg, names="sessionDefaultChannelGroup", values="activeUsers",
            title="Distribución de Canales", color_discrete_sequence=COLORS,
            hole=0.45)
        dark_chart(fig3a, 300)
        st.plotly_chart(fig3a, use_container_width=True)

    with c2:
        st.dataframe(
            chan_agg.rename(columns={
                "sessionDefaultChannelGroup": "Canal",
                "activeUsers": "Usuarios Activos",
                "screenPageViews": "Vistas",
                "sessions": "Sesiones"
            }).style.format({"Usuarios Activos":"{:,.0f}","Vistas":"{:,.0f}","Sesiones":"{:,.0f}"}),
            use_container_width=True, hide_index=True
        )

# 4 · Tráfico por ciudad
st.markdown('<div class="section-header">🏙️ Tráfico por Ciudad</div>', unsafe_allow_html=True)
if not ga4_city.empty and "city" in ga4_city.columns:
    city_all = filter_by_date(ga4_city, "date", start_date, end_date)
    city_agg = city_all.groupby("city").agg(activeUsers=("activeUsers","sum")).reset_index()
    city_agg = city_agg[city_agg["city"] != "(not set)"].sort_values("activeUsers", ascending=False).head(20)
    fig4 = px.bar(city_agg, x="activeUsers", y="city", orientation="h",
        title="Top 20 Ciudades · Usuarios Activos", color="activeUsers",
        color_continuous_scale=["#1e1b4b","#4f46e5","#06b6d4"])
    fig4.update_layout(yaxis=dict(autorange="reversed"), coloraxis_showscale=False)
    dark_chart(fig4, 500)
    st.plotly_chart(fig4, use_container_width=True)

# 5 · Tráfico por país
st.markdown('<div class="section-header">🌎 Tráfico por País</div>', unsafe_allow_html=True)
if not ga4_cntry.empty and "country" in ga4_cntry.columns:
    cntry_all = filter_by_date(ga4_cntry, "date", start_date, end_date)
    cntry_agg = cntry_all.groupby("country").agg(activeUsers=("activeUsers","sum")).reset_index()
    cntry_agg = cntry_agg[cntry_agg["country"] != "(not set)"].sort_values("activeUsers", ascending=False)

    fig5 = px.choropleth(cntry_agg, locations="country", locationmode="country names",
        color="activeUsers", title="Usuarios por País",
        color_continuous_scale=["#1e1b4b","#4f46e5","#06b6d4","#10b981"])
    fig5.update_layout(geo=dict(bgcolor=DARK_BG, showframe=False), coloraxis_colorbar=dict(title="Usuarios"))
    dark_chart(fig5, 400)
    st.plotly_chart(fig5, use_container_width=True)

# 6 · Tabla URLs más leídas + autores
st.markdown('<div class="section-header">📰 Notas y Autores Más Leídos</div>', unsafe_allow_html=True)
c1, c2 = st.columns(2)

with c1:
    st.markdown("**🔝 URLs Más Leídas del Período**")
    if not ga4_urls_f.empty:
        urls_agg = ga4_urls_f.groupby(["pagePath","pageTitle"] if "pageTitle" in ga4_urls_f.columns else ["pagePath"]).agg(
            Vistas=("screenPageViews","sum"),
            Usuarios=("activeUsers","sum")
        ).reset_index().sort_values("Vistas", ascending=False).head(20)

        # enriquecer con autor
        if not prod.empty and "url" in prod.columns and "post_author_name" in prod.columns:
            from urllib.parse import urlparse
            prod_url_map = {urlparse(str(u)).path: a for u, a in zip(prod["url"], prod["post_author_name"])}
            path_col = "pagePath" if "pagePath" in urls_agg.columns else urls_agg.columns[0]
            urls_agg["Autor"] = urls_agg[path_col].map(prod_url_map).fillna("—")
        
        cols_show = [c for c in ["pageTitle","pagePath","Autor","Vistas","Usuarios"] if c in urls_agg.columns]
        st.dataframe(urls_agg[cols_show].style.format({"Vistas":"{:,.0f}","Usuarios":"{:,.0f}"}),
            use_container_width=True, hide_index=True, height=350)

with c2:
    st.markdown("**✍️ Autores Más Leídos**")
    if not prod.empty and "post_author_name" in prod.columns and "ga4_views" in prod.columns:
        prod_f_all = prod if selected_author == "Todos" else prod_f
        author_agg = prod_f_all.groupby("post_author_name").agg(
            Vistas=("ga4_views","sum"),
            Notas=("post_id","count")
        ).reset_index().sort_values("Vistas", ascending=False).head(15)
        author_agg["Vistas/Nota"] = (author_agg["Vistas"] / author_agg["Notas"]).round(0).astype(int)
        st.dataframe(author_agg.rename(columns={"post_author_name":"Autor"})\
            .style.format({"Vistas":"{:,.0f}","Notas":"{:,.0f}","Vistas/Nota":"{:,.0f}"}),
            use_container_width=True, hide_index=True, height=350)

# 7 · Secciones
st.markdown('<div class="section-header">📂 Secciones</div>', unsafe_allow_html=True)
c1, c2 = st.columns([1,2])
if not prod.empty and "categories" in prod.columns and "ga4_views" in prod.columns:
    prod_sec = prod.copy()
    # Expandir categorías (pueden ser comma-separated)
    prod_sec["cat"] = prod_sec["categories"].fillna("Sin categoría").apply(
        lambda x: str(x).split(",")[0].strip() if pd.notna(x) else "Sin categoría"
    )
    sec_agg = prod_sec.groupby("cat").agg(
        Usuarios=("ga4_users","sum"),
        Vistas=("ga4_views","sum"),
        Notas=("post_id","count")
    ).reset_index().sort_values("Vistas", ascending=False).head(15)

    with c1:
        top10 = sec_agg.head(10)
        fig7a = px.pie(top10, names="cat", values="Usuarios",
            title="Usuarios por Sección", color_discrete_sequence=COLORS, hole=0.4)
        dark_chart(fig7a, 300)
        st.plotly_chart(fig7a, use_container_width=True)

    with c2:
        st.dataframe(sec_agg.rename(columns={"cat":"Sección"})\
            .style.format({"Usuarios":"{:,.0f}","Vistas":"{:,.0f}","Notas":"{:,.0f}"}),
            use_container_width=True, hide_index=True, height=350)

# 8 · Notas IA
st.markdown('<div class="section-header">🤖 Notas IA Más Leídas</div>', unsafe_allow_html=True)
if not prod.empty and "is_ia" in prod.columns:
    ia_df = prod[prod["is_ia"] == True].copy() if "is_ia" in prod.columns else pd.DataFrame()
    if not ia_df.empty:
        ia_top = ia_df.sort_values("ga4_views", ascending=False).head(20)
        cols_ia = [c for c in ["post_title","post_author_name","post_date","ga4_views","ga4_users"] if c in ia_top.columns]
        st.dataframe(ia_top[cols_ia].rename(columns={
            "post_title":"Título","post_author_name":"Autor","post_date":"Fecha",
            "ga4_views":"Vistas","ga4_users":"Usuarios"
        }).style.format({"Vistas":"{:,.0f}","Usuarios":"{:,.0f}"}),
        use_container_width=True, hide_index=True)
    else:
        st.info("No se encontraron notas con tag 'IA' en el período seleccionado.")

# 9 · Audiencia: edad, dispositivo, intereses
st.markdown('<div class="section-header">👥 Audiencia</div>', unsafe_allow_html=True)
t1, t2, t3 = st.tabs(["📅 Edad", "📱 Dispositivo", "🎯 Intereses"])

with t1:
    if not ga4_age_f.empty and "userAgeBracket" in ga4_age_f.columns:
        age_agg = ga4_age_f.groupby("userAgeBracket").agg(
            activeUsers=("activeUsers","sum"),
            sessions=("sessions","sum")
        ).reset_index().sort_values("activeUsers", ascending=False)
        fig_age = px.bar(age_agg, x="userAgeBracket", y="activeUsers",
            title="Usuarios por Rango de Edad", color="activeUsers",
            color_continuous_scale=["#1e1b4b","#4f46e5"])
        dark_chart(fig_age)
        st.plotly_chart(fig_age, use_container_width=True)

with t2:
    if not ga4_dev_f.empty and "deviceCategory" in ga4_dev_f.columns:
        dev_agg = ga4_dev_f.groupby("deviceCategory").agg(activeUsers=("activeUsers","sum")).reset_index()
        fig_dev = px.pie(dev_agg, names="deviceCategory", values="activeUsers",
            title="Distribución por Dispositivo", color_discrete_sequence=COLORS, hole=0.4)
        dark_chart(fig_dev)
        st.plotly_chart(fig_dev, use_container_width=True)
        st.dataframe(dev_agg.rename(columns={"deviceCategory":"Dispositivo","activeUsers":"Usuarios Activos"})
            .style.format({"Usuarios Activos":"{:,.0f}"}), use_container_width=True, hide_index=True)

with t3:
    interests = load_ga4_interests()
    if not interests.empty and "brandingInterest" in interests.columns:
        int_agg = interests.groupby("brandingInterest").agg(activeUsers=("activeUsers","sum")).reset_index()\
            .sort_values("activeUsers", ascending=False).head(20)
        fig_int = px.bar(int_agg, x="activeUsers", y="brandingInterest", orientation="h",
            title="Top Intereses de Audiencia", color="activeUsers",
            color_continuous_scale=["#1e1b4b","#8b5cf6"])
        fig_int.update_layout(yaxis=dict(autorange="reversed"), coloraxis_showscale=False)
        dark_chart(fig_int, 500)
        st.plotly_chart(fig_int, use_container_width=True)
    else:
        st.info("Datos de intereses no disponibles.")
