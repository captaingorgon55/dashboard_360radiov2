import sys, os
sys.path.insert(0, os.getcwd())

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta
from urllib.parse import urlparse as up

from data_loader import (
    load_ga4_general,
    load_ga4_city,
    load_ga4_country,
    load_ga4_channel,
    load_ga4_age,
    load_ga4_device,
    load_ga4_interests,
    load_ga4_urls,
    load_produccion_con_metricas,
    filter_by_date,
    fmt_number,
    safe_sum,
    get_date_range,
    deltastr,
    match_stats,
)

C = ["#6366f1", "#06b6d4", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#14b8a6"]
PBG = "#0d0d20"


def fig(fig, h=340):
    fig.update_layout(
        height=h,
        paper_bgcolor=PBG,
        plot_bgcolor=PBG,
        font=dict(family="Inter", color="#8890b8", size=11),
        margin=dict(l=6, r=6, t=36, b=6),
        legend=dict(bgcolor="rgba(0,0,0,0)", font_size=11),
        xaxis=dict(gridcolor="#14142e", zerolinecolor="#14142e"),
        yaxis=dict(gridcolor="#14142e", zerolinecolor="#14142e"),
        title_font=dict(family="Syne", size=13, color="#c0c8e8"),
    )
    return fig


def sh(t):
    st.markdown(f"<div class='sec-hdr'>{t}</div>", unsafe_allow_html=True)


def author_col(df):
    if df is None or df.empty:
        return None
    if "author_resolved" in df.columns:
        return "author_resolved"
    if "post_author_name" in df.columns:
        return "post_author_name"
    return None


def author_paths(prod_df):
    if prod_df.empty or "url" not in prod_df.columns:
        return set()
    return {up(str(u)).path.rstrip("/") for u in prod_df["url"] if pd.notna(u)}


def urls_to_daily(urls_df):
    if urls_df.empty or "date" not in urls_df.columns:
        return pd.DataFrame()
    cols = [c for c in ["date", "screenPageViews", "activeUsers", "sessions", "userEngagementDuration"] if c in urls_df.columns]
    agg = {c: (c, "sum") for c in cols if c != "date"}
    return urls_df[cols].groupby("date", as_index=False).agg(**agg)


st.markdown("<div class='page-title'>General · Tráfico y Producción</div>", unsafe_allow_html=True)
st.markdown("<div class='page-subtitle'>GA4 + Producción editorial</div>", unsafe_allow_html=True)

with st.spinner("Cargando datos..."):
    ga4r = load_ga4_general()
    cityr = load_ga4_city()
    cntr = load_ga4_country()
    chanr = load_ga4_channel()
    ager = load_ga4_age()
    devr = load_ga4_device()
    urlsr = load_ga4_urls()
    prodr = load_produccion_con_metricas()

mind, maxd = get_date_range(ga4r, "date")

prodconmatch = prodr[prodr["ga4_views"] > 0] if not prodr.empty and "ga4_views" in prodr.columns else pd.DataFrame()

authlist = ["Todos"]
acol_list = author_col(prodconmatch)
if not prodconmatch.empty and acol_list:
    vals = (
        prodconmatch[acol_list]
        .dropna()
        .astype(str)
        .loc[lambda s: s.str.strip() != ""]
        .unique()
        .tolist()
    )
    authlist = ["Todos"] + sorted(vals)

catlist = ["Todas"]
if not prodconmatch.empty and "categories" in prodconmatch.columns:
    cats = (
        prodconmatch["categories"]
        .fillna("")
        .apply(lambda x: [p.strip() for p in str(x).split(",") if p.strip()])
        .explode()
        .value_counts()
        .head(40)
        .index
        .tolist()
    )
    catlist = ["Todas"] + cats

citylist = ["Todas"]
if not cityr.empty and "city" in cityr.columns:
    citylist = ["Todas"] + (
        cityr[cityr["city"] != "(not set)"]
        .groupby("city")["activeUsers"]
        .sum()
        .sort_values(ascending=False)
        .head(50)
        .index
        .tolist()
    )

chanlist = ["Todos"]
if not chanr.empty and "sessionDefaultChannelGroup" in chanr.columns:
    chanlist = ["Todos"] + sorted(chanr["sessionDefaultChannelGroup"].dropna().unique().tolist())

sh("Filtros")
st.markdown("<div class='filter-box'>", unsafe_allow_html=True)
c1, c2, c3, c4, c5, c6 = st.columns(6)

with c1:
    start = st.date_input("Desde", maxd - timedelta(days=90), min_value=mind, max_value=maxd, key="gs")
with c2:
    end = st.date_input("Hasta", maxd, min_value=mind, max_value=maxd, key="ge")
with c3:
    selaut = st.selectbox("Autor", authlist, key="ga")
with c4:
    selcity = st.selectbox("Ciudad", citylist, key="gc")
with c5:
    selcat = st.selectbox("Sección", catlist, key="gcat")
with c6:
    selchan = st.selectbox("Canal", chanlist, key="gch")
st.markdown("</div>", unsafe_allow_html=True)

hasaut = selaut != "Todos"
hascat = selcat != "Todas"
hascity = selcity != "Todas"
haschan = selchan != "Todos"
haseditorial = hasaut or hascat
hasga4dim = hascity or haschan

ga4 = filter_by_date(ga4r, "date", start, end)
city = filter_by_date(cityr, "date", start, end)
cnt = filter_by_date(cntr, "date", start, end)
chan = filter_by_date(chanr, "date", start, end)
age = filter_by_date(ager, "date", start, end)
dev = filter_by_date(devr, "date", start, end)
urls = filter_by_date(urlsr, "date", start, end)

period_days = max((end - start).days, 1)
prevs = start - timedelta(days=period_days)
preve = start - timedelta(days=1)

if hascity and "city" in city.columns:
    city = city[city["city"] == selcity].copy()

if haschan and "sessionDefaultChannelGroup" in chan.columns:
    chan = chan[chan["sessionDefaultChannelGroup"] == selchan].copy()

prod = filter_by_date(prodr, "post_date", start, end)
acol_prod = author_col(prod)

if hasaut and acol_prod:
    prod = prod[prod[acol_prod] == selaut].copy()

if hascat and "categories" in prod.columns:
    prod = prod[
        prod["categories"].fillna("").apply(
            lambda x: selcat in [p.strip() for p in str(x).split(",")]
        )
    ].copy()

if haseditorial and not prod.empty and not urls.empty and "pagePath" in urls.columns:
    validpaths = author_paths(prod)
    urls = urls[urls["pagePath"].apply(lambda p: str(p).rstrip("/") in validpaths)].copy() if validpaths else pd.DataFrame()


def prev_editorial(urlsr_full, prodr_full, prevs, preve, selaut, selcat, hasaut, hascat):
    urlsp = filter_by_date(urlsr_full, "date", prevs, preve)
    prodp = prodr_full.copy()

    acol_prevp = author_col(prodp)
    if hasaut and acol_prevp:
        prodp = prodp[prodp[acol_prevp] == selaut]

    if hascat and "categories" in prodp.columns:
        prodp = prodp[
            prodp["categories"].fillna("").apply(
                lambda x: selcat in [p.strip() for p in str(x).split(",")]
            )
        ]

    valid = author_paths(prodp)
    if not urlsp.empty and valid and "pagePath" in urlsp.columns:
        urlsp = urlsp[urlsp["pagePath"].apply(lambda p: str(p).rstrip("/") in valid)]

    return urls_to_daily(urlsp)


captions = []

if haseditorial:
    src = urls_to_daily(urls)
    srcp = prev_editorial(urlsr, prodr, prevs, preve, selaut, selcat, hasaut, hascat)
    if hasaut:
        captions.append(selaut)
    if hascat:
        captions.append(selcat)
elif haschan and hascity:
    d1 = set(city["date"].dt.date) if "date" in city.columns else set()
    d2 = set(chan["date"].dt.date) if "date" in chan.columns else set()
    common = d1 & d2
    src = city[city["date"].dt.date.isin(common)].copy() if common else city.copy()
    cp = filter_by_date(cityr, "date", prevs, preve)
    srcp = cp[cp["city"] == selcity].copy() if not cp.empty and "city" in cp.columns else pd.DataFrame()
    captions += [selcity, selchan]
elif haschan:
    src = chan.copy()
    chp = filter_by_date(chanr, "date", prevs, preve)
    srcp = chp[chp["sessionDefaultChannelGroup"] == selchan].copy() if not chp.empty and "sessionDefaultChannelGroup" in chp.columns else pd.DataFrame()
    captions.append(selchan)
elif hascity:
    src = city.copy()
    cp = filter_by_date(cityr, "date", prevs, preve)
    srcp = cp[cp["city"] == selcity].copy() if not cp.empty and "city" in cp.columns else pd.DataFrame()
    captions.append(selcity)
else:
    src = ga4.copy()
    srcp = filter_by_date(ga4r, "date", prevs, preve)

if captions:
    st.caption(" · ".join(captions))

sh("Métricas del Período")
m1, m2, m3, m4, m5, m6 = st.columns(6)

au = int(safe_sum(src, "activeUsers"))
aup = int(safe_sum(srcp, "activeUsers"))
vw = int(safe_sum(src, "screenPageViews"))
vwp = int(safe_sum(srcp, "screenPageViews"))
ss = int(safe_sum(src, "sessions"))
ssp = int(safe_sum(srcp, "sessions"))

dur = (
    float(src["userEngagementDuration"].sum()) / max(au, 1)
    if not src.empty and "userEngagementDuration" in src.columns and au > 0
    else 0.0
)

uct = urls["pagePath"].nunique() if not urls.empty and "pagePath" in urls.columns else 0
pct = len(prod)

m1.metric("Usuarios", fmt_number(au), deltastr(au, aup))
m2.metric("Vistas", fmt_number(vw), deltastr(vw, vwp))
m3.metric("Sesiones", fmt_number(ss), deltastr(ss, ssp))
m4.metric("Tiempo Prom.", f"{dur/60:.1f}m" if dur else "0m")
m5.metric("URLs c/Tráfico", fmt_number(uct))
m6.metric("Publicaciones", fmt_number(pct))

sh("Meta Q1 · 750,000 Usuarios")
ga4q = filter_by_date(ga4r, "date", date(end.year, 1, 1), date(end.year, 3, 31))
q1u = int(safe_sum(ga4q, "activeUsers"))
pct = min(q1u / 750000, 1.0)

qa, qb, qc = st.columns((4, 1, 1))
with qa:
    st.progress(pct, text=f"{fmt_number(q1u)} / 750K · {pct*100:.1f}%")
with qb:
    st.metric("Alcanzado", fmt_number(q1u))
with qc:
    st.metric(
        "Faltan",
        fmt_number(max(750000 - q1u, 0)),
        delta="Meta!" if q1u >= 750000 else f"-{fmt_number(max(750000 - q1u, 0))}",
        delta_color="normal" if q1u >= 750000 else "inverse",
    )

with st.expander("Diagnóstico matching Producción/GA4", expanded=False):
    stats = match_stats(prodr)
    if stats:
        total = sum(stats.values())
        matched = total - stats.get("sin_match", 0)
        st.markdown(f"**{matched:,} / {total:,}** notas conectadas ({matched/total*100:.1f}%)")
        for m, n in sorted(stats.items(), key=lambda x: -x[1]):
            st.markdown(f"- {m}: **{n:,}** ({n/total*100:.1f}%)")
    else:
        st.info("Sin datos.")

st.markdown("---")

sh("Evolución Mensual · Usuarios vs Vistas")
if not src.empty and "date" in src.columns:
    ev = src.copy()
    ev["mes"] = ev["date"].dt.to_period("M").astype(str)
    kw = {}
    if "activeUsers" in ev.columns:
        kw["U"] = ("activeUsers", "sum")
    if "screenPageViews" in ev.columns:
        kw["V"] = ("screenPageViews", "sum")
    if kw:
        mo = ev.groupby("mes", as_index=False).agg(**kw)
        fig1 = go.Figure()
        if "V" in mo.columns:
            fig1.add_trace(go.Bar(x=mo["mes"], y=mo["V"], name="Vistas", marker_color="#06b6d4", opacity=0.4, yaxis="y2"))
        if "U" in mo.columns:
            fig1.add_trace(go.Scatter(
                x=mo["mes"], y=mo["U"], name="Usuarios",
                mode="lines+markers",
                line=dict(color="#6366f1", width=3),
                marker=dict(size=7, color="#6366f1", line=dict(color="#fff", width=1.5))
            ))
        fig1.update_layout(
            yaxis2=dict(overlaying="y", side="right", showgrid=False, tickfont=dict(color="#06b6d4"), title="Vistas"),
            yaxis=dict(title="Usuarios"),
            barmode="overlay",
            legend=dict(orientation="h", y=1.12),
        )
        fig(fig1, 340)
        st.plotly_chart(fig1, use_container_width=True)
    else:
        st.info("Sin datos GA4 para el período y filtros seleccionados.")
else:
    st.info("Sin datos GA4 para el período y filtros seleccionados.")

sh("Canales de Tráfico")
if haseditorial:
    st.info("Desglose por canal no disponible con filtro de autor/sección.")
else:
    chansrc = filter_by_date(chanr, "date", start, end)
    if not chansrc.empty and "sessionDefaultChannelGroup" in chansrc.columns:
        ca = (
            chansrc.groupby("sessionDefaultChannelGroup", as_index=False)
            .agg(U=("activeUsers", "sum"), V=("screenPageViews", "sum"), S=("sessions", "sum"))
            .sort_values("U", ascending=False)
        )
        cc1, cc2 = st.columns((1, 2))
        with cc1:
            f2 = px.pie(ca, names="sessionDefaultChannelGroup", values="U", color_discrete_sequence=C, hole=0.52)
            f2.update_traces(textposition="inside", textinfo="percent+label", textfont_size=11)
            f2.update_layout(showlegend=False)
            fig(f2, 280)
            st.plotly_chart(f2, use_container_width=True)
        with cc2:
            styled = ca.rename(columns={"sessionDefaultChannelGroup": "Canal", "U": "Usuarios", "V": "Vistas", "S": "Sesiones"})
            st.dataframe(
                styled.style.format({"Usuarios": "{:,.0f}", "Vistas": "{:,.0f}", "Sesiones": "{:,.0f}"}),
                use_container_width=True,
                hide_index=True,
                height=260,
            )
        if haschan:
            selrow = ca[ca["sessionDefaultChannelGroup"] == selchan]
            if not selrow.empty:
                st.caption(f"Canal {selchan}: {fmt_number(int(selrow['U'].iloc[0]))} usuarios · {fmt_number(int(selrow['V'].iloc[0]))} vistas · {fmt_number(int(selrow['S'].iloc[0]))} sesiones")
    else:
        st.info("Sin datos de canales.")

sh("Tráfico por Ciudad · Top 20")
if haseditorial:
    st.info("Desglose por ciudad no disponible con filtro de autor/sección.")
else:
    citysrc = filter_by_date(cityr, "date", start, end)
    if not citysrc.empty and "city" in citysrc.columns:
        cv = (
            citysrc[citysrc["city"] != "(not set)"]
            .groupby("city", as_index=False)
            .agg(U=("activeUsers", "sum"))
            .sort_values("U", ascending=False)
            .head(20)
        )
        f3 = px.bar(cv, x="U", y="city", orientation="h", color="U", color_continuous_scale=["#14143a", "#6366f1", "#06b6d4"], text="U")
        f3.update_traces(texttemplate="%{text:,.0f}", textposition="outside", textfont_size=10)
        f3.update_layout(yaxis=dict(autorange="reversed"), coloraxis_showscale=False, yaxis_title="", xaxis_title="Usuarios Activos")
        fig(f3, max(360, len(cv) * 26 + 60))
        st.plotly_chart(f3, use_container_width=True)

        if hascity:
            selcv = cv[cv["city"] == selcity]
            if not selcv.empty:
                st.caption(f"Ciudad {selcity}: {fmt_number(int(selcv['U'].iloc[0]))} usuarios")
    else:
        st.info("Sin datos de ciudades.")

sh("Tráfico por País")
if haseditorial:
    st.info("Desglose por país no disponible con filtro de autor/sección.")
elif not cnt.empty and "country" in cnt.columns:
    cv2 = (
        cnt[cnt["country"] != "(not set)"]
        .groupby("country", as_index=False)
        .agg(U=("activeUsers", "sum"))
        .sort_values("U", ascending=False)
    )
    pc1, pc2 = st.columns((3, 1))
    with pc1:
        f4 = px.choropleth(cv2, locations="country", location_mode="country names", color="U",
                           color_continuous_scale=["#0a0a20", "#6366f1", "#06b6d4", "#10b981"])
        f4.update_layout(
            geo=dict(
                bgcolor=PBG,
                showframe=False,
                landcolor="#10102a",
                showocean=True,
                oceancolor="#080814",
                showcoastlines=True,
                coastlinecolor="#1a1a3a",
            )
        )
        fig(f4, 340)
        st.plotly_chart(f4, use_container_width=True)
    with pc2:
        st.dataframe(
            cv2.head(25).rename(columns={"country": "País", "U": "Usuarios"}).style.format({"Usuarios": "{:,.0f}"}),
            use_container_width=True,
            hide_index=True,
            height=320,
        )
else:
    st.info("Sin datos de países.")

sh("URLs y Autores")
n1, n2 = st.columns(2)

with n1:
    st.markdown("**URLs más leídas**")
    if not urls.empty and "pagePath" in urls.columns:
        grp = ["pagePath", "pageTitle"] if "pageTitle" in urls.columns else ["pagePath"]
        ua = (
            urls.groupby(grp, as_index=False)
            .agg(Vistas=("screenPageViews", "sum"), Usuarios=("activeUsers", "sum"))
            .sort_values("Vistas", ascending=False)
            .head(30)
        )

        acol_urls = author_col(prodr)
        if not prodr.empty and "url" in prodr.columns and acol_urls:
            p2a = {
                up(str(u)).path.rstrip("/"): a
                for u, a in zip(prodr["url"], prodr[acol_urls])
                if pd.notna(u)
            }
            ua["Autor"] = ua["pagePath"].apply(lambda p: p2a.get(str(p).rstrip("/"), ""))

        dc = [c for c in ["pageTitle", "Autor", "Vistas", "Usuarios"] if c in ua.columns]
        st.dataframe(
            ua[dc].style.format({"Vistas": "{:,.0f}", "Usuarios": "{:,.0f}"}),
            use_container_width=True,
            hide_index=True,
            height=400,
        )
    else:
        st.info("Sin datos de URLs.")

with n2:
    st.markdown("**Autores más leídos**")
    acol_aa = author_col(prod)
    if not prod.empty and acol_aa and "ga4_views" in prod.columns:
        aa = (
            prod.groupby(acol_aa, as_index=False)
            .agg(Vistas=("ga4_views", "sum"), Notas=("post_id", "count"), Usuarios=("ga4_users", "sum"))
            .sort_values("Vistas", ascending=False)
            .head(25)
        )
        aa["VNota"] = (aa["Vistas"] / aa["Notas"].clip(lower=1)).round(0).astype(int)
        st.dataframe(
            aa.rename(columns={acol_aa: "Autor"}).style.format(
                {"Vistas": "{:,.0f}", "Notas": "{:,.0f}", "Usuarios": "{:,.0f}", "VNota": "{:,.0f}"}
            ),
            use_container_width=True,
            hide_index=True,
            height=400,
        )
    else:
        st.info("Sin datos de autores.")

sh("Secciones")
if not prod.empty and "categories" in prod.columns and "ga4_views" in prod.columns:
    sp = prod.copy()
    sp["cat"] = sp["categories"].fillna("Sin cat").apply(
        lambda x: ", ".join([p.strip() for p in str(x).split(",") if p.strip()]) if hascat else str(x).split(",")[0].strip()
    )
    sa = (
        sp.groupby("cat", as_index=False)
        .agg(U=("ga4_users", "sum"), V=("ga4_views", "sum"), N=("post_id", "count"))
        .sort_values("V", ascending=False)
        .head(20)
    )
    sc1, sc2 = st.columns((1, 2))
    with sc1:
        f6 = px.pie(sa.head(10), names="cat", values="U", color_discrete_sequence=C, hole=0.48)
        f6.update_traces(textposition="inside", textinfo="percent+label", textfont_size=10)
        f6.update_layout(showlegend=False)
        fig(f6, 280)
        st.plotly_chart(f6, use_container_width=True)
    with sc2:
        st.dataframe(
            sa.rename(columns={"cat": "Sección", "U": "Usuarios", "V": "Vistas", "N": "Notas"}).style.format(
                {"Usuarios": "{:,.0f}", "Vistas": "{:,.0f}", "Notas": "{:,.0f}"}
            ),
            use_container_width=True,
            hide_index=True,
            height=300,
        )
else:
    st.info("Sin datos de secciones.")

sh("Producción por Mes")
if not prod.empty and "post_date" in prod.columns:
    tp = prod.copy()
    tp["mes"] = tp["post_date"].dt.to_period("M").astype(str)
    pm = tp.groupby("mes", as_index=False).agg(
        pub=("post_id", "count"),
        con=("ga4_views", lambda x: (x > 0).sum()),
    )
    pm["sin"] = pm["pub"] - pm["con"]
    fig7 = go.Figure()
    fig7.add_trace(go.Bar(x=pm["mes"], y=pm["con"], name="Con tráfico", marker_color="#10b981"))
    fig7.add_trace(go.Bar(x=pm["mes"], y=pm["sin"], name="Sin tráfico", marker_color="#1e1e40"))
    fig7.update_layout(barmode="stack", legend=dict(orientation="h", y=1.12))
    fig(fig7, 260)
    st.plotly_chart(fig7, use_container_width=True)

sh("Notas IA Más Leídas")
if not prod.empty and "is_ia" in prod.columns:
    ia = prod[prod["is_ia"]].sort_values("ga4_views", ascending=False).head(25)
    if not ia.empty:
        acol_ia = author_col(ia)
        cols = [c for c in ["post_title", "post_date", "ga4_views", "ga4_users", "match_method"] if c in ia.columns]
        if acol_ia:
            cols.insert(1, acol_ia)

        rename_cols = {
            "post_title": "Título",
            "post_date": "Fecha",
            "ga4_views": "Vistas",
            "ga4_users": "Usuarios",
            "match_method": "Match",
        }
        if acol_ia:
            rename_cols[acol_ia] = "Autor"

        st.dataframe(
            ia[cols].rename(columns=rename_cols).style.format({"Vistas": "{:,.0f}", "Usuarios": "{:,.0f}"}),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No hay notas IA en el período seleccionado.")

sh("Audiencia")
t1, t2, t3 = st.tabs(["Edad", "Dispositivo", "Intereses"])

with t1:
    if haseditorial:
        st.info("Desglose por edad no disponible con filtro de autor/sección.")
    elif not age.empty and "userAgeBracket" in age.columns:
        a2 = age.groupby("userAgeBracket", as_index=False).agg(U=("activeUsers", "sum")).sort_values("userAgeBracket")
        fa = px.bar(a2, x="userAgeBracket", y="U", color="U", color_continuous_scale=["#14143a", "#6366f1"], text="U")
        fa.update_traces(texttemplate="%{text:,.0f}", textposition="outside", textfont_size=10)
        fa.update_layout(coloraxis_showscale=False, xaxis_title="Edad", yaxis_title="Usuarios")
        fig(fa, 270)
        st.plotly_chart(fa, use_container_width=True)
    else:
        st.info("Sin datos de edad.")

with t2:
    if haseditorial:
        st.info("Desglose por dispositivo no disponible con filtro de autor/sección.")
    elif not dev.empty and "deviceCategory" in dev.columns:
        da = dev.groupby("deviceCategory", as_index=False).agg(U=("activeUsers", "sum"), V=("screenPageViews", "sum"))
        d1, d2 = st.columns(2)
        with d1:
            fd = px.pie(da, names="deviceCategory", values="U", color_discrete_sequence=C, hole=0.52)
            fd.update_traces(textposition="inside", textinfo="percent+label", textfont_size=13)
            fd.update_layout(showlegend=False)
            fig(fd, 260)
            st.plotly_chart(fd, use_container_width=True)
        with d2:
            fdv = px.bar(da, x="deviceCategory", y="V", color="deviceCategory", color_discrete_sequence=C, text="V")
            fdv.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
            fdv.update_layout(showlegend=False, xaxis_title="", yaxis_title="Vistas")
            fig(fdv, 260)
            st.plotly_chart(fdv, use_container_width=True)

        st.dataframe(
            da.rename(columns={"deviceCategory": "Dispositivo", "U": "Usuarios", "V": "Vistas"}).style.format(
                {"Usuarios": "{:,.0f}", "Vistas": "{:,.0f}"}
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Sin datos de dispositivos.")

with t3:
    intrr = load_ga4_interests()
    intr = filter_by_date(intrr, "date", start, end) if not intrr.empty else intrr
    if not intr.empty and "brandingInterest" in intr.columns:
        ia2 = intr.groupby("brandingInterest", as_index=False).agg(U=("activeUsers", "sum")).sort_values("U", ascending=False).head(25)
        fi = px.bar(ia2, x="U", y="brandingInterest", orientation="h", color="U", color_continuous_scale=["#14143a", "#8b5cf6"])
        fi.update_layout(yaxis=dict(autorange="reversed"), coloraxis_showscale=False, yaxis_title="")
        fig(fi, 500)
        st.plotly_chart(fi, use_container_width=True)
    else:
        st.info("Sin datos de intereses.")
