import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta
import sys, os
sys.path.insert(0, os.getcwd())
from data_loader import (
    load_ga4_general, load_ga4_city, load_ga4_country, load_ga4_channel,
    load_ga4_age, load_ga4_device, load_ga4_interests,
    load_search_console, load_produccion_con_metricas, load_ga4_urls_daily,
    filter_by_date, fmt_number, safe_sum, get_date_range, pct_delta
)

# ── Paleta & estilo de gráficos ───────────────────────────────────────────────
C  = ["#6366f1","#06b6d4","#10b981","#f59e0b","#ef4444","#8b5cf6","#ec4899","#14b8a6"]
BG = "#0a0a14"
PBG = "#0d0d1e"

def _fig(fig, h=340, legend=True):
    fig.update_layout(
        height=h, paper_bgcolor=PBG, plot_bgcolor=PBG,
        font=dict(family="Inter", color="#9aa3c2", size=12),
        margin=dict(l=8, r=8, t=38, b=8),
        legend=dict(bgcolor="rgba(0,0,0,0)", font_size=11) if legend else dict(visible=False),
        xaxis=dict(gridcolor="#181828", zerolinecolor="#181828", tickfont_size=11),
        yaxis=dict(gridcolor="#181828", zerolinecolor="#181828", tickfont_size=11),
        title_font=dict(family="Syne", size=14, color="#c8cedc"),
    )
    return fig

def sh(label):
    st.markdown(f'<div class="sec-hdr">{label}</div>', unsafe_allow_html=True)

# ── Título ────────────────────────────────────────────────────────────────────
st.markdown('<div class="page-title">🏠 General · Tráfico y Producción</div>', unsafe_allow_html=True)
st.markdown('<div class="page-subtitle">GA4 · Search Console · Producción editorial</div>', unsafe_allow_html=True)

# ── Carga de datos ────────────────────────────────────────────────────────────
with st.spinner("Cargando datos..."):
    ga4      = load_ga4_general()
    ga4_city = load_ga4_city()
    ga4_cntry= load_ga4_country()
    ga4_chan  = load_ga4_channel()
    ga4_age  = load_ga4_age()
    ga4_dev  = load_ga4_device()
    ga4_urls = load_ga4_urls_daily()
    sc       = load_search_console()
    prod     = load_produccion_con_metricas()

# ── FILTROS ───────────────────────────────────────────────────────────────────
min_d, max_d = get_date_range(ga4, "date")

with st.container():
    st.markdown('<div class="filter-box">', unsafe_allow_html=True)
    sh("⚙️ Filtros")
    fc1, fc2, fc3, fc4, fc5, fc6 = st.columns([1.5, 1.5, 1.5, 1.5, 1.5, 1.5])

    with fc1:
        start_date = st.date_input("📅 Desde", value=max_d - timedelta(days=90),
                                    min_value=min_d, max_value=max_d, key="gen_start")
    with fc2:
        end_date = st.date_input("📅 Hasta", value=max_d,
                                  min_value=min_d, max_value=max_d, key="gen_end")

    # Filtro página/URL
    url_opts = ["Todas"]
    if not ga4_urls.empty and "pageTitle" in ga4_urls.columns:
        url_opts += sorted(ga4_urls["pageTitle"].dropna().unique().tolist())[:200]
    with fc3:
        sel_page = st.selectbox("📄 Título de página", url_opts, key="gen_page")

    # Filtro autor
    auth_opts = ["Todos"]
    if not prod.empty and "post_author_name" in prod.columns:
        auth_opts += sorted(prod["post_author_name"].dropna().unique().tolist())
    with fc4:
        sel_author = st.selectbox("✍️ Autor", auth_opts, key="gen_author")

    # Filtro ciudad
    city_opts = ["Todas"]
    if not ga4_city.empty and "city" in ga4_city.columns:
        top_cities = (
            ga4_city.groupby("city")["activeUsers"].sum()
            .sort_values(ascending=False)
            .head(50).index.tolist()
        )
        city_opts += [c for c in top_cities if c != "(not set)"]
    with fc5:
        sel_city = st.selectbox("🏙️ Ciudad", city_opts, key="gen_city")

    # Filtro categoría
    cat_opts = ["Todas"]
    if not prod.empty and "categories" in prod.columns:
        cats = (
            prod["categories"].dropna()
            .apply(lambda x: str(x).split(",")[0].strip())
            .value_counts().head(40).index.tolist()
        )
        cat_opts += cats
    with fc6:
        sel_cat = st.selectbox("📂 Sección", cat_opts, key="gen_cat")
    st.markdown('</div>', unsafe_allow_html=True)

# ── Aplicar filtros ───────────────────────────────────────────────────────────
ga4_f     = filter_by_date(ga4,      "date", start_date, end_date)
ga4_city_f= filter_by_date(ga4_city, "date", start_date, end_date)
ga4_cnt_f = filter_by_date(ga4_cntry,"date", start_date, end_date)
ga4_chan_f = filter_by_date(ga4_chan, "date", start_date, end_date)
ga4_age_f = filter_by_date(ga4_age,  "date", start_date, end_date)
ga4_dev_f = filter_by_date(ga4_dev,  "date", start_date, end_date)
ga4_urls_f= filter_by_date(ga4_urls, "date", start_date, end_date)
sc_f      = {k: filter_by_date(v, "date", start_date, end_date) for k,v in sc.items()}

# Filtros adicionales en GA4 URLs
if sel_page != "Todas" and not ga4_urls_f.empty and "pageTitle" in ga4_urls_f.columns:
    ga4_urls_f = ga4_urls_f[ga4_urls_f["pageTitle"] == sel_page]

# Filtros en ciudad
if sel_city != "Todas" and not ga4_city_f.empty:
    ga4_city_f = ga4_city_f[ga4_city_f["city"] == sel_city]

# Filtros en producción
prod_f = filter_by_date(prod, "post_date", start_date, end_date)
if sel_author != "Todos" and "post_author_name" in prod_f.columns:
    prod_f = prod_f[prod_f["post_author_name"] == sel_author]
if sel_cat != "Todas" and "categories" in prod_f.columns:
    prod_f = prod_f[prod_f["categories"].fillna("").apply(
        lambda x: sel_cat in [p.strip() for p in str(x).split(",")]
    )]

# ── Período previo para deltas ────────────────────────────────────────────────
period_days  = (end_date - start_date).days or 1
prev_start   = start_date - timedelta(days=period_days)
prev_end     = start_date - timedelta(days=1)
ga4_prev     = filter_by_date(ga4, "date", prev_start, prev_end)
sc_prev_d    = filter_by_date(sc["daily"], "date", prev_start, prev_end)

def _delta(cur, prev):
    d = pct_delta(cur, prev)
    return f"{d:+.1f}%" if d is not None else None

# ── MÉTRICAS GENERALES ────────────────────────────────────────────────────────
sh("📊 Métricas Generales")
m1,m2,m3,m4,m5,m6,m7 = st.columns(7)

active_u  = int(safe_sum(ga4_f, "activeUsers"))
views     = int(safe_sum(ga4_f, "screenPageViews"))
sessions  = int(safe_sum(ga4_f, "sessions"))
avg_dur   = ga4_f["userEngagementDuration"].mean() if not ga4_f.empty and "userEngagementDuration" in ga4_f.columns else 0
sc_clicks = int(safe_sum(sc_f["daily"], "clicks"))
sc_impr   = int(safe_sum(sc_f["daily"], "impressions"))
urls_ct   = ga4_urls_f["pagePath"].nunique() if not ga4_urls_f.empty and "pagePath" in ga4_urls_f.columns else 0

p_u   = int(safe_sum(ga4_prev, "activeUsers"))
p_v   = int(safe_sum(ga4_prev, "screenPageViews"))
p_s   = int(safe_sum(ga4_prev, "sessions"))
p_sc  = int(safe_sum(sc_prev_d, "clicks"))
p_si  = int(safe_sum(sc_prev_d, "impressions"))

m1.metric("👤 Usuarios Activos",  fmt_number(active_u),  _delta(active_u, p_u))
m2.metric("📄 Vistas",            fmt_number(views),     _delta(views, p_v))
m3.metric("🔄 Sesiones",          fmt_number(sessions),  _delta(sessions, p_s))
m4.metric("⏱ Tiempo Promedio",    f"{avg_dur/60:.1f} min" if avg_dur else "—")
m5.metric("🔍 Clicks GSC",        fmt_number(sc_clicks), _delta(sc_clicks, p_sc))
m6.metric("👁 Impresiones GSC",   fmt_number(sc_impr),   _delta(sc_impr, p_si))
m7.metric("🔗 URLs con Tráfico",  fmt_number(urls_ct))

# ── META Q1 ───────────────────────────────────────────────────────────────────
META_Q1 = 750_000
sh("🎯 Meta Q1 · 750,000 Usuarios Activos")
q1_s = date(end_date.year, 1, 1)
q1_e = date(end_date.year, 3, 31)
ga4_q1   = filter_by_date(ga4, "date", q1_s, q1_e)
q1_users = int(safe_sum(ga4_q1, "activeUsers"))
pct_meta = min(q1_users / META_Q1, 1.0)

qc1, qc2, qc3 = st.columns([4, 1, 1])
with qc1:
    st.progress(pct_meta,
        text=f"**{fmt_number(q1_users)}** de **{fmt_number(META_Q1)}** usuarios · {pct_meta*100:.1f}% completado")
with qc2:
    st.metric("Alcanzado", fmt_number(q1_users))
with qc3:
    remaining = max(META_Q1 - q1_users, 0)
    st.metric("Faltan", fmt_number(remaining),
        delta="✅ Meta!" if remaining == 0 else f"-{fmt_number(remaining)}",
        delta_color="normal" if remaining == 0 else "inverse")

# ── GRÁFICOS EVOLUCIÓN ────────────────────────────────────────────────────────
st.markdown("---")
sh("📈 Evolución · Usuarios Activos vs Vistas")
if not ga4_f.empty and "date" in ga4_f.columns:
    df_m = ga4_f.copy()
    df_m["mes"] = df_m["date"].dt.to_period("M").astype(str)
    monthly = df_m.groupby("mes").agg(
        activeUsers=("activeUsers","sum"),
        screenPageViews=("screenPageViews","sum")
    ).reset_index()

    fig1 = go.Figure()
    fig1.add_trace(go.Bar(
        x=monthly["mes"], y=monthly["screenPageViews"],
        name="Vistas", marker_color="#06b6d4", opacity=0.45,
        yaxis="y2"
    ))
    fig1.add_trace(go.Scatter(
        x=monthly["mes"], y=monthly["activeUsers"],
        name="Usuarios Activos", mode="lines+markers",
        line=dict(color="#6366f1", width=3),
        marker=dict(size=7, color="#6366f1", line=dict(color="#fff", width=1.5))
    ))
    fig1.update_layout(
        yaxis2=dict(overlaying="y", side="right", showgrid=False,
                    tickfont=dict(color="#06b6d4"), title="Vistas"),
        yaxis=dict(title="Usuarios Activos"),
        barmode="overlay", legend=dict(orientation="h", y=1.12)
    )
    _fig(fig1, 360)
    st.plotly_chart(fig1, use_container_width=True)

# ── PRODUCCIÓN ────────────────────────────────────────────────────────────────
sh("✍️ Evolución de Producción de URLs")
if not prod_f.empty and "post_date" in prod_f.columns:
    df_p = prod_f.copy()
    df_p["mes"] = df_p["post_date"].dt.to_period("M").astype(str)
    prod_m = df_p.groupby("mes").agg(
        publicaciones=("post_id","count"),
        con_trafico=("ga4_views", lambda x: (x > 0).sum())
    ).reset_index()
    prod_m["sin_trafico"] = prod_m["publicaciones"] - prod_m["con_trafico"]

    fig2 = go.Figure()
    fig2.add_trace(go.Bar(x=prod_m["mes"], y=prod_m["con_trafico"],
        name="Con tráfico GA4", marker_color="#10b981"))
    fig2.add_trace(go.Bar(x=prod_m["mes"], y=prod_m["sin_trafico"],
        name="Sin tráfico registrado", marker_color="#252550"))
    fig2.update_layout(barmode="stack", legend=dict(orientation="h", y=1.12))
    _fig(fig2, 300)
    st.plotly_chart(fig2, use_container_width=True)

# ── CANALES ───────────────────────────────────────────────────────────────────
sh("📡 Canales de Tráfico")
if not ga4_chan_f.empty and "sessionDefaultChannelGroup" in ga4_chan_f.columns:
    chan_agg = (
        ga4_chan_f.groupby("sessionDefaultChannelGroup")
        .agg(activeUsers=("activeUsers","sum"),
             screenPageViews=("screenPageViews","sum"),
             sessions=("sessions","sum"))
        .reset_index()
        .sort_values("activeUsers", ascending=False)
    )
    cc1, cc2 = st.columns([1, 2])
    with cc1:
        fig3 = px.pie(chan_agg, names="sessionDefaultChannelGroup", values="activeUsers",
            title="Distribución de Canales", color_discrete_sequence=C, hole=0.5)
        fig3.update_traces(textposition="inside", textinfo="percent+label",
                           textfont_size=11)
        _fig(fig3, 300, legend=False)
        st.plotly_chart(fig3, use_container_width=True)
    with cc2:
        st.dataframe(
            chan_agg.rename(columns={
                "sessionDefaultChannelGroup": "Canal",
                "activeUsers": "Usuarios", "screenPageViews": "Vistas", "sessions": "Sesiones"
            }).style.format({"Usuarios":"{:,.0f}","Vistas":"{:,.0f}","Sesiones":"{:,.0f}"}),
            use_container_width=True, hide_index=True, height=280
        )

# ── CIUDADES ──────────────────────────────────────────────────────────────────
sh("🏙️ Tráfico por Ciudad · Top 20")
if not ga4_city_f.empty and "city" in ga4_city_f.columns:
    city_agg = (
        ga4_city_f[ga4_city_f["city"] != "(not set)"]
        .groupby("city").agg(
            Usuarios=("activeUsers","sum"),
            Vistas=("screenPageViews","sum")
        ).reset_index()
        .sort_values("Usuarios", ascending=False).head(20)
    )
    fig4 = px.bar(city_agg, x="Usuarios", y="city", orientation="h",
        color="Usuarios", color_continuous_scale=["#1a1a3e","#6366f1","#06b6d4"],
        text="Usuarios")
    fig4.update_traces(texttemplate="%{text:,.0f}", textposition="outside",
                       textfont_size=10)
    fig4.update_layout(yaxis=dict(autorange="reversed"), coloraxis_showscale=False,
                       xaxis_title="Usuarios Activos", yaxis_title="")
    _fig(fig4, 520)
    st.plotly_chart(fig4, use_container_width=True)

# ── PAÍSES ────────────────────────────────────────────────────────────────────
sh("🌎 Tráfico por País")
if not ga4_cnt_f.empty and "country" in ga4_cnt_f.columns:
    cnt_agg = (
        ga4_cnt_f[ga4_cnt_f["country"] != "(not set)"]
        .groupby("country").agg(Usuarios=("activeUsers","sum")).reset_index()
        .sort_values("Usuarios", ascending=False)
    )
    pc1, pc2 = st.columns([3, 1])
    with pc1:
        fig5 = px.choropleth(cnt_agg, locations="country",
            locationmode="country names", color="Usuarios",
            color_continuous_scale=["#0d0d24","#6366f1","#06b6d4","#10b981"])
        fig5.update_layout(
            geo=dict(bgcolor=PBG, showframe=False, showcoastlines=True,
                     coastlinecolor="#1e1e3a", landcolor="#12122a", showland=True,
                     showocean=True, oceancolor="#0a0a14"),
            coloraxis_colorbar=dict(title="Usuarios", tickfont=dict(size=10))
        )
        _fig(fig5, 380, legend=False)
        st.plotly_chart(fig5, use_container_width=True)
    with pc2:
        st.dataframe(
            cnt_agg.head(20).rename(columns={"country":"País"})\
                .style.format({"Usuarios":"{:,.0f}"}),
            use_container_width=True, hide_index=True, height=360
        )

# ── NOTAS + AUTORES ───────────────────────────────────────────────────────────
sh("📰 Notas y Autores Más Leídos")
nc1, nc2 = st.columns(2)

with nc1:
    st.markdown("**🔝 URLs más leídas del período**")
    if not ga4_urls_f.empty and "pagePath" in ga4_urls_f.columns:
        grp_cols = ["pagePath"]
        if "pageTitle" in ga4_urls_f.columns:
            grp_cols = ["pagePath", "pageTitle"]
        url_agg = (
            ga4_urls_f.groupby(grp_cols)
            .agg(Vistas=("screenPageViews","sum"), Usuarios=("activeUsers","sum"))
            .reset_index().sort_values("Vistas", ascending=False).head(25)
        )
        # Enriquecer con autor desde producción
        if not prod.empty and "url" in prod.columns and "post_author_name" in prod.columns:
            from urllib.parse import urlparse as _up
            path_to_author = {
                _up(str(u)).path.rstrip("/"): a
                for u, a in zip(prod["url"], prod["post_author_name"])
                if pd.notna(u)
            }
            url_agg["Autor"] = url_agg["pagePath"].apply(
                lambda p: path_to_author.get(str(p).rstrip("/"), "—")
            )
        disp_cols = [c for c in ["pageTitle","Autor","Vistas","Usuarios"] if c in url_agg.columns]
        st.dataframe(
            url_agg[disp_cols].style.format({"Vistas":"{:,.0f}","Usuarios":"{:,.0f}"}),
            use_container_width=True, hide_index=True, height=380
        )
    else:
        st.info("Sin datos de URLs en el período.")

with nc2:
    st.markdown("**✍️ Autores más leídos del período**")
    if not prod_f.empty and "post_author_name" in prod_f.columns and "ga4_views" in prod_f.columns:
        auth_agg = (
            prod_f.groupby("post_author_name")
            .agg(Vistas=("ga4_views","sum"), Notas=("post_id","count"),
                 Usuarios=("ga4_users","sum"))
            .reset_index().sort_values("Vistas", ascending=False).head(20)
        )
        auth_agg["Vistas/Nota"] = (auth_agg["Vistas"] / auth_agg["Notas"].clip(1)).round(0).astype(int)
        st.dataframe(
            auth_agg.rename(columns={"post_author_name":"Autor"})
            .style.format({"Vistas":"{:,.0f}","Notas":"{:,.0f}",
                           "Usuarios":"{:,.0f}","Vistas/Nota":"{:,.0f}"}),
            use_container_width=True, hide_index=True, height=380
        )

# ── SECCIONES ─────────────────────────────────────────────────────────────────
sh("📂 Secciones")
if not prod_f.empty and "categories" in prod_f.columns and "ga4_views" in prod_f.columns:
    prod_s = prod_f.copy()
    prod_s["cat"] = prod_s["categories"].fillna("Sin categoría").apply(
        lambda x: str(x).split(",")[0].strip()
    )
    sec_agg = (
        prod_s.groupby("cat")
        .agg(Usuarios=("ga4_users","sum"), Vistas=("ga4_views","sum"),
             Notas=("post_id","count"))
        .reset_index().sort_values("Vistas", ascending=False).head(20)
    )
    sc1, sc2 = st.columns([1, 2])
    with sc1:
        fig7 = px.pie(sec_agg.head(10), names="cat", values="Usuarios",
            title="Usuarios por Sección", color_discrete_sequence=C, hole=0.45)
        fig7.update_traces(textposition="inside", textinfo="percent+label",
                           textfont_size=10)
        _fig(fig7, 320, legend=False)
        st.plotly_chart(fig7, use_container_width=True)
    with sc2:
        st.dataframe(
            sec_agg.rename(columns={"cat":"Sección"})
            .style.format({"Usuarios":"{:,.0f}","Vistas":"{:,.0f}","Notas":"{:,.0f}"}),
            use_container_width=True, hide_index=True, height=340
        )
else:
    st.info("Datos de secciones no disponibles.")

# ── NOTAS IA ──────────────────────────────────────────────────────────────────
sh("🤖 Notas IA Más Leídas")
if not prod_f.empty and "is_ia" in prod_f.columns:
    ia_df = prod_f[prod_f["is_ia"]].sort_values("ga4_views", ascending=False).head(25)
    if not ia_df.empty:
        show_cols = [c for c in ["post_title","post_author_name","post_date","categories","ga4_views","ga4_users","match_method"] if c in ia_df.columns]
        st.dataframe(
            ia_df[show_cols].rename(columns={
                "post_title":"Título","post_author_name":"Autor",
                "post_date":"Fecha","categories":"Categorías",
                "ga4_views":"Vistas","ga4_users":"Usuarios",
                "match_method":"Match"
            }).style.format({"Vistas":"{:,.0f}","Usuarios":"{:,.0f}"}),
            use_container_width=True, hide_index=True
        )
    else:
        st.info("No hay notas con tag IA en el período seleccionado.")

# ── AUDIENCIA ─────────────────────────────────────────────────────────────────
sh("👥 Audiencia · Edad · Dispositivo · Intereses")
t1, t2, t3 = st.tabs(["📅 Edad", "📱 Dispositivo", "🎯 Intereses"])

with t1:
    if not ga4_age_f.empty and "userAgeBracket" in ga4_age_f.columns:
        age_agg = (
            ga4_age_f.groupby("userAgeBracket")
            .agg(Usuarios=("activeUsers","sum"), Sesiones=("sessions","sum"))
            .reset_index().sort_values("userAgeBracket")
        )
        fig_a = px.bar(age_agg, x="userAgeBracket", y="Usuarios",
            color="Usuarios", color_continuous_scale=["#1a1a3e","#6366f1"],
            text="Usuarios")
        fig_a.update_traces(texttemplate="%{text:,.0f}", textposition="outside", textfont_size=10)
        fig_a.update_layout(coloraxis_showscale=False, xaxis_title="Rango de Edad")
        _fig(fig_a, 300)
        st.plotly_chart(fig_a, use_container_width=True)
        st.dataframe(age_agg.rename(columns={"userAgeBracket":"Rango Edad"})
            .style.format({"Usuarios":"{:,.0f}","Sesiones":"{:,.0f}"}),
            use_container_width=True, hide_index=True)
    else:
        st.info("Datos de edad no disponibles.")

with t2:
    if not ga4_dev_f.empty and "deviceCategory" in ga4_dev_f.columns:
        dev_agg = (
            ga4_dev_f.groupby("deviceCategory")
            .agg(Usuarios=("activeUsers","sum"), Vistas=("screenPageViews","sum"))
            .reset_index()
        )
        dc1, dc2 = st.columns(2)
        with dc1:
            fig_d = px.pie(dev_agg, names="deviceCategory", values="Usuarios",
                title="Usuarios por Dispositivo", color_discrete_sequence=C, hole=0.5)
            fig_d.update_traces(textposition="inside", textinfo="percent+label",
                                textfont_size=12)
            _fig(fig_d, 300, legend=False)
            st.plotly_chart(fig_d, use_container_width=True)
        with dc2:
            fig_dv = px.bar(dev_agg, x="deviceCategory", y="Vistas",
                color="deviceCategory", color_discrete_sequence=C, text="Vistas")
            fig_dv.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
            fig_dv.update_layout(showlegend=False, xaxis_title="")
            _fig(fig_dv, 300)
            st.plotly_chart(fig_dv, use_container_width=True)
        st.dataframe(dev_agg.rename(columns={"deviceCategory":"Dispositivo"})
            .style.format({"Usuarios":"{:,.0f}","Vistas":"{:,.0f}"}),
            use_container_width=True, hide_index=True)
    else:
        st.info("Datos de dispositivo no disponibles.")

with t3:
    interests = load_ga4_interests()
    if not interests.empty and "brandingInterest" in interests.columns:
        int_agg = (
            interests.groupby("brandingInterest")
            .agg(Usuarios=("activeUsers","sum"))
            .reset_index().sort_values("Usuarios", ascending=False).head(25)
        )
        fig_i = px.bar(int_agg, x="Usuarios", y="brandingInterest", orientation="h",
            color="Usuarios", color_continuous_scale=["#1a1a3e","#8b5cf6"])
        fig_i.update_layout(yaxis=dict(autorange="reversed"), coloraxis_showscale=False,
                             yaxis_title="")
        _fig(fig_i, 550)
        st.plotly_chart(fig_i, use_container_width=True)
    else:
        st.info("Datos de intereses no disponibles.")
