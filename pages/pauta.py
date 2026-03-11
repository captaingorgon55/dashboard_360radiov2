import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta
import sys, os
sys.path.insert(0, os.getcwd())
from data_loader import load_admanager, filter_by_date, fmt_number, safe_sum, get_date_range, pct_delta

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

st.markdown('<div class="page-title">📣 Pauta</div>', unsafe_allow_html=True)
st.markdown('<div class="page-subtitle">Campañas · Orders · Line Items · Fill Rate · Ad Manager</div>', unsafe_allow_html=True)

gam = load_admanager()
diario = gam["diario"]
orders = gam["orders"]
fill   = gam["fill"]

min_d, max_d = get_date_range(diario, "DATE")

# ── Filtros ────────────────────────────────────────────────────────────────────
with st.container():
    st.markdown('<div class="filter-box">', unsafe_allow_html=True)
    sh("⚙️ Filtros")
    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        start = st.date_input("📅 Desde", value=max_d - timedelta(days=90),
                               min_value=min_d, max_value=max_d, key="pau_s")
    with fc2:
        end   = st.date_input("📅 Hasta", value=max_d,
                               min_value=min_d, max_value=max_d, key="pau_e")

    # Filtro campaña
    camp_opts = ["Todas"]
    if not orders.empty and "ORDER_NAME" in orders.columns:
        camp_opts += sorted(orders["ORDER_NAME"].dropna().unique().tolist())
    with fc3:
        sel_camp = st.selectbox("📢 Campaña", camp_opts, key="pau_camp")
    st.markdown('</div>', unsafe_allow_html=True)

diario_f = filter_by_date(diario, "DATE", start, end)
fill_f   = filter_by_date(fill,   "DATE", start, end)

orders_f = orders.copy() if not orders.empty else pd.DataFrame()
if sel_camp != "Todas" and not orders_f.empty and "ORDER_NAME" in orders_f.columns:
    orders_f = orders_f[orders_f["ORDER_NAME"] == sel_camp]

period_days = (end - start).days or 1
diario_p = filter_by_date(diario, "DATE", start-timedelta(days=period_days), start-timedelta(days=1))

def _delta(cur, prev):
    d = pct_delta(cur, prev)
    return f"{d:+.1f}%" if d is not None else None

def _si(df, col): return int(safe_sum(df, col))
def _sf(df, col): return float(safe_sum(df, col))

# ── Métricas ──────────────────────────────────────────────────────────────────
sh("📊 Métricas de Pauta · Con Variación")

impr   = _si(diario_f, "AD_SERVER_IMPRESSIONS")
fill_i = _si(diario_f, "TOTAL_LINE_ITEM_LEVEL_IMPRESSIONS")
clicks = _si(diario_f, "AD_SERVER_CLICKS")
rev    = _sf(diario_f, "AD_SERVER_CPM_AND_CPC_REVENUE")
ctr    = diario_f["AD_SERVER_CTR"].mean()*100 if not diario_f.empty and "AD_SERVER_CTR" in diario_f.columns else 0

impr_p   = _si(diario_p, "AD_SERVER_IMPRESSIONS")
fill_i_p = _si(diario_p, "TOTAL_LINE_ITEM_LEVEL_IMPRESSIONS")
clicks_p = _si(diario_p, "AD_SERVER_CLICKS")
rev_p    = _sf(diario_p, "AD_SERVER_CPM_AND_CPC_REVENUE")

m1,m2,m3,m4,m5 = st.columns(5)
m1.metric("📢 Impresiones",      fmt_number(impr),   _delta(impr, impr_p))
m2.metric("🎯 Total Line Items", fmt_number(fill_i), _delta(fill_i, fill_i_p))
m3.metric("🖱️ Clicks",           fmt_number(clicks), _delta(clicks, clicks_p))
m4.metric("💵 Revenue",          f"${rev:,.2f}",     _delta(rev, rev_p))
m5.metric("📈 CTR",              f"{ctr:.2f}%")

# ── GRÁFICO 1: Impresiones vs Alcance ─────────────────────────────────────────
sh("📈 Impresiones vs Alcance · Evolución Mensual")
if not diario_f.empty and "DATE" in diario_f.columns:
    df_g = diario_f.copy()
    df_g["mes"] = df_g["DATE"].dt.to_period("M").astype(str)
    agg = {}
    if "AD_SERVER_IMPRESSIONS" in df_g.columns:          agg["AD_SERVER_IMPRESSIONS"]          = "sum"
    if "TOTAL_LINE_ITEM_LEVEL_IMPRESSIONS" in df_g.columns: agg["TOTAL_LINE_ITEM_LEVEL_IMPRESSIONS"] = "sum"
    if "AD_SERVER_CPM_AND_CPC_REVENUE" in df_g.columns:  agg["AD_SERVER_CPM_AND_CPC_REVENUE"]  = "sum"
    if agg:
        monthly = df_g.groupby("mes").agg(agg).reset_index()
        fig1 = go.Figure()
        if "AD_SERVER_IMPRESSIONS" in monthly.columns:
            fig1.add_trace(go.Bar(x=monthly["mes"], y=monthly["AD_SERVER_IMPRESSIONS"],
                name="Impresiones Servidas", marker_color=C[0], opacity=0.7))
        if "TOTAL_LINE_ITEM_LEVEL_IMPRESSIONS" in monthly.columns:
            fig1.add_trace(go.Scatter(x=monthly["mes"], y=monthly["TOTAL_LINE_ITEM_LEVEL_IMPRESSIONS"],
                name="Total Line Items", mode="lines+markers",
                line=dict(color=C[1], width=2.5, dash="dash"),
                marker=dict(size=6)))
        if "AD_SERVER_CPM_AND_CPC_REVENUE" in monthly.columns:
            fig1.add_trace(go.Scatter(x=monthly["mes"], y=monthly["AD_SERVER_CPM_AND_CPC_REVENUE"],
                name="Revenue", mode="lines+markers",
                line=dict(color=C[3], width=2), yaxis="y2",
                marker=dict(size=5)))
        fig1.update_layout(
            barmode="overlay",
            yaxis2=dict(overlaying="y", side="right", showgrid=False,
                        tickfont=dict(color=C[3]), tickprefix="$"),
            legend=dict(orientation="h", y=1.12)
        )
        _fig(fig1, 360)
        st.plotly_chart(fig1, use_container_width=True)
else:
    st.info("Sin datos de Ad Manager en el período.")

# ── Orders / Line Items ───────────────────────────────────────────────────────
if not orders_f.empty:
    sh("📋 Campañas · Orders & Line Items")

    col_map = {
        "ORDER_NAME":                     "Campaña",
        "LINE_ITEM_NAME":                 "Line Item",
        "LINE_ITEM_TYPE":                 "Tipo",
        "AD_SERVER_IMPRESSIONS":          "Impresiones",
        "AD_SERVER_CLICKS":               "Clicks",
        "AD_SERVER_CPM_AND_CPC_REVENUE":  "Revenue",
        "AD_SERVER_WITHOUT_CPD_AVERAGE_ECPM": "eCPM",
        "LINE_ITEM_START_DATE_TIME":      "Inicio",
        "LINE_ITEM_END_DATE_TIME":        "Fin",
    }
    show = {k:v for k,v in col_map.items() if k in orders_f.columns}
    ord_show = orders_f[list(show.keys())].rename(columns=show)

    num_fmt = {}
    if "Impresiones" in ord_show.columns: num_fmt["Impresiones"] = "{:,.0f}"
    if "Clicks"      in ord_show.columns: num_fmt["Clicks"]      = "{:,.0f}"
    if "Revenue"     in ord_show.columns: num_fmt["Revenue"]     = "${:,.2f}"
    if "eCPM"        in ord_show.columns: num_fmt["eCPM"]        = "${:,.2f}"

    # ── GRÁFICO 2: Tráfico real al sitio por campaña ─────────────────────────
    if "Campaña" in ord_show.columns and "Impresiones" in ord_show.columns:
        sh("📊 Impresiones por Campaña")
        camp_agg = (
            ord_show.groupby("Campaña")["Impresiones"].sum()
            .reset_index().sort_values("Impresiones", ascending=False).head(15)
        )
        fig2 = px.bar(camp_agg, x="Impresiones", y="Campaña", orientation="h",
            color="Impresiones", color_continuous_scale=["#1a1a3e","#6366f1"],
            text="Impresiones")
        fig2.update_traces(texttemplate="%{text:,.0f}", textposition="outside", textfont_size=9)
        fig2.update_layout(yaxis=dict(autorange="reversed"), coloraxis_showscale=False, yaxis_title="")
        _fig(fig2, max(300, len(camp_agg)*30+60))
        st.plotly_chart(fig2, use_container_width=True)

    # ── GRÁFICO 3: Interacciones + Revenue por campaña ───────────────────────
    if "Campaña" in ord_show.columns:
        sh("💼 Interacciones y Revenue por Campaña")
        grp = {}
        if "Impresiones" in ord_show.columns: grp["Impresiones"] = "sum"
        if "Clicks"      in ord_show.columns: grp["Clicks"]      = "sum"
        if "Revenue"     in ord_show.columns: grp["Revenue"]     = "sum"
        if grp:
            camp_det = (
                ord_show.groupby("Campaña").agg(grp)
                .reset_index().sort_values(list(grp.keys())[0], ascending=False).head(15)
            )
            fig3 = go.Figure()
            if "Impresiones" in camp_det.columns:
                fig3.add_trace(go.Bar(x=camp_det["Campaña"], y=camp_det["Impresiones"],
                    name="Impresiones", marker_color=C[0]))
            if "Clicks" in camp_det.columns:
                fig3.add_trace(go.Bar(x=camp_det["Campaña"], y=camp_det["Clicks"],
                    name="Clicks", marker_color=C[2]))
            if "Revenue" in camp_det.columns:
                fig3.add_trace(go.Scatter(x=camp_det["Campaña"], y=camp_det["Revenue"],
                    name="Revenue USD", mode="lines+markers",
                    line=dict(color=C[3], width=2.5), yaxis="y2",
                    marker=dict(size=7)))
            fig3.update_layout(
                barmode="group",
                yaxis2=dict(overlaying="y", side="right", showgrid=False,
                            tickprefix="$", tickfont=dict(color=C[3])),
                xaxis=dict(tickangle=-30),
                legend=dict(orientation="h", y=1.12)
            )
            _fig(fig3, 420)
            st.plotly_chart(fig3, use_container_width=True)

    # Tabla completa
    sh("📄 Detalle Completo de Line Items")
    search_li = st.text_input("🔎 Buscar campaña o line item...", key="li_search")
    ord_disp = ord_show.copy()
    if search_li:
        mask = pd.Series(False, index=ord_disp.index)
        for col in ["Campaña","Line Item"]:
            if col in ord_disp.columns:
                mask |= ord_disp[col].fillna("").str.contains(search_li, case=False)
        ord_disp = ord_disp[mask]
    st.dataframe(ord_disp.style.format(num_fmt), use_container_width=True, hide_index=True, height=400)

else:
    st.info("Sin datos de orders/line items disponibles.")

# ── Fill Rate ─────────────────────────────────────────────────────────────────
if not fill_f.empty and "FILL_RATE_%" in fill_f.columns and "DATE" in fill_f.columns:
    sh("📊 Fill Rate · Evolución Mensual")
    fc = fill_f.copy()
    fc["mes"] = fc["DATE"].dt.to_period("M").astype(str)
    fill_m = fc.groupby("mes")["FILL_RATE_%"].mean().reset_index()
    avg_fill = fill_m["FILL_RATE_%"].mean()

    fig_fill = px.line(fill_m, x="mes", y="FILL_RATE_%",
        title="Fill Rate Promedio Mensual (%)", markers=True,
        color_discrete_sequence=[C[2]])
    fig_fill.update_traces(line_width=2.5, marker_size=7,
        marker=dict(color=C[2], line=dict(color="#fff",width=1.5)))
    fig_fill.add_hline(y=avg_fill, line_dash="dot", line_color=C[3],
        annotation_text=f"Promedio: {avg_fill:.1f}%",
        annotation_font_color=C[3], annotation_font_size=11)
    fig_fill.update_layout(yaxis_title="Fill Rate (%)", yaxis_ticksuffix="%")
    _fig(fig_fill, 280)
    st.plotly_chart(fig_fill, use_container_width=True)

# ── Dispositivos Ad Manager ───────────────────────────────────────────────────
gam_dev = gam["devices"]
if not gam_dev.empty and "DEVICE_CATEGORY_NAME" in gam_dev.columns:
    sh("📱 Impresiones por Dispositivo · Ad Manager")
    dc1, dc2 = st.columns(2)
    with dc1:
        fig_dev = px.pie(gam_dev, names="DEVICE_CATEGORY_NAME",
            values="AD_SERVER_IMPRESSIONS" if "AD_SERVER_IMPRESSIONS" in gam_dev.columns else gam_dev.columns[2],
            title="Impresiones por Dispositivo", color_discrete_sequence=C, hole=0.5)
        fig_dev.update_traces(textposition="inside", textinfo="percent+label", textfont_size=12)
        fig_dev.update_layout(legend=dict(visible=False))
        _fig(fig_dev, 280)
        st.plotly_chart(fig_dev, use_container_width=True)
    with dc2:
        dev_map = {"DEVICE_CATEGORY_NAME":"Dispositivo","AD_SERVER_IMPRESSIONS":"Impresiones",
                   "AD_SERVER_CLICKS":"Clicks","AD_SERVER_CPM_AND_CPC_REVENUE":"Revenue",
                   "AD_SERVER_WITHOUT_CPD_AVERAGE_ECPM":"eCPM"}
        dev_show = {k:v for k,v in dev_map.items() if k in gam_dev.columns}
        dev_df = gam_dev[list(dev_show.keys())].rename(columns=dev_show)
        dev_fmt = {}
        if "Impresiones" in dev_df.columns: dev_fmt["Impresiones"] = "{:,.0f}"
        if "Revenue" in dev_df.columns: dev_fmt["Revenue"] = "${:,.2f}"
        if "eCPM" in dev_df.columns: dev_fmt["eCPM"] = "${:,.2f}"
        st.dataframe(dev_df.style.format(dev_fmt), use_container_width=True, hide_index=True)
