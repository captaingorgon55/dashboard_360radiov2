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

C   = ["#6366f1","#06b6d4","#10b981","#f59e0b","#ef4444","#8b5cf6","#ec4899"]
PBG = "#0d0d20"

def _fig(fig, h=300):
    fig.update_layout(height=h, paper_bgcolor=PBG, plot_bgcolor=PBG,
        font=dict(family="Inter", color="#8890b8", size=11),
        margin=dict(l=6,r=6,t=36,b=6),
        legend=dict(bgcolor="rgba(0,0,0,0)", font_size=11),
        xaxis=dict(gridcolor="#14142e", zerolinecolor="#14142e"),
        yaxis=dict(gridcolor="#14142e", zerolinecolor="#14142e"),
        title_font=dict(family="Syne", size=13, color="#c0c8e8"))
    return fig

def sh(t): st.markdown(f'<div class="sec-hdr">{t}</div>', unsafe_allow_html=True)

def _s(df, *cols):
    for c in cols:
        if not df.empty and c in df.columns:
            return int(safe_sum(df, c))
    return 0

def _fc(df, *cols):
    """Retorna la primera columna que exista en df, buscando también variantes sin tilde."""
    import unicodedata
    def _norm(s):
        return "".join(c for c in unicodedata.normalize("NFD", s)
                       if unicodedata.category(c) != "Mn").lower().strip()
    df_cols_norm = {_norm(c): c for c in df.columns} if not df.empty else {}
    for col in cols:
        if not df.empty and col in df.columns:
            return col
        # Buscar sin tilde
        col_norm = _norm(col)
        if col_norm in df_cols_norm:
            return df_cols_norm[col_norm]
    return None

# ─── Título de Facebook: columna exacta del CSV ──────────────────────────────
FB_TITULO = "T\u00edtulo"   # "Título" en UTF-8

st.markdown('<div class="page-title">📱 Social Media</div>', unsafe_allow_html=True)
st.markdown('<div class="page-subtitle">Instagram Posts · Instagram Stories · Facebook · YouTube</div>', unsafe_allow_html=True)

with st.spinner("Cargando redes sociales..."):
    ig_raw  = load_instagram_posts()
    igs_raw = load_instagram_stories()
    fb_raw  = load_facebook()
    yt      = load_youtube()

yt_g   = yt.get("grafico",  pd.DataFrame())
yt_t   = yt.get("tabla",    pd.DataFrame())
yt_tot = yt.get("totales",  pd.DataFrame())

# Debug expandible
with st.expander("🔬 Debug — archivos cargados", expanded=False):
    for nombre, df_ in [("IG Posts", ig_raw),("IG Stories", igs_raw),("Facebook", fb_raw)]:
        if df_.empty:
            st.error(f"❌ {nombre}: vacío o no encontrado en data/")
        else:
            mn = df_["fecha_post"].min().date() if "fecha_post" in df_.columns and df_["fecha_post"].notna().any() else "?"
            mx = df_["fecha_post"].max().date() if "fecha_post" in df_.columns and df_["fecha_post"].notna().any() else "?"
            st.success(f"✅ {nombre}: {len(df_)} filas | {mn} → {mx}")
            st.caption(f"Columnas: {', '.join(df_.columns[:12])}{'...' if len(df_.columns)>12 else ''}")
    # Mostrar columna título FB para debug
    if not fb_raw.empty:
        titulo_col = _fc(fb_raw, FB_TITULO, "Titulo", "titulo")
        st.caption(f"FB columna título detectada: `{titulo_col}`")

# Rango de fechas disponible
all_d = []
for df_, col in [(ig_raw,"fecha_post"),(igs_raw,"fecha_post"),(fb_raw,"fecha_post")]:
    if not df_.empty and col in df_.columns:
        all_d += df_[col].dropna().tolist()
if not yt_g.empty and "Fecha" in yt_g.columns:
    all_d += pd.to_datetime(yt_g["Fecha"], errors="coerce").dropna().tolist()

min_d = min(all_d).date() if all_d else date(2024,1,1)
max_d = max(all_d).date() if all_d else date.today()

# FILTROS
sh("⚙️ Filtros")
st.markdown('<div class="filter-box">', unsafe_allow_html=True)
fc1,fc2,fc3 = st.columns([1.4,1.4,3.2])
with fc1: start = st.date_input("📅 Desde", max_d-timedelta(days=90), min_value=min_d, max_value=max_d, key="gs")
with fc2: end   = st.date_input("📅 Hasta", max_d, min_value=min_d, max_value=max_d, key="soc_e")
with fc3:
    redes = st.multiselect("📡 Redes", ["Instagram Posts","Instagram Stories","Facebook","YouTube"],
        default=["Instagram Posts","Instagram Stories","Facebook","YouTube"], key="soc_r")
st.markdown('</div>', unsafe_allow_html=True)

# Aplicar filtros
ig    = filter_by_date(ig_raw,  "fecha_post", start, end) if not ig_raw.empty  else pd.DataFrame()
igs   = filter_by_date(igs_raw, "fecha_post", start, end) if not igs_raw.empty else pd.DataFrame()
fb    = filter_by_date(fb_raw,  "fecha_post", start, end) if not fb_raw.empty  else pd.DataFrame()
yt_gf = filter_by_date(yt_g,   "Fecha",      start, end) if not yt_g.empty    else pd.DataFrame()

pd_  = max((end-start).days,1)
ps,pe = start-timedelta(days=pd_), start-timedelta(days=1)
ig_p  = filter_by_date(ig_raw,  "fecha_post", ps, pe) if not ig_raw.empty  else pd.DataFrame()
igs_p = filter_by_date(igs_raw, "fecha_post", ps, pe) if not igs_raw.empty else pd.DataFrame()
fb_p  = filter_by_date(fb_raw,  "fecha_post", ps, pe) if not fb_raw.empty  else pd.DataFrame()

# Solo redes seleccionadas
ig_s  = ig  if "Instagram Posts"   in redes else pd.DataFrame()
igs_s = igs if "Instagram Stories" in redes else pd.DataFrame()
fb_s  = fb  if "Facebook"          in redes else pd.DataFrame()

# Métricas período
ig_views  = _s(ig_s,  "Visualizaciones");  ig_reach = _s(ig_s,  "Alcance")
ig_likes  = _s(ig_s,  "Me gusta");         ig_comm  = _s(ig_s,  "Comentarios")
ig_share  = _s(ig_s,  "Veces que se ha compartido")
ig_save   = _s(ig_s,  "Veces guardado");   ig_n     = len(ig_s)

igs_views = _s(igs_s, "Visualizaciones");  igs_reach = _s(igs_s, "Alcance")
igs_click = _s(igs_s, "Clics en el enlace"); igs_resp = _s(igs_s, "Respuestas"); igs_n = len(igs_s)

fb_reach  = _s(fb_s,  "Alcance");          fb_v3   = _s(fb_s,  "Visualizaciones de vídeo de 3 segundos")
fb_v1     = _s(fb_s,  "Visualizaciones de vídeo de 1 minuto")
fb_react  = _s(fb_s,  "Reacciones");       fb_comm = _s(fb_s,  "Comentarios")
fb_share  = _s(fb_s,  "Veces que se ha compartido"); fb_n = len(fb_s)

yt_plays  = _s(yt_gf, "Visualizaciones") if "YouTube" in redes else 0

# Previos
ig_p_v  = _s(ig_p,  "Visualizaciones"); ig_p_r  = _s(ig_p,  "Alcance")
igs_p_v = _s(igs_p, "Visualizaciones"); igs_p_r = _s(igs_p, "Alcance")
fb_p_r  = _s(fb_p,  "Alcance");        fb_p_v3 = _s(fb_p,  "Visualizaciones de vídeo de 3 segundos")

total_v = ig_views + igs_views + fb_v3 + yt_plays
total_r = ig_reach + igs_reach + fb_reach
total_e = ig_likes + ig_share + igs_resp + fb_react + fb_share + fb_comm
total_n = ig_n + igs_n + fb_n

# MÉTRICAS GENERALES
sh("📊 Métricas Generales")
m1,m2,m3,m4,m5 = st.columns(5)
m1.metric("👁 Impresiones/Plays", fmt_number(total_v), _delta_str(total_v, ig_p_v+igs_p_v+fb_p_v3))
m2.metric("📢 Alcance Total",     fmt_number(total_r), _delta_str(total_r, ig_p_r+igs_p_r+fb_p_r))
m3.metric("▶️ YouTube Plays",     fmt_number(yt_plays))
m4.metric("📝 Publicaciones",     fmt_number(total_n))
m5.metric("❤️ Engagement Total",  fmt_number(total_e))

# TABLA RESUMEN
sh("📋 Resumen por Red")
rows = []
if "Instagram Posts"   in redes and not ig_s.empty:
    rows.append({"Red":"📸 IG Posts","Posts":ig_n,"Impresiones":ig_views,"Alcance":ig_reach,
                 "Me gusta":ig_likes,"Comentarios":ig_comm,"Compartidos":ig_share,"Guardados":ig_save})
if "Instagram Stories" in redes and not igs_s.empty:
    rows.append({"Red":"💬 IG Stories","Posts":igs_n,"Impresiones":igs_views,"Alcance":igs_reach,
                 "Me gusta":_s(igs_s,"Me gusta"),"Comentarios":igs_resp,"Compartidos":igs_click,"Guardados":0})
if "Facebook"          in redes and not fb_s.empty:
    rows.append({"Red":"👥 Facebook","Posts":fb_n,"Impresiones":fb_v3,"Alcance":fb_reach,
                 "Me gusta":fb_react,"Comentarios":fb_comm,"Compartidos":fb_share,"Guardados":0})
if "YouTube"           in redes and not yt_t.empty:
    rows.append({"Red":"▶️ YouTube","Posts":int(_s(yt_t,"Visualizaciones")),"Impresiones":yt_plays,
                 "Alcance":0,"Me gusta":0,"Comentarios":0,"Compartidos":0,"Guardados":0})
if rows:
    rdf = pd.DataFrame(rows); nc = [c for c in rdf.columns if c != "Red"]
    st.dataframe(rdf.style.format({c:"{:,.0f}" for c in nc}), use_container_width=True, hide_index=True)

# EVOLUCIÓN ALCANCE
sh("📈 Evolución Mensual — Alcance")
frames = []; cmap = {}
for df_, label, color in [(ig_s,"📸 IG Posts",C[1]),(igs_s,"💬 IG Stories",C[6]),(fb_s,"👥 Facebook",C[0])]:
    if not df_.empty and "Alcance" in df_.columns and "fecha_post" in df_.columns:
        tmp = df_.copy(); tmp["mes"] = tmp["fecha_post"].dt.to_period("M").astype(str)
        grp = tmp.groupby("mes")["Alcance"].sum().reset_index(); grp["Red"] = label
        frames.append(grp); cmap[label] = color
if frames:
    comb = pd.concat(frames, ignore_index=True)
    fig_e = px.line(comb, x="mes", y="Alcance", color="Red", markers=True, color_discrete_map=cmap)
    fig_e.update_traces(line_width=2.5, marker_size=8)
    fig_e.update_layout(legend=dict(orientation="h", y=1.12), xaxis_title="Mes")
    _fig(fig_e, 300); st.plotly_chart(fig_e, use_container_width=True)
else:
    st.info("No hay datos de alcance para el período.")

# ── INSTAGRAM POSTS ───────────────────────────────────────────────────────────
if "Instagram Posts" in redes:
    sh("📸 Instagram Posts")
    if ig_s.empty:
        st.warning("Sin datos de Instagram Posts en el período seleccionado.")
    else:
        c1,c2,c3,c4,c5,c6 = st.columns(6)
        c1.metric("📝 Posts",           fmt_number(ig_n))
        c2.metric("👁 Visualizaciones",  fmt_number(ig_views), _delta_str(ig_views, ig_p_v))
        c3.metric("📢 Alcance",          fmt_number(ig_reach), _delta_str(ig_reach, ig_p_r))
        c4.metric("❤️ Me gusta",         fmt_number(ig_likes))
        c5.metric("💬 Comentarios",      fmt_number(ig_comm))
        c6.metric("🔗 Compartidos",      fmt_number(ig_share))

        tc = _fc(ig_s, "Tipo de publicación")
        if tc and "Alcance" in ig_s.columns:
            agg_d = {"Posts": (tc,"count"), "Alcance": ("Alcance","sum")}
            if "Visualizaciones" in ig_s.columns: agg_d["Visualizaciones"] = ("Visualizaciones","sum")
            if "Me gusta"        in ig_s.columns: agg_d["Me gusta"]        = ("Me gusta","sum")
            tipo_agg = ig_s.groupby(tc, as_index=False).agg(**agg_d).sort_values("Alcance", ascending=False)
            tt1,tt2 = st.columns([1.2,2])
            with tt1:
                ft = px.pie(tipo_agg, names=tc, values="Alcance", color_discrete_sequence=C,
                            hole=0.5, title="Por formato")
                ft.update_traces(textposition="inside", textinfo="percent+label", textfont_size=11)
                ft.update_layout(showlegend=False); _fig(ft,260); st.plotly_chart(ft, use_container_width=True)
            with tt2:
                nc_ = [c for c in tipo_agg.columns if c != tc and tipo_agg[c].dtype in ["int64","float64"]]
                st.dataframe(tipo_agg.style.format({c:"{:,.0f}" for c in nc_}),
                             use_container_width=True, hide_index=True)

        ig2 = ig_s.copy(); ig2["sem"] = ig2["fecha_post"].dt.to_period("W").astype(str)
        cols_evo = [c for c in ["Alcance","Visualizaciones"] if c in ig2.columns]
        if cols_evo:
            evo = ig2.groupby("sem")[cols_evo].sum().reset_index()
            fig2 = go.Figure()
            if "Visualizaciones" in evo.columns:
                fig2.add_trace(go.Bar(x=evo["sem"], y=evo["Visualizaciones"], name="Views",
                    marker_color="#06b6d4", opacity=0.4, yaxis="y2"))
            fig2.add_trace(go.Scatter(x=evo["sem"], y=evo["Alcance"], name="Alcance",
                mode="lines+markers", line=dict(color="#8b5cf6", width=2.5), marker=dict(size=7)))
            fig2.update_layout(yaxis2=dict(overlaying="y", side="right", showgrid=False),
                               barmode="overlay", legend=dict(orientation="h", y=1.12))
            _fig(fig2, 260); st.plotly_chart(fig2, use_container_width=True)

        with st.expander("📋 Todos los posts de Instagram (por Alcance)", expanded=False):
            sc_ = [c for c in ["Descripción","Tipo de publicación","Hora de publicación","Alcance",
                               "Visualizaciones","Me gusta","Comentarios",
                               "Veces que se ha compartido","Veces guardado",
                               "Seguidores","Enlace permanente"] if c in ig_s.columns]
            s_c = _fc(ig_s, "Alcance", "Visualizaciones")
            if sc_ and s_c:
                st.dataframe(ig_s[sc_].sort_values(s_c, ascending=False)
                    .style.format({c:"{:,.0f}" for c in ig_s.select_dtypes("number").columns}),
                    use_container_width=True, hide_index=True)

# ── INSTAGRAM STORIES ─────────────────────────────────────────────────────────
if "Instagram Stories" in redes:
    sh("💬 Instagram Stories")
    if igs_s.empty:
        st.warning("Sin datos de Instagram Stories en el período.")
    else:
        s1,s2,s3,s4,s5 = st.columns(5)
        s1.metric("📝 Stories",         fmt_number(igs_n))
        s2.metric("👁 Visualizaciones",  fmt_number(igs_views), _delta_str(igs_views, igs_p_v))
        s3.metric("📢 Alcance",          fmt_number(igs_reach), _delta_str(igs_reach, igs_p_r))
        s4.metric("🔗 Clics enlace",     fmt_number(igs_click))
        s5.metric("💬 Respuestas",       fmt_number(igs_resp))

        igs2 = igs_s.copy(); igs2["sem"] = igs2["fecha_post"].dt.to_period("W").astype(str)
        cols_ev = [c for c in ["Alcance","Visualizaciones"] if c in igs2.columns]
        if cols_ev:
            ev2 = igs2.groupby("sem")[cols_ev].sum().reset_index()
            fig_s = px.bar(ev2, x="sem", y="Alcance", color_discrete_sequence=[C[6]],
                           text="Alcance", title="Alcance semanal Stories")
            fig_s.update_traces(texttemplate="%{text:,.0f}", textposition="outside", textfont_size=9)
            _fig(fig_s, 240); st.plotly_chart(fig_s, use_container_width=True)

        with st.expander("📋 Todas las stories", expanded=False):
            sc2 = [c for c in ["Descripción","Tipo de publicación","Hora de publicación",
                               "Visualizaciones","Alcance","Me gusta","Respuestas",
                               "Clics en el enlace","Seguidores"] if c in igs_s.columns]
            s_c2 = _fc(igs_s, "Alcance", "Visualizaciones")
            if sc2 and s_c2:
                st.dataframe(igs_s[sc2].sort_values(s_c2, ascending=False),
                             use_container_width=True, hide_index=True)

# ── FACEBOOK ─────────────────────────────────────────────────────────────────
if "Facebook" in redes:
    sh("👥 Facebook")
    if fb_s.empty:
        st.warning("Sin datos de Facebook en el período.")
    else:
        f1,f2,f3,f4,f5,f6 = st.columns(6)
        f1.metric("📝 Vídeos",          fmt_number(fb_n))
        f2.metric("📢 Alcance",          fmt_number(fb_reach), _delta_str(fb_reach, fb_p_r))
        f3.metric("▶️ Views 3s",         fmt_number(fb_v3),    _delta_str(fb_v3, fb_p_v3))
        f4.metric("⏱ Views 1min",        fmt_number(fb_v1))
        f5.metric("❤️ Reacciones",       fmt_number(fb_react))
        f6.metric("💬 Comentarios",      fmt_number(fb_comm))

        fb2 = fb_s.copy(); fb2["mes"] = fb2["fecha_post"].dt.to_period("M").astype(str)
        cols_fb = [c for c in ["Alcance","Visualizaciones de vídeo de 3 segundos"] if c in fb2.columns]
        if cols_fb:
            ev3 = fb2.groupby("mes")[cols_fb].sum().reset_index()
            fig_f = go.Figure()
            if "Visualizaciones de vídeo de 3 segundos" in ev3.columns:
                fig_f.add_trace(go.Bar(x=ev3["mes"], y=ev3["Visualizaciones de vídeo de 3 segundos"],
                    name="Views 3s", marker_color="#ef4444", opacity=0.4, yaxis="y2"))
            fig_f.add_trace(go.Scatter(x=ev3["mes"], y=ev3["Alcance"], name="Alcance",
                mode="lines+markers", line=dict(color="#6366f1", width=2.5), marker=dict(size=7)))
            fig_f.update_layout(yaxis2=dict(overlaying="y", side="right", showgrid=False),
                                barmode="overlay", legend=dict(orientation="h", y=1.12))
            _fig(fig_f, 260); st.plotly_chart(fig_f, use_container_width=True)

        # Detección robusta de columna Título usando _fc
        tc_fb  = _fc(fb_s, FB_TITULO, "Titulo", "titulo", "TITULO")
        sr_c   = _fc(fb_s, "Segundos reproducidos de media")

        if tc_fb and sr_c:
            top_r = fb_s.nlargest(15, sr_c)
            show_r = [c for c in [tc_fb, "Hora de publicación", "Alcance",
                                  "Visualizaciones de vídeo de 3 segundos", sr_c] if c in top_r.columns]
            sh("⏱ Vídeos con mayor retención")
            st.dataframe(
                top_r[show_r].style.format({c:"{:,.1f}" for c in top_r[show_r].select_dtypes("float").columns}),
                use_container_width=True, hide_index=True)

        with st.expander("📋 Todos los vídeos de Facebook", expanded=False):
            # Construir lista de columnas a mostrar incluyendo título detectado dinámicamente
            fb_cols_base = ["Hora de publicación","Alcance",
                           "Visualizaciones de vídeo de 3 segundos",
                           "Visualizaciones de vídeo de 1 minuto",
                           "Reacciones","Comentarios",
                           "Veces que se ha compartido",
                           "Segundos reproducidos de media"]
            # Añadir título al frente si existe
            sc3 = ([tc_fb] if tc_fb else []) + [c for c in fb_cols_base if c in fb_s.columns]
            s_c3 = _fc(fb_s, "Alcance")
            if sc3 and s_c3:
                st.dataframe(
                    fb_s[sc3].sort_values(s_c3, ascending=False)
                    .style.format({c:"{:,.1f}" for c in fb_s[sc3].select_dtypes("float").columns}),
                    use_container_width=True, hide_index=True)

# ── YOUTUBE ───────────────────────────────────────────────────────────────────
if "YouTube" in redes:
    sh("▶️ YouTube")
    if yt_t.empty and yt_gf.empty:
        st.warning("Sin datos de YouTube.")
    else:
        y1,y2,y3,y4 = st.columns(4)
        y1.metric("▶️ Visualizaciones", fmt_number(_s(yt_t, "Visualizaciones")))
        y2.metric("📢 Impresiones",     fmt_number(_s(yt_t, "Impresiones")))
        y3.metric("🔔 Suscriptores",    fmt_number(_s(yt_t, "Suscriptores")))
        rc = _fc(yt_t, "Ingresos estimados (USD)", "Ingresos estimados")
        y4.metric("💰 Revenue", f"${safe_sum(yt_t, rc):.2f}" if rc else "—")

        if not yt_gf.empty and "Fecha" in yt_gf.columns and "Visualizaciones" in yt_gf.columns:
            ytc = yt_gf.copy()
            ytc["mes"] = pd.to_datetime(ytc["Fecha"], errors="coerce").dt.to_period("M").astype(str)
            yt_e = ytc.groupby("mes")["Visualizaciones"].sum().reset_index()
            fy = px.bar(yt_e, x="mes", y="Visualizaciones", color="Visualizaciones",
                        color_continuous_scale=["#1a0808","#ef4444"],
                        text="Visualizaciones", title="Visualizaciones YouTube por Mes")
            fy.update_traces(texttemplate="%{text:,.0f}", textposition="outside", textfont_size=9)
            fy.update_layout(coloraxis_showscale=False); _fig(fy, 260)
            st.plotly_chart(fy, use_container_width=True)

        tc_yt = _fc(yt_t, "Título del vídeo", "Titulo del video", "Título")
        vc_yt = _fc(yt_t, "Visualizaciones")
        if tc_yt and vc_yt and not yt_t.empty:
            sh("🏆 Top Vídeos YouTube")
            tc_show = [c for c in [tc_yt, "Hora de publicación del vídeo", "Duración", vc_yt,
                                   "Tiempo de visualización (horas)", "Impresiones",
                                   "Porcentaje de clics de las impresiones (%)",
                                   "Suscriptores", "Ingresos estimados (USD)"] if c in yt_t.columns]
            st.dataframe(
                yt_t.sort_values(vc_yt, ascending=False).head(30)[tc_show]
                .style.format({c:"{:,.0f}" for c in yt_t.select_dtypes("number").columns}),
                use_container_width=True, hide_index=True)
