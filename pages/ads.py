import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from data_loader import (
    load_adsense, load_mgid, load_admanager, load_youtube,
    filter_by_date, fmt_number, safe_sum
)

COLORS = ["#4f46e5","#06b6d4","#10b981","#f59e0b","#ef4444","#8b5cf6"]
DARK_BG = "#0f0f1a"

def dark_chart(fig, height=340):
    fig.update_layout(height=height, paper_bgcolor=DARK_BG, plot_bgcolor=DARK_BG,
        font=dict(family="DM Sans", color="#cdd6f4"), margin=dict(l=10,r=10,t=36,b=10),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(gridcolor="#1e2040"), yaxis=dict(gridcolor="#1e2040"))
    return fig

st.markdown("# 💰 Ads y Monetización")

# ── Carga ─────────────────────────────────────────────────────────────────────
adsense = load_adsense()
mgid    = load_mgid()
gam     = load_admanager()
yt      = load_youtube()

# ── Filtros ───────────────────────────────────────────────────────────────────
c1, c2, c3 = st.columns(3)

all_dates = []
if not adsense.empty and "Date" in adsense.columns: all_dates += adsense["Date"].dropna().tolist()
if not mgid.empty and "Date" in mgid.columns: all_dates += mgid["Date"].dropna().tolist()
if not gam["diario"].empty and "DATE" in gam["diario"].columns: all_dates += gam["diario"]["DATE"].dropna().tolist()

if all_dates:
    all_dates = pd.to_datetime(all_dates)
    min_d, max_d = all_dates.min().date(), all_dates.max().date()
else:
    min_d, max_d = date(2024,1,1), date.today()

with c1:
    start = st.date_input("Desde", value=max_d - timedelta(days=90), min_value=min_d, max_value=max_d, key="ads_start")
with c2:
    end   = st.date_input("Hasta", value=max_d, min_value=min_d, max_value=max_d, key="ads_end")
with c3:
    plataformas = st.multiselect("Plataforma", ["AdSense","MGID","Ad Manager","YouTube"],
        default=["AdSense","MGID","Ad Manager"])

# Filtrar
adsense_f = filter_by_date(adsense, "Date", start, end)
mgid_f    = filter_by_date(mgid,    "Date", start, end)
gam_f     = filter_by_date(gam["diario"], "DATE", start, end)
yt_tabla  = yt["tabla"]

# ── Métricas generales ────────────────────────────────────────────────────────
st.markdown("---")
st.markdown('<div class="section-header">📊 Métricas Generales</div>', unsafe_allow_html=True)

# Revenue
rev_adsense = safe_sum(adsense_f, "Estimated earnings (USD)") if "Estimated earnings (USD)" in adsense_f.columns else 0
rev_mgid    = safe_sum(mgid_f,    "Revenue") if "Revenue" in mgid_f.columns else 0
rev_gam     = safe_sum(gam_f,     "AD_SERVER_CPM_AND_CPC_REVENUE") if "AD_SERVER_CPM_AND_CPC_REVENUE" in gam_f.columns else 0
rev_yt      = safe_sum(yt_tabla,  "Ingresos estimados (USD)") if not yt_tabla.empty and "Ingresos estimados (USD)" in yt_tabla.columns else 0
rev_total   = rev_adsense + rev_mgid + rev_gam + rev_yt

# Impresiones
impr_adsense = int(safe_sum(adsense_f, "Impressions")) if "Impressions" in adsense_f.columns else 0
impr_mgid    = int(safe_sum(mgid_f,    "Page views")) if "Page views" in mgid_f.columns else 0
impr_gam     = int(safe_sum(gam_f,     "AD_SERVER_IMPRESSIONS")) if "AD_SERVER_IMPRESSIONS" in gam_f.columns else 0
total_impr   = impr_adsense + impr_mgid + impr_gam

# Clicks
clicks_adsense = int(safe_sum(adsense_f, "Clicks")) if "Clicks" in adsense_f.columns else 0
clicks_mgid    = int(safe_sum(mgid_f,    "Ad Clicks")) if "Ad Clicks" in mgid_f.columns else 0
clicks_gam     = int(safe_sum(gam_f,     "AD_SERVER_CLICKS")) if "AD_SERVER_CLICKS" in gam_f.columns else 0
total_clicks   = clicks_adsense + clicks_mgid + clicks_gam

# CTR promedio
ctr_adsense = adsense_f["Active View Viewable"].mean() if not adsense_f.empty and "Active View Viewable" in adsense_f.columns else 0
ctr_gam     = gam_f["AD_SERVER_CTR"].mean() if not gam_f.empty and "AD_SERVER_CTR" in gam_f.columns else 0

# CPM promedio
cpm_adsense = adsense_f["Impression RPM (USD)"].mean() if not adsense_f.empty and "Impression RPM (USD)" in adsense_f.columns else 0
cpm_gam     = gam_f["AD_SERVER_WITHOUT_CPD_AVERAGE_ECPM"].mean() if not gam_f.empty and "AD_SERVER_WITHOUT_CPD_AVERAGE_ECPM" in gam_f.columns else 0
cpm_mgid    = mgid_f["Ad RPM"].mean() if not mgid_f.empty and "Ad RPM" in mgid_f.columns else 0
cpm_avg     = np.mean([x for x in [cpm_adsense, cpm_gam, cpm_mgid] if x > 0]) if any([cpm_adsense, cpm_gam, cpm_mgid]) else 0

m1,m2,m3,m4,m5 = st.columns(5)
m1.metric("💵 Revenue Total", f"${rev_total:,.2f}")
m2.metric("📈 CPM Promedio", f"${cpm_avg:.2f}")
m3.metric("👁 Impresiones Ads", fmt_number(total_impr))
m4.metric("🖱️ Clicks Totales", fmt_number(total_clicks))
m5.metric("📊 CTR (GAM)", f"{ctr_gam*100:.2f}%" if ctr_gam else "—")

# ── Gráfico 1: Impresiones vs sin rellenar ─────────────────────────────────────
st.markdown('<div class="section-header">📈 Impresiones Totales vs Sin Rellenar (Ad Manager)</div>', unsafe_allow_html=True)
if not gam_f.empty and "DATE" in gam_f.columns:
    gam_c = gam_f.copy()
    gam_c["mes"] = gam_c["DATE"].dt.to_period("M").astype(str)
    cols_sum = {}
    if "AD_SERVER_IMPRESSIONS" in gam_c.columns:
        cols_sum["AD_SERVER_IMPRESSIONS"] = "sum"
    if "TOTAL_LINE_ITEM_LEVEL_IMPRESSIONS" in gam_c.columns:
        cols_sum["TOTAL_LINE_ITEM_LEVEL_IMPRESSIONS"] = "sum"
    if cols_sum:
        gam_monthly = gam_c.groupby("mes").agg(cols_sum).reset_index()
        fig1 = go.Figure()
        if "AD_SERVER_IMPRESSIONS" in gam_monthly.columns:
            fig1.add_trace(go.Scatter(x=gam_monthly["mes"], y=gam_monthly["AD_SERVER_IMPRESSIONS"],
                name="Impresiones Servidas", line=dict(color=COLORS[0], width=2.5), mode="lines+markers"))
        if "TOTAL_LINE_ITEM_LEVEL_IMPRESSIONS" in gam_monthly.columns:
            fig1.add_trace(go.Scatter(x=gam_monthly["mes"], y=gam_monthly["TOTAL_LINE_ITEM_LEVEL_IMPRESSIONS"],
                name="Total Line Items", line=dict(color=COLORS[1], width=2, dash="dash"), mode="lines+markers"))
        fig1.update_layout(title="Impresiones Ad Manager · Mensual")
        dark_chart(fig1)
        st.plotly_chart(fig1, use_container_width=True)

# ── Gráfico 2: Revenue por plataforma ─────────────────────────────────────────
st.markdown('<div class="section-header">💰 Revenue por Plataforma</div>', unsafe_allow_html=True)
rev_data = []
if "AdSense" in plataformas and rev_adsense > 0:
    rev_data.append({"Plataforma": "AdSense", "Revenue": rev_adsense, "Impresiones": impr_adsense})
if "MGID" in plataformas and rev_mgid > 0:
    rev_data.append({"Plataforma": "MGID", "Revenue": rev_mgid, "Impresiones": impr_mgid})
if "Ad Manager" in plataformas and rev_gam > 0:
    rev_data.append({"Plataforma": "Ad Manager", "Revenue": rev_gam, "Impresiones": impr_gam})
if "YouTube" in plataformas and rev_yt > 0:
    rev_data.append({"Plataforma": "YouTube", "Revenue": rev_yt, "Impresiones": 0})

if rev_data:
    rev_df = pd.DataFrame(rev_data)
    c1, c2 = st.columns(2)
    with c1:
        fig2a = px.bar(rev_df, x="Plataforma", y="Revenue",
            title="Revenue por Plataforma (USD)", color="Plataforma",
            color_discrete_sequence=COLORS)
        dark_chart(fig2a, 300)
        st.plotly_chart(fig2a, use_container_width=True)
    with c2:
        fig2b = px.pie(rev_df, names="Plataforma", values="Revenue",
            title="Distribución de Revenue", color_discrete_sequence=COLORS, hole=0.45)
        dark_chart(fig2b, 300)
        st.plotly_chart(fig2b, use_container_width=True)

# ── Gráfico 3: Formatos Ad Manager ────────────────────────────────────────────
st.markdown('<div class="section-header">📐 Formatos · Ad Manager</div>', unsafe_allow_html=True)
gam_fmt = gam["formatos"]
if not gam_fmt.empty and "CREATIVE_SIZE" in gam_fmt.columns:
    fmt_cols = {
        "CREATIVE_SIZE": "Formato",
        "AD_SERVER_IMPRESSIONS": "Impresiones",
        "AD_SERVER_CLICKS": "Clicks",
        "AD_SERVER_CTR": "CTR",
        "AD_SERVER_WITHOUT_CPD_AVERAGE_ECPM": "eCPM Promedio",
        "AD_SERVER_CPM_AND_CPC_REVENUE": "Revenue"
    }
    show_cols = [c for c in fmt_cols.keys() if c in gam_fmt.columns]
    gam_fmt_show = gam_fmt[show_cols].sort_values("AD_SERVER_IMPRESSIONS", ascending=False) if "AD_SERVER_IMPRESSIONS" in gam_fmt.columns else gam_fmt[show_cols]
    gam_fmt_show = gam_fmt_show.rename(columns=fmt_cols)
    
    num_cols = [v for k, v in fmt_cols.items() if k != "CREATIVE_SIZE" and v in gam_fmt_show.columns]
    fmt_dict = {}
    for c in num_cols:
        if c in ["CTR"]: fmt_dict[c] = "{:.4f}"
        elif c in ["eCPM Promedio","Revenue"]: fmt_dict[c] = "${:,.2f}"
        else: fmt_dict[c] = "{:,.0f}"
    
    st.dataframe(gam_fmt_show.style.format(fmt_dict), use_container_width=True, hide_index=True)

# ── AdSense detalle ────────────────────────────────────────────────────────────
if "AdSense" in plataformas and not adsense_f.empty:
    st.markdown('<div class="section-header">💡 AdSense · Evolución</div>', unsafe_allow_html=True)
    adsense_c = adsense_f.copy()
    if "Date" in adsense_c.columns:
        adsense_c["mes"] = adsense_c["Date"].dt.to_period("M").astype(str)
        as_monthly_cols = {}
        if "Estimated earnings (USD)" in adsense_c.columns: as_monthly_cols["Estimated earnings (USD)"] = "sum"
        if "Impressions" in adsense_c.columns: as_monthly_cols["Impressions"] = "sum"
        if as_monthly_cols:
            as_monthly = adsense_c.groupby("mes").agg(as_monthly_cols).reset_index()
            fig_as = go.Figure()
            if "Estimated earnings (USD)" in as_monthly.columns:
                fig_as.add_trace(go.Bar(x=as_monthly["mes"], y=as_monthly["Estimated earnings (USD)"],
                    name="Revenue USD", marker_color=COLORS[3]))
            fig_as.update_layout(title="AdSense Revenue Mensual")
            dark_chart(fig_as)
            st.plotly_chart(fig_as, use_container_width=True)

# ── MGID detalle ───────────────────────────────────────────────────────────────
if "MGID" in plataformas and not mgid_f.empty:
    st.markdown('<div class="section-header">📊 MGID · Detalle</div>', unsafe_allow_html=True)
    col_map = {
        "Date": "Fecha", "Page views": "Page Views", "Revenue": "Revenue",
        "Ad Clicks": "Clicks", "Ad RPM": "RPM", "Ad vRPM": "vRPM"
    }
    show = [c for c in col_map.keys() if c in mgid_f.columns]
    mgid_show = mgid_f[show].rename(columns=col_map).sort_values("Fecha", ascending=False) if "Date" in mgid_f.columns else mgid_f[show].rename(columns=col_map)
    num_f = {}
    if "Revenue" in mgid_show.columns: num_f["Revenue"] = "${:,.2f}"
    if "RPM" in mgid_show.columns: num_f["RPM"] = "${:,.3f}"
    st.dataframe(mgid_show.style.format(num_f), use_container_width=True, hide_index=True, height=300)
