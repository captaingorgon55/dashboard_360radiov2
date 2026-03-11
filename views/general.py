import sys, os
sys.path.insert(0, os.getcwd())
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta
from data_loader import (
    load_ga4_general, load_ga4_city, load_ga4_country, load_ga4_channel,
    load_ga4_age, load_ga4_device, load_ga4_interests,
    load_search_console, load_produccion_con_metricas, load_ga4_urls_daily,
    filter_by_date, fmt_number, safe_sum, get_date_range, _delta_str
)
C = ["#6366f1","#06b6d4","#10b981","#f59e0b","#ef4444","#8b5cf6","#ec4899","#14b8a6"]
PBG = "#0d0d1e"

def _fig(fig, h=340):
    fig.update_layout(height=h, paper_bgcolor=PBG, plot_bgcolor=PBG,
        font=dict(family="Inter", color="#9aa3c2", size=12),
        margin=dict(l=8,r=8,t=38,b=8),
        legend=dict(bgcolor="rgba(0,0,0,0)", font_size=11),
        xaxis=dict(gridcolor="#181828", zerolinecolor="#181828"),
        yaxis=dict(gridcolor="#181828", zerolinecolor="#181828"),
        title_font=dict(family="Syne", size=14, color="#c8cedc"))
    return fig

def sh(txt): st.markdown(f'<div class="sec-hdr">{txt}</div>', unsafe_allow_html=True)

st.markdown('<div class="page-title">🏠 General · Tráfico y Producción</div>', unsafe_allow_html=True)
st.markdown('<div class="page-subtitle">GA4 · Search Console · Producción editorial</div>', unsafe_allow_html=True)

with st.spinner("Cargando datos..."):
    ga4_raw      = load_ga4_general()
    ga4_city_raw = load_ga4_city()
    ga4_cnt_raw  = load_ga4_country()
    ga4_chan_raw  = load_ga4_channel()
    ga4_age_raw  = load_ga4_age()
    ga4_dev_raw  = load_ga4_device()
    ga4_urls_raw = load_ga4_urls_daily()
    sc_raw       = load_search_console()
    prod_raw     = load_produccion_con_metricas()

min_d, max_d = get_date_range(ga4_raw, "date")

sh("⚙️ Filtros")
st.markdown('<div class="filter-box">', unsafe_allow_html=True)
fc1,fc2,fc3,fc4,fc5,fc6 = st.columns(6)
with fc1:
    start_date = st.date_input("📅 Desde", value=max_d-timedelta(days=90),
                                min_value=min_d, max_value=max_d, key="gen_start")
with fc2:
    end_date = st.date_input("📅 Hasta", value=max_d,
                              min_value=min_d, max_value=max_d, key="gen_end")
auth_opts = ["Todos"] + (sorted(prod_raw["post_author_name"].dropna().unique().tolist())
    if not prod_raw.empty and "post_author_name" in prod_raw.columns else [])
with fc3:
    sel_author = st.selectbox("✍️ Autor", auth_opts, key="gen_author")
city_opts = ["Todas"]
if not ga4_city_raw.empty and "city" in ga4_city_raw.columns:
    city_opts += [c for c in (ga4_city_raw[ga4_city_raw["city"]!="(not set)"]
        .groupby("city")["activeUsers"].sum().sort_values(ascending=False).head(50).index.tolist())]
with fc4:
    sel_city = st.selectbox("🏙️ Ciudad", city_opts, key="gen_city")
cat_opts = ["Todas"]
if not prod_raw.empty and "categories" in prod_raw.columns:
    cat_opts += (prod_raw["categories"].fillna("").apply(lambda x: [p.strip() for p in str(x).split(",") if p.strip()])
        .explode().value_counts().head(40).index.tolist())
with fc5:
    sel_cat = st.selectbox("📂 Sección", cat_opts, key="gen_cat")
chan_opts = ["Todos"] + (sorted(ga4_chan_raw["sessionDefaultChannelGroup"].dropna().unique().tolist())
    if not ga4_chan_raw.empty and "sessionDefaultChannelGroup" in ga4_chan_raw.columns else [])
with fc6:
    sel_chan = st.selectbox("📡 Canal", chan_opts, key="gen_chan")
st.markdown('</div>', unsafe_allow_html=True)

# Aplicar filtros de fecha
ga4      = filter_by_date(ga4_raw,      "date", start_date, end_date)
ga4_city = filter_by_date(ga4_city_raw, "date", start_date, end_date)
ga4_cnt  = filter_by_date(ga4_cnt_raw,  "date", start_date, end_date)
ga4_chan  = filter_by_date(ga4_chan_raw, "date", start_date, end_date)
ga4_age  = filter_by_date(ga4_age_raw,  "date", start_date, end_date)
ga4_dev  = filter_by_date(ga4_dev_raw,  "date", start_date, end_date)
ga4_urls = filter_by_date(ga4_urls_raw, "date", start_date, end_date)
sc       = {k: filter_by_date(v,"date",start_date,end_date) for k,v in sc_raw.items()}

# Filtros adicionales
if sel_city != "Todas" and not ga4_city.empty and "city" in ga4_city.columns:
    ga4_city = ga4_city[ga4_city["city"]==sel_city]
if sel_chan != "Todos" and not ga4_chan.empty and "sessionDefaultChannelGroup" in ga4_chan.columns:
    ga4_chan = ga4_chan[ga4_chan["sessionDefaultChannelGroup"]==sel_chan]

prod = filter_by_date(prod_raw, "post_date", start_date, end_date)
if sel_author != "Todos" and "post_author_name" in prod.columns:
    prod = prod[prod["post_author_name"]==sel_author]
if sel_cat != "Todas" and "categories" in prod.columns:
    prod = prod[prod["categories"].fillna("").apply(
        lambda x: sel_cat in [p.strip() for p in str(x).split(",")])]
if sel_cat != "Todas" and not prod.empty and "url" in prod.columns and not ga4_urls.empty and "pagePath" in ga4_urls.columns:
    from urllib.parse import urlparse as _up
    valid = set(prod["url"].dropna().apply(lambda u: _up(str(u)).path.rstrip("/")))
    ga4_urls = ga4_urls[ga4_urls["pagePath"].apply(lambda p: str(p).rstrip("/")).isin(valid)]

# Período previo
period_days = max((end_date - start_date).days, 1)
ga4_prev  = filter_by_date(ga4_raw,        "date", start_date-timedelta(days=period_days), start_date-timedelta(days=1))
sc_prev_d = filter_by_date(sc_raw["daily"],"date", start_date-timedelta(days=period_days), start_date-timedelta(days=1))

# MÉTRICAS
sh("📊 Métricas Generales")
m1,m2,m3,m4,m5,m6,m7 = st.columns(7)
active_u = int(safe_sum(ga4,"activeUsers"))
views    = int(safe_sum(ga4,"screenPageViews"))
sessions = int(safe_sum(ga4,"sessions"))
avg_dur  = float(ga4["userEngagementDuration"].mean()) if not ga4.empty and "userEngagementDuration" in ga4.columns else 0
sc_cl    = int(safe_sum(sc["daily"],"clicks"))
sc_im    = int(safe_sum(sc["daily"],"impressions"))
urls_ct  = ga4_urls["pagePath"].nunique() if not ga4_urls.empty and "pagePath" in ga4_urls.columns else 0
p_u=int(safe_sum(ga4_prev,"activeUsers")); p_v=int(safe_sum(ga4_prev,"screenPageViews"))
p_s=int(safe_sum(ga4_prev,"sessions"));   p_sc=int(safe_sum(sc_prev_d,"clicks"))
p_si=int(safe_sum(sc_prev_d,"impressions"))
m1.metric("👤 Usuarios Activos",fmt_number(active_u),_delta_str(active_u,p_u))
m2.metric("📄 Vistas",          fmt_number(views),   _delta_str(views,p_v))
m3.metric("🔄 Sesiones",        fmt_number(sessions),_delta_str(sessions,p_s))
m4.metric("⏱ Tiempo Promedio",  f"{avg_dur/60:.1f} min" if avg_dur else "—")
m5.metric("🔍 Clicks GSC",      fmt_number(sc_cl),   _delta_str(sc_cl,p_sc))
m6.metric("👁 Impresiones GSC", fmt_number(sc_im),   _delta_str(sc_im,p_si))
m7.metric("🔗 URLs con Tráfico",fmt_number(urls_ct))

# META Q1
META_Q1 = 750_000
sh("🎯 Meta Q1 · 750,000 Usuarios Activos")
ga4_q1   = filter_by_date(ga4_raw,"date",date(end_date.year,1,1),date(end_date.year,3,31))
q1_users = int(safe_sum(ga4_q1,"activeUsers"))
pct_meta = min(q1_users/META_Q1,1.0)
mc1,mc2,mc3 = st.columns([4,1,1])
with mc1:
    st.progress(pct_meta, text=f"**{fmt_number(q1_users)}** de **{fmt_number(META_Q1)}** · {pct_meta*100:.1f}%")
with mc2: st.metric("Alcanzado",fmt_number(q1_users))
with mc3:
    left=max(META_Q1-q1_users,0)
    st.metric("Faltan",fmt_number(left),delta="✅ Meta!" if left==0 else f"-{fmt_number(left)}",
              delta_color="normal" if left==0 else "inverse")

# GRÁFICO 1
st.markdown("---")
sh("📈 Usuarios Activos vs Vistas por Mes")
if not ga4.empty and "date" in ga4.columns:
    tmp=ga4.copy(); tmp["mes"]=tmp["date"].dt.to_period("M").astype(str)
    mo=tmp.groupby("mes",as_index=False).agg(activeUsers=("activeUsers","sum"),screenPageViews=("screenPageViews","sum"))
    fig1=go.Figure()
    fig1.add_trace(go.Bar(x=mo["mes"],y=mo["screenPageViews"],name="Vistas",marker_color="#06b6d4",opacity=0.4,yaxis="y2"))
    fig1.add_trace(go.Scatter(x=mo["mes"],y=mo["activeUsers"],name="Usuarios Activos",mode="lines+markers",
        line=dict(color="#6366f1",width=3),marker=dict(size=7,color="#6366f1",line=dict(color="#fff",width=1.5))))
    fig1.update_layout(yaxis2=dict(overlaying="y",side="right",showgrid=False,tickfont=dict(color="#06b6d4"),title="Vistas"),
        yaxis=dict(title="Usuarios"),barmode="overlay",legend=dict(orientation="h",y=1.12))
    _fig(fig1,360); st.plotly_chart(fig1,use_container_width=True)
else:
    st.info("Sin datos GA4 en el período.")

# GRÁFICO 2
sh("✍️ Evolución de Producción de URLs")
if not prod.empty and "post_date" in prod.columns:
    tmp_p=prod.copy(); tmp_p["mes"]=tmp_p["post_date"].dt.to_period("M").astype(str)
    pm=tmp_p.groupby("mes",as_index=False).agg(publicaciones=("post_id","count"),con_trafico=("ga4_views",lambda x:(x>0).sum()))
    pm["sin_trafico"]=pm["publicaciones"]-pm["con_trafico"]
    fig2=go.Figure()
    fig2.add_trace(go.Bar(x=pm["mes"],y=pm["con_trafico"],name="Con tráfico",marker_color="#10b981"))
    fig2.add_trace(go.Bar(x=pm["mes"],y=pm["sin_trafico"],name="Sin tráfico",marker_color="#252550"))
    fig2.update_layout(barmode="stack",legend=dict(orientation="h",y=1.12))
    _fig(fig2,300); st.plotly_chart(fig2,use_container_width=True)
else:
    st.info("Sin datos de producción.")

# GRÁFICO 3
sh("📡 Canales de Tráfico")
if not ga4_chan.empty and "sessionDefaultChannelGroup" in ga4_chan.columns:
    ca=ga4_chan.groupby("sessionDefaultChannelGroup",as_index=False).agg(
        Usuarios=("activeUsers","sum"),Vistas=("screenPageViews","sum"),Sesiones=("sessions","sum")
    ).sort_values("Usuarios",ascending=False)
    cc1,cc2=st.columns([1,2])
    with cc1:
        fig3=px.pie(ca,names="sessionDefaultChannelGroup",values="Usuarios",color_discrete_sequence=C,hole=0.5)
        fig3.update_traces(textposition="inside",textinfo="percent+label",textfont_size=11)
        fig3.update_layout(showlegend=False); _fig(fig3,300); st.plotly_chart(fig3,use_container_width=True)
    with cc2:
        st.dataframe(ca.rename(columns={"sessionDefaultChannelGroup":"Canal"})
            .style.format({"Usuarios":"{:,.0f}","Vistas":"{:,.0f}","Sesiones":"{:,.0f}"}),
            use_container_width=True,hide_index=True,height=280)
else:
    st.info("Sin datos de canales.")

# GRÁFICO 4
sh("🏙️ Tráfico por Ciudad · Top 20")
if not ga4_city.empty and "city" in ga4_city.columns:
    ca2=(ga4_city[ga4_city["city"]!="(not set)"].groupby("city",as_index=False)
        .agg(Usuarios=("activeUsers","sum")).sort_values("Usuarios",ascending=False).head(20))
    fig4=px.bar(ca2,x="Usuarios",y="city",orientation="h",color="Usuarios",
        color_continuous_scale=["#1a1a3e","#6366f1","#06b6d4"],text="Usuarios")
    fig4.update_traces(texttemplate="%{text:,.0f}",textposition="outside",textfont_size=10)
    fig4.update_layout(yaxis=dict(autorange="reversed"),coloraxis_showscale=False,yaxis_title="")
    _fig(fig4,max(400,len(ca2)*28+60)); st.plotly_chart(fig4,use_container_width=True)
else:
    st.info("Sin datos de ciudades.")

# GRÁFICO 5
sh("🌎 Tráfico por País")
if not ga4_cnt.empty and "country" in ga4_cnt.columns:
    ca3=(ga4_cnt[ga4_cnt["country"]!="(not set)"].groupby("country",as_index=False)
        .agg(Usuarios=("activeUsers","sum")).sort_values("Usuarios",ascending=False))
    pc1,pc2=st.columns([3,1])
    with pc1:
        fig5=px.choropleth(ca3,locations="country",locationmode="country names",color="Usuarios",
            color_continuous_scale=["#0d0d24","#6366f1","#06b6d4","#10b981"])
        fig5.update_layout(geo=dict(bgcolor=PBG,showframe=False,landcolor="#12122a",
            showocean=True,oceancolor="#0a0a14",showcoastlines=True,coastlinecolor="#1e1e3a"))
        _fig(fig5,380); st.plotly_chart(fig5,use_container_width=True)
    with pc2:
        st.dataframe(ca3.head(25).rename(columns={"country":"País"})
            .style.format({"Usuarios":"{:,.0f}"}),use_container_width=True,hide_index=True,height=360)
else:
    st.info("Sin datos de países.")

# GRÁFICO 6
sh("📰 Notas y Autores Más Leídos")
nc1,nc2=st.columns(2)
with nc1:
    st.markdown("**🔝 URLs más leídas**")
    if not ga4_urls.empty and "pagePath" in ga4_urls.columns:
        grp=["pagePath"]+( ["pageTitle"] if "pageTitle" in ga4_urls.columns else [])
        ua=(ga4_urls.groupby(grp,as_index=False).agg(Vistas=("screenPageViews","sum"),Usuarios=("activeUsers","sum"))
            .sort_values("Vistas",ascending=False).head(30))
        if not prod_raw.empty and "url" in prod_raw.columns and "post_author_name" in prod_raw.columns:
            from urllib.parse import urlparse as _up
            p2a={_up(str(u)).path.rstrip("/"): a for u,a in zip(prod_raw["url"],prod_raw["post_author_name"]) if pd.notna(u)}
            ua["Autor"]=ua["pagePath"].apply(lambda p: p2a.get(str(p).rstrip("/"),"—"))
        disp=[c for c in ["pageTitle","Autor","Vistas","Usuarios"] if c in ua.columns]
        st.dataframe(ua[disp].style.format({"Vistas":"{:,.0f}","Usuarios":"{:,.0f}"}),
            use_container_width=True,hide_index=True,height=400)
    else:
        st.info("Sin datos de URLs.")
with nc2:
    st.markdown("**✍️ Autores más leídos**")
    if not prod.empty and "post_author_name" in prod.columns and "ga4_views" in prod.columns:
        aa=(prod.groupby("post_author_name",as_index=False)
            .agg(Vistas=("ga4_views","sum"),Notas=("post_id","count"),Usuarios=("ga4_users","sum"))
            .sort_values("Vistas",ascending=False).head(25))
        aa["Vistas/Nota"]=(aa["Vistas"]/aa["Notas"].clip(1)).round(0).astype(int)
        st.dataframe(aa.rename(columns={"post_author_name":"Autor"})
            .style.format({"Vistas":"{:,.0f}","Notas":"{:,.0f}","Usuarios":"{:,.0f}","Vistas/Nota":"{:,.0f}"}),
            use_container_width=True,hide_index=True,height=400)
    else:
        st.info("Sin datos de autores.")

# GRÁFICO 7
sh("📂 Secciones")
if not prod.empty and "categories" in prod.columns and "ga4_views" in prod.columns:
    st_=prod.copy()
    st_["cat"]=st_["categories"].fillna("Sin cat").apply(lambda x: str(x).split(",")[0].strip())
    sa=(st_.groupby("cat",as_index=False).agg(Usuarios=("ga4_users","sum"),Vistas=("ga4_views","sum"),Notas=("post_id","count"))
        .sort_values("Vistas",ascending=False).head(20))
    sc1,sc2=st.columns([1,2])
    with sc1:
        fig7=px.pie(sa.head(10),names="cat",values="Usuarios",color_discrete_sequence=C,hole=0.45)
        fig7.update_traces(textposition="inside",textinfo="percent+label",textfont_size=10)
        fig7.update_layout(showlegend=False); _fig(fig7,320); st.plotly_chart(fig7,use_container_width=True)
    with sc2:
        st.dataframe(sa.rename(columns={"cat":"Sección"})
            .style.format({"Usuarios":"{:,.0f}","Vistas":"{:,.0f}","Notas":"{:,.0f}"}),
            use_container_width=True,hide_index=True,height=340)
else:
    st.info("Sin datos de secciones.")

# GRÁFICO 8
sh("🤖 Notas IA Más Leídas")
if not prod.empty and "is_ia" in prod.columns:
    ia=(prod[prod["is_ia"]].sort_values("ga4_views",ascending=False).head(25))
    if not ia.empty:
        show=[c for c in ["post_title","post_author_name","post_date","categories","ga4_views","ga4_users","match_method"] if c in ia.columns]
        st.dataframe(ia[show].rename(columns={"post_title":"Título","post_author_name":"Autor","post_date":"Fecha",
            "categories":"Categorías","ga4_views":"Vistas","ga4_users":"Usuarios","match_method":"Match"})
            .style.format({"Vistas":"{:,.0f}","Usuarios":"{:,.0f}"}),use_container_width=True,hide_index=True)
    else:
        st.info("No hay notas IA en el período.")

# GRÁFICO 9
sh("👥 Audiencia · Edad · Dispositivo · Intereses")
t1,t2,t3=st.tabs(["📅 Edad","📱 Dispositivo","🎯 Intereses"])
with t1:
    if not ga4_age.empty and "userAgeBracket" in ga4_age.columns:
        aa2=(ga4_age.groupby("userAgeBracket",as_index=False).agg(Usuarios=("activeUsers","sum"),Sesiones=("sessions","sum")).sort_values("userAgeBracket"))
        fig_a=px.bar(aa2,x="userAgeBracket",y="Usuarios",color="Usuarios",color_continuous_scale=["#1a1a3e","#6366f1"],text="Usuarios")
        fig_a.update_traces(texttemplate="%{text:,.0f}",textposition="outside",textfont_size=10)
        fig_a.update_layout(coloraxis_showscale=False,xaxis_title="Rango de Edad"); _fig(fig_a,300); st.plotly_chart(fig_a,use_container_width=True)
        st.dataframe(aa2.rename(columns={"userAgeBracket":"Rango"}).style.format({"Usuarios":"{:,.0f}","Sesiones":"{:,.0f}"}),use_container_width=True,hide_index=True)
    else:
        st.info("Sin datos de edad.")
with t2:
    if not ga4_dev.empty and "deviceCategory" in ga4_dev.columns:
        da=(ga4_dev.groupby("deviceCategory",as_index=False).agg(Usuarios=("activeUsers","sum"),Vistas=("screenPageViews","sum")))
        dc1,dc2=st.columns(2)
        with dc1:
            fd=px.pie(da,names="deviceCategory",values="Usuarios",color_discrete_sequence=C,hole=0.5)
            fd.update_traces(textposition="inside",textinfo="percent+label",textfont_size=13)
            fd.update_layout(showlegend=False); _fig(fd,300); st.plotly_chart(fd,use_container_width=True)
        with dc2:
            fdv=px.bar(da,x="deviceCategory",y="Vistas",color="deviceCategory",color_discrete_sequence=C,text="Vistas")
            fdv.update_traces(texttemplate="%{text:,.0f}",textposition="outside")
            fdv.update_layout(showlegend=False,xaxis_title=""); _fig(fdv,300); st.plotly_chart(fdv,use_container_width=True)
        st.dataframe(da.rename(columns={"deviceCategory":"Dispositivo"}).style.format({"Usuarios":"{:,.0f}","Vistas":"{:,.0f}"}),use_container_width=True,hide_index=True)
    else:
        st.info("Sin datos de dispositivos.")
with t3:
    interests=load_ga4_interests()
    if not interests.empty and "brandingInterest" in interests.columns:
        ia2=(interests.groupby("brandingInterest",as_index=False).agg(Usuarios=("activeUsers","sum")).sort_values("Usuarios",ascending=False).head(25))
        fig_i=px.bar(ia2,x="Usuarios",y="brandingInterest",orientation="h",color="Usuarios",color_continuous_scale=["#1a1a3e","#8b5cf6"])
        fig_i.update_layout(yaxis=dict(autorange="reversed"),coloraxis_showscale=False,yaxis_title=""); _fig(fig_i,550); st.plotly_chart(fig_i,use_container_width=True)
    else:
        st.info("Sin datos de intereses.")
