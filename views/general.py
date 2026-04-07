import sys, os; sys.path.insert(0, os.getcwd())
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta
from urllib.parse import urlparse as _up
from data_loader import (
    load_ga4_general, load_ga4_city, load_ga4_country, load_ga4_channel,
    load_ga4_age, load_ga4_device, load_ga4_interests, load_ga4_urls,
    load_produccion_con_metricas,
    filter_by_date, fmt_number, safe_sum, get_date_range, _delta_str, match_stats
)
C   = ["#6366f1","#06b6d4","#10b981","#f59e0b","#ef4444","#8b5cf6","#ec4899","#14b8a6"]
PBG = "#0d0d20"

def _fig(fig, h=340):
    fig.update_layout(
        height=h, paper_bgcolor=PBG, plot_bgcolor=PBG,
        font=dict(family="Inter", color="#8890b8", size=11),
        margin=dict(l=6, r=6, t=36, b=6),
        legend=dict(bgcolor="rgba(0,0,0,0)", font_size=11),
        xaxis=dict(gridcolor="#14142e", zerolinecolor="#14142e"),
        yaxis=dict(gridcolor="#14142e", zerolinecolor="#14142e"),
        title_font=dict(family="Syne", size=13, color="#c0c8e8"),
    )
    return fig

def sh(t):
    st.markdown(f'<div class="sec-hdr">{t}</div>', unsafe_allow_html=True)

def _author_paths(prod_df):
    if prod_df.empty or "url" not in prod_df.columns:
        return set()
    return {_up(str(u)).path.rstrip("/") for u in prod_df["url"] if pd.notna(u)}

def _urls_to_daily(urls_df):
    """Agrupa urls_df por fecha sumando todas las métricas disponibles."""
    if urls_df.empty or "date" not in urls_df.columns:
        return pd.DataFrame()
    cols = [c for c in ["date","screenPageViews","activeUsers","sessions",
                         "userEngagementDuration"] if c in urls_df.columns]
    agg  = {c: (c, "sum") for c in cols if c != "date"}
    return urls_df[cols].groupby("date", as_index=False).agg(**agg)

# ════════════════════════════════════════════════════════════════════════
st.markdown('<div class="page-title">🏠 General · Tráfico y Producción</div>',
            unsafe_allow_html=True)
st.markdown('<div class="page-subtitle">GA4 · Producción editorial</div>',
            unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════
# CARGA
# Los loaders deben mapear a las hojas del Excel v2:
#   load_ga4_general()   → "01_General_Diario"
#   load_ga4_device()    → "02_General_x_Device"
#   load_ga4_age()       → "04_General_x_Edad"
#   load_ga4_city()      → "05_General_x_Ciudad"
#   load_ga4_channel()   → "06_General_x_Canal"
#   load_ga4_country()   → "07_General_x_Pais"
#   load_ga4_urls()      → "10_URLs_Diario"
#   load_ga4_interests() → "15_BRANDING_General"
# ════════════════════════════════════════════════════════════════════════
with st.spinner("Cargando datos..."):
    ga4_r  = load_ga4_general()
    city_r = load_ga4_city()
    cnt_r  = load_ga4_country()
    chan_r  = load_ga4_channel()
    age_r  = load_ga4_age()
    dev_r  = load_ga4_device()
    urls_r = load_ga4_urls()
    prod_r = load_produccion_con_metricas()

min_d, max_d = get_date_range(ga4_r, "date")

# ════════════════════════════════════════════════════════════════════════
# LISTAS DE FILTROS
# ════════════════════════════════════════════════════════════════════════
prod_con_match = (
    prod_r[prod_r["ga4_views"] > 0]
    if not prod_r.empty and "ga4_views" in prod_r.columns
    else pd.DataFrame()
)

auth_list = ["Todos"]
if not prod_con_match.empty and "post_author_name" in prod_con_match.columns:
    auth_list += sorted(prod_con_match["post_author_name"].dropna().unique().tolist())

cat_list = ["Todas"]
if not prod_con_match.empty and "categories" in prod_con_match.columns:
    cat_list += (
        prod_con_match["categories"].fillna("")
        .apply(lambda x: [p.strip() for p in str(x).split(",") if p.strip()])
        .explode().value_counts().head(40).index.tolist()
    )

city_list = ["Todas"]
if not city_r.empty and "city" in city_r.columns:
    city_list += (
        city_r[city_r["city"] != "(not set)"]
        .groupby("city")["activeUsers"].sum()
        .sort_values(ascending=False).head(50).index.tolist()
    )

chan_list = ["Todos"]
if not chan_r.empty and "sessionDefaultChannelGroup" in chan_r.columns:
    chan_list += sorted(chan_r["sessionDefaultChannelGroup"].dropna().unique().tolist())

# ════════════════════════════════════════════════════════════════════════
# FILTROS UI
# ════════════════════════════════════════════════════════════════════════
sh("⚙️ Filtros")
st.markdown('<div class="filter-box">', unsafe_allow_html=True)
c1, c2, c3, c4, c5, c6 = st.columns(6)
with c1: start    = st.date_input("📅 Desde", max_d - timedelta(days=90),
                                   min_value=min_d, max_value=max_d, key="gs")
with c2: end      = st.date_input("📅 Hasta", max_d,
                                   min_value=min_d, max_value=max_d, key="ge")
with c3: sel_aut  = st.selectbox("✍️ Autor",   auth_list, key="ga")
with c4: sel_city = st.selectbox("🏙️ Ciudad",  city_list, key="gc")
with c5: sel_cat  = st.selectbox("📂 Sección", cat_list,  key="gcat")
with c6: sel_chan  = st.selectbox("📡 Canal",   chan_list, key="gch")
st.markdown('</div>', unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════
# FLAGS
# ════════════════════════════════════════════════════════════════════════
has_aut       = sel_aut  != "Todos"
has_cat       = sel_cat  != "Todas"
has_city      = sel_city != "Todas"
has_chan       = sel_chan != "Todos"
has_editorial = has_aut or has_cat
has_ga4dim    = has_city or has_chan

# ════════════════════════════════════════════════════════════════════════
# FILTRAR POR FECHA
# ════════════════════════════════════════════════════════════════════════
ga4  = filter_by_date(ga4_r,  "date", start, end)
city = filter_by_date(city_r, "date", start, end)
cnt  = filter_by_date(cnt_r,  "date", start, end)
chan = filter_by_date(chan_r,  "date", start, end)
age  = filter_by_date(age_r,  "date", start, end)
dev  = filter_by_date(dev_r,  "date", start, end)
urls = filter_by_date(urls_r, "date", start, end)

pd_    = max((end - start).days, 1)
prev_s = start - timedelta(days=pd_)
prev_e = start - timedelta(days=1)

# Filtros de dimensión GA4 — cada uno sobre su propio df
if has_city and "city" in city.columns:
    city = city[city["city"] == sel_city].copy()
if has_chan and "sessionDefaultChannelGroup" in chan.columns:
    chan = chan[chan["sessionDefaultChannelGroup"] == sel_chan].copy()

# ════════════════════════════════════════════════════════════════════════
# FILTRAR PRODUCCIÓN
# ════════════════════════════════════════════════════════════════════════
prod = filter_by_date(prod_r, "post_date", start, end)
if has_aut and "post_author_name" in prod.columns:
    prod = prod[prod["post_author_name"] == sel_aut].copy()
if has_cat and "categories" in prod.columns:
    prod = prod[prod["categories"].fillna("").apply(
        lambda x: sel_cat in [p.strip() for p in str(x).split(",")])].copy()

# ════════════════════════════════════════════════════════════════════════
# FILTRAR URLs por autor/categoría
# ════════════════════════════════════════════════════════════════════════
if has_editorial and not prod.empty and not urls.empty and "pagePath" in urls.columns:
    valid_paths = _author_paths(prod)
    urls = (
        urls[urls["pagePath"].apply(lambda p: str(p).rstrip("/")).isin(valid_paths)].copy()
        if valid_paths else pd.DataFrame()
    )

# ════════════════════════════════════════════════════════════════════════
# _src — FUENTE DE MÉTRICAS SEGÚN PRIORIDAD DE FILTROS
#
#   1. Editorial (autor/cat)  → urls filtradas → diario (tiene userEngagementDuration)
#   2. Canal + Ciudad         → city df
#   3. Canal solo             → chan df
#   4. Ciudad solo            → city df
#   5. Sin filtro             → ga4 (01_General_Diario) ← más preciso
#
# city / chan NO tienen userEngagementDuration → se muestra "—"
# ════════════════════════════════════════════════════════════════════════
def _prev_editorial(urls_r_full, prod_r_full, prev_s, prev_e, sel_aut, sel_cat, has_aut, has_cat):
    urls_p = filter_by_date(urls_r_full, "date", prev_s, prev_e)
    prod_p = prod_r_full.copy()
    if has_aut and "post_author_name" in prod_p.columns:
        prod_p = prod_p[prod_p["post_author_name"] == sel_aut]
    if has_cat and "categories" in prod_p.columns:
        prod_p = prod_p[prod_p["categories"].fillna("").apply(
            lambda x: sel_cat in [p.strip() for p in str(x).split(",")])]
    valid = _author_paths(prod_p)
    if not urls_p.empty and valid and "pagePath" in urls_p.columns:
        urls_p = urls_p[urls_p["pagePath"].apply(lambda p: str(p).rstrip("/")).isin(valid)]
    return _urls_to_daily(urls_p)

captions = []

if has_editorial:
    _src   = _urls_to_daily(urls)
    _src_p = _prev_editorial(urls_r, prod_r, prev_s, prev_e, sel_aut, sel_cat, has_aut, has_cat)
    if has_aut:  captions.append(f"✍️ **{sel_aut}**")
    if has_cat:  captions.append(f"📂 **{sel_cat}**")
    if has_chan:  captions.append(f"📡 **{sel_chan}** *(solo en gráfico de canales)*")
    if has_city: captions.append(f"🏙️ **{sel_city}** *(solo en gráfico de ciudades)*")

elif has_chan and has_city:
    d1 = set(city["date"].dt.date) if "date" in city.columns else set()
    d2 = set(chan["date"].dt.date) if "date" in chan.columns else set()
    common = d1 & d2
    _src = city[city["date"].dt.date.isin(common)].copy() if common else city.copy()
    cp = filter_by_date(city_r, "date", prev_s, prev_e)
    _src_p = (cp[cp["city"] == sel_city].copy()
              if not cp.empty and "city" in cp.columns else pd.DataFrame())
    captions += [f"🏙️ **{sel_city}**", f"📡 **{sel_chan}**"]

elif has_chan:
    _src = chan.copy()
    chp  = filter_by_date(chan_r, "date", prev_s, prev_e)
    _src_p = (chp[chp["sessionDefaultChannelGroup"] == sel_chan].copy()
              if not chp.empty and "sessionDefaultChannelGroup" in chp.columns
              else pd.DataFrame())
    captions.append(f"📡 **{sel_chan}**")

elif has_city:
    _src = city.copy()
    cp   = filter_by_date(city_r, "date", prev_s, prev_e)
    _src_p = (cp[cp["city"] == sel_city].copy()
              if not cp.empty and "city" in cp.columns else pd.DataFrame())
    captions.append(f"🏙️ **{sel_city}**")

else:
    # Sin filtro: usa 01_General_Diario directamente (más preciso, concuerda con GA4)
    _src   = ga4.copy()
    _src_p = filter_by_date(ga4_r, "date", prev_s, prev_e)

if captions:
    st.caption("  ·  ".join(captions))

# ════════════════════════════════════════════════════════════════════════
# MÉTRICAS DEL PERÍODO
# ════════════════════════════════════════════════════════════════════════
sh("📊 Métricas del Período")
m1, m2, m3, m4, m5, m6 = st.columns(6)

au   = int(safe_sum(_src, "activeUsers"));      au_p  = int(safe_sum(_src_p, "activeUsers"))
vw   = int(safe_sum(_src, "screenPageViews"));  vw_p  = int(safe_sum(_src_p, "screenPageViews"))
ss   = int(safe_sum(_src, "sessions"));         ss_p  = int(safe_sum(_src_p, "sessions"))

# userEngagementDuration: segundos totales / usuarios → promedio por usuario
# Disponible en 01_General_Diario y 10_URLs_Diario; NO en city ni chan
dur = (
    float(_src["userEngagementDuration"].sum() / max(au, 1))
    if not _src.empty and "userEngagementDuration" in _src.columns and au > 0
    else 0.0
)

u_ct = urls["pagePath"].nunique() if not urls.empty and "pagePath" in urls.columns else 0
p_ct = len(prod)

m1.metric("👤 Usuarios",       fmt_number(au),           _delta_str(au, au_p))
m2.metric("📄 Vistas",         fmt_number(vw),           _delta_str(vw, vw_p))
m3.metric("🔄 Sesiones",       fmt_number(ss),           _delta_str(ss, ss_p))
m4.metric("⏱ Tiempo Prom.",    f"{dur/60:.1f}m" if dur else "—")
m5.metric("🔗 URLs c/Tráfico", fmt_number(u_ct))
m6.metric("✍️ Publicaciones",  fmt_number(p_ct))

# ════════════════════════════════════════════════════════════════════════
# META Q1
# Siempre usa ga4_r sin filtrar (meta global del sitio)
# ════════════════════════════════════════════════════════════════════════
sh("🎯 Meta Q1 — 750,000 Usuarios")
ga4_q = filter_by_date(ga4_r, "date", date(end.year, 1, 1), date(end.year, 3, 31))
q1u   = int(safe_sum(ga4_q, "activeUsers"))
pct   = min(q1u / 750_000, 1.0)
qa, qb, qc = st.columns([4, 1, 1])
with qa:
    st.progress(pct, text=f"**{fmt_number(q1u)}** / **750K** — {pct*100:.1f}%")
with qb:
    st.metric("Alcanzado", fmt_number(q1u))
with qc:
    st.metric(
        "Faltan", fmt_number(max(750_000 - q1u, 0)),
        delta="✅ Meta!" if q1u >= 750_000 else f"-{fmt_number(max(750_000 - q1u, 0))}",
        delta_color="normal" if q1u >= 750_000 else "inverse",
    )

with st.expander("🔬 Diagnóstico matching Producción↔GA4", expanded=False):
    stats = match_stats(prod_r)
    if stats:
        total   = sum(stats.values())
        matched = total - stats.get("sin_match", 0)
        st.markdown(f"**{matched:,} / {total:,} notas** conectadas ({matched/total*100:.1f}%)")
        for m, n in sorted(stats.items(), key=lambda x: -x[1]):
            st.markdown(f"- `{m}`: **{n:,}** ({n/total*100:.1f}%)")
    else:
        st.info("Sin datos.")

# ════════════════════════════════════════════════════════════════════════
# G1: Evolución Mensual
# ════════════════════════════════════════════════════════════════════════
st.markdown("---")
sh("📈 Evolución Mensual · Usuarios vs Vistas")
if not _src.empty and "date" in _src.columns:
    ev = _src.copy()
    ev["mes"] = ev["date"].dt.to_period("M").astype(str)
    kw = {}
    if "activeUsers"     in ev.columns: kw["U"] = ("activeUsers",     "sum")
    if "screenPageViews" in ev.columns: kw["V"] = ("screenPageViews", "sum")
    if kw:
        mo = ev.groupby("mes", as_index=False).agg(**kw)
        fig1 = go.Figure()
        if "V" in mo.columns:
            fig1.add_trace(go.Bar(x=mo["mes"], y=mo["V"], name="Vistas",
                marker_color="#06b6d4", opacity=0.4, yaxis="y2"))
        if "U" in mo.columns:
            fig1.add_trace(go.Scatter(x=mo["mes"], y=mo["U"], name="Usuarios",
                mode="lines+markers", line=dict(color="#6366f1", width=3),
                marker=dict(size=7, color="#6366f1", line=dict(color="#fff", width=1.5))))
        fig1.update_layout(
            yaxis2=dict(overlaying="y", side="right", showgrid=False,
                        tickfont=dict(color="#06b6d4"), title="Vistas"),
            yaxis=dict(title="Usuarios"),
            barmode="overlay",
            legend=dict(orientation="h", y=1.12),
        )
        _fig(fig1, 340)
        st.plotly_chart(fig1, use_container_width=True)
else:
    st.info("Sin datos GA4 para el período y filtros seleccionados.")

# ════════════════════════════════════════════════════════════════════════
# G2: Canales de Tráfico
# Siempre muestra todos los canales con chan_r filtrado por fecha.
# Si hay sel_chan activo: caption con métricas del canal elegido.
# Filtro editorial → no disponible.
# ════════════════════════════════════════════════════════════════════════
sh("📡 Canales de Tráfico")
if has_editorial:
    st.info("ℹ️ Desglose por canal no disponible con filtro de autor/sección.")
else:
    _chan_src = filter_by_date(chan_r, "date", start, end)
    if not _chan_src.empty and "sessionDefaultChannelGroup" in _chan_src.columns:
        ca = (
            _chan_src.groupby("sessionDefaultChannelGroup", as_index=False)
            .agg(U=("activeUsers","sum"), V=("screenPageViews","sum"), S=("sessions","sum"))
            .sort_values("U", ascending=False)
        )
        cc1, cc2 = st.columns([1, 2])
        with cc1:
            f2 = px.pie(ca, names="sessionDefaultChannelGroup", values="U",
                color_discrete_sequence=C, hole=0.52)
            f2.update_traces(textposition="inside", textinfo="percent+label", textfont_size=11)
            f2.update_layout(showlegend=False)
            _fig(f2, 280)
            st.plotly_chart(f2, use_container_width=True)
        with cc2:
            styled = ca.rename(columns={
                "sessionDefaultChannelGroup": "Canal",
                "U": "Usuarios", "V": "Vistas", "S": "Sesiones",
            })
            st.dataframe(
                styled.style.format({"Usuarios":"{:,.0f}","Vistas":"{:,.0f}","Sesiones":"{:,.0f}"}),
                use_container_width=True, hide_index=True, height=260,
            )
        if has_chan:
            sel_row = ca[ca["sessionDefaultChannelGroup"] == sel_chan]
            if not sel_row.empty:
                st.caption(
                    f"📡 Canal **{sel_chan}**: "
                    f"{fmt_number(int(sel_row['U'].iloc[0]))} usuarios · "
                    f"{fmt_number(int(sel_row['V'].iloc[0]))} vistas · "
                    f"{fmt_number(int(sel_row['S'].iloc[0]))} sesiones"
                )
    else:
        st.info("Sin datos de canales.")

# ════════════════════════════════════════════════════════════════════════
# G3: Ciudades Top 20
# Siempre muestra todas las ciudades con city_r filtrado por fecha.
# Si hay sel_city: caption con usuarios de esa ciudad.
# Filtro editorial → no disponible.
# ════════════════════════════════════════════════════════════════════════
sh("🏙️ Tráfico por Ciudad — Top 20")
if has_editorial:
    st.info("ℹ️ Desglose por ciudad no disponible con filtro de autor/sección.")
else:
    _city_src = filter_by_date(city_r, "date", start, end)
    if not _city_src.empty and "city" in _city_src.columns:
        cv = (
            _city_src[_city_src["city"] != "(not set)"]
            .groupby("city", as_index=False).agg(U=("activeUsers","sum"))
            .sort_values("U", ascending=False).head(20)
        )
        f3 = px.bar(cv, x="U", y="city", orientation="h",
            color="U", color_continuous_scale=["#14143a","#6366f1","#06b6d4"], text="U")
        f3.update_traces(texttemplate="%{text:,.0f}", textposition="outside", textfont_size=10)
        f3.update_layout(
            yaxis=dict(autorange="reversed"),
            coloraxis_showscale=False,
            yaxis_title="", xaxis_title="Usuarios Activos",
        )
        _fig(f3, max(360, len(cv) * 26 + 60))
        st.plotly_chart(f3, use_container_width=True)
        if has_city:
            sel_cv = cv[cv["city"] == sel_city]
            if not sel_cv.empty:
                st.caption(f"🏙️ Ciudad **{sel_city}**: {fmt_number(int(sel_cv['U'].iloc[0]))} usuarios")
    else:
        st.info("Sin datos de ciudades.")

# ════════════════════════════════════════════════════════════════════════
# G4: Países
# ════════════════════════════════════════════════════════════════════════
sh("🌎 Tráfico por País")
if has_editorial:
    st.info("ℹ️ Desglose por país no disponible con filtro de autor/sección.")
elif not cnt.empty and "country" in cnt.columns:
    cv2 = (
        cnt[cnt["country"] != "(not set)"]
        .groupby("country", as_index=False).agg(U=("activeUsers","sum"))
        .sort_values("U", ascending=False)
    )
    pc1, pc2 = st.columns([3, 1])
    with pc1:
        f4 = px.choropleth(cv2, locations="country", locationmode="country names", color="U",
            color_continuous_scale=["#0a0a20","#6366f1","#06b6d4","#10b981"])
        f4.update_layout(geo=dict(bgcolor=PBG, showframe=False, landcolor="#10102a",
            showocean=True, oceancolor="#080814", showcoastlines=True, coastlinecolor="#1a1a3a"))
        _fig(f4, 340)
        st.plotly_chart(f4, use_container_width=True)
    with pc2:
        st.dataframe(
            cv2.head(25).rename(columns={"country":"País","U":"Usuarios"})
            .style.format({"Usuarios":"{:,.0f}"}),
            use_container_width=True, hide_index=True, height=320,
        )
else:
    st.info("Sin datos de países.")

# ════════════════════════════════════════════════════════════════════════
# G5: URLs más leídas + Autores
# ════════════════════════════════════════════════════════════════════════
sh("📰 URLs y Autores")
n1, n2 = st.columns(2)

with n1:
    st.markdown("**🔝 URLs más leídas**")
    if not urls.empty and "pagePath" in urls.columns:
        grp = ["pagePath"] + (["pageTitle"] if "pageTitle" in urls.columns else [])
        ua  = (
            urls.groupby(grp, as_index=False)
            .agg(Vistas=("screenPageViews","sum"), Usuarios=("activeUsers","sum"))
            .sort_values("Vistas", ascending=False).head(30)
        )
        if not prod_r.empty and "url" in prod_r.columns and "post_author_name" in prod_r.columns:
            p2a = {
                _up(str(u)).path.rstrip("/"): a
                for u, a in zip(prod_r["url"], prod_r["post_author_name"])
                if pd.notna(u)
            }
            ua["Autor"] = ua["pagePath"].apply(lambda p: p2a.get(str(p).rstrip("/"), "—"))
        dc = [c for c in ["pageTitle","Autor","Vistas","Usuarios"] if c in ua.columns]
        st.dataframe(
            ua[dc].style.format({"Vistas":"{:,.0f}","Usuarios":"{:,.0f}"}),
            use_container_width=True, hide_index=True, height=400,
        )
    else:
        st.info("Sin datos de URLs.")

with n2:
    st.markdown("**✍️ Autores más leídos**")
    if not prod.empty and "post_author_name" in prod.columns and "ga4_views" in prod.columns:
        aa = (
            prod.groupby("post_author_name", as_index=False)
            .agg(Vistas=("ga4_views","sum"), Notas=("post_id","count"), Usuarios=("ga4_users","sum"))
            .sort_values("Vistas", ascending=False).head(25)
        )
        aa["V/Nota"] = (aa["Vistas"] / aa["Notas"].clip(1)).round(0).astype(int)
        st.dataframe(
            aa.rename(columns={"post_author_name":"Autor"})
            .style.format({"Vistas":"{:,.0f}","Notas":"{:,.0f}","Usuarios":"{:,.0f}","V/Nota":"{:,.0f}"}),
            use_container_width=True, hide_index=True, height=400,
        )
    else:
        st.info("Sin datos de autores.")

# ════════════════════════════════════════════════════════════════════════
# G6: Secciones
# ════════════════════════════════════════════════════════════════════════
sh("📂 Secciones")
if not prod.empty and "categories" in prod.columns and "ga4_views" in prod.columns:
    sp = prod.copy()
    sp["cat"] = sp["categories"].fillna("Sin cat").apply(
        lambda x: ", ".join([p.strip() for p in str(x).split(",") if p.strip()])
        if has_cat
        else str(x).split(",")[0].strip()
    )
    sa = (
        sp.groupby("cat", as_index=False)
        .agg(U=("ga4_users","sum"), V=("ga4_views","sum"), N=("post_id","count"))
        .sort_values("V", ascending=False).head(20)
    )
    sc1, sc2 = st.columns([1, 2])
    with sc1:
        f6 = px.pie(sa.head(10), names="cat", values="U",
            color_discrete_sequence=C, hole=0.48)
        f6.update_traces(textposition="inside", textinfo="percent+label", textfont_size=10)
        f6.update_layout(showlegend=False)
        _fig(f6, 280)
        st.plotly_chart(f6, use_container_width=True)
    with sc2:
        st.dataframe(
            sa.rename(columns={"cat":"Sección","U":"Usuarios","V":"Vistas","N":"Notas"})
            .style.format({"Usuarios":"{:,.0f}","Vistas":"{:,.0f}","Notas":"{:,.0f}"}),
            use_container_width=True, hide_index=True, height=300,
        )
else:
    st.info("Sin datos de secciones.")

# ════════════════════════════════════════════════════════════════════════
# G7: Producción mensual
# ════════════════════════════════════════════════════════════════════════
sh("✍️ Producción por Mes")
if not prod.empty and "post_date" in prod.columns:
    tp = prod.copy()
    tp["mes"] = tp["post_date"].dt.to_period("M").astype(str)
    pm = tp.groupby("mes", as_index=False).agg(
        pub=("post_id", "count"),
        con=("ga4_views", lambda x: (x > 0).sum()),
    )
    pm["sin"] = pm["pub"] - pm["con"]
    fig7 = go.Figure()
    fig7.add_trace(go.Bar(x=pm["mes"], y=pm["con"], name="Con tráfico GA4", marker_color="#10b981"))
    fig7.add_trace(go.Bar(x=pm["mes"], y=pm["sin"], name="Sin match GA4",   marker_color="#1e1e40"))
    fig7.update_layout(barmode="stack", legend=dict(orientation="h", y=1.12))
    _fig(fig7, 260)
    st.plotly_chart(fig7, use_container_width=True)

# ════════════════════════════════════════════════════════════════════════
# G8: Notas IA
# ════════════════════════════════════════════════════════════════════════
sh("🤖 Notas IA Más Leídas")
if not prod.empty and "is_ia" in prod.columns:
    ia = prod[prod["is_ia"]].sort_values("ga4_views", ascending=False).head(25)
    if not ia.empty:
        cols_ = [c for c in ["post_title","post_author_name","post_date",
                              "ga4_views","ga4_users","match_method"] if c in ia.columns]
        st.dataframe(
            ia[cols_].rename(columns={
                "post_title":"Título","post_author_name":"Autor",
                "post_date":"Fecha","ga4_views":"Vistas",
                "ga4_users":"Usuarios","match_method":"Match",
            }).style.format({"Vistas":"{:,.0f}","Usuarios":"{:,.0f}"}),
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("No hay notas IA en el período seleccionado.")

# ════════════════════════════════════════════════════════════════════════
# G9: Audiencia — Edad / Dispositivo / Intereses
# ════════════════════════════════════════════════════════════════════════
sh("👥 Audiencia")
t1, t2, t3 = st.tabs(["👤 Edad", "📱 Dispositivo", "🎯 Intereses"])

with t1:
    if has_editorial:
        st.info("ℹ️ Desglose por edad no disponible con filtro de autor/sección.")
    elif not age.empty and "userAgeBracket" in age.columns:
        a2 = (age.groupby("userAgeBracket", as_index=False).agg(U=("activeUsers","sum"))
              .sort_values("userAgeBracket"))
        fa = px.bar(a2, x="userAgeBracket", y="U", color="U",
            color_continuous_scale=["#14143a","#6366f1"], text="U")
        fa.update_traces(texttemplate="%{text:,.0f}", textposition="outside", textfont_size=10)
        fa.update_layout(coloraxis_showscale=False, xaxis_title="Edad", yaxis_title="Usuarios")
        _fig(fa, 270)
        st.plotly_chart(fa, use_container_width=True)
    else:
        st.info("Sin datos de edad.")

with t2:
    if has_editorial:
        st.info("ℹ️ Desglose por dispositivo no disponible con filtro de autor/sección.")
    elif not dev.empty and "deviceCategory" in dev.columns:
        da = dev.groupby("deviceCategory", as_index=False).agg(
            U=("activeUsers","sum"), V=("screenPageViews","sum")
        )
        d1_, d2_ = st.columns(2)
        with d1_:
            fd = px.pie(da, names="deviceCategory", values="U",
                color_discrete_sequence=C, hole=0.52)
            fd.update_traces(textposition="inside", textinfo="percent+label", textfont_size=13)
            fd.update_layout(showlegend=False)
            _fig(fd, 260)
            st.plotly_chart(fd, use_container_width=True)
        with d2_:
            fdv = px.bar(da, x="deviceCategory", y="V", color="deviceCategory",
                color_discrete_sequence=C, text="V")
            fdv.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
            fdv.update_layout(showlegend=False, xaxis_title="", yaxis_title="Vistas")
            _fig(fdv, 260)
            st.plotly_chart(fdv, use_container_width=True)
        st.dataframe(
            da.rename(columns={"deviceCategory":"Dispositivo","U":"Usuarios","V":"Vistas"})
            .style.format({"Usuarios":"{:,.0f}","Vistas":"{:,.0f}"}),
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("Sin datos de dispositivos.")

with t3:
    # Intereses filtrados por fecha igual que el resto
    intr_r = load_ga4_interests()
    intr   = filter_by_date(intr_r, "date", start, end) if not intr_r.empty else intr_r
    if not intr.empty and "brandingInterest" in intr.columns:
        ia2 = (
            intr.groupby("brandingInterest", as_index=False).agg(U=("activeUsers","sum"))
            .sort_values("U", ascending=False).head(25)
        )
        fi = px.bar(ia2, x="U", y="brandingInterest", orientation="h",
            color="U", color_continuous_scale=["#14143a","#8b5cf6"])
        fi.update_layout(yaxis=dict(autorange="reversed"), coloraxis_showscale=False, yaxis_title="")
        _fig(fi, 500)
        st.plotly_chart(fi, use_container_width=True)
    else:
        st.info("Sin datos de intereses.")
