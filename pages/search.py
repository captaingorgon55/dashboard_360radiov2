import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from data_loader import load_search_console, filter_by_date, fmt_number, safe_sum

COLORS = ["#4f46e5","#06b6d4","#10b981","#f59e0b","#ef4444","#8b5cf6"]
DARK_BG = "#0f0f1a"

def dark_chart(fig, height=340):
    fig.update_layout(height=height, paper_bgcolor=DARK_BG, plot_bgcolor=DARK_BG,
        font=dict(family="DM Sans", color="#cdd6f4"), margin=dict(l=10,r=10,t=36,b=10),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(gridcolor="#1e2040"), yaxis=dict(gridcolor="#1e2040"))
    return fig

st.markdown("# 🔍 Search Console")

sc = load_search_console()

# ── Filtros ──────────────────────────────────────────────────────────────────
c1, c2, c3 = st.columns(3)
daily = sc["daily"]
if not daily.empty and "date" in daily.columns:
    min_d = daily["date"].dropna().min().date()
    max_d = daily["date"].dropna().max().date()
else:
    min_d, max_d = date(2024,1,1), date.today()

with c1:
    start = st.date_input("Desde", value=max_d - timedelta(days=90), min_value=min_d, max_value=max_d, key="sc_start")
with c2:
    end   = st.date_input("Hasta", value=max_d, min_value=min_d, max_value=max_d, key="sc_end")

sc_f = {k: filter_by_date(v, "date", start, end) for k, v in sc.items()}

# ── Métricas generales ────────────────────────────────────────────────────────
st.markdown("---")
st.markdown('<div class="section-header">📊 Métricas Generales</div>', unsafe_allow_html=True)

m1, m2, m3, m4, m5 = st.columns(5)
daily_f   = sc_f["daily"]
queries_f = sc_f["queries"]
pages_f   = sc_f["pages"]

clicks     = int(safe_sum(daily_f, "clicks"))
impressions= int(safe_sum(daily_f, "impressions"))
avg_ctr    = daily_f["ctr"].mean() * 100 if not daily_f.empty and "ctr" in daily_f.columns else 0
avg_pos    = daily_f["position"].mean() if not daily_f.empty and "position" in daily_f.columns else 0
total_q    = queries_f["query"].nunique() if not queries_f.empty and "query" in queries_f.columns else 0

m1.metric("🖱️ Clicks Totales", fmt_number(clicks))
m2.metric("👁 Impresiones", fmt_number(impressions))
m3.metric("📈 CTR Promedio", f"{avg_ctr:.2f}%")
m4.metric("📍 Posición Promedio", f"{avg_pos:.1f}")
m5.metric("🔑 Queries Únicas", fmt_number(total_q))

# ── Evolución temporal ────────────────────────────────────────────────────────
st.markdown('<div class="section-header">📈 Evolución Temporal</div>', unsafe_allow_html=True)
if not daily_f.empty and "date" in daily_f.columns:
    daily_c = daily_f.copy()
    daily_c["mes"] = daily_c["date"].dt.to_period("M").astype(str)
    monthly = daily_c.groupby("mes").agg(
        clicks=("clicks","sum"), impressions=("impressions","sum")
    ).reset_index()

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=monthly["mes"], y=monthly["clicks"], name="Clicks",
        line=dict(color=COLORS[0], width=2.5), mode="lines+markers"))
    fig.add_trace(go.Bar(x=monthly["mes"], y=monthly["impressions"], name="Impresiones",
        marker_color=COLORS[1], opacity=0.5, yaxis="y2"))
    fig.update_layout(title="Clicks vs Impresiones por Mes",
        yaxis2=dict(overlaying="y", side="right", showgrid=False))
    dark_chart(fig)
    st.plotly_chart(fig, use_container_width=True)

# ── Tabs detallados ───────────────────────────────────────────────────────────
t1, t2, t3, t4 = st.tabs(["🔑 Queries", "📄 Páginas", "🌎 Países", "📱 Dispositivos"])

with t1:
    if not queries_f.empty:
        q_agg = queries_f.groupby("query").agg(
            Clicks=("clicks","sum"), Impresiones=("impressions","sum"),
            CTR=("ctr","mean"), Posición=("position","mean")
        ).reset_index().sort_values("Clicks", ascending=False).head(50)
        q_agg["CTR"] = (q_agg["CTR"] * 100).round(2)
        q_agg["Posición"] = q_agg["Posición"].round(1)
        
        search_q = st.text_input("🔎 Buscar query", "", key="q_search")
        if search_q:
            q_agg = q_agg[q_agg["query"].str.contains(search_q, case=False, na=False)]
        
        st.dataframe(q_agg.rename(columns={"query":"Query"})
            .style.format({"Clicks":"{:,.0f}","Impresiones":"{:,.0f}","CTR":"{:.2f}%","Posición":"{:.1f}"}),
            use_container_width=True, hide_index=True, height=400)

with t2:
    if not pages_f.empty:
        p_agg = pages_f.groupby("page").agg(
            Clicks=("clicks","sum"), Impresiones=("impressions","sum"),
            CTR=("ctr","mean"), Posición=("position","mean")
        ).reset_index().sort_values("Clicks", ascending=False).head(50)
        p_agg["CTR"] = (p_agg["CTR"] * 100).round(2)
        p_agg["Posición"] = p_agg["Posición"].round(1)
        st.dataframe(p_agg.rename(columns={"page":"Página"})
            .style.format({"Clicks":"{:,.0f}","Impresiones":"{:,.0f}","CTR":"{:.2f}%","Posición":"{:.1f}"}),
            use_container_width=True, hide_index=True, height=400)

with t3:
    if not sc_f["country"].empty:
        c_agg = sc_f["country"].groupby("country").agg(
            Clicks=("clicks","sum"), Impresiones=("impressions","sum")
        ).reset_index().sort_values("Clicks", ascending=False).head(30)
        
        col1, col2 = st.columns(2)
        with col1:
            fig_c = px.bar(c_agg.head(15), x="Clicks", y="country", orientation="h",
                title="Clicks por País", color="Clicks",
                color_continuous_scale=["#1e1b4b","#4f46e5"])
            fig_c.update_layout(yaxis=dict(autorange="reversed"), coloraxis_showscale=False)
            dark_chart(fig_c, 400)
            st.plotly_chart(fig_c, use_container_width=True)
        with col2:
            st.dataframe(c_agg.rename(columns={"country":"País"})
                .style.format({"Clicks":"{:,.0f}","Impresiones":"{:,.0f}"}),
                use_container_width=True, hide_index=True, height=400)

with t4:
    if not sc_f["device"].empty:
        d_agg = sc_f["device"].groupby("device").agg(
            Clicks=("clicks","sum"), Impresiones=("impressions","sum"),
            CTR=("ctr","mean")
        ).reset_index()
        d_agg["CTR"] = (d_agg["CTR"] * 100).round(2)
        
        col1, col2 = st.columns(2)
        with col1:
            fig_d = px.pie(d_agg, names="device", values="Clicks",
                title="Clicks por Dispositivo", color_discrete_sequence=COLORS, hole=0.4)
            dark_chart(fig_d, 300)
            st.plotly_chart(fig_d, use_container_width=True)
        with col2:
            st.dataframe(d_agg.rename(columns={"device":"Dispositivo"})
                .style.format({"Clicks":"{:,.0f}","Impresiones":"{:,.0f}","CTR":"{:.2f}%"}),
                use_container_width=True, hide_index=True)
