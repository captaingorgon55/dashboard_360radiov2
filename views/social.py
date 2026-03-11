import sys, os; sys.path.insert(0, os.getcwd())
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta
from data_loader import (
    load_youtube, load_instagram_posts, load_instagram_stories, load_facebook,
    filter_by_date, fmt_number, safe_sum, get_date_range, _delta_str
)

C = ["#6366f1","#06b6d4","#10b981","#f59e0b","#ef4444","#8b5cf6","#ec4899"]
PBG = "#0d0d20"

def _fig(fig, h=320):
    fig.update_layout(height=h, paper_bgcolor=PBG, plot_bgcolor=PBG,
        font=dict(family="Inter",color="#8890b8",size=11),
        margin=dict(l=6,r=6,t=34,b=6),
        legend=dict(bgcolor="rgba(0,0,0,0)",font_size=11),
        xaxis=dict(gridcolor="#14142e",zerolinecolor="#14142e"),
        yaxis=dict(gridcolor="#14142e",zerolinecolor="#14142e"),
        title_font=dict(family="Syne",size=13,color="#c0c8e8"))
    return fig

def sh(t): st.markdown(f'<div class="sec-hdr">{t}</div>', unsafe_allow_html=True)

def _col(df, *candidates, default=0):
    """Devuelve la primera columna que exista, o default."""
    for c in candidates:
        if c in df.columns:
            return df[c]
    return pd.Series([default]*len(df), index=df.index)

def _scol(df, *candidates):
    for c in candidates:
        if c in df.columns: return c
    return None

st.markdown('<div class="page-title">📱 Social Media</div>', unsafe_allow_html=True)
st.markdown('<div class="page-subtitle">Instagram · Facebook · YouTube</div>', unsafe_allow_html=True)

# ── Carga ─────────────────────────────────────────────────────────────────────
with st.spinner("Cargando redes sociales..."):
    ig_raw  = load_instagram_posts()
    igs_raw = load_instagram_stories()
    fb_raw  = load_facebook()
    yt      = load_youtube()

# Debug: mostrar columnas reales si hay problemas
def _debug_cols(df, name):
    if df.empty:
        st.warning(f"⚠️ {name}: archivo no encontrado o vacío.")
    else:
        with st.expander(f"🔬 Columnas de {name} ({len(df)} filas)", expanded=False):
            st.write(list(df.columns))

_debug_cols(ig_raw,  "Post Instagram.csv")
_debug_cols(igs_raw, "Instagram Historys.csv")
_debug_cols(fb_raw,  "Post Facebook.csv")

# ── Detectar rangos de fechas disponibles ─────────────────────────────────────
all_dates = []
for df, col in [(ig_raw,"Fecha"),(igs_raw,"Fecha"),(fb_raw,"Fecha")]:
    if not df.empty and col in df.columns:
        all_dates += pd.to_datetime(df[col],errors="coerce").dropna().tolist()
yt_g = yt.get("grafico", pd.DataFrame())
if not yt_g.empty and "Fecha" in yt_g.columns:
    all_dates += pd.to_datetime(yt_g["Fecha"],errors="coerce").dropna().tolist()

min_d = min(all_dates).date() if all_dates else date(2024,1,1)
max_d = max(all_dates).date() if all_dates else date.today()

# ── FILTROS ───────────────────────────────────────────────────────────────────
sh("⚙️ Filtros")
st.markdown('<div class="filter-box">', unsafe_allow_html=True)
fc1,fc2,fc3 = st.columns([1.5,1.5,3])
with fc1: start = st.date_input("📅 Desde", max_d-timedelta(days=90), min_value=min_d, max_value=max_d, key="soc_s")
with fc2: end   = st.date_input("📅 Hasta", max_d, min_value=min_d, max_value=max_d, key="soc_e")
with fc3:
    redes = st.multiselect("📡 Redes",
        ["Instagram Posts","Instagram Stories","Facebook","YouTube"],
        default=["Instagram Posts","Instagram Stories","Facebook","YouTube"])
st.markdown('</div>', unsafe_allow_html=True)

# Aplicar filtros
ig  = filter_by_date(ig_raw,  "Fecha", start, end) if not ig_raw.empty  else pd.DataFrame()
igs = filter_by_date(igs_raw, "Fecha", start, end) if not igs_raw.empty else pd.DataFrame()
fb  = filter_by_date(fb_raw,  "Fecha", start, end) if not fb_raw.empty  else pd.DataFrame()
yt_gf = filter_by_date(yt_g, "Fecha", start, end)  if not yt_g.empty   else pd.DataFrame()

# Período previo
pd_ = max((end-start).days,1)
ig_p  = filter_by_date(ig_raw,  "Fecha", start-timedelta(days=pd_), start-timedelta(days=1)) if not ig_raw.empty  else pd.DataFrame()
igs_p = filter_by_date(igs_raw, "Fecha", start-timedelta(days=pd_), start-timedelta(days=1)) if not igs_raw.empty else pd.DataFrame()
fb_p  = filter_by_date(fb_raw,  "Fecha", start-timedelta(days=pd_), start-timedelta(days=1)) if not fb_raw.empty  else pd.DataFrame()

# ── Helpers para sumar columnas de forma robusta ──────────────────────────────
def _s(df, *cols):
    for c in cols:
        if not df.empty and c in df.columns:
            return int(safe_sum(df, c))
    return 0

# Post Instagram: Visualizaciones, Alcance, Me gusta, Comentarios, Veces que se ha compartido, Veces guardado
ig_impr  = _s(ig,  "Visualizaciones")
ig_reach = _s(ig,  "Alcance")
ig_likes = _s(ig,  "Me gusta")

# Instagram Stories: Visualizaciones, Alcance, Respuestas, Clics en el enlace
igs_impr  = _s(igs, "Visualizaciones")
igs_reach = _s(igs, "Alcance")
igs_click = _s(igs, "Clics en el enlace")

# Facebook: Alcance, Visualizaciones de vídeo de 3 segundos, Reacciones
fb_reach = _s(fb, "Alcance")
fb_impr  = _s(fb, "Visualizaciones de vídeo de 3 segundos","Visualizaciones")
fb_react = _s(fb, "Reacciones, comentarios y veces que se ha compartido","Reacciones")

# YouTube
yt_tb   = yt.get("tabla", pd.DataFrame())
yt_plays = _s(yt_gf, "Visualizaciones")

total_impr  = ig_impr + igs_impr + fb_impr + yt_plays
total_reach = ig_reach + igs_reach + fb_reach
total_pub   = (len(ig) if "Instagram Posts" in redes else 0) + \
              (len(igs) if "Instagram Stories" in redes else 0) + \
              (len(fb) if "Facebook" in redes else 0)
total_click = igs_click + _s(ig, "Veces que se ha compartido")

p_impr  = _s(ig_p,"Visualizaciones")+_s(igs_p,"Visualizaciones")+_s(fb_p,"Visualizaciones de vídeo de 3 segundos","Visualizaciones")
p_reach = _s(ig_p,"Alcance")+_s(igs_p,"Alcance")+_s(fb_p,"Alcance")

# ── MÉTRICAS ──────────────────────────────────────────────────────────────────
sh("📊 Métricas Generales — Todas las Redes")
m1,m2,m3,m4,m5 = st.columns(5)
m1.metric("👁 Impresiones/Plays", fmt_number(total_impr),  _delta_str(total_impr,p_impr))
m2.metric("📢 Alcance Total",     fmt_number(total_reach), _delta_str(total_reach,p_reach))
m3.metric("▶️ Plays YouTube",     fmt_number(yt_plays))
m4.metric("📝 Publicaciones",     fmt_number(total_pub))
m5.metric("🔗 Clicks/Compartidos",fmt_number(total_click))

# ── TABLA RESUMEN ─────────────────────────────────────────────────────────────
sh("📊 Resumen por Red Social")
rows = []
if "Instagram Posts" in redes and not ig.empty:
    rows.append({"Red":"📸 Instagram Posts","Publicaciones":len(ig),"Impresiones":ig_impr,
        "Alcance":ig_reach,"Me gusta":ig_likes,"Comentarios":_s(ig,"Comentarios"),"Guardado":_s(ig,"Veces guardado"),"Compartidos":_s(ig,"Veces que se ha compartido")})
if "Instagram Stories" in redes and not igs.empty:
    rows.append({"Red":"💬 Instagram Stories","Publicaciones":len(igs),"Impresiones":igs_impr,
        "Alcance":igs_reach,"Me gusta":_s(igs,"Me gusta"),"Comentarios":_s(igs,"Respuestas"),"Guardado":0,"Compartidos":_s(igs,"Clics en el enlace")})
if "Facebook" in redes and not fb.empty:
    rows.append({"Red":"👥 Facebook","Publicaciones":len(fb),"Impresiones":fb_impr,
        "Alcance":fb_reach,"Me gusta":_s(fb,"Reacciones"),"Comentarios":_s(fb,"Comentarios"),"Guardado":0,"Compartidos":_s(fb,"Veces que se ha compartido")})
if "YouTube" in redes and not yt_tb.empty:
    rows.append({"Red":"▶️ YouTube","Publicaciones":_s(yt_tb,"Vídeos"),
        "Impresiones":_s(yt_gf,"Visualizaciones"),"Alcance":0,"Me gusta":0,"Comentarios":0,"Guardado":0,"Compartidos":0})
if rows:
    r_df=pd.DataFrame(rows)
    ncols=[c for c in r_df.columns if c!="Red"]
    st.dataframe(r_df.style.format({c:"{:,.0f}" for c in ncols}),use_container_width=True,hide_index=True)

# ── EVOLUCIÓN ALCANCE ─────────────────────────────────────────────────────────
sh("📈 Alcance por Mes")
frames=[]; cmap={}
for df_, label, color in [(ig,"📸 Instagram Posts",C[1]),(igs,"💬 Stories",C[6]),(fb,"👥 Facebook",C[0])]:
    if label.split()[0].strip("📸💬👥").strip() in " ".join(redes) or any(x in label for x in redes):
        if not df_.empty and "Alcance" in df_.columns and "Fecha" in df_.columns:
            t=df_.copy(); t["mes"]=t["Fecha"].dt.to_period("M").astype(str)
            tmp=t.groupby("mes")["Alcance"].sum().reset_index(); tmp["Red"]=label
            frames.append(tmp); cmap[label]=color

# Simplify: always try to add all selected
frames2=[]; cmap2={}
for df_, label, color in [
    (ig, "Instagram Posts", C[1]),
    (igs,"Instagram Stories", C[6]),
    (fb, "Facebook", C[0])]:
    if label in redes and not df_.empty and "Alcance" in df_.columns and "Fecha" in df_.columns:
        t=df_.copy(); t["mes"]=t["Fecha"].dt.to_period("M").astype(str)
        tmp=t.groupby("mes")["Alcance"].sum().reset_index(); tmp["Red"]=label
        frames2.append(tmp); cmap2[label]=color

if frames2:
    combined=pd.concat(frames2,ignore_index=True)
    f_evo=px.line(combined,x="mes",y="Alcance",color="Red",markers=True,color_discrete_map=cmap2)
    f_evo.update_traces(line_width=2.5,marker_size=7)
    _fig(f_evo,320); st.plotly_chart(f_evo,use_container_width=True)
else:
    st.info("No hay datos de alcance para el período.")

# ── YOUTUBE ───────────────────────────────────────────────────────────────────
if "YouTube" in redes:
    sh("▶️ YouTube — Rendimiento")
    yt_tabla = yt.get("tabla", pd.DataFrame())
    if not yt_tabla.empty:
        ym1,ym2,ym3,ym4 = st.columns(4)
        ym1.metric("▶️ Visualizaciones", fmt_number(_s(yt_tabla,"Visualizaciones")))
        ym2.metric("📢 Impresiones",     fmt_number(_s(yt_tabla,"Impresiones")))
        ym3.metric("🔔 Suscriptores",    fmt_number(_s(yt_tabla,"Suscriptores")))
        rev_col = _scol(yt_tabla,"Ingresos estimados (USD)","Ingresos estimados","Revenue")
        ym4.metric("💰 Revenue",         f"${safe_sum(yt_tabla,rev_col):.2f}" if rev_col else "—")

        # Top videos
        view_col = _scol(yt_tabla,"Visualizaciones")
        title_col = _scol(yt_tabla,"Título del vídeo","Título","Title")
        if view_col and title_col:
            sh("🏆 Top Videos")
            top_cols = [c for c in [title_col,"Hora de publicación del vídeo","Hora de publicación",
                view_col,"Tiempo de visualización (horas)","Impresiones",
                "Porcentaje de clics de las impresiones (%)","Ingresos estimados (USD)"] if c in yt_tabla.columns]
            top_yt = yt_tabla.sort_values(view_col,ascending=False).head(30)
            st.dataframe(top_yt[top_cols].style.format({view_col:"{:,.0f}"}),use_container_width=True,hide_index=True)

        # Evolución mensual
        if not yt_gf.empty and "Fecha" in yt_gf.columns and "Visualizaciones" in yt_gf.columns:
            sh("📅 Visualizaciones YouTube por Mes")
            yc=yt_gf.copy(); yc["mes"]=yc["Fecha"].dt.to_period("M").astype(str)
            ym=yc.groupby("mes")["Visualizaciones"].sum().reset_index()
            fy=px.bar(ym,x="mes",y="Visualizaciones",color="Visualizaciones",
                color_continuous_scale=["#200a0a","#ef4444"],text="Visualizaciones")
            fy.update_traces(texttemplate="%{text:,.0f}",textposition="outside",textfont_size=9)
            fy.update_layout(coloraxis_showscale=False); _fig(fy,280); st.plotly_chart(fy,use_container_width=True)
    else:
        st.info("Sin datos de YouTube.")

# ── INSTAGRAM POSTS ───────────────────────────────────────────────────────────
if "Instagram Posts" in redes and not ig.empty:
    sh("📸 Instagram Posts — Detalle")
    # Formatos
    if "Tipo de publicación" in ig.columns and "Alcance" in ig.columns:
        tipo=ig.groupby("Tipo de publicación",as_index=False).agg(
            Alcance=("Alcance","sum"),
            Publicaciones=("id_post","count") if "id_post" in ig.columns else ("Tipo de publicación","count"),
            Visualizaciones=("Visualizaciones","sum") if "Visualizaciones" in ig.columns else ("Alcance","count")
        ).sort_values("Alcance",ascending=False)
        t1_,t2_=st.columns([1,2])
        with t1_:
            ft=px.bar(tipo,x="Tipo de publicación",y="Alcance",color="Tipo de publicación",
                color_discrete_sequence=C,text="Alcance")
            ft.update_traces(texttemplate="%{text:,.0f}",textposition="outside",textfont_size=10)
            ft.update_layout(showlegend=False,xaxis_title="",title="Alcance por Formato")
            _fig(ft,280); st.plotly_chart(ft,use_container_width=True)
        with t2_:
            st.dataframe(tipo.style.format({c:"{:,.0f}" for c in tipo.select_dtypes("number").columns}),
                use_container_width=True,hide_index=True)

    # Tabla completa
    show_ig=[c for c in ["Descripción","Tipo de publicación","Fecha","Alcance","Visualizaciones",
        "Me gusta","Comentarios","Veces que se ha compartido","Veces guardado","Seguidores"] if c in ig.columns]
    sort_ig = "Alcance" if "Alcance" in ig.columns else (show_ig[0] if show_ig else None)
    if sort_ig and show_ig:
        with st.expander("📋 Ver todos los posts de Instagram", expanded=False):
            st.dataframe(ig[show_ig].sort_values(sort_ig,ascending=False),
                use_container_width=True,hide_index=True)

# ── INSTAGRAM STORIES ─────────────────────────────────────────────────────────
if "Instagram Stories" in redes and not igs.empty:
    sh("💬 Instagram Stories — Detalle")
    show_igs=[c for c in ["Descripción","Tipo de publicación","Fecha","Visualizaciones","Alcance",
        "Me gusta","Respuestas","Clics en el enlace","Seguidores"] if c in igs.columns]
    sort_igs="Alcance" if "Alcance" in igs.columns else (show_igs[0] if show_igs else None)
    if sort_igs and show_igs:
        im1,im2,im3,im4 = st.columns(4)
        im1.metric("👁 Visualizaciones", fmt_number(igs_impr))
        im2.metric("📢 Alcance",         fmt_number(igs_reach))
        im3.metric("🔗 Clics enlace",    fmt_number(_s(igs,"Clics en el enlace")))
        im4.metric("💬 Respuestas",      fmt_number(_s(igs,"Respuestas")))
        with st.expander("📋 Ver todas las stories", expanded=False):
            st.dataframe(igs[show_igs].sort_values(sort_igs,ascending=False),
                use_container_width=True,hide_index=True)

# ── FACEBOOK ─────────────────────────────────────────────────────────────────
if "Facebook" in redes and not fb.empty:
    sh("👥 Facebook — Detalle")
    fm1,fm2,fm3,fm4 = st.columns(4)
    fm1.metric("📢 Alcance",          fmt_number(fb_reach))
    fm2.metric("▶️ Views 3s",         fmt_number(fb_impr))
    fm3.metric("❤️ Reacciones",       fmt_number(_s(fb,"Reacciones","Reacciones, comentarios y veces que se ha compartido")))
    fm4.metric("💬 Comentarios",       fmt_number(_s(fb,"Comentarios")))

    # Evolución alcance FB
    if "Alcance" in fb.columns and "Fecha" in fb.columns:
        fbc=fb.copy(); fbc["mes"]=fbc["Fecha"].dt.to_period("M").astype(str)
        fbm=fbc.groupby("mes")["Alcance"].sum().reset_index()
        ff=px.bar(fbm,x="mes",y="Alcance",color="Alcance",color_continuous_scale=["#08081a","#6366f1"],text="Alcance")
        ff.update_traces(texttemplate="%{text:,.0f}",textposition="outside",textfont_size=9)
        ff.update_layout(coloraxis_showscale=False,title="Alcance Facebook por Mes"); _fig(ff,260); st.plotly_chart(ff,use_container_width=True)

    show_fb=[c for c in ["Título","Fecha","Alcance","Visualizaciones de vídeo de 3 segundos",
        "Visualizaciones de vídeo de 1 minuto","Reacciones","Comentarios",
        "Veces que se ha compartido","Segundos reproducidos de media"] if c in fb.columns]
    sort_fb="Alcance" if "Alcance" in fb.columns else (show_fb[0] if show_fb else None)
    if sort_fb and show_fb:
        with st.expander("📋 Ver todos los posts de Facebook", expanded=False):
            st.dataframe(fb[show_fb].sort_values(sort_fb,ascending=False),
                use_container_width=True,hide_index=True)
