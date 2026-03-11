import sys, os; sys.path.insert(0, os.getcwd())
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta
from data_loader import (
    load_ga4_general, load_ga4_city, load_ga4_country, load_ga4_channel,
    load_ga4_age, load_ga4_device, load_ga4_interests, load_ga4_urls,
    load_search_console, load_produccion_con_metricas,
    filter_by_date, fmt_number, safe_sum, get_date_range, _delta_str, match_stats
)

C = ["#6366f1","#06b6d4","#10b981","#f59e0b","#ef4444","#8b5cf6","#ec4899","#14b8a6"]
BG = "#080814"; PBG = "#0d0d20"

def _fig(fig, h=340):
    fig.update_layout(height=h, paper_bgcolor=PBG, plot_bgcolor=PBG,
        font=dict(family="Inter", color="#8890b8", size=11),
        margin=dict(l=6,r=6,t=36,b=6),
        legend=dict(bgcolor="rgba(0,0,0,0)", font_size=11),
        xaxis=dict(gridcolor="#14142e", zerolinecolor="#14142e"),
        yaxis=dict(gridcolor="#14142e", zerolinecolor="#14142e"),
        title_font=dict(family="Syne", size=13, color="#c0c8e8"))
    return fig

def sh(t): st.markdown(f'<div class="sec-hdr">{t}</div>', unsafe_allow_html=True)

st.markdown('<div class="page-title">🏠 General · Tráfico y Producción</div>', unsafe_allow_html=True)
st.markdown('<div class="page-subtitle">GA4 · Search Console · Producción editorial</div>', unsafe_allow_html=True)

# ── Carga ─────────────────────────────────────────────────────────────────────
with st.spinner("Cargando datos..."):
    ga4_r     = load_ga4_general()
    city_r    = load_ga4_city()
    cnt_r     = load_ga4_country()
    chan_r    = load_ga4_channel()
    age_r     = load_ga4_age()
    dev_r     = load_ga4_device()
    urls_r    = load_ga4_urls()
    sc_r      = load_search_console()
    prod_r    = load_produccion_con_metricas()

min_d, max_d = get_date_range(ga4_r, "date")

# ── FILTROS ───────────────────────────────────────────────────────────────────
sh("⚙️ Filtros")
st.markdown('<div class="filter-box">', unsafe_allow_html=True)
c1,c2,c3,c4,c5,c6 = st.columns(6)
with c1: start = st.date_input("📅 Desde", max_d-timedelta(days=90), min_value=min_d, max_value=max_d, key="gs")
with c2: end   = st.date_input("📅 Hasta", max_d, min_value=min_d, max_value=max_d, key="ge")

auth_list = ["Todos"] + (sorted(prod_r["post_author_name"].dropna().unique().tolist()) if not prod_r.empty and "post_author_name" in prod_r.columns else [])
with c3: sel_aut = st.selectbox("✍️ Autor", auth_list, key="ga")

city_list = ["Todas"]
if not city_r.empty and "city" in city_r.columns:
    city_list += [x for x in city_r[city_r["city"]!="(not set)"].groupby("city")["activeUsers"].sum().sort_values(ascending=False).head(50).index if x]
with c4: sel_city = st.selectbox("🏙️ Ciudad", city_list, key="gc")

cat_list = ["Todas"]
if not prod_r.empty and "categories" in prod_r.columns:
    cat_list += (prod_r["categories"].fillna("").apply(lambda x:[p.strip() for p in str(x).split(",") if p.strip()]).explode().value_counts().head(40).index.tolist())
with c5: sel_cat = st.selectbox("📂 Sección", cat_list, key="gcat")

chan_list = ["Todos"] + (sorted(chan_r["sessionDefaultChannelGroup"].dropna().unique().tolist()) if not chan_r.empty and "sessionDefaultChannelGroup" in chan_r.columns else [])
with c6: sel_chan = st.selectbox("📡 Canal", chan_list, key="gch")
st.markdown('</div>', unsafe_allow_html=True)

# ── Aplicar filtros ───────────────────────────────────────────────────────────
ga4  = filter_by_date(ga4_r,  "date", start, end)
city = filter_by_date(city_r, "date", start, end)
cnt  = filter_by_date(cnt_r,  "date", start, end)
chan = filter_by_date(chan_r,  "date", start, end)
age  = filter_by_date(age_r,  "date", start, end)
dev  = filter_by_date(dev_r,  "date", start, end)
urls = filter_by_date(urls_r, "date", start, end)
sc   = {k: filter_by_date(v,"date",start,end) for k,v in sc_r.items()}

if sel_city  != "Todas" and not city.empty and "city" in city.columns:
    city = city[city["city"]==sel_city]
if sel_chan  != "Todos" and not chan.empty and "sessionDefaultChannelGroup" in chan.columns:
    chan = chan[chan["sessionDefaultChannelGroup"]==sel_chan]

prod = filter_by_date(prod_r, "post_date", start, end)
if sel_aut  != "Todos"  and "post_author_name" in prod.columns:
    prod = prod[prod["post_author_name"]==sel_aut]
if sel_cat  != "Todas"  and "categories" in prod.columns:
    prod = prod[prod["categories"].fillna("").apply(lambda x: sel_cat in [p.strip() for p in str(x).split(",")])]

# Si hay filtro de categoría, filtrar ga4_urls a esas URLs
if sel_cat != "Todas" and not prod.empty and "url" in prod.columns and not urls.empty and "pagePath" in urls.columns:
    from urllib.parse import urlparse as _up
    valid = set(prod["url"].dropna().apply(lambda u: _up(str(u)).path.rstrip("/")))
    urls = urls[urls["pagePath"].apply(lambda p: str(p).rstrip("/")).isin(valid)]

# Período previo
pd_ = max((end-start).days,1)
ga4_p  = filter_by_date(ga4_r,       "date", start-timedelta(days=pd_), start-timedelta(days=1))
scd_p  = filter_by_date(sc_r["daily"],"date", start-timedelta(days=pd_), start-timedelta(days=1))

# ── MÉTRICAS ──────────────────────────────────────────────────────────────────
sh("📊 Métricas del Período")
m1,m2,m3,m4,m5,m6,m7 = st.columns(7)
au = int(safe_sum(ga4,"activeUsers")); au_p = int(safe_sum(ga4_p,"activeUsers"))
vw = int(safe_sum(ga4,"screenPageViews")); vw_p = int(safe_sum(ga4_p,"screenPageViews"))
ss = int(safe_sum(ga4,"sessions")); ss_p = int(safe_sum(ga4_p,"sessions"))
dur = float(ga4["userEngagementDuration"].mean()) if not ga4.empty and "userEngagementDuration" in ga4.columns else 0
sc_cl = int(safe_sum(sc["daily"],"clicks")); sc_cl_p = int(safe_sum(scd_p,"clicks"))
sc_im = int(safe_sum(sc["daily"],"impressions")); sc_im_p = int(safe_sum(scd_p,"impressions"))
u_ct  = urls["pagePath"].nunique() if not urls.empty and "pagePath" in urls.columns else 0

m1.metric("👤 Usuarios",        fmt_number(au),   _delta_str(au,au_p))
m2.metric("📄 Vistas",          fmt_number(vw),   _delta_str(vw,vw_p))
m3.metric("🔄 Sesiones",        fmt_number(ss),   _delta_str(ss,ss_p))
m4.metric("⏱ Tiempo Prom.",     f"{dur/60:.1f}m" if dur else "—")
m5.metric("🔍 Clicks GSC",      fmt_number(sc_cl),_delta_str(sc_cl,sc_cl_p))
m6.metric("👁 Impres. GSC",     fmt_number(sc_im),_delta_str(sc_im,sc_im_p))
m7.metric("🔗 URLs c/Tráfico",  fmt_number(u_ct))

# META Q1
sh("🎯 Meta Q1 — 750,000 Usuarios")
ga4_q = filter_by_date(ga4_r,"date",date(end.year,1,1),date(end.year,3,31))
q1u   = int(safe_sum(ga4_q,"activeUsers")); pct = min(q1u/750_000,1.0)
qa,qb,qc = st.columns([4,1,1])
with qa: st.progress(pct, text=f"**{fmt_number(q1u)}** / **750K** — {pct*100:.1f}%")
with qb: st.metric("Alcanzado",fmt_number(q1u))
with qc:
    left = max(750_000-q1u,0)
    st.metric("Faltan",fmt_number(left),delta="✅ Meta!" if left==0 else f"-{fmt_number(left)}",delta_color="normal" if left==0 else "inverse")

# Match stats (expandible)
with st.expander("🔬 Diagnóstico de matching Producción↔GA4", expanded=False):
    stats = match_stats(prod_r)
    if stats:
        total = sum(stats.values())
        matched = total - stats.get("sin_match",0)
        st.markdown(f"**{matched:,} de {total:,} notas** conectadas con GA4 ({matched/total*100:.1f}%)")
        for method, cnt_m in sorted(stats.items(), key=lambda x:-x[1]):
            pct_m = cnt_m/total*100
            st.markdown(f"- `{method}`: **{cnt_m:,}** ({pct_m:.1f}%)")
    else:
        st.info("Sin datos de matching.")

# ── G1: Usuarios vs Vistas ────────────────────────────────────────────────────
st.markdown("---")
sh("📈 Evolución Mensual")
if not ga4.empty and "date" in ga4.columns:
    tmp = ga4.copy(); tmp["mes"]=tmp["date"].dt.to_period("M").astype(str)
    mo = tmp.groupby("mes",as_index=False).agg(U=("activeUsers","sum"),V=("screenPageViews","sum"))
    fig1=go.Figure()
    fig1.add_trace(go.Bar(x=mo["mes"],y=mo["V"],name="Vistas",marker_color="#06b6d4",opacity=0.4,yaxis="y2"))
    fig1.add_trace(go.Scatter(x=mo["mes"],y=mo["U"],name="Usuarios",mode="lines+markers",
        line=dict(color="#6366f1",width=3),marker=dict(size=7,color="#6366f1",line=dict(color="#fff",width=1.5))))
    fig1.update_layout(yaxis2=dict(overlaying="y",side="right",showgrid=False,tickfont=dict(color="#06b6d4")),
        barmode="overlay",legend=dict(orientation="h",y=1.12))
    _fig(fig1,340); st.plotly_chart(fig1,use_container_width=True)
else:
    st.info("Sin datos GA4 en el período.")

# ── G2: Producción ────────────────────────────────────────────────────────────
sh("✍️ Producción de URLs por Mes")
if not prod.empty and "post_date" in prod.columns:
    tp=prod.copy(); tp["mes"]=tp["post_date"].dt.to_period("M").astype(str)
    pm=tp.groupby("mes",as_index=False).agg(pub=("post_id","count"),con=("ga4_views",lambda x:(x>0).sum()))
    pm["sin"]=pm["pub"]-pm["con"]
    fig2=go.Figure()
    fig2.add_trace(go.Bar(x=pm["mes"],y=pm["con"],name="Con tráfico GA4",marker_color="#10b981"))
    fig2.add_trace(go.Bar(x=pm["mes"],y=pm["sin"],name="Sin match GA4",marker_color="#1e1e40"))
    fig2.update_layout(barmode="stack",legend=dict(orientation="h",y=1.12))
    _fig(fig2,300); st.plotly_chart(fig2,use_container_width=True)
else: st.info("Sin datos de producción.")

# ── G3: Canales ───────────────────────────────────────────────────────────────
sh("📡 Canales de Tráfico")
if not chan.empty and "sessionDefaultChannelGroup" in chan.columns:
    ca=chan.groupby("sessionDefaultChannelGroup",as_index=False).agg(U=("activeUsers","sum"),V=("screenPageViews","sum"),S=("sessions","sum")).sort_values("U",ascending=False)
    cc1,cc2=st.columns([1,2])
    with cc1:
        f3=px.pie(ca,names="sessionDefaultChannelGroup",values="U",color_discrete_sequence=C,hole=0.52)
        f3.update_traces(textposition="inside",textinfo="percent+label",textfont_size=11); f3.update_layout(showlegend=False)
        _fig(f3,300); st.plotly_chart(f3,use_container_width=True)
    with cc2:
        st.dataframe(ca.rename(columns={"sessionDefaultChannelGroup":"Canal","U":"Usuarios","V":"Vistas","S":"Sesiones"})
            .style.format({"Usuarios":"{:,.0f}","Vistas":"{:,.0f}","Sesiones":"{:,.0f}"}),use_container_width=True,hide_index=True,height=280)
else: st.info("Sin datos de canales.")

# ── G4: Ciudades ──────────────────────────────────────────────────────────────
sh("🏙️ Tráfico por Ciudad — Top 20")
if not city.empty and "city" in city.columns:
    cv=city[city["city"]!="(not set)"].groupby("city",as_index=False).agg(U=("activeUsers","sum")).sort_values("U",ascending=False).head(20)
    f4=px.bar(cv,x="U",y="city",orientation="h",color="U",color_continuous_scale=["#14143a","#6366f1","#06b6d4"],text="U")
    f4.update_traces(texttemplate="%{text:,.0f}",textposition="outside",textfont_size=10)
    f4.update_layout(yaxis=dict(autorange="reversed"),coloraxis_showscale=False,yaxis_title="",xaxis_title="Usuarios Activos")
    _fig(f4,max(380,len(cv)*26+60)); st.plotly_chart(f4,use_container_width=True)
else: st.info("Sin datos de ciudades.")

# ── G5: Países ────────────────────────────────────────────────────────────────
sh("🌎 Tráfico por País")
if not cnt.empty and "country" in cnt.columns:
    cv2=cnt[cnt["country"]!="(not set)"].groupby("country",as_index=False).agg(U=("activeUsers","sum")).sort_values("U",ascending=False)
    pc1,pc2=st.columns([3,1])
    with pc1:
        f5=px.choropleth(cv2,locations="country",locationmode="country names",color="U",color_continuous_scale=["#0a0a20","#6366f1","#06b6d4","#10b981"])
        f5.update_layout(geo=dict(bgcolor=PBG,showframe=False,landcolor="#10102a",showocean=True,oceancolor=BG,showcoastlines=True,coastlinecolor="#1a1a3a"))
        _fig(f5,360); st.plotly_chart(f5,use_container_width=True)
    with pc2:
        st.dataframe(cv2.head(25).rename(columns={"country":"País","U":"Usuarios"}).style.format({"Usuarios":"{:,.0f}"}),use_container_width=True,hide_index=True,height=340)
else: st.info("Sin datos de países.")

# ── G6: URLs + Autores ────────────────────────────────────────────────────────
sh("📰 URLs y Autores Más Leídos")
n1,n2=st.columns(2)
with n1:
    st.markdown("**🔝 URLs más leídas**")
    if not urls.empty and "pagePath" in urls.columns:
        grp=["pagePath"]+( ["pageTitle"] if "pageTitle" in urls.columns else [])
        ua=urls.groupby(grp,as_index=False).agg(Vistas=("screenPageViews","sum"),Usuarios=("activeUsers","sum")).sort_values("Vistas",ascending=False).head(30)
        if not prod_r.empty and "url" in prod_r.columns and "post_author_name" in prod_r.columns:
            from urllib.parse import urlparse as _up
            p2a={_up(str(u)).path.rstrip("/"): a for u,a in zip(prod_r["url"],prod_r["post_author_name"]) if pd.notna(u)}
            ua["Autor"]=ua["pagePath"].apply(lambda p: p2a.get(str(p).rstrip("/"),"—"))
        disp=[c for c in ["pageTitle","Autor","Vistas","Usuarios"] if c in ua.columns]
        st.dataframe(ua[disp].style.format({"Vistas":"{:,.0f}","Usuarios":"{:,.0f}"}),use_container_width=True,hide_index=True,height=400)
    else: st.info("Sin datos de URLs.")
with n2:
    st.markdown("**✍️ Autores más leídos**")
    if not prod.empty and "post_author_name" in prod.columns and "ga4_views" in prod.columns:
        aa=prod.groupby("post_author_name",as_index=False).agg(Vistas=("ga4_views","sum"),Notas=("post_id","count"),Usuarios=("ga4_users","sum")).sort_values("Vistas",ascending=False).head(25)
        aa["V/Nota"]=(aa["Vistas"]/aa["Notas"].clip(1)).round(0).astype(int)
        st.dataframe(aa.rename(columns={"post_author_name":"Autor"}).style.format({"Vistas":"{:,.0f}","Notas":"{:,.0f}","Usuarios":"{:,.0f}","V/Nota":"{:,.0f}"}),use_container_width=True,hide_index=True,height=400)
    else: st.info("Sin datos de autores.")

# ── G7: Secciones ─────────────────────────────────────────────────────────────
sh("📂 Secciones")
if not prod.empty and "categories" in prod.columns and "ga4_views" in prod.columns:
    sp=prod.copy(); sp["cat"]=sp["categories"].fillna("Sin cat").apply(lambda x:str(x).split(",")[0].strip())
    sa=sp.groupby("cat",as_index=False).agg(U=("ga4_users","sum"),V=("ga4_views","sum"),N=("post_id","count")).sort_values("V",ascending=False).head(20)
    sc1_,sc2_=st.columns([1,2])
    with sc1_:
        f7=px.pie(sa.head(10),names="cat",values="U",color_discrete_sequence=C,hole=0.48)
        f7.update_traces(textposition="inside",textinfo="percent+label",textfont_size=10); f7.update_layout(showlegend=False)
        _fig(f7,300); st.plotly_chart(f7,use_container_width=True)
    with sc2_:
        st.dataframe(sa.rename(columns={"cat":"Sección","U":"Usuarios","V":"Vistas","N":"Notas"}).style.format({"Usuarios":"{:,.0f}","Vistas":"{:,.0f}","Notas":"{:,.0f}"}),use_container_width=True,hide_index=True,height=320)
else: st.info("Sin datos de secciones.")

# ── G8: Notas IA ──────────────────────────────────────────────────────────────
sh("🤖 Notas IA Más Leídas")
if not prod.empty and "is_ia" in prod.columns:
    ia=prod[prod["is_ia"]].sort_values("ga4_views",ascending=False).head(25)
    if not ia.empty:
        cols_=[c for c in ["post_title","post_author_name","post_date","ga4_views","ga4_users","match_method"] if c in ia.columns]
        st.dataframe(ia[cols_].rename(columns={"post_title":"Título","post_author_name":"Autor","post_date":"Fecha","ga4_views":"Vistas","ga4_users":"Usuarios","match_method":"Match"}).style.format({"Vistas":"{:,.0f}","Usuarios":"{:,.0f}"}),use_container_width=True,hide_index=True)
    else: st.info("No hay notas IA en el período.")

# ── G9: Audiencia ─────────────────────────────────────────────────────────────
sh("👥 Audiencia")
t1,t2,t3=st.tabs(["📅 Edad","📱 Dispositivo","🎯 Intereses"])
with t1:
    if not age.empty and "userAgeBracket" in age.columns:
        a2=age.groupby("userAgeBracket",as_index=False).agg(U=("activeUsers","sum")).sort_values("userAgeBracket")
        fa=px.bar(a2,x="userAgeBracket",y="U",color="U",color_continuous_scale=["#14143a","#6366f1"],text="U")
        fa.update_traces(texttemplate="%{text:,.0f}",textposition="outside",textfont_size=10); fa.update_layout(coloraxis_showscale=False,xaxis_title="Edad")
        _fig(fa,280); st.plotly_chart(fa,use_container_width=True)
        st.dataframe(a2.rename(columns={"userAgeBracket":"Rango","U":"Usuarios"}).style.format({"Usuarios":"{:,.0f}"}),use_container_width=True,hide_index=True)
    else: st.info("Sin datos de edad.")
with t2:
    if not dev.empty and "deviceCategory" in dev.columns:
        da=dev.groupby("deviceCategory",as_index=False).agg(U=("activeUsers","sum"),V=("screenPageViews","sum"))
        d1,d2=st.columns(2)
        with d1:
            fd=px.pie(da,names="deviceCategory",values="U",color_discrete_sequence=C,hole=0.52)
            fd.update_traces(textposition="inside",textinfo="percent+label",textfont_size=13); fd.update_layout(showlegend=False)
            _fig(fd,280); st.plotly_chart(fd,use_container_width=True)
        with d2:
            fdv=px.bar(da,x="deviceCategory",y="V",color="deviceCategory",color_discrete_sequence=C,text="V")
            fdv.update_traces(texttemplate="%{text:,.0f}",textposition="outside"); fdv.update_layout(showlegend=False,xaxis_title="")
            _fig(fdv,280); st.plotly_chart(fdv,use_container_width=True)
        st.dataframe(da.rename(columns={"deviceCategory":"Dispositivo","U":"Usuarios","V":"Vistas"}).style.format({"Usuarios":"{:,.0f}","Vistas":"{:,.0f}"}),use_container_width=True,hide_index=True)
    else: st.info("Sin datos de dispositivos.")
with t3:
    intr=load_ga4_interests()
    if not intr.empty and "brandingInterest" in intr.columns:
        ia2=intr.groupby("brandingInterest",as_index=False).agg(U=("activeUsers","sum")).sort_values("U",ascending=False).head(25)
        fi=px.bar(ia2,x="U",y="brandingInterest",orientation="h",color="U",color_continuous_scale=["#14143a","#8b5cf6"])
        fi.update_layout(yaxis=dict(autorange="reversed"),coloraxis_showscale=False,yaxis_title=""); _fig(fi,520); st.plotly_chart(fi,use_container_width=True)
    else: st.info("Sin datos de intereses.")
