import sys, os; sys.path.insert(0, os.getcwd())
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta
import sys, os

from data_loader import (
    load_adsense, load_mgid, load_admanager, load_youtube,
    filter_by_date, fmt_number, safe_sum, get_date_range, pct_delta
)

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

st.markdown('<div class="page-title">💰 Ads y Monetización</div>', unsafe_allow_html=True)
st.markdown('<div class="page-subtitle">AdSense · MGID · Ad Manager · YouTube Revenue</div>', unsafe_allow_html=True)

# ── Carga ─────────────────────────────────────────────────────────────────────
adsense = load_adsense()
mgid    = load_mgid()
gam     = load_admanager()
yt      = load_youtube()

# Rango de fechas cross-plataforma
all_dates = []
for df, col in [(adsense,"Date"),(mgid,"Date"),(gam["diario"],"DATE")]:
    if not df.empty and col in df.columns:
        all_dates += pd.to_datetime(df[col], errors="coerce").dropna().tolist()
min_d = min(all_dates).date() if all_dates else date(2024,1,1)
max_d = max(all_dates).date() if all_dates else date.today()

# ── Filtros ────────────────────────────────────────────────────────────────────
with st.container():
    st.markdown('<div class="filter-box">', unsafe_allow_html=True)
    sh("⚙️ Filtros")
    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        start = st.date_input("📅 Desde", value=max_d - timedelta(days=90),
                               min_value=min_d, max_value=max_d, key="ads_s")
    with fc2:
        end   = st.date_input("📅 Hasta", value=max_d,
                               min_value=min_d, max_value=max_d, key="ads_e")
    with fc3:
        plataformas = st.multiselect("💳 Plataforma",
            ["AdSense","MGID","Ad Manager","YouTube"],
            default=["AdSense","MGID","Ad Manager","YouTube"])
    st.markdown('</div>', unsafe_allow_html=True)

# Filtrar
as_f  = filter_by_date(adsense, "Date",  start, end)
mg_f  = filter_by_date(mgid,    "Date",  start, end)
gd_f  = filter_by_date(gam["diario"], "DATE", start, end)
yt_tb = yt["tabla"]  # tabla YouTube no tiene fecha diaria fácil, usar global

period_days = (end - start).days or 1
as_p  = filter_by_date(adsense, "Date",  start-timedelta(days=period_days), start-timedelta(days=1))
mg_p  = filter_by_date(mgid,    "Date",  start-timedelta(days=period_days), start-timedelta(days=1))
gd_p  = filter_by_date(gam["diario"], "DATE", start-timedelta(days=period_days), start-timedelta(days=1))

def _delta(cur, prev):
    d = pct_delta(cur, prev)
    return f"{d:+.1f}%" if d is not None else None

def _s(df, col): return safe_sum(df, col)

# ── Revenue ───────────────────────────────────────────────────────────────────
rev_as  = _s(as_f,  "Estimated earnings (USD)") if "AdSense"     in plataformas else 0
rev_mg  = _s(mg_f,  "Revenue")                   if "MGID"       in plataformas else 0
rev_gam = _s(gd_f,  "AD_SERVER_CPM_AND_CPC_REVENUE") if "Ad Manager" in plataformas else 0
rev_yt  = _s(yt_tb, "Ingresos estimados (USD)")  if "YouTube"    in plataformas and not yt_tb.empty else 0
rev_tot = rev_as + rev_mg + rev_gam + rev_yt

rev_as_p  = _s(as_p,  "Estimated earnings (USD)")
rev_mg_p  = _s(mg_p,  "Revenue")
rev_gam_p = _s(gd_p,  "AD_SERVER_CPM_AND_CPC_REVENUE")
rev_tot_p = rev_as_p + rev_mg_p + rev_gam_p

# Impresiones
impr_as  = int(_s(as_f,  "Impressions"))           if "AdSense"     in plataformas else 0
impr_mg  = int(_s(mg_f,  "Page views"))             if "MGID"       in plataformas else 0
impr_gam = int(_s(gd_f,  "AD_SERVER_IMPRESSIONS"))  if "Ad Manager" in plataformas else 0
tot_impr = impr_as + impr_mg + impr_gam

impr_as_p  = int(_s(as_p, "Impressions"))
impr_gam_p = int(_s(gd_p, "AD_SERVER_IMPRESSIONS"))
tot_impr_p = impr_as_p + impr_gam_p

# Clicks
cl_as  = int(_s(as_f,  "Clicks"))       if "AdSense"     in plataformas else 0
cl_mg  = int(_s(mg_f,  "Ad Clicks"))    if "MGID"       in plataformas else 0
cl_gam = int(_s(gd_f,  "AD_SERVER_CLICKS")) if "Ad Manager" in plataformas else 0
tot_cl = cl_as + cl_mg + cl_gam

# CPM
cpm_as  = as_f["Impression RPM (USD)"].mean()        if not as_f.empty  and "Impression RPM (USD)" in as_f.columns else 0
cpm_gam = gd_f["AD_SERVER_WITHOUT_CPD_AVERAGE_ECPM"].mean() if not gd_f.empty and "AD_SERVER_WITHOUT_CPD_AVERAGE_ECPM" in gd_f.columns else 0
cpm_mg  = mg_f["Ad RPM"].mean()                       if not mg_f.empty  and "Ad RPM" in mg_f.columns else 0
cpm_vals = [x for x in [cpm_as, cpm_gam, cpm_mg] if x > 0]
cpm_avg = float(np.mean(cpm_vals)) if cpm_vals else 0

# CTR
ctr_gam = gd_f["AD_SERVER_CTR"].mean()*100 if not gd_f.empty and "AD_SERVER_CTR" in gd_f.columns else 0

# ── MÉTRICAS ──────────────────────────────────────────────────────────────────
sh("📊 Métricas Generales · Con Variación")
m1,m2,m3,m4,m5 = st.columns(5)
m1.metric("💵 Revenue Total",     f"${rev_tot:,.2f}",   _delta(rev_tot, rev_tot_p))
m2.metric("📈 CPM Promedio",      f"${cpm_avg:.2f}")
m3.metric("👁 Impresiones Ads",   fmt_number(tot_impr), _delta(tot_impr, tot_impr_p))
m4.metric("🖱️ Clicks Totales",    fmt_number(tot_cl),   _delta(tot_cl, int(_s(as_p,"Clicks"))+int(_s(gd_p,"AD_SERVER_CLICKS"))))
m5.metric("📊 CTR · Ad Manager",  f"{ctr_gam:.2f}%")

# ── GRÁFiCO 1: Impresiones vs sin rellenar ────────────────────────────────────
sh("📈 Impresiones Totales vs Sin Rellenar · Ad Manager")
if not gd_f.empty and "DATE" in gd_f.columns:
    df_g = gd_f.copy()
    df_g["mes"] = df_g["DATE"].dt.to_period("M").astype(str)
    agg_cols = {}
    if "AD_SERVER_IMPRESSIONS" in df_g.columns: agg_cols["AD_SERVER_IMPRESSIONS"] = "sum"
    if "TOTAL_LINE_ITEM_LEVEL_IMPRESSIONS" in df_g.columns: agg_cols["TOTAL_LINE_ITEM_LEVEL_IMPRESSIONS"] = "sum"
    if agg_cols:
        gam_m = df_g.groupby("mes").agg(agg_cols).reset_index()
        gam_m["Sin rellenar"] = (
            gam_m.get("TOTAL_LINE_ITEM_LEVEL_IMPRESSIONS", 0) - gam_m.get("AD_SERVER_IMPRESSIONS", 0)
        ).clip(lower=0)
        fig1 = go.Figure()
        if "AD_SERVER_IMPRESSIONS" in gam_m.columns:
            fig1.add_trace(go.Scatter(x=gam_m["mes"], y=gam_m["AD_SERVER_IMPRESSIONS"],
                name="Impresiones Servidas", mode="lines+markers",
                line=dict(color=C[0], width=3),
                marker=dict(size=7, line=dict(color="#fff",width=1.5))))
        if "Sin rellenar" in gam_m.columns:
            fig1.add_trace(go.Scatter(x=gam_m["mes"], y=gam_m["Sin rellenar"],
                name="Sin Rellenar", mode="lines+markers",
                line=dict(color=C[4], width=2.5, dash="dash"),
                marker=dict(size=6)))
        _fig(fig1, 320)
        st.plotly_chart(fig1, use_container_width=True)
else:
    st.info("Sin datos de Ad Manager en el período.")

# ── GRÁFICO 2: Revenue por plataforma ─────────────────────────────────────────
sh("💰 Revenue por Plataforma")
rev_rows = []
if "AdSense"     in plataformas and rev_as  > 0: rev_rows.append({"Plataforma":"AdSense",    "Revenue":rev_as,  "Impresiones":impr_as})
if "MGID"        in plataformas and rev_mg  > 0: rev_rows.append({"Plataforma":"MGID",       "Revenue":rev_mg,  "Impresiones":impr_mg})
if "Ad Manager"  in plataformas and rev_gam > 0: rev_rows.append({"Plataforma":"Ad Manager", "Revenue":rev_gam, "Impresiones":impr_gam})
if "YouTube"     in plataformas and rev_yt  > 0: rev_rows.append({"Plataforma":"YouTube",    "Revenue":rev_yt,  "Impresiones":0})

if rev_rows:
    rev_df = pd.DataFrame(rev_rows)
    rc1, rc2 = st.columns(2)
    with rc1:
        fig2a = px.bar(rev_df, x="Plataforma", y="Revenue", text="Revenue",
            color="Plataforma", color_discrete_sequence=C,
            title="Revenue USD por Plataforma")
        fig2a.update_traces(texttemplate="$%{text:,.2f}", textposition="outside", textfont_size=10)
        fig2a.update_layout(showlegend=False)
        _fig(fig2a, 320)
        st.plotly_chart(fig2a, use_container_width=True)
    with rc2:
        fig2b = px.pie(rev_df, names="Plataforma", values="Revenue",
            title="Distribución de Revenue", color_discrete_sequence=C, hole=0.5)
        fig2b.update_traces(textposition="inside", textinfo="percent+label", textfont_size=12)
        fig2b.update_layout(legend=dict(visible=False))
        _fig(fig2b, 320)
        st.plotly_chart(fig2b, use_container_width=True)
    # Tabla resumen
    st.dataframe(rev_df.style.format({"Revenue":"${:,.2f}","Impresiones":"{:,.0f}"}),
        use_container_width=True, hide_index=True)

# ── GRÁFICO 3: Formatos ───────────────────────────────────────────────────────
sh("📐 Formatos · Ad Manager")
gam_fmt = gam["formatos"]
if not gam_fmt.empty and "CREATIVE_SIZE" in gam_fmt.columns:
    col_map = {
        "CREATIVE_SIZE":"Formato",
        "AD_SERVER_IMPRESSIONS":"Impresiones",
        "AD_SERVER_CLICKS":"Clicks",
        "AD_SERVER_CTR":"CTR",
        "AD_SERVER_WITHOUT_CPD_AVERAGE_ECPM":"eCPM Promedio",
        "AD_SERVER_CPM_AND_CPC_REVENUE":"Revenue"
    }
    show = {k:v for k,v in col_map.items() if k in gam_fmt.columns}
    fmt_show = gam_fmt[list(show.keys())].rename(columns=show)
    if "Impresiones" in fmt_show.columns:
        fmt_show = fmt_show.sort_values("Impresiones", ascending=False)
    num_fmt = {}
    for col in fmt_show.select_dtypes("number").columns:
        if col in ["Revenue","eCPM Promedio"]: num_fmt[col] = "${:,.2f}"
        elif col == "CTR": num_fmt[col] = "{:.4f}"
        else: num_fmt[col] = "{:,.0f}"
    st.dataframe(fmt_show.style.format(num_fmt), use_container_width=True, hide_index=True)

    if "Impresiones" in fmt_show.columns:
        fig3 = px.bar(fmt_show.head(10), x="Impresiones", y="Formato", orientation="h",
            color="Impresiones", color_continuous_scale=["#1a1a3e","#6366f1"],
            text="Impresiones")
        fig3.update_traces(texttemplate="%{text:,.0f}", textposition="outside", textfont_size=9)
        fig3.update_layout(yaxis=dict(autorange="reversed"), coloraxis_showscale=False, yaxis_title="")
        _fig(fig3, 350)
        st.plotly_chart(fig3, use_container_width=True)

# ── AdSense detalle ────────────────────────────────────────────────────────────
if "AdSense" in plataformas and not as_f.empty:
    sh("💡 AdSense · Evolución Mensual")
    if "Date" in as_f.columns:
        asc = as_f.copy()
        asc["mes"] = asc["Date"].dt.to_period("M").astype(str)
        ag = {}
        if "Estimated earnings (USD)" in asc.columns: ag["Estimated earnings (USD)"] = "sum"
        if "Impressions" in asc.columns: ag["Impressions"] = "sum"
        if "Clicks" in asc.columns: ag["Clicks"] = "sum"
        if ag:
            as_m = asc.groupby("mes").agg(ag).reset_index()
            fig_as = go.Figure()
            if "Estimated earnings (USD)" in as_m.columns:
                fig_as.add_trace(go.Bar(x=as_m["mes"], y=as_m["Estimated earnings (USD)"],
                    name="Revenue USD", marker_color=C[3]))
            if "Impressions" in as_m.columns:
                fig_as.add_trace(go.Scatter(x=as_m["mes"], y=as_m["Impressions"],
                    name="Impresiones", mode="lines+markers",
                    line=dict(color=C[1], width=2), yaxis="y2"))
            fig_as.update_layout(yaxis2=dict(overlaying="y",side="right",showgrid=False),
                                  title="AdSense Revenue e Impresiones Mensuales")
            _fig(fig_as, 300)
            st.plotly_chart(fig_as, use_container_width=True)

# ── MGID detalle ───────────────────────────────────────────────────────────────
if "MGID" in plataformas and not mg_f.empty:
    sh("📊 MGID · Detalle")
    col_map2 = {"Date":"Fecha","Page views":"Page Views","Revenue":"Revenue",
                "Ad Clicks":"Clicks","Ad RPM":"RPM","Ad vRPM":"vRPM",
                "Views with visibility":"Vistas con Visibilidad"}
    show2 = {k:v for k,v in col_map2.items() if k in mg_f.columns}
    mg_show = mg_f[list(show2.keys())].rename(columns=show2)
    if "Fecha" in mg_show.columns:
        mg_show = mg_show.sort_values("Fecha", ascending=False)
    num_fmt2 = {}
    if "Revenue" in mg_show.columns: num_fmt2["Revenue"] = "${:,.3f}"
    if "RPM" in mg_show.columns: num_fmt2["RPM"] = "${:,.3f}"
    st.dataframe(mg_show.style.format(num_fmt2), use_container_width=True, hide_index=True, height=300)
