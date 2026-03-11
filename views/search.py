import sys, os; sys.path.insert(0, os.getcwd())
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta
import sys, os

from data_loader import load_search_console, filter_by_date, fmt_number, safe_sum, get_date_range, pct_delta

C   = ["#6366f1","#06b6d4","#10b981","#f59e0b","#ef4444","#8b5cf6"]
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

st.markdown('<div class="page-title">🔍 Search Console</div>', unsafe_allow_html=True)
st.markdown('<div class="page-subtitle">Rendimiento orgánico · Queries · Páginas · Dispositivos</div>', unsafe_allow_html=True)

sc = load_search_console()
min_d, max_d = get_date_range(sc["daily"], "date")

# ── Filtros ────────────────────────────────────────────────────────────────────
with st.container():
    st.markdown('<div class="filter-box">', unsafe_allow_html=True)
    sh("⚙️ Filtros")
    fc1, fc2, fc3, fc4 = st.columns(4)
    with fc1:
        start = st.date_input("📅 Desde", value=max_d - timedelta(days=90),
                               min_value=min_d, max_value=max_d, key="sc_s")
    with fc2:
        end   = st.date_input("📅 Hasta", value=max_d,
                               min_value=min_d, max_value=max_d, key="sc_e")
    
    dev_opts = ["Todos"]
    if not sc["device"].empty and "device" in sc["device"].columns:
        dev_opts += sc["device"]["device"].dropna().unique().tolist()
    with fc3:
        sel_dev = st.selectbox("📱 Dispositivo", dev_opts, key="sc_dev")
    
    cntry_opts = ["Todos"]
    if not sc["country"].empty and "country" in sc["country"].columns:
        top_c = sc["country"].groupby("country")["clicks"].sum().sort_values(ascending=False).head(30).index.tolist()
        cntry_opts += top_c
    with fc4:
        sel_cntry = st.selectbox("🌎 País", cntry_opts, key="sc_cntry")
    st.markdown('</div>', unsafe_allow_html=True)

sc_f = {k: filter_by_date(v, "date", start, end) for k,v in sc.items()}

if sel_dev != "Todos" and not sc_f["device"].empty and "device" in sc_f["device"].columns:
    sc_f["device"] = sc_f["device"][sc_f["device"]["device"] == sel_dev]

if sel_cntry != "Todos" and not sc_f["country"].empty and "country" in sc_f["country"].columns:
    sc_f["country"] = sc_f["country"][sc_f["country"]["country"] == sel_cntry]

# Período previo
period_days = (end - start).days or 1
sc_prev = {k: filter_by_date(v, "date", start - timedelta(days=period_days), start - timedelta(days=1)) for k,v in sc.items()}

def _delta(cur, prev):
    d = pct_delta(cur, prev)
    return f"{d:+.1f}%" if d is not None else None

# ── Métricas ───────────────────────────────────────────────────────────────────
sh("📊 Métricas Generales")
m1,m2,m3,m4,m5 = st.columns(5)
daily = sc_f["daily"]
clicks    = int(safe_sum(daily, "clicks"))
impr      = int(safe_sum(daily, "impressions"))
avg_ctr   = daily["ctr"].mean()*100 if not daily.empty and "ctr" in daily.columns else 0
avg_pos   = daily["position"].mean()   if not daily.empty and "position" in daily.columns else 0
n_queries = sc_f["queries"]["query"].nunique() if not sc_f["queries"].empty and "query" in sc_f["queries"].columns else 0

p_cl = int(safe_sum(sc_prev["daily"], "clicks"))
p_im = int(safe_sum(sc_prev["daily"], "impressions"))

m1.metric("🖱️ Clicks",        fmt_number(clicks), _delta(clicks, p_cl))
m2.metric("👁 Impresiones",   fmt_number(impr),   _delta(impr, p_im))
m3.metric("📈 CTR Promedio",  f"{avg_ctr:.2f}%")
m4.metric("📍 Posición Media",f"{avg_pos:.1f}")
m5.metric("🔑 Queries Únicas",fmt_number(n_queries))

# ── Evolución ──────────────────────────────────────────────────────────────────
sh("📈 Evolución Mensual · Clicks e Impresiones")
if not daily.empty and "date" in daily.columns:
    df_m = daily.copy()
    df_m["mes"] = df_m["date"].dt.to_period("M").astype(str)
    mly = df_m.groupby("mes").agg(clicks=("clicks","sum"), impressions=("impressions","sum")).reset_index()

    fig = go.Figure()
    fig.add_trace(go.Bar(x=mly["mes"], y=mly["impressions"],
        name="Impresiones", marker_color="#06b6d4", opacity=0.45, yaxis="y2"))
    fig.add_trace(go.Scatter(x=mly["mes"], y=mly["clicks"],
        name="Clicks", mode="lines+markers",
        line=dict(color="#6366f1", width=3),
        marker=dict(size=7, color="#6366f1", line=dict(color="#fff", width=1.5))))
    fig.update_layout(
        yaxis2=dict(overlaying="y", side="right", showgrid=False,
                    tickfont=dict(color="#06b6d4"), title="Impresiones"),
        yaxis=dict(title="Clicks"), barmode="overlay",
        legend=dict(orientation="h", y=1.12)
    )
    _fig(fig, 360)
    st.plotly_chart(fig, use_container_width=True)

# ── Tabs detalle ───────────────────────────────────────────────────────────────
t1, t2, t3, t4 = st.tabs(["🔑 Queries", "📄 Páginas", "🌎 Países", "📱 Dispositivos"])

with t1:
    sh("🔑 Queries más clickeadas")
    if not sc_f["queries"].empty and "query" in sc_f["queries"].columns:
        q_agg = (
            sc_f["queries"].groupby("query")
            .agg(Clicks=("clicks","sum"), Impresiones=("impressions","sum"),
                 CTR=("ctr","mean"), Posición=("position","mean"))
            .reset_index().sort_values("Clicks", ascending=False)
        )
        q_agg["CTR"]     = (q_agg["CTR"] * 100).round(2)
        q_agg["Posición"]= q_agg["Posición"].round(1)

        search_q = st.text_input("🔎 Buscar query...", key="q_search")
        if search_q:
            q_agg = q_agg[q_agg["query"].str.contains(search_q, case=False, na=False)]

        st.dataframe(
            q_agg.rename(columns={"query":"Query"}).head(100)
            .style.format({"Clicks":"{:,.0f}","Impresiones":"{:,.0f}",
                           "CTR":"{:.2f}%","Posición":"{:.1f}"}),
            use_container_width=True, hide_index=True, height=420
        )
        # Top queries gráfico
        top_q = q_agg.head(15)
        fig_q = px.bar(top_q, x="Clicks", y="query", orientation="h",
            color="Clicks", color_continuous_scale=["#1a1a3e","#6366f1"])
        fig_q.update_layout(yaxis=dict(autorange="reversed"), coloraxis_showscale=False,
                             yaxis_title="")
        _fig(fig_q, 460)
        st.plotly_chart(fig_q, use_container_width=True)
    else:
        st.info("Sin datos de queries.")

with t2:
    sh("📄 Páginas más clickeadas")
    if not sc_f["pages"].empty and "page" in sc_f["pages"].columns:
        p_agg = (
            sc_f["pages"].groupby("page")
            .agg(Clicks=("clicks","sum"), Impresiones=("impressions","sum"),
                 CTR=("ctr","mean"), Posición=("position","mean"))
            .reset_index().sort_values("Clicks", ascending=False)
        )
        p_agg["CTR"]     = (p_agg["CTR"] * 100).round(2)
        p_agg["Posición"]= p_agg["Posición"].round(1)

        search_p = st.text_input("🔎 Buscar página...", key="p_search")
        if search_p:
            p_agg = p_agg[p_agg["page"].str.contains(search_p, case=False, na=False)]

        st.dataframe(
            p_agg.rename(columns={"page":"Página"}).head(100)
            .style.format({"Clicks":"{:,.0f}","Impresiones":"{:,.0f}",
                           "CTR":"{:.2f}%","Posición":"{:.1f}"}),
            use_container_width=True, hide_index=True, height=420
        )
    else:
        st.info("Sin datos de páginas.")

with t3:
    sh("🌎 Clicks por País")
    if not sc_f["country"].empty and "country" in sc_f["country"].columns:
        c_agg = (
            sc_f["country"].groupby("country")
            .agg(Clicks=("clicks","sum"), Impresiones=("impressions","sum"),
                 CTR=("ctr","mean"))
            .reset_index().sort_values("Clicks", ascending=False)
        )
        c_agg["CTR"] = (c_agg["CTR"] * 100).round(2)
        col1, col2 = st.columns([2, 1])
        with col1:
            fig_c = px.bar(c_agg.head(20), x="Clicks", y="country", orientation="h",
                color="Clicks", color_continuous_scale=["#1a1a3e","#6366f1"])
            fig_c.update_layout(yaxis=dict(autorange="reversed"), coloraxis_showscale=False,
                                 yaxis_title="")
            _fig(fig_c, 480)
            st.plotly_chart(fig_c, use_container_width=True)
        with col2:
            st.dataframe(c_agg.rename(columns={"country":"País"})
                .style.format({"Clicks":"{:,.0f}","Impresiones":"{:,.0f}","CTR":"{:.2f}%"}),
                use_container_width=True, hide_index=True, height=480)
    else:
        st.info("Sin datos de países.")

with t4:
    sh("📱 Clicks por Dispositivo")
    if not sc_f["device"].empty and "device" in sc_f["device"].columns:
        d_agg = (
            sc_f["device"].groupby("device")
            .agg(Clicks=("clicks","sum"), Impresiones=("impressions","sum"),
                 CTR=("ctr","mean"))
            .reset_index()
        )
        d_agg["CTR"] = (d_agg["CTR"] * 100).round(2)
        dc1, dc2 = st.columns(2)
        with dc1:
            fig_d = px.pie(d_agg, names="device", values="Clicks",
                title="Clicks por Dispositivo", color_discrete_sequence=C, hole=0.5)
            fig_d.update_traces(textposition="inside", textinfo="percent+label", textfont_size=13)
            _fig(fig_d, 300, )
            fig_d.update_layout(legend=dict(visible=False))
            st.plotly_chart(fig_d, use_container_width=True)
        with dc2:
            st.dataframe(d_agg.rename(columns={"device":"Dispositivo"})
                .style.format({"Clicks":"{:,.0f}","Impresiones":"{:,.0f}","CTR":"{:.2f}%"}),
                use_container_width=True, hide_index=True)
    else:
        st.info("Sin datos de dispositivos.")
