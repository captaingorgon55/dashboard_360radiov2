import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from data_loader import (
    load_youtube, load_instagram_posts, load_instagram_stories,
    load_facebook, filter_by_date, fmt_number, safe_sum, pct_change_label
)

COLORS = ["#4f46e5","#06b6d4","#10b981","#f59e0b","#ef4444","#8b5cf6","#ec4899"]
DARK_BG = "#0f0f1a"

def dark_chart(fig, height=340):
    fig.update_layout(height=height, paper_bgcolor=DARK_BG, plot_bgcolor=DARK_BG,
        font=dict(family="DM Sans", color="#cdd6f4"), margin=dict(l=10,r=10,t=36,b=10),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(gridcolor="#1e2040"), yaxis=dict(gridcolor="#1e2040"))
    return fig

st.markdown("# 📱 Social Media")

# ── Carga ─────────────────────────────────────────────────────────────────────
yt   = load_youtube()
ig   = load_instagram_posts()
igs  = load_instagram_stories()
fb   = load_facebook()

# ── Filtros ───────────────────────────────────────────────────────────────────
c1, c2, c3 = st.columns(3)

# Rango fechas mínimo/máximo cross-plataforma
dates_all = []
if not ig.empty and "Fecha" in ig.columns: dates_all += ig["Fecha"].dropna().tolist()
if not fb.empty and "Fecha" in fb.columns: dates_all += fb["Fecha"].dropna().tolist()
if not yt["grafico"].empty and "Fecha" in yt["grafico"].columns: dates_all += yt["grafico"]["Fecha"].dropna().tolist()

if dates_all:
    dates_all = pd.to_datetime(dates_all)
    min_d, max_d = dates_all.min().date(), dates_all.max().date()
else:
    min_d, max_d = date(2024,1,1), date.today()

with c1:
    start = st.date_input("Desde", value=max_d - timedelta(days=90), min_value=min_d, max_value=max_d, key="soc_start")
with c2:
    end   = st.date_input("Hasta", value=max_d, min_value=min_d, max_value=max_d, key="soc_end")
with c3:
    redes = st.multiselect("Red Social", ["YouTube","Instagram Posts","Instagram Stories","Facebook"],
        default=["YouTube","Instagram Posts","Facebook"])

# Filtrar
ig_f  = filter_by_date(ig,  "Fecha", start, end)
igs_f = filter_by_date(igs, "Fecha", start, end)
fb_f  = filter_by_date(fb,  "Fecha", start, end)
yt_g_f= filter_by_date(yt["grafico"], "Fecha", start, end)

# ── Métricas generales ────────────────────────────────────────────────────────
st.markdown("---")
st.markdown('<div class="section-header">📊 Métricas Generales · Todas las Redes</div>', unsafe_allow_html=True)

# Impresiones totales (reach/views como proxy)
ig_impr  = int(safe_sum(ig_f,  "Visualizaciones")) if "Visualizaciones" in ig_f.columns else 0
igs_impr = int(safe_sum(igs_f, "Visualizaciones")) if "Visualizaciones" in igs_f.columns else 0
fb_impr  = int(safe_sum(fb_f,  "Visualizaciones de vídeo de 3 segundos")) if "Visualizaciones de vídeo de 3 segundos" in fb_f.columns else 0
yt_plays = int(safe_sum(yt_g_f,"Visualizaciones")) if "Visualizaciones" in yt_g_f.columns else 0

ig_reach  = int(safe_sum(ig_f,  "Alcance")) if "Alcance" in ig_f.columns else 0
igs_reach = int(safe_sum(igs_f, "Alcance")) if "Alcance" in igs_f.columns else 0
fb_reach  = int(safe_sum(fb_f,  "Alcance")) if "Alcance" in fb_f.columns else 0

total_impr  = ig_impr + igs_impr + fb_impr + yt_plays
total_reach = ig_reach + igs_reach + fb_reach
ig_pub   = len(ig_f)
igs_pub  = len(igs_f)
fb_pub   = len(fb_f)
total_pub= ig_pub + igs_pub + fb_pub

ig_clicks = int(safe_sum(ig_f, "Clics en el enlace")) if "Clics en el enlace" in ig_f.columns else 0

m1,m2,m3,m4,m5 = st.columns(5)
m1.metric("👁 Impresiones/Plays", fmt_number(total_impr))
m2.metric("📢 Alcance Total", fmt_number(total_reach))
m3.metric("▶️ Plays YT", fmt_number(yt_plays))
m4.metric("📝 Publicaciones", fmt_number(total_pub))
m5.metric("🔗 Clicks a Sitio", fmt_number(ig_clicks))

# ── Evolución alcance por mes ─────────────────────────────────────────────────
st.markdown('<div class="section-header">📈 Evolución de Alcance por Mes</div>', unsafe_allow_html=True)

frames = []
if "Instagram Posts" in redes and not ig_f.empty and "Alcance" in ig_f.columns:
    tmp = ig_f.copy()
    tmp["mes"] = tmp["Fecha"].dt.to_period("M").astype(str)
    tmp2 = tmp.groupby("mes")["Alcance"].sum().reset_index()
    tmp2["Red"] = "Instagram Posts"
    frames.append(tmp2)

if "Instagram Stories" in redes and not igs_f.empty and "Alcance" in igs_f.columns:
    tmp = igs_f.copy()
    tmp["mes"] = tmp["Fecha"].dt.to_period("M").astype(str)
    tmp2 = tmp.groupby("mes")["Alcance"].sum().reset_index()
    tmp2["Red"] = "Instagram Stories"
    frames.append(tmp2)

if "Facebook" in redes and not fb_f.empty and "Alcance" in fb_f.columns:
    tmp = fb_f.copy()
    tmp["mes"] = tmp["Fecha"].dt.to_period("M").astype(str)
    tmp2 = tmp.groupby("mes")["Alcance"].sum().reset_index()
    tmp2["Red"] = "Facebook"
    frames.append(tmp2)

if frames:
    combined = pd.concat(frames, ignore_index=True)
    fig1 = px.line(combined, x="mes", y="Alcance", color="Red",
        title="Alcance por Mes y Red Social", color_discrete_sequence=COLORS,
        markers=True)
    dark_chart(fig1)
    st.plotly_chart(fig1, use_container_width=True)

# ── YouTube ───────────────────────────────────────────────────────────────────
if "YouTube" in redes:
    st.markdown('<div class="section-header">▶️ YouTube</div>', unsafe_allow_html=True)

    yt_tabla = yt["tabla"]
    if not yt_tabla.empty:
        # Gráfico evolución
        if not yt_g_f.empty and "Fecha" in yt_g_f.columns and "Visualizaciones" in yt_g_f.columns:
            yt_m = yt_g_f.copy()
            yt_m["mes"] = yt_m["Fecha"].dt.to_period("M").astype(str)
            yt_monthly = yt_m.groupby("mes")["Visualizaciones"].sum().reset_index()
            fig_yt = px.bar(yt_monthly, x="mes", y="Visualizaciones",
                title="Visualizaciones YouTube por Mes",
                color="Visualizaciones", color_continuous_scale=["#1e1b4b","#ef4444"])
            dark_chart(fig_yt)
            st.plotly_chart(fig_yt, use_container_width=True)

        # Top videos
        view_col = "Visualizaciones" if "Visualizaciones" in yt_tabla.columns else None
        title_col = "Título del vídeo" if "Título del vídeo" in yt_tabla.columns else yt_tabla.columns[0]
        if view_col:
            yt_top = yt_tabla.sort_values(view_col, ascending=False).head(20)
            cols_show = [c for c in [title_col, "Hora de publicación del vídeo", view_col, 
                "Tiempo de visualización (horas)", "Impresiones",
                "Porcentaje de clics de las impresiones (%)", "Ingresos estimados (USD)"] if c in yt_top.columns]
            st.markdown("**🏆 Top Videos**")
            st.dataframe(yt_top[cols_show].style.format({view_col:"{:,.0f}"}), 
                use_container_width=True, hide_index=True)

# ── Instagram Posts ───────────────────────────────────────────────────────────
if "Instagram Posts" in redes and not ig_f.empty:
    st.markdown('<div class="section-header">📸 Instagram Posts</div>', unsafe_allow_html=True)

    ig_c1, ig_c2 = st.columns(2)
    with ig_c1:
        if "Tipo de publicación" in ig_f.columns and "Alcance" in ig_f.columns:
            tipo_agg = ig_f.groupby("Tipo de publicación").agg(
                Alcance=("Alcance","sum"),
                Visualizaciones=("Visualizaciones","sum") if "Visualizaciones" in ig_f.columns else ("Alcance","count"),
                Publicaciones=("Alcance","count")
            ).reset_index().sort_values("Alcance", ascending=False)
            fig_tipo = px.bar(tipo_agg, x="Tipo de publicación", y="Alcance",
                title="Alcance por Formato", color="Tipo de publicación",
                color_discrete_sequence=COLORS)
            dark_chart(fig_tipo, 300)
            st.plotly_chart(fig_tipo, use_container_width=True)

    with ig_c2:
        st.markdown("**📊 Formatos más Exitosos**")
        if "Tipo de publicación" in ig_f.columns:
            fmt_agg = ig_f.groupby("Tipo de publicación").agg(
                Alcance=("Alcance","sum") if "Alcance" in ig_f.columns else ("Tipo de publicación","count"),
                Publicaciones=("identificador de la publicación","count") if "identificador de la publicación" in ig_f.columns else ("Tipo de publicación","count")
            ).reset_index()
            if "Visualizaciones" in ig_f.columns:
                fmt_agg2 = ig_f.groupby("Tipo de publicación")["Visualizaciones"].sum().reset_index()
                fmt_agg = fmt_agg.merge(fmt_agg2, on="Tipo de publicación")
            st.dataframe(fmt_agg.style.format({c:"{:,.0f}" for c in fmt_agg.select_dtypes("number").columns}),
                use_container_width=True, hide_index=True)

# ── Tabla resumen por red social ──────────────────────────────────────────────
st.markdown('<div class="section-header">📊 Resumen por Red Social</div>', unsafe_allow_html=True)

summary_rows = []
if not ig_f.empty:
    summary_rows.append({
        "Red Social": "Instagram Posts",
        "Publicaciones": len(ig_f),
        "Impresiones": int(safe_sum(ig_f, "Visualizaciones")) if "Visualizaciones" in ig_f.columns else 0,
        "Alcance": int(safe_sum(ig_f, "Alcance")) if "Alcance" in ig_f.columns else 0,
        "Tráfico al Sitio": int(safe_sum(ig_f, "Clics en el enlace")) if "Clics en el enlace" in ig_f.columns else 0,
    })
if not igs_f.empty:
    summary_rows.append({
        "Red Social": "Instagram Stories",
        "Publicaciones": len(igs_f),
        "Impresiones": int(safe_sum(igs_f, "Visualizaciones")) if "Visualizaciones" in igs_f.columns else 0,
        "Alcance": int(safe_sum(igs_f, "Alcance")) if "Alcance" in igs_f.columns else 0,
        "Tráfico al Sitio": int(safe_sum(igs_f, "Clics en el enlace")) if "Clics en el enlace" in igs_f.columns else 0,
    })
if not fb_f.empty:
    summary_rows.append({
        "Red Social": "Facebook",
        "Publicaciones": len(fb_f),
        "Impresiones": int(safe_sum(fb_f, "Visualizaciones de vídeo de 3 segundos")) if "Visualizaciones de vídeo de 3 segundos" in fb_f.columns else 0,
        "Alcance": int(safe_sum(fb_f, "Alcance")) if "Alcance" in fb_f.columns else 0,
        "Tráfico al Sitio": 0,
    })
if not yt_g_f.empty:
    summary_rows.append({
        "Red Social": "YouTube",
        "Publicaciones": yt_g_f["Título del vídeo"].nunique() if "Título del vídeo" in yt_g_f.columns else 0,
        "Impresiones": int(safe_sum(yt_g_f, "Visualizaciones")) if "Visualizaciones" in yt_g_f.columns else 0,
        "Alcance": 0,
        "Tráfico al Sitio": 0,
    })

if summary_rows:
    summary_df = pd.DataFrame(summary_rows)
    st.dataframe(summary_df.style.format({c:"{:,.0f}" for c in ["Publicaciones","Impresiones","Alcance","Tráfico al Sitio"]}),
        use_container_width=True, hide_index=True)

# ── Tabla de posts detallada ──────────────────────────────────────────────────
st.markdown('<div class="section-header">📋 Posts Detallados</div>', unsafe_allow_html=True)
red_tab = st.selectbox("Seleccionar red", ["Instagram Posts", "Instagram Stories", "Facebook"])

if red_tab == "Instagram Posts" and not ig_f.empty:
    cols_show = [c for c in ["Descripción","Tipo de publicación","Fecha","Alcance","Visualizaciones",
        "Me gusta","Comentarios","Veces que se ha compartido","Clics en el enlace"] if c in ig_f.columns]
    st.dataframe(ig_f[cols_show].sort_values("Fecha", ascending=False) if "Fecha" in ig_f.columns else ig_f[cols_show],
        use_container_width=True, hide_index=True)

elif red_tab == "Instagram Stories" and not igs_f.empty:
    cols_show = [c for c in ["Descripción","Fecha","Alcance","Visualizaciones","Respuestas","Clics en el enlace"] if c in igs_f.columns]
    st.dataframe(igs_f[cols_show].sort_values("Fecha", ascending=False) if "Fecha" in igs_f.columns else igs_f[cols_show],
        use_container_width=True, hide_index=True)

elif red_tab == "Facebook" and not fb_f.empty:
    cols_show = [c for c in ["Título","Fecha","Alcance","Visualizaciones de vídeo de 3 segundos",
        "Reacciones, comentarios y veces que se ha compartido","Segundos reproducidos de media"] if c in fb_f.columns]
    st.dataframe(fb_f[cols_show].sort_values("Fecha", ascending=False) if "Fecha" in fb_f.columns else fb_f[cols_show],
        use_container_width=True, hide_index=True)
