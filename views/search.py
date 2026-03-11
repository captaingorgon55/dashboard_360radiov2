import sys, os; sys.path.insert(0, os.getcwd())
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta
from data_loader import load_search_console, filter_by_date, fmt_number, safe_sum, get_date_range, pct_delta

C   = ["#6366f1","#06b6d4","#10b981","#f59e0b","#ef4444","#8b5cf6"]
PBG = "#0d0d20"

def _fig(fig, h=340):
    fig.update_layout(height=h, paper_bgcolor=PBG, plot_bgcolor=PBG,
        font=dict(family="Inter",color="#8890b8",size=11),
        margin=dict(l=6,r=6,t=36,b=6),
        legend=dict(bgcolor="rgba(0,0,0,0)",font_size=11),
        xaxis=dict(gridcolor="#14142e",zerolinecolor="#14142e"),
        yaxis=dict(gridcolor="#14142e",zerolinecolor="#14142e"),
        title_font=dict(family="Syne",size=13,color="#c0c8e8"))
    return fig

def sh(t): st.markdown(f'<div class="sec-hdr">{t}</div>', unsafe_allow_html=True)
def _delta(cur, prev):
    d = pct_delta(cur, prev)
    return f"{d:+.1f}%" if d is not None else None

st.markdown('<div class="page-title">🔍 Search Console</div>', unsafe_allow_html=True)
st.markdown('<div class="page-subtitle">Rendimiento orgánico · Queries · Páginas · Dispositivos · Países</div>', unsafe_allow_html=True)

sc = load_search_console()
# Hojas: daily(date,clicks,impressions,ctr,position) | queries(+query) | pages(+page) | country(+country) | device(+device)

min_d, max_d = get_date_range(sc["daily"], "date")

# ── FILTROS ───────────────────────────────────────────────────────────────────
sh("⚙️ Filtros")
st.markdown('<div class="filter-box">', unsafe_allow_html=True)
fc1,fc2,fc3,fc4 = st.columns(4)
with c1: start = st.date_input("📅 Desde", max_d-timedelta(days=90), min_value=min_d, max_value=max_d, key="gs")
with fc2: end   = st.date_input("📅 Hasta", max_d, min_value=min_d, max_value=max_d, key="sc_e")

dev_opts = ["Todos"]
if not sc["device"].empty and "device" in sc["device"].columns:
    dev_opts += sorted(sc["device"]["device"].dropna().unique().tolist())
with fc3: sel_dev = st.selectbox("📱 Dispositivo", dev_opts, key="sc_dev")

cnt_opts = ["Todos"]
if not sc["country"].empty and "country" in sc["country"].columns:
    cnt_opts += sc["country"].groupby("country")["clicks"].sum().sort_values(ascending=False).head(40).index.tolist()
with fc4: sel_cntry = st.selectbox("🌎 País", cnt_opts, key="sc_cnt")
st.markdown('</div>', unsafe_allow_html=True)

# ── Filtrar por fecha TODAS las hojas ─────────────────────────────────────────
sc_f = {k: filter_by_date(v,"date",start,end) for k,v in sc.items()}
pd_  = (end-start).days or 1
sc_p = {k: filter_by_date(v,"date",start-timedelta(days=pd_),start-timedelta(days=1)) for k,v in sc.items()}

# ── Filtrar por dimensión específica ──────────────────────────────────────────
has_dev = sel_dev   != "Todos" and not sc_f["device"].empty  and "device"  in sc_f["device"].columns
has_cnt = sel_cntry != "Todos" and not sc_f["country"].empty and "country" in sc_f["country"].columns

if has_dev:
    sc_f["device"] = sc_f["device"][sc_f["device"]["device"] == sel_dev]
    sc_p["device"] = sc_p["device"][sc_p["device"]["device"] == sel_dev] if not sc_p["device"].empty and "device" in sc_p["device"].columns else pd.DataFrame()

if has_cnt:
    sc_f["country"] = sc_f["country"][sc_f["country"]["country"] == sel_cntry]
    sc_p["country"] = sc_p["country"][sc_p["country"]["country"] == sel_cntry] if not sc_p["country"].empty and "country" in sc_p["country"].columns else pd.DataFrame()

# ══════════════════════════════════════════════════════════════════════════════
# FUENTE DE MÉTRICAS PRINCIPALES:
#   Sin filtros        → daily (totales globales, más preciso)
#   Solo dispositivo   → device (ya filtrado por ese device)
#   Solo país          → country (ya filtrado por ese país)
#   Ambos              → device filtrado, intersectando fechas con country
# Esto garantiza que métricas + gráfico + tabs reflejen el filtro activo
# ══════════════════════════════════════════════════════════════════════════════
if has_dev and has_cnt:
    # Intersección de fechas entre las dos hojas filtradas
    d1 = set(sc_f["device"]["date"].dt.date)  if "date" in sc_f["device"].columns  else set()
    d2 = set(sc_f["country"]["date"].dt.date) if "date" in sc_f["country"].columns else set()
    common = d1 & d2
    _src   = sc_f["device"][sc_f["device"]["date"].dt.date.isin(common)]   if common else sc_f["device"]
    _src_p = sc_p["device"][sc_p["device"]["date"].dt.date.isin(common)]   if common and not sc_p["device"].empty and "date" in sc_p["device"].columns else pd.DataFrame()
    st.caption(f"📱 **{sel_dev}** &nbsp;·&nbsp; 🌎 **{sel_cntry}**  — mostrando intersección de fechas")
elif has_dev:
    _src   = sc_f["device"]
    _src_p = sc_p["device"]
    st.caption(f"📱 Filtrando por dispositivo: **{sel_dev}**")
elif has_cnt:
    _src   = sc_f["country"]
    _src_p = sc_p["country"]
    st.caption(f"🌎 Filtrando por país: **{sel_cntry}**")
else:
    _src   = sc_f["daily"]
    _src_p = sc_p["daily"]

# ── MÉTRICAS ──────────────────────────────────────────────────────────────────
sh("📊 Métricas Generales")
m1,m2,m3,m4,m5 = st.columns(5)
clicks  = int(safe_sum(_src,"clicks"))
impr    = int(safe_sum(_src,"impressions"))
ctr     = float(_src["ctr"].mean()*100)   if not _src.empty and "ctr"      in _src.columns else 0
pos     = float(_src["position"].mean())   if not _src.empty and "position" in _src.columns else 0
n_q     = sc_f["queries"]["query"].nunique() if not sc_f["queries"].empty and "query" in sc_f["queries"].columns else 0
p_cl    = int(safe_sum(_src_p,"clicks"))
p_im    = int(safe_sum(_src_p,"impressions"))

m1.metric("🖱️ Clicks",         fmt_number(clicks), _delta(clicks,p_cl))
m2.metric("👁 Impresiones",    fmt_number(impr),   _delta(impr,p_im))
m3.metric("📈 CTR Promedio",   f"{ctr:.2f}%")
m4.metric("📍 Posición Media", f"{pos:.1f}")
m5.metric("🔑 Queries Únicas", fmt_number(n_q))

# ── GRÁFICO EVOLUCIÓN ─────────────────────────────────────────────────────────
sh("📈 Evolución Mensual · Clicks e Impresiones")
if not _src.empty and "date" in _src.columns:
    ev = _src.copy(); ev["mes"] = ev["date"].dt.to_period("M").astype(str)
    mly = ev.groupby("mes").agg(clicks=("clicks","sum"),impressions=("impressions","sum")).reset_index()
    fig1 = go.Figure()
    fig1.add_trace(go.Bar(x=mly["mes"],y=mly["impressions"],
        name="Impresiones",marker_color="#06b6d4",opacity=0.45,yaxis="y2"))
    fig1.add_trace(go.Scatter(x=mly["mes"],y=mly["clicks"],
        name="Clicks",mode="lines+markers",
        line=dict(color="#6366f1",width=3),
        marker=dict(size=7,color="#6366f1",line=dict(color="#fff",width=1.5))))
    fig1.update_layout(
        yaxis2=dict(overlaying="y",side="right",showgrid=False,tickfont=dict(color="#06b6d4"),title="Impresiones"),
        yaxis=dict(title="Clicks"),barmode="overlay",legend=dict(orientation="h",y=1.12))
    _fig(fig1,360); st.plotly_chart(fig1,use_container_width=True)
else:
    st.info("Sin datos para el período y filtros seleccionados.")

# ── TABS ──────────────────────────────────────────────────────────────────────
# Las fechas válidas según filtro activo (para cruzar con queries/páginas)
_valid_dates = set(_src["date"].dt.date) if not _src.empty and "date" in _src.columns else set()

t1,t2,t3,t4 = st.tabs(["🔑 Queries","📄 Páginas","🌎 Países","📱 Dispositivos"])

with t1:
    sh("🔑 Queries más clickeadas")
    df_q = sc_f["queries"].copy()
    # Si hay filtro activo, limitar queries a las fechas de la fuente filtrada
    if (has_dev or has_cnt) and _valid_dates and "date" in df_q.columns:
        df_q = df_q[df_q["date"].dt.date.isin(_valid_dates)]
    if not df_q.empty and "query" in df_q.columns:
        q_agg = (df_q.groupby("query")
            .agg(Clicks=("clicks","sum"),Impresiones=("impressions","sum"),
                 CTR=("ctr","mean"),Posición=("position","mean"))
            .reset_index().sort_values("Clicks",ascending=False))
        q_agg["CTR"]=(q_agg["CTR"]*100).round(2); q_agg["Posición"]=q_agg["Posición"].round(1)
        srch=st.text_input("🔎 Buscar query...",key="q_srch")
        if srch: q_agg=q_agg[q_agg["query"].str.contains(srch,case=False,na=False)]
        st.dataframe(q_agg.rename(columns={"query":"Query"}).head(100)
            .style.format({"Clicks":"{:,.0f}","Impresiones":"{:,.0f}","CTR":"{:.2f}%","Posición":"{:.1f}"}),
            use_container_width=True,hide_index=True,height=400)
        fq=px.bar(q_agg.head(15),x="Clicks",y="query",orientation="h",
            color="Clicks",color_continuous_scale=["#14143a","#6366f1"])
        fq.update_layout(yaxis=dict(autorange="reversed"),coloraxis_showscale=False,yaxis_title="")
        _fig(fq,440); st.plotly_chart(fq,use_container_width=True)
    else:
        st.info("Sin datos de queries para los filtros aplicados.")

with t2:
    sh("📄 Páginas más clickeadas")
    df_pg = sc_f["pages"].copy()
    if (has_dev or has_cnt) and _valid_dates and "date" in df_pg.columns:
        df_pg = df_pg[df_pg["date"].dt.date.isin(_valid_dates)]
    if not df_pg.empty and "page" in df_pg.columns:
        p_agg = (df_pg.groupby("page")
            .agg(Clicks=("clicks","sum"),Impresiones=("impressions","sum"),
                 CTR=("ctr","mean"),Posición=("position","mean"))
            .reset_index().sort_values("Clicks",ascending=False))
        p_agg["CTR"]=(p_agg["CTR"]*100).round(2); p_agg["Posición"]=p_agg["Posición"].round(1)
        srch_p=st.text_input("🔎 Buscar página...",key="pg_srch")
        if srch_p: p_agg=p_agg[p_agg["page"].str.contains(srch_p,case=False,na=False)]
        st.dataframe(p_agg.rename(columns={"page":"Página"}).head(100)
            .style.format({"Clicks":"{:,.0f}","Impresiones":"{:,.0f}","CTR":"{:.2f}%","Posición":"{:.1f}"}),
            use_container_width=True,hide_index=True,height=400)
    else:
        st.info("Sin datos de páginas para los filtros aplicados.")

with t3:
    sh("🌎 Clicks por País")
    df_cnt = sc_f["country"].copy()
    # Si hay filtro de device, cruzar countries por esas mismas fechas
    if has_dev and _valid_dates and "date" in df_cnt.columns:
        df_cnt = df_cnt[df_cnt["date"].dt.date.isin(_valid_dates)]
    if not df_cnt.empty and "country" in df_cnt.columns:
        c_agg = (df_cnt.groupby("country")
            .agg(Clicks=("clicks","sum"),Impresiones=("impressions","sum"),CTR=("ctr","mean"))
            .reset_index().sort_values("Clicks",ascending=False))
        c_agg["CTR"]=(c_agg["CTR"]*100).round(2)
        cc1,cc2 = st.columns([2,1])
        with cc1:
            fc_=px.bar(c_agg.head(20),x="Clicks",y="country",orientation="h",
                color="Clicks",color_continuous_scale=["#14143a","#6366f1"])
            fc_.update_layout(yaxis=dict(autorange="reversed"),coloraxis_showscale=False,yaxis_title="")
            _fig(fc_,480); st.plotly_chart(fc_,use_container_width=True)
        with cc2:
            st.dataframe(c_agg.rename(columns={"country":"País"})
                .style.format({"Clicks":"{:,.0f}","Impresiones":"{:,.0f}","CTR":"{:.2f}%"}),
                use_container_width=True,hide_index=True,height=480)
    else:
        st.info("Sin datos de países para los filtros aplicados.")

with t4:
    sh("📱 Clicks por Dispositivo")
    df_dev = sc_f["device"].copy()
    # Si hay filtro de country, cruzar devices por esas mismas fechas
    if has_cnt and _valid_dates and "date" in df_dev.columns:
        df_dev = df_dev[df_dev["date"].dt.date.isin(_valid_dates)]
    if not df_dev.empty and "device" in df_dev.columns:
        d_agg = (df_dev.groupby("device")
            .agg(Clicks=("clicks","sum"),Impresiones=("impressions","sum"),CTR=("ctr","mean"))
            .reset_index())
        d_agg["CTR"]=(d_agg["CTR"]*100).round(2)
        dc1,dc2 = st.columns(2)
        with dc1:
            fd=px.pie(d_agg,names="device",values="Clicks",color_discrete_sequence=C,hole=0.52)
            fd.update_traces(textposition="inside",textinfo="percent+label",textfont_size=13)
            fd.update_layout(showlegend=False); _fig(fd,300); st.plotly_chart(fd,use_container_width=True)
        with dc2:
            st.dataframe(d_agg.rename(columns={"device":"Dispositivo"})
                .style.format({"Clicks":"{:,.0f}","Impresiones":"{:,.0f}","CTR":"{:.2f}%"}),
                use_container_width=True,hide_index=True)
    else:
        st.info("Sin datos de dispositivos para los filtros aplicados.")
