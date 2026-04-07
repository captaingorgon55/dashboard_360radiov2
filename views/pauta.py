import sys, os; sys.path.insert(0, os.getcwd())
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta
from data_loader import load_admanager, load_viads, filter_by_date, fmt_number, safe_sum, get_date_range, pct_delta

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

st.markdown('<div class="page-title">📣 Pauta</div>', unsafe_allow_html=True)
st.markdown('<div class="page-subtitle">Campañas · Orders · Line Items · Fill Rate · Ad Manager</div>', unsafe_allow_html=True)

# ── Carga ─────────────────────────────────────────────────────────────────────
gam    = load_admanager()
diario = gam["diario"]
orders = gam["orders"]
fill   = gam["fill"]
viads  = load_viads()

min_d, max_d = get_date_range(diario, "DATE")

# ── FILTROS ───────────────────────────────────────────────────────────────────
sh("⚙️ Filtros")
st.markdown('<div class="filter-box">', unsafe_allow_html=True)
fc1, fc2, fc3, fc4 = st.columns(4)
with fc1: start = st.date_input("📅 Desde", max_d - timedelta(days=90), min_value=min_d, max_value=max_d, key="gs")
with fc2: end   = st.date_input("📅 Hasta", max_d, min_value=min_d, max_value=max_d, key="pau_e")

camp_opts = ["Todas"]
if not orders.empty and "ORDER_NAME" in orders.columns:
    camp_opts += sorted(orders["ORDER_NAME"].dropna().unique().tolist())
with fc3: sel_camp = st.selectbox("📢 Campaña", camp_opts, key="pau_camp")

# Opciones de Ad Unit: combinar fill + diario para mayor cobertura
unit_opts = ["Todas"]
all_units = set()
if not fill.empty and "AD_UNIT_NAME" in fill.columns:
    all_units.update(fill["AD_UNIT_NAME"].dropna().unique().tolist())
if not diario.empty and "AD_UNIT_NAME" in diario.columns:
    all_units.update(diario["AD_UNIT_NAME"].dropna().unique().tolist())
unit_opts += sorted(all_units)
with fc4: sel_unit = st.selectbox("📦 Ad Unit", unit_opts, key="pau_unit")
st.markdown('</div>', unsafe_allow_html=True)

# ── Filtrar por fecha ─────────────────────────────────────────────────────────
diario_f = filter_by_date(diario, "DATE", start, end)
fill_f   = filter_by_date(fill,   "DATE", start, end)
pd_      = (end - start).days or 1
diario_p = filter_by_date(diario, "DATE", start - timedelta(days=pd_), start - timedelta(days=1))

# ── Filtro Ad Unit → diario_f, diario_p, fill_f ───────────────────────────────
diario_tiene_unit = "AD_UNIT_NAME" in diario.columns
if sel_unit != "Todas":
    # fill_f siempre se puede filtrar por unit
    if not fill_f.empty and "AD_UNIT_NAME" in fill_f.columns:
        fill_f = fill_f[fill_f["AD_UNIT_NAME"] == sel_unit]
    # diario_f y diario_p solo si tienen la columna
    if diario_tiene_unit:
        if not diario_f.empty:
            diario_f = diario_f[diario_f["AD_UNIT_NAME"] == sel_unit]
        if not diario_p.empty:
            diario_p = diario_p[diario_p["AD_UNIT_NAME"] == sel_unit]
    else:
        st.warning(
            "⚠️ **GAM_Diario** no contiene la dimensión `AD_UNIT_NAME`. "
            "Las métricas de Impresiones/Revenue/CTR reflejan el total global. "
            "El filtro de Ad Unit aplica únicamente en la sección de Fill Rate.",
            icon="⚠️"
        )

# ── Filtro Campaña → orders_f ─────────────────────────────────────────────────
orders_f = orders.copy() if not orders.empty else pd.DataFrame()
if sel_camp != "Todas" and not orders_f.empty and "ORDER_NAME" in orders_f.columns:
    orders_f = orders_f[orders_f["ORDER_NAME"] == sel_camp]

# ── Captions de filtros activos ───────────────────────────────────────────────
if sel_camp != "Todas":
    st.caption(f"📢 Filtrando por campaña: **{sel_camp}**")
if sel_unit != "Todas":
    st.caption(f"📦 Ad Unit: **{sel_unit}**")

# ══════════════════════════════════════════════════════════════════════════════
# MÉTRICAS: si hay filtro de campaña → desde orders_f; si no → desde diario_f
# ══════════════════════════════════════════════════════════════════════════════
has_camp = sel_camp != "Todas" and not orders_f.empty

def _si(df, col): return int(safe_sum(df, col))
def _sf(df, col): return float(safe_sum(df, col))

if has_camp:
    impr   = _si(orders_f, "AD_SERVER_IMPRESSIONS")
    clicks = _si(orders_f, "AD_SERVER_CLICKS")
    rev    = _sf(orders_f, "AD_SERVER_CPM_AND_CPC_REVENUE")
    fill_i = impr  # aproximado desde orders
    ctr    = orders_f["AD_SERVER_CTR"].mean() * 100 if not orders_f.empty and "AD_SERVER_CTR" in orders_f.columns else 0
    impr_p = clicks_p = rev_p = fill_i_p = 0
else:
    impr   = _si(diario_f, "AD_SERVER_IMPRESSIONS")
    fill_i = _si(diario_f, "TOTAL_LINE_ITEM_LEVEL_IMPRESSIONS")
    clicks = _si(diario_f, "AD_SERVER_CLICKS")
    rev    = _sf(diario_f, "AD_SERVER_CPM_AND_CPC_REVENUE")
    ctr    = diario_f["AD_SERVER_CTR"].mean() * 100 if not diario_f.empty and "AD_SERVER_CTR" in diario_f.columns else 0
    impr_p   = _si(diario_p, "AD_SERVER_IMPRESSIONS")
    fill_i_p = _si(diario_p, "TOTAL_LINE_ITEM_LEVEL_IMPRESSIONS")
    clicks_p = _si(diario_p, "AD_SERVER_CLICKS")
    rev_p    = _sf(diario_p, "AD_SERVER_CPM_AND_CPC_REVENUE")

# ── MÉTRICAS ──────────────────────────────────────────────────────────────────
sh("📊 Métricas del Período")
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("📢 Impresiones",      fmt_number(impr),   _delta(impr, impr_p)     if not has_camp else None)
m2.metric("🎯 Total Line Items", fmt_number(fill_i), _delta(fill_i, fill_i_p) if not has_camp else None)
m3.metric("🖱️ Clicks",           fmt_number(clicks), _delta(clicks, clicks_p) if not has_camp else None)
m4.metric("💵 Revenue",          f"${rev:,.2f}",     _delta(rev, rev_p)       if not has_camp else None)
m5.metric("📈 CTR",              f"{ctr:.2f}%")

# ── G1: Evolución mensual ─────────────────────────────────────────────────────
sh("📈 Evolución Mensual · Impresiones y Revenue")

# Si hay filtro de Ad Unit y diario no tiene esa columna,
# intentar usar fill_f como fuente alternativa para el gráfico
if sel_unit != "Todas" and not diario_tiene_unit and not fill_f.empty and "AD_SERVER_IMPRESSIONS" in fill_f.columns:
    src_evol = fill_f.rename(columns={"DATE": "DATE"})
    st.caption("ℹ️ Gráfico usando GAM_Fill_Rate como fuente (filtrado por Ad Unit).")
else:
    src_evol = diario_f
    if sel_camp == "Todas" and sel_unit == "Todas":
        st.caption("ℹ️ Gráfico de evolución usa datos diarios globales. El filtro de campaña aplica en las tablas de abajo.")

if not src_evol.empty and "DATE" in src_evol.columns:
    dg = src_evol.copy()
    dg["mes"] = dg["DATE"].dt.to_period("M").astype(str)
    ag = {}
    if "AD_SERVER_IMPRESSIONS"             in dg.columns: ag["AD_SERVER_IMPRESSIONS"]             = "sum"
    if "TOTAL_LINE_ITEM_LEVEL_IMPRESSIONS" in dg.columns: ag["TOTAL_LINE_ITEM_LEVEL_IMPRESSIONS"] = "sum"
    if "AD_SERVER_CPM_AND_CPC_REVENUE"     in dg.columns: ag["AD_SERVER_CPM_AND_CPC_REVENUE"]     = "sum"
    if ag:
        mo = dg.groupby("mes").agg(ag).reset_index()
        fig1 = go.Figure()
        if "AD_SERVER_IMPRESSIONS" in mo.columns:
            fig1.add_trace(go.Bar(x=mo["mes"], y=mo["AD_SERVER_IMPRESSIONS"],
                name="Impresiones Servidas", marker_color=C[0], opacity=0.7))
        if "TOTAL_LINE_ITEM_LEVEL_IMPRESSIONS" in mo.columns:
            fig1.add_trace(go.Scatter(x=mo["mes"], y=mo["TOTAL_LINE_ITEM_LEVEL_IMPRESSIONS"],
                name="Total Line Items", mode="lines+markers",
                line=dict(color=C[1], width=2.5, dash="dash"), marker=dict(size=6)))
        if "AD_SERVER_CPM_AND_CPC_REVENUE" in mo.columns:
            fig1.add_trace(go.Scatter(x=mo["mes"], y=mo["AD_SERVER_CPM_AND_CPC_REVENUE"],
                name="Revenue", mode="lines+markers",
                line=dict(color=C[3], width=2), yaxis="y2", marker=dict(size=5)))
        fig1.update_layout(barmode="overlay",
            yaxis2=dict(overlaying="y", side="right", showgrid=False,
                        tickprefix="$", tickfont=dict(color=C[3])),
            legend=dict(orientation="h", y=1.12))
        _fig(fig1, 360)
        st.plotly_chart(fig1, use_container_width=True)
else:
    st.info("Sin datos de Ad Manager en el período.")

# ── G2: Campañas (orders) ─────────────────────────────────────────────────────
if not orders_f.empty:
    sh("📋 Campañas · Orders & Line Items")
    col_map = {
        "ORDER_NAME": "Campaña", "LINE_ITEM_NAME": "Line Item", "LINE_ITEM_TYPE": "Tipo",
        "AD_SERVER_IMPRESSIONS": "Impresiones", "AD_SERVER_CLICKS": "Clicks",
        "AD_SERVER_CPM_AND_CPC_REVENUE": "Revenue",
        "AD_SERVER_WITHOUT_CPD_AVERAGE_ECPM": "eCPM",
        "LINE_ITEM_START_DATE_TIME": "Inicio", "LINE_ITEM_END_DATE_TIME": "Fin"
    }
    show    = {k: v for k, v in col_map.items() if k in orders_f.columns}
    ord_s   = orders_f[list(show.keys())].rename(columns=show)
    nf = {}
    if "Impresiones" in ord_s.columns: nf["Impresiones"] = "{:,.0f}"
    if "Clicks"      in ord_s.columns: nf["Clicks"]      = "{:,.0f}"
    if "Revenue"     in ord_s.columns: nf["Revenue"]     = "${:,.2f}"
    if "eCPM"        in ord_s.columns: nf["eCPM"]        = "${:,.2f}"

    # Gráfico impresiones por campaña
    if "Campaña" in ord_s.columns and "Impresiones" in ord_s.columns:
        ca = ord_s.groupby("Campaña")["Impresiones"].sum().reset_index()\
                  .sort_values("Impresiones", ascending=False).head(15)
        f2 = px.bar(ca, x="Impresiones", y="Campaña", orientation="h",
            color="Impresiones", color_continuous_scale=["#14143a","#6366f1"], text="Impresiones")
        f2.update_traces(texttemplate="%{text:,.0f}", textposition="outside", textfont_size=9)
        f2.update_layout(yaxis=dict(autorange="reversed"), coloraxis_showscale=False, yaxis_title="")
        _fig(f2, max(280, len(ca) * 30 + 60))
        st.plotly_chart(f2, use_container_width=True)

    # Gráfico Revenue + Clicks por campaña
    if "Campaña" in ord_s.columns and len(orders_f) > 1:
        grp = {}
        if "Impresiones" in ord_s.columns: grp["Impresiones"] = "sum"
        if "Clicks"      in ord_s.columns: grp["Clicks"]      = "sum"
        if "Revenue"     in ord_s.columns: grp["Revenue"]     = "sum"
        if grp:
            cd = ord_s.groupby("Campaña").agg(grp).reset_index()\
                      .sort_values(list(grp.keys())[0], ascending=False).head(15)
            f3 = go.Figure()
            if "Impresiones" in cd.columns:
                f3.add_trace(go.Bar(x=cd["Campaña"], y=cd["Impresiones"], name="Impresiones", marker_color=C[0]))
            if "Clicks" in cd.columns:
                f3.add_trace(go.Bar(x=cd["Campaña"], y=cd["Clicks"], name="Clicks", marker_color=C[2]))
            if "Revenue" in cd.columns:
                f3.add_trace(go.Scatter(x=cd["Campaña"], y=cd["Revenue"], name="Revenue",
                    mode="lines+markers", line=dict(color=C[3], width=2.5),
                    yaxis="y2", marker=dict(size=7)))
            f3.update_layout(barmode="group",
                yaxis2=dict(overlaying="y", side="right", showgrid=False,
                            tickprefix="$", tickfont=dict(color=C[3])),
                xaxis=dict(tickangle=-30), legend=dict(orientation="h", y=1.12))
            _fig(f3, 420)
            st.plotly_chart(f3, use_container_width=True)

    # Tabla detalle
    sh("📄 Detalle de Line Items")
    srch = st.text_input("🔎 Buscar campaña o line item...", key="li_srch")
    od = ord_s.copy()
    if srch:
        mask = pd.Series(False, index=od.index)
        for col in ["Campaña", "Line Item"]:
            if col in od.columns:
                mask |= od[col].fillna("").str.contains(srch, case=False)
        od = od[mask]
    st.dataframe(od.style.format(nf), use_container_width=True, hide_index=True, height=400)
else:
    st.info("Sin datos de orders/line items.")

# ── G3: Fill Rate ─────────────────────────────────────────────────────────────
if not fill_f.empty and "FILL_RATE_%" in fill_f.columns and "DATE" in fill_f.columns:
    sh("📊 Fill Rate · Evolución Mensual")
    fc = fill_f.copy()
    fc["mes"] = fc["DATE"].dt.to_period("M").astype(str)
    fill_m  = fc.groupby("mes")["FILL_RATE_%"].mean().reset_index()
    avg_f   = fill_m["FILL_RATE_%"].mean()
    ff = px.line(fill_m, x="mes", y="FILL_RATE_%", markers=True, color_discrete_sequence=[C[2]])
    ff.update_traces(line_width=2.5, marker_size=7,
                     marker=dict(color=C[2], line=dict(color="#fff", width=1.5)))
    ff.add_hline(y=avg_f, line_dash="dot", line_color=C[3],
        annotation_text=f"Prom: {avg_f:.1f}%",
        annotation_font_color=C[3], annotation_font_size=11)
    ff.update_layout(yaxis_title="Fill Rate (%)", yaxis_ticksuffix="%")
    _fig(ff, 280)
    st.plotly_chart(ff, use_container_width=True)

    # Tabla fill rate por ad unit
    if "AD_UNIT_NAME" in fill_f.columns:
        sh("📦 Fill Rate por Unidad de Anuncio")
        agg_dict = {"Fill_Rate_Prom": ("FILL_RATE_%", "mean")}
        if "AD_SERVER_IMPRESSIONS" in fill_f.columns:
            agg_dict["Impresiones_Servidas"] = ("AD_SERVER_IMPRESSIONS", "sum")
        else:
            agg_dict["Registros"] = ("FILL_RATE_%", "count")
        u_agg = fill_f.groupby("AD_UNIT_NAME").agg(**agg_dict).reset_index()\
                      .sort_values("Fill_Rate_Prom", ascending=False)
        nf_u = {"Fill_Rate_Prom": "{:.1f}%"}
        if "Impresiones_Servidas" in u_agg.columns: nf_u["Impresiones_Servidas"] = "{:,.0f}"
        st.dataframe(
            u_agg.rename(columns={"AD_UNIT_NAME": "Ad Unit"}).style.format(nf_u),
            use_container_width=True, hide_index=True
        )
else:
    st.info("Sin datos de fill rate para el período.")

# ── G4: Mensual acumulado ─────────────────────────────────────────────────────
gam_men = gam["mensual"]
if not gam_men.empty and "YEAR_MONTH" in gam_men.columns:
    sh("📅 Resumen Mensual Acumulado")
    cm2 = {
        "YEAR_MONTH": "Mes", "AD_SERVER_IMPRESSIONS": "Impresiones",
        "AD_SERVER_CLICKS": "Clicks", "AD_SERVER_CPM_AND_CPC_REVENUE": "Revenue",
        "FILL_RATE_%": "Fill Rate %", "eCPM_CALCULADO": "eCPM", "CTR_CALCULADO": "CTR"
    }
    s3   = {k: v for k, v in cm2.items() if k in gam_men.columns}
    gm_s = gam_men[list(s3.keys())].rename(columns=s3)
    nf4  = {}
    if "Impresiones" in gm_s.columns: nf4["Impresiones"] = "{:,.0f}"
    if "Revenue"     in gm_s.columns: nf4["Revenue"]     = "${:,.2f}"
    if "Fill Rate %" in gm_s.columns: nf4["Fill Rate %"] = "{:.1f}%"
    if "eCPM"        in gm_s.columns: nf4["eCPM"]        = "${:,.2f}"
    st.dataframe(gm_s.style.format(nf4), use_container_width=True, hide_index=True)

# ── VIADS ─────────────────────────────────────────────────────────────────────
sh("📡 VIADS · Video Ads")
if viads.empty:
    st.info("Sin datos de VIADS. Coloca el archivo `statistics_*.csv` en la carpeta `data/`.")
else:
    viads_f  = filter_by_date(viads, "date", start, end)
    pd_v     = (end - start).days or 1
    viads_fp = filter_by_date(viads, "date", start - timedelta(days=pd_v), start - timedelta(days=1))

    if viads_f.empty:
        st.info("Sin datos de VIADS para el período seleccionado.")
    else:
        # Métricas
        v_impr  = int(safe_sum(viads_f, "impressions"))
        v_cl    = int(safe_sum(viads_f, "clicks"))
        v_inc   = float(safe_sum(viads_f, "income"))
        v_cpm   = float(viads_f["cpm"].mean()) if "cpm" in viads_f.columns else 0
        v_ctr   = float(viads_f["ctr"].mean()) if "ctr" in viads_f.columns else 0

        v_impr_p = int(safe_sum(viads_fp, "impressions"))
        v_cl_p   = int(safe_sum(viads_fp, "clicks"))
        v_inc_p  = float(safe_sum(viads_fp, "income"))

        vm1, vm2, vm3, vm4, vm5 = st.columns(5)
        vm1.metric("👁 Impresiones",  fmt_number(v_impr), _delta(v_impr, v_impr_p))
        vm2.metric("🖱️ Clicks",        fmt_number(v_cl),   _delta(v_cl,   v_cl_p))
        vm3.metric("💵 Ingresos",      f"${v_inc:,.2f}",   _delta(v_inc,  v_inc_p))
        vm4.metric("📊 CPM Promedio",  f"${v_cpm:.2f}")
        vm5.metric("📈 CTR Promedio",  f"{v_ctr:.2f}%")

        # Evolución mensual
        sh("📈 VIADS · Evolución Mensual")
        vd = viads_f.copy()
        vd["mes"] = vd["date"].dt.to_period("M").astype(str)
        ag_v = {}
        if "impressions" in vd.columns: ag_v["impressions"] = "sum"
        if "income"      in vd.columns: ag_v["income"]      = "sum"
        if "clicks"      in vd.columns: ag_v["clicks"]      = "sum"
        if ag_v:
            vm = vd.groupby("mes").agg(ag_v).reset_index()
            fv = go.Figure()
            if "impressions" in vm.columns:
                fv.add_trace(go.Bar(x=vm["mes"], y=vm["impressions"],
                    name="Impresiones", marker_color=C[1], opacity=0.7))
            if "income" in vm.columns:
                fv.add_trace(go.Scatter(x=vm["mes"], y=vm["income"],
                    name="Ingresos (USD)", mode="lines+markers",
                    line=dict(color=C[3], width=2.5), yaxis="y2", marker=dict(size=7)))
            fv.update_layout(
                yaxis2=dict(overlaying="y", side="right", showgrid=False,
                            tickprefix="$", tickfont=dict(color=C[3])),
                legend=dict(orientation="h", y=1.12))
            _fig(fv, 300)
            st.plotly_chart(fv, use_container_width=True)

        # Tabla diaria detalle
        sh("📄 VIADS · Detalle Diario")
        col_map_v = {
            "date": "Fecha", "impressions": "Impresiones", "clicks": "Clicks",
            "ctr": "CTR", "cpm": "CPM", "income": "Ingresos (USD)"
        }
        vd_show = viads_f[[c for c in col_map_v if c in viads_f.columns]].rename(columns=col_map_v)
        if "Fecha" in vd_show.columns:
            vd_show = vd_show.sort_values("Fecha", ascending=False)
        nf_v = {}
        if "Impresiones"   in vd_show.columns: nf_v["Impresiones"]   = "{:,.0f}"
        if "Clicks"        in vd_show.columns: nf_v["Clicks"]        = "{:,.0f}"
        if "CTR"           in vd_show.columns: nf_v["CTR"]           = "{:.2f}%"
        if "CPM"           in vd_show.columns: nf_v["CPM"]           = "${:.2f}"
        if "Ingresos (USD)" in vd_show.columns: nf_v["Ingresos (USD)"] = "${:,.2f}"
        st.dataframe(vd_show.style.format(nf_v), use_container_width=True, hide_index=True, height=350)
