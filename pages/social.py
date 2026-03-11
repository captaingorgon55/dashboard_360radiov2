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
    load_facebook, filter_by_date, fmt_number, safe_sum, get_date_range, pct_delta
)

C   = ["#6366f1","#06b6d4","#10b981","#f59e0b","#ef4444","#8b5cf6","#ec4899"]
PBG = "#0d0d1e"

def _fig(fig, h=340):
    fig.update_layout(
        height=h, paper_bgcolor=PBG, plot_bgcolor=PBG,
        font=dict(family="Inter", color="#9aa3c2", size=12),
        margin=dict(l=8, r=8, t=38, b=8),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(gridcolor="#181828", zerolinecolor="#181828"),
        yaxis=dict(gridcolor="#181828", zerolinecolor="#181828"),
        title_font=dict(family="Syne", size=14, color="#c8cedc"),
    )
    return fig

def sh(label):
    st.markdown(f'<div class="sec-hdr">{label}</div>', unsafe_allow_html=True)

st.markdown('<div class="page-title">📱 Social Media</div>', unsafe_allow_html=True)
st.markdown('<div class="page-subtitle">YouTube · Instagram · Facebook · Todas las redes</div>', unsafe_allow_html=True)

# ── Carga ─────────────────────────────────────────────────────────────────────
yt  = load_youtube()
ig  = load_instagram_posts()
igs = load_instagram_stories()
fb  = load_facebook()

# ── Detectar rango de fechas cross-platform ───────────────────────────────────
all_dates = []
for df, col in [(ig,"Fecha"),(igs,"Fecha"),(fb,"Fecha"),(yt["grafico"],"Fecha")]:
    if not df.empty and col in df.columns:
        all_dates += pd.to_datetime(df[col], errors="coerce").dropna().tolist()
if all_dates:
    min_d = min(all_dates).date()
    max_d = max(all_dates).date()
else:
    min_d, max_d = date(2024,1,1), date.today()

# ── Filtros ────────────────────────────────────────────────────────────────────
with st.container():
    st.markdown('<div class="filter-box">', unsafe_allow_html=True)
    sh("⚙️ Filtros")
    fc1, fc2, fc3 = st.columns([1.5, 1.5, 3])
    with fc1:
        start = st.date_input("📅 Desde", value=max_d - timedelta(days=90),
                               min_value=min_d, max_value=max_d, key="soc_s")
    with fc2:
        end   = st.date_input("📅 Hasta", value=max_d,
                               min_value=min_d, max_value=max_d, key="soc_e")
    with fc3:
        redes = st.multiselect("📡 Redes sociales",
            ["YouTube","Instagram Posts","Instagram Stories","Facebook"],
            default=["YouTube","Instagram Posts","Instagram Stories","Facebook"])
    st.markdown('</div>', unsafe_allow_html=True)

# Filtrar por fecha
ig_f  = filter_by_date(ig,  "Fecha", start, end)
igs_f = filter_by_date(igs, "Fecha", start, end)
fb_f  = filter_by_date(fb,  "Fecha", start, end)
yt_gf = filter_by_date(yt["grafico"], "Fecha", start, end)

# Período previo
period_days = (end - start).days or 1
ig_p  = filter_by_date(ig,  "Fecha", start-timedelta(days=period_days), start-timedelta(days=1))
igs_p = filter_by_date(igs, "Fecha", start-timedelta(days=period_days), start-timedelta(days=1))
fb_p  = filter_by_date(fb,  "Fecha", start-timedelta(days=period_days), start-timedelta(days=1))
yt_gp = filter_by_date(yt["grafico"], "Fecha", start-timedelta(days=period_days), start-timedelta(days=1))

def _delta(cur, prev):
    d = pct_delta(cur, prev)
    return f"{d:+.1f}%" if d is not None else None

def _s(df, col): return int(safe_sum(df, col)) if not df.empty and col in df.columns else 0

# ── MÉTRICAS GENERALES ────────────────────────────────────────────────────────
sh("📊 Métricas Generales · Todas las Redes")

ig_impr  = _s(ig_f,  "Visualizaciones")
igs_impr = _s(igs_f, "Visualizaciones")
fb_impr  = _s(fb_f,  "Visualizaciones de vídeo de 3 segundos")
yt_plays = _s(yt_gf, "Visualizaciones")

ig_reach  = _s(ig_f,  "Alcance")
igs_reach = _s(igs_f, "Alcance")
fb_reach  = _s(fb_f,  "Alcance")

ig_click  = _s(ig_f, "Clics en el enlace")
igs_click = _s(igs_f, "Clics en el enlace")

total_impr  = ig_impr + igs_impr + fb_impr + yt_plays
total_reach = ig_reach + igs_reach + fb_reach
total_pub   = (len(ig_f) if "Instagram Posts" in redes else 0) + \
              (len(igs_f) if "Instagram Stories" in redes else 0) + \
              (len(fb_f) if "Facebook" in redes else 0)
total_click = ig_click + igs_click

p_impr  = _s(ig_p,"Visualizaciones")+_s(igs_p,"Visualizaciones")+_s(fb_p,"Visualizaciones de vídeo de 3 segundos")+_s(yt_gp,"Visualizaciones")
p_reach = _s(ig_p,"Alcance")+_s(igs_p,"Alcance")+_s(fb_p,"Alcance")

m1,m2,m3,m4,m5 = st.columns(5)
m1.metric("👁 Impresiones / Plays", fmt_number(total_impr), _delta(total_impr, p_impr))
m2.metric("📢 Alcance Total",       fmt_number(total_reach), _delta(total_reach, p_reach))
m3.metric("▶️ Plays YouTube",       fmt_number(yt_plays),   _delta(yt_plays, _s(yt_gp,"Visualizaciones")))
m4.metric("📝 Publicaciones",       fmt_number(total_pub))
m5.metric("🔗 Clicks al Sitio",     fmt_number(total_click), _delta(total_click, _s(ig_p,"Clics en el enlace")+_s(igs_p,"Clics en el enlace")))

# ── EVOLUCIÓN ALCANCE ─────────────────────────────────────────────────────────
sh("📈 Evolución de Alcance por Mes")
frames = []
color_map = {}
if "Instagram Posts" in redes and not ig_f.empty and "Alcance" in ig_f.columns:
    t = ig_f.copy(); t["mes"]=t["Fecha"].dt.to_period("M").astype(str)
    tmp = t.groupby("mes")["Alcance"].sum().reset_index(); tmp["Red"]="Instagram Posts"
    frames.append(tmp); color_map["Instagram Posts"] = C[1]
if "Instagram Stories" in redes and not igs_f.empty and "Alcance" in igs_f.columns:
    t = igs_f.copy(); t["mes"]=t["Fecha"].dt.to_period("M").astype(str)
    tmp = t.groupby("mes")["Alcance"].sum().reset_index(); tmp["Red"]="Instagram Stories"
    frames.append(tmp); color_map["Instagram Stories"] = C[6]
if "Facebook" in redes and not fb_f.empty and "Alcance" in fb_f.columns:
    t = fb_f.copy(); t["mes"]=t["Fecha"].dt.to_period("M").astype(str)
    tmp = t.groupby("mes")["Alcance"].sum().reset_index(); tmp["Red"]="Facebook"
    frames.append(tmp); color_map["Facebook"] = C[0]

if frames:
    combined = pd.concat(frames, ignore_index=True)
    fig1 = px.line(combined, x="mes", y="Alcance", color="Red",
        markers=True, color_discrete_map=color_map)
    fig1.update_traces(line_width=2.5, marker_size=7)
    _fig(fig1, 340)
    st.plotly_chart(fig1, use_container_width=True)
else:
    st.info("Selecciona al menos una red con datos de alcance.")

# ── TABLA RESUMEN ─────────────────────────────────────────────────────────────
sh("📊 Resumen Comparativo por Red Social")
rows = []
if "Instagram Posts" in redes and not ig_f.empty:
    rows.append({
        "Red Social": "📸 Instagram Posts",
        "Publicaciones": len(ig_f),
        "Impresiones/Plays": _s(ig_f,"Visualizaciones"),
        "Alcance": _s(ig_f,"Alcance"),
        "Tráfico al Sitio": _s(ig_f,"Clics en el enlace"),
        "Me Gusta": _s(ig_f,"Me gusta"),
        "Comentarios": _s(ig_f,"Comentarios") if "Comentarios" in ig_f.columns else 0,
    })
if "Instagram Stories" in redes and not igs_f.empty:
    rows.append({
        "Red Social": "💬 Instagram Stories",
        "Publicaciones": len(igs_f),
        "Impresiones/Plays": _s(igs_f,"Visualizaciones"),
        "Alcance": _s(igs_f,"Alcance"),
        "Tráfico al Sitio": _s(igs_f,"Clics en el enlace"),
        "Me Gusta": _s(igs_f,"Me gusta"),
        "Comentarios": _s(igs_f,"Respuestas") if "Respuestas" in igs_f.columns else 0,
    })
if "Facebook" in redes and not fb_f.empty:
    rows.append({
        "Red Social": "👥 Facebook",
        "Publicaciones": len(fb_f),
        "Impresiones/Plays": _s(fb_f,"Visualizaciones de vídeo de 3 segundos"),
        "Alcance": _s(fb_f,"Alcance"),
        "Tráfico al Sitio": 0,
        "Me Gusta": _s(fb_f,"Reacciones"),
        "Comentarios": _s(fb_f,"Comentarios") if "Comentarios" in fb_f.columns else 0,
    })
if "YouTube" in redes and not yt_gf.empty:
    rows.append({
        "Red Social": "▶️ YouTube",
        "Publicaciones": yt_gf["Título del vídeo"].nunique() if "Título del vídeo" in yt_gf.columns else 0,
        "Impresiones/Plays": _s(yt_gf,"Visualizaciones"),
        "Alcance": 0,
        "Tráfico al Sitio": 0,
        "Me Gusta": 0,
        "Comentarios": 0,
    })

if rows:
    summary = pd.DataFrame(rows)
    num_cols = [c for c in summary.columns if c != "Red Social"]
    st.dataframe(
        summary.style.format({c:"{:,.0f}" for c in num_cols}),
        use_container_width=True, hide_index=True
    )

# ── YOUTUBE ───────────────────────────────────────────────────────────────────
if "YouTube" in redes:
    sh("▶️ YouTube · Rendimiento")
    yt_tabla = yt["tabla"]
    if not yt_tabla.empty:
        # KPIs
        yt_m1, yt_m2, yt_m3, yt_m4 = st.columns(4)
        yt_m1.metric("▶️ Total Visualizaciones", fmt_number(_s(yt_tabla,"Visualizaciones")))
        yt_m2.metric("💰 Ingresos Estimados",    f"${safe_sum(yt_tabla,'Ingresos estimados (USD)'):.2f}" if "Ingresos estimados (USD)" in yt_tabla.columns else "—")
        yt_m3.metric("🔔 Suscriptores",           fmt_number(_s(yt_tabla,"Suscriptores")))
        yt_m4.metric("📢 Impresiones",            fmt_number(_s(yt_tabla,"Impresiones")))

        # Evolución
        if not yt_gf.empty and "Fecha" in yt_gf.columns and "Visualizaciones" in yt_gf.columns:
            yt_c = yt_gf.copy()
            yt_c["mes"] = yt_c["Fecha"].dt.to_period("M").astype(str)
            yt_m = yt_c.groupby("mes")["Visualizaciones"].sum().reset_index()
            fig_yt = px.bar(yt_m, x="mes", y="Visualizaciones",
                color="Visualizaciones", color_continuous_scale=["#1a0505","#ef4444"],
                text="Visualizaciones")
            fig_yt.update_traces(texttemplate="%{text:,.0f}", textposition="outside", textfont_size=9)
            fig_yt.update_layout(coloraxis_showscale=False, title="Visualizaciones YouTube por Mes")
            _fig(fig_yt, 300)
            st.plotly_chart(fig_yt, use_container_width=True)

        # Tabla top videos
        view_col  = "Visualizaciones" if "Visualizaciones" in yt_tabla.columns else None
        title_col = "Título del vídeo" if "Título del vídeo" in yt_tabla.columns else yt_tabla.columns[0]
        if view_col:
            yt_top = yt_tabla.sort_values(view_col, ascending=False).head(25)
            show_yt = [c for c in [title_col, "Hora de publicación del vídeo", view_col,
                "Tiempo de visualización (horas)", "Impresiones",
                "Porcentaje de clics de las impresiones (%)",
                "Ingresos estimados (USD)"] if c in yt_top.columns]
            sh("🏆 Top Videos")
            st.dataframe(yt_top[show_yt].style.format({view_col:"{:,.0f}"}),
                use_container_width=True, hide_index=True)

# ── FORMATOS MÁS EXITOSOS ─────────────────────────────────────────────────────
if ("Instagram Posts" in redes and not ig_f.empty) or ("Instagram Stories" in redes and not igs_f.empty):
    sh("📐 Formatos más Exitosos · Instagram")
    fc1, fc2 = st.columns(2)
    if "Instagram Posts" in redes and not ig_f.empty and "Tipo de publicación" in ig_f.columns:
        tipo_agg = (
            ig_f.groupby("Tipo de publicación")
            .agg(Alcance=("Alcance","sum") if "Alcance" in ig_f.columns else ("Tipo de publicación","count"),
                 Publicaciones=("identificador de la publicación","count") if "identificador de la publicación" in ig_f.columns else ("Tipo de publicación","count"))
            .reset_index().sort_values("Alcance", ascending=False)
        )
        if "Visualizaciones" in ig_f.columns:
            viz = ig_f.groupby("Tipo de publicación")["Visualizaciones"].sum().reset_index()
            tipo_agg = tipo_agg.merge(viz, on="Tipo de publicación", how="left")

        with fc1:
            fig_t = px.bar(tipo_agg, x="Tipo de publicación", y="Alcance",
                color="Tipo de publicación", color_discrete_sequence=C,
                text="Alcance", title="Alcance por Formato · Posts")
            fig_t.update_traces(texttemplate="%{text:,.0f}", textposition="outside", textfont_size=10)
            fig_t.update_layout(showlegend=False)
            _fig(fig_t, 300)
            st.plotly_chart(fig_t, use_container_width=True)
        with fc2:
            sh("📊 Tabla de Formatos")
            st.dataframe(tipo_agg.style.format(
                {c:"{:,.0f}" for c in tipo_agg.select_dtypes("number").columns}),
                use_container_width=True, hide_index=True)

# ── TABLA DE POSTS ────────────────────────────────────────────────────────────
sh("📋 Posts Detallados")
red_tab = st.selectbox("Red Social", ["Instagram Posts","Instagram Stories","Facebook"],
    key="soc_tab_red")

if red_tab == "Instagram Posts" and not ig_f.empty:
    show = [c for c in ["Descripción","Tipo de publicación","Fecha","Alcance",
        "Visualizaciones","Me gusta","Comentarios","Veces que se ha compartido",
        "Clics en el enlace"] if c in ig_f.columns]
    sort_col = "Alcance" if "Alcance" in ig_f.columns else ig_f.columns[0]
    st.dataframe(ig_f[show].sort_values(sort_col, ascending=False),
        use_container_width=True, hide_index=True)

elif red_tab == "Instagram Stories" and not igs_f.empty:
    show = [c for c in ["Descripción","Fecha","Alcance","Visualizaciones",
        "Respuestas","Clics en el enlace","Me gusta"] if c in igs_f.columns]
    sort_col = "Alcance" if "Alcance" in igs_f.columns else igs_f.columns[0]
    st.dataframe(igs_f[show].sort_values(sort_col, ascending=False),
        use_container_width=True, hide_index=True)

elif red_tab == "Facebook" and not fb_f.empty:
    show = [c for c in ["Título","Fecha","Alcance",
        "Visualizaciones de vídeo de 3 segundos",
        "Reacciones, comentarios y veces que se ha compartido",
        "Segundos reproducidos de media"] if c in fb_f.columns]
    sort_col = "Alcance" if "Alcance" in fb_f.columns else fb_f.columns[0]
    st.dataframe(fb_f[show].sort_values(sort_col, ascending=False),
        use_container_width=True, hide_index=True)
