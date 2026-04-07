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

C = ["#6366f1", "#06b6d4", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#14b8a6"]
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

def _clean_text(x):
    if pd.isna(x):
        return ""
    s = str(x).strip()
    return "" if s.lower() in {"nan", "none", "null", "<na>"} else s

def _norm_path(u):
    if pd.isna(u) or not str(u).strip():
        return ""
    try:
        return _up(str(u)).path.rstrip("/").lower()
    except Exception:
        return str(u).strip().rstrip("/").lower()

def _split_cats(x):
    s = _clean_text(x)
    if not s:
        return []
    return [p.strip() for p in s.split(",") if p.strip()]

def _author_paths(prod_df):
    if prod_df.empty or "url" not in prod_df.columns:
        return set()
    return {_norm_path(u) for u in prod_df["url"] if _clean_text(u)}

def _urls_to_daily(urls_df):
    if urls_df.empty or "date" not in urls_df.columns:
        return pd.DataFrame()
    cols = [c for c in ["date", "screenPageViews", "activeUsers", "sessions", "userEngagementDuration"] if c in urls_df.columns]
    agg = {c: (c, "sum") for c in cols if c != "date"}
    return urls_df[cols].groupby("date", as_index=False).agg(**agg)

st.markdown('<div class="page-title">🏠 General · Tráfico y Producción</div>', unsafe_allow_html=True)
st.markdown('<div class="page-subtitle">GA4 · Producción editorial</div>', unsafe_allow_html=True)

with st.spinner("Cargando datos..."):
    ga4_r = load_ga4_general()
    city_r = load_ga4_city()
    cnt_r = load_ga4_country()
    chan_r = load_ga4_channel()
    age_r = load_ga4_age()
    dev_r = load_ga4_device()
    urls_r = load_ga4_urls()
    prod_r = load_produccion_con_metricas()

if not prod_r.empty:
    prod_work = prod_r.copy()
    for c in ["post_author_name", "author_resolved", "categories", "tags", "post_title", "url"]:
        if c not in prod_work.columns:
            prod_work[c] = ""
        prod_work[c] = prod_work[c].map(_clean_text)
    prod_work["post_author_name"] = prod_work["post_author_name"].replace("", pd.NA)
    if "author_resolved" in prod_work.columns:
        prod_work["post_author_name"] = prod_work["post_author_name"].fillna(prod_work["author_resolved"])
    prod_work["post_author_name"] = prod_work["post_author_name"].fillna("Sin autor")
    if "ga4_views" not in prod_work.columns:
        prod_work["ga4_views"] = 0
    if "ga4_users" not in prod_work.columns:
        prod_work["ga4_users"] = 0
else:
    prod_work = pd.DataFrame(columns=["post_author_name", "categories", "tags", "post_title", "url", "ga4_views", "ga4_users"])

min_d, max_d = get_date_range(ga4_r, "date")

prod_base = prod_work.copy()
prod_con_data = prod_base[prod_base["ga4_views"] >= 0].copy() if not prod_base.empty else pd.DataFrame()

auth_list = ["Todos"]
if not prod_con_data.empty and "post_author_name" in prod_con_data.columns:
    auth_list += sorted(prod_con_data["post_author_name"].fillna("Sin autor").replace("", "Sin autor").drop_duplicates().tolist())

cat_list = ["Todas"]
if not prod_con_data.empty and "categories" in prod_con_data.columns:
    cat_list += prod_con_data["categories"].fillna("").apply(_split_cats).explode().dropna().replace("", pd.NA).dropna().value_counts().head(40).index.tolist()

city_list = ["Todas"]
if not city_r.empty and "city" in city_r.columns:
    city_list += city_r[city_r["city"] != "(not set)"].groupby("city")["activeUsers"].sum().sort_values(ascending=False).head(50).index.tolist()

chan_list = ["Todos"]
if not chan_r.empty and "sessionDefaultChannelGroup" in chan_r.columns:
    chan_list += sorted(chan_r["sessionDefaultChannelGroup"].dropna().unique().tolist())

sh("⚙️ Filtros")
st.markdown('<div class="filter-box">', unsafe_allow_html=True)
c1, c2, c3, c4, c5, c6 = st.columns(6)
with c1: start = st.date_input("📅 Desde", max_d - timedelta(days=90), min_value=min_d, max_value=max_d, key="gs")
with c2: end = st.date_input("📅 Hasta", max_d, min_value=min_d, max_value=max_d, key="ge")
with c3: sel_aut = st.selectbox("✍️ Autor", auth_list, key="ga")
with c4: sel_city = st.selectbox("🏙️ Ciudad", city_list, key="gc")
with c5: sel_cat = st.selectbox("📂 Sección", cat_list, key="gcat")
with c6: sel_chan = st.selectbox("📡 Canal", chan_list, key="gch")
st.markdown('</div>', unsafe_allow_html=True)

has_aut = sel_aut != "Todos"
has_cat = sel_cat != "Todas"
has_city = sel_city != "Todas"
has_chan = sel_chan != "Todos"
has_editorial = has_aut or has_cat

ga4 = filter_by_date(ga4_r, "date", start, end)
city = filter_by_date(city_r, "date", start, end)
cnt = filter_by_date(cnt_r, "date", start, end)
chan = filter_by_date(chan_r, "date", start, end)
age = filter_by_date(age_r, "date", start, end)
dev = filter_by_date(dev_r, "date", start, end)
urls = filter_by_date(urls_r, "date", start, end)
prod = filter_by_date(prod_base, "post_date", start, end) if "post_date" in prod_base.columns else prod_base.copy()

pd_ = max((end - start).days, 1)
prev_s = start - timedelta(days=pd_)
prev_e = start - timedelta(days=1)

if has_city and "city" in city.columns:
    city = city[city["city"] == sel_city].copy()
if has_chan and "sessionDefaultChannelGroup" in chan.columns:
    chan = chan[chan["sessionDefaultChannelGroup"] == sel_chan].copy()
if has_aut and "post_author_name" in prod.columns:
    prod = prod[prod["post_author_name"] == sel_aut].copy()
if has_cat and "categories" in prod.columns:
    prod = prod[prod["categories"].fillna("").apply(lambda x: sel_cat in _split_cats(x))].copy()

if has_editorial and not prod.empty and not urls.empty and "pagePath" in urls.columns:
    valid_paths = _author_paths(prod)
    urls = urls.copy()
    urls["pagePath_norm"] = urls["pagePath"].apply(_norm_path)
    urls = urls[urls["pagePath_norm"].isin(valid_paths)].copy() if valid_paths else pd.DataFrame()

def _prev_editorial(urls_r_full, prod_r_full, prev_s, prev_e, sel_aut, sel_cat, has_aut, has_cat):
    urls_p = filter_by_date(urls_r_full, "date", prev_s, prev_e)
    prod_p = filter_by_date(prod_r_full, "post_date", prev_s, prev_e) if "post_date" in prod_r_full.columns else prod_r_full.copy()
    if has_aut and "post_author_name" in prod_p.columns:
        prod_p = prod_p[prod_p["post_author_name"] == sel_aut]
    if has_cat and "categories" in prod_p.columns:
        prod_p = prod_p[prod_p["categories"].fillna("").apply(lambda x: sel_cat in _split_cats(x))]
    valid = _author_paths(prod_p)
    if not urls_p.empty and valid and "pagePath" in urls_p.columns:
        urls_p = urls_p.copy()
        urls_p["pagePath_norm"] = urls_p["pagePath"].apply(_norm_path)
        urls_p = urls_p[urls_p["pagePath_norm"].isin(valid)]
    return _urls_to_daily(urls_p)

captions = []
if has_editorial:
    _src = _urls_to_daily(urls)
    _src_p = _prev_editorial(urls_r, prod_base, prev_s, prev_e, sel_aut, sel_cat, has_aut, has_cat)
    if has_aut: captions.append(f"✍️ **{sel_aut}**")
    if has_cat: captions.append(f"📂 **{sel_cat}**")
elif has_chan and has_city:
    d1 = set(city["date"].dt.date) if "date" in city.columns else set()
    d2 = set(chan["date"].dt.date) if "date" in chan.columns else set()
    common = d1 & d2
    _src = city[city["date"].dt.date.isin(common)].copy() if common else city.copy()
    cp = filter_by_date(city_r, "date", prev_s, prev_e)
    _src_p = cp[cp["city"] == sel_city].copy() if not cp.empty and "city" in cp.columns else pd.DataFrame()
    captions += [f"🏙️ **{sel_city}**", f"📡 **{sel_chan}**"]
elif has_chan:
    _src = chan.copy()
    chp = filter_by_date(chan_r, "date", prev_s, prev_e)
    _src_p = chp[chp["sessionDefaultChannelGroup"] == sel_chan].copy() if not chp.empty and "sessionDefaultChannelGroup" in chp.columns else pd.DataFrame()
    captions.append(f"📡 **{sel_chan}**")
elif has_city:
    _src = city.copy()
    cp = filter_by_date(city_r, "date", prev_s, prev_e)
    _src_p = cp[cp["city"] == sel_city].copy() if not cp.empty and "city" in cp.columns else pd.DataFrame()
    captions.append(f"🏙️ **{sel_city}**")
else:
    _src = ga4.copy()
    _src_p = filter_by_date(ga4_r, "date", prev_s, prev_e)

if captions:
    st.caption("  ·  ".join(captions))

sh("📊 Métricas del Período")
m1, m2, m3, m4, m5, m6 = st.columns(6)
au = int(safe_sum(_src, "activeUsers")); au_p = int(safe_sum(_src_p, "activeUsers"))
vw = int(safe_sum(_src, "screenPageViews")); vw_p = int(safe_sum(_src_p, "screenPageViews"))
ss = int(safe_sum(_src, "sessions")); ss_p = int(safe_sum(_src_p, "sessions"))
dur = float(_src["userEngagementDuration"].sum() / max(au, 1)) if not _src.empty and "userEngagementDuration" in _src.columns and au > 0 else 0.0
u_ct = urls["pagePath"].nunique() if not urls.empty and "pagePath" in urls.columns else 0
p_ct = len(prod)
m1.metric("👤 Usuarios", fmt_number(au), _delta_str(au, au_p))
m2.metric("📄 Vistas", fmt_number(vw), _delta_str(vw, vw_p))
m3.metric("🔄 Sesiones", fmt_number(ss), _delta_str(ss, ss_p))
m4.metric("⏱ Tiempo Prom.", f"{dur/60:.1f}m" if dur else "—")
m5.metric("🔗 URLs c/Tráfico", fmt_number(u_ct))
m6.metric("✍️ Publicaciones", fmt_number(p_ct))

sh("🎯 Meta Q1 — 750,000 Usuarios")
ga4_q = filter_by_date(ga4_r, "date", date(end.year, 1, 1), date(end.year, 3, 31))
q1u = int(safe_sum(ga4_q, "activeUsers"))
pct = min(q1u / 750_000, 1.0)
qa, qb, qc = st.columns([4, 1, 1])
with qa:
    st.progress(pct, text=f"**{fmt_number(q1u)}** / **750K** — {pct*100:.1f}%")
with qb:
    st.metric("Alcanzado", fmt_number(q1u))
with qc:
    st.metric("Faltan", fmt_number(max(750_000 - q1u, 0)), delta="✅ Meta!" if q1u >= 750_000 else f"-{fmt_number(max(750_000 - q1u, 0))}", delta_color="normal" if q1u >= 750_000 else "inverse")

with st.expander("🔬 Diagnóstico Producción", expanded=False):
    stats = match_stats(prod_r)
    if stats:
        total = sum(stats.values())
        st.markdown(f"**{total:,} notas** cargadas desde Producción")
        for m, n in sorted(stats.items(), key=lambda x: -x[1]):
            st.markdown(f"- `{m}`: **{n:,}** ({n/total*100:.1f}%)")
    else:
        st.info("Sin datos.")

st.markdown("---")
sh("📈 Evolución Mensual · Usuarios vs Vistas")
if not _src.empty and "date" in _src.columns:
    ev = _src.copy()
    ev["mes"] = ev["date"].dt.to_period("M").astype(str)
    kw = {}
    if "activeUsers" in ev.columns: kw["U"] = ("activeUsers", "sum")
    if "screenPageViews" in ev.columns: kw["V"] = ("screenPageViews", "sum")
    if kw:
        mo = ev.groupby("mes", as_index=False).agg(**kw)
        fig1 = go.Figure()
        if "V" in mo.columns:
            fig1.add_trace(go.Bar(x=mo["mes"], y=mo["V"], name="Vistas", marker_color="#06b6d4", opacity=0.4, yaxis="y2"))
        if "U" in mo.columns:
            fig1.add_trace(go.Scatter(x=mo["mes"], y=mo["U"], name="Usuarios", mode="lines+markers", line=dict(color="#6366f1", width=3), marker=dict(size=7, color="#6366f1", line=dict(color="#fff", width=1.5))))
        fig1.update_layout(yaxis2=dict(overlaying="y", side="right", showgrid=False, tickfont=dict(color="#06b6d4"), title="Vistas"), yaxis=dict(title="Usuarios"), barmode="overlay", legend=dict(orientation="h", y=1.12))
        _fig(fig1, 340)
        st.plotly_chart(fig1, use_container_width=True)
else:
    st.info("Sin datos GA4 para el período y filtros seleccionados.")

sh("📰 URLs y Autores")
n1, n2 = st.columns(2)
with n1:
    st.markdown("**🔝 URLs más leídas**")
    if not urls.empty and "pagePath" in urls.columns:
        urls = urls.copy()
        urls["pagePath_norm"] = urls["pagePath"].apply(_norm_path)
        grp = ["pagePath", "pagePath_norm"] + (["pageTitle"] if "pageTitle" in urls.columns else [])
        ua = urls.groupby(grp, as_index=False).agg(Vistas=("screenPageViews", "sum"), Usuarios=("activeUsers", "sum")).sort_values("Vistas", ascending=False).head(30)
        p2a = { _norm_path(u): a for u, a in zip(prod_base["url"], prod_base["post_author_name"]) if _norm_path(u) }
        ua["Autor"] = ua["pagePath_norm"].apply(lambda p: p2a.get(p, "—"))
        dc = [c for c in ["pageTitle", "Autor", "Vistas", "Usuarios"] if c in ua.columns]
        st.dataframe(ua[dc].style.format({"Vistas": "{:,.0f}", "Usuarios": "{:,.0f}"}), use_container_width=True, hide_index=True, height=400)
    else:
        st.info("Sin datos de URLs.")
with n2:
    st.markdown("**✍️ Autores más leídos**")
    if not prod.empty and "post_author_name" in prod.columns and "ga4_views" in prod.columns:
        tmp = prod.copy()
        tmp["post_author_name"] = tmp["post_author_name"].replace("", "Sin autor").fillna("Sin autor")
        if "post_id" not in tmp.columns:
            tmp["post_id"] = range(1, len(tmp) + 1)
        if "ga4_users" not in tmp.columns:
            tmp["ga4_users"] = 0
        aa = tmp.groupby("post_author_name", as_index=False).agg(Vistas=("ga4_views", "sum"), Notas=("post_id", "count"), Usuarios=("ga4_users", "sum")).sort_values("Vistas", ascending=False).head(25)
        aa["V/Nota"] = (aa["Vistas"] / aa["Notas"].clip(1)).round(0).astype(int)
        st.dataframe(aa.rename(columns={"post_author_name": "Autor"}).style.format({"Vistas": "{:,.0f}", "Notas": "{:,.0f}", "Usuarios": "{:,.0f}", "V/Nota": "{:,.0f}"}), use_container_width=True, hide_index=True, height=400)
    else:
        st.info("Sin datos de autores.")
