import sys, os; sys.path.insert(0, os.getcwd())
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta
from data_loader import load_adsense, load_mgid, load_admanager, load_youtube, filter_by_date, fmt_number, safe_sum, get_date_range, pct_delta

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
def _s(df, col): return safe_sum(df, col)

st.markdown('<div class="page-title">💰 Ads y Monetización</div>', unsafe_allow_html=True)
st.markdown('<div class="page-subtitle">AdSense · MGID · Ad Manager · YouTube Revenue</div>', unsafe_allow_html=True)

# ── Carga ─────────────────────────────────────────────────────────────────────
adsense = load_adsense()
mgid    = load_mgid()
gam     = load_admanager()
yt      = load_youtube()

# YouTube: "grafico" ahora es el mismo df que "tabla" (con columna "Fecha")
yt_gr_raw = yt.get("grafico", pd.DataFrame())
yt_tb_raw = yt.get("tabla",   pd.DataFrame())

# Detectar columna de fecha en YouTube
# Primero buscar "Fecha" (alias creado en data_loader),
# luego el nombre original con tilde
yt_date_col = None
for c in ["Fecha", "Hora de publicación del vídeo", "DATE", "Date"]:
    if not yt_gr_raw.empty and c in yt_gr_raw.columns:
        yt_date_col = c
        break

# Detectar columna de revenue en YouTube
yt_rev_col = None
for c in ["Ingresos estimados (USD)", "Revenue (USD)", "Estimated revenue (USD)", "Ingresos estimados", "Ingresos"]:
    if not yt_gr_raw.empty and c in yt_gr_raw.columns:
        yt_rev_col = c
        break

# Detectar columna de visualizaciones en YouTube
yt_views_col = None
for c in ["Visualizaciones", "Views", "Vistas"]:
    if not yt_gr_raw.empty and c in yt_gr_raw.columns:
        yt_views_col = c
        break

# ── Rango de fechas global ────────────────────────────────────────────────────
all_dates = []
for df, col in [(adsense,"Date"),(mgid,"Date"),(gam["diario"],"DATE")]:
    if not df.empty and col in df.columns:
        all_dates += pd.to_datetime(df[col], errors="coerce").dropna().tolist()
if yt_date_col and not yt_gr_raw.empty:
    all_dates += pd.to_datetime(yt_gr_raw[yt_date_col], errors="coerce").dropna().tolist()

min_d = min(all_dates).date() if all_dates else date(2024,1,1)
max_d = max(all_dates).date() if all_dates else date.today()

# ── FILTROS ───────────────────────────────────────────────────────────────────
sh("⚙️ Filtros")
st.markdown('<div class="filter-box">', unsafe_allow_html=True)
fc1, fc2, fc3 = st.columns(3)
with fc1: start = st.date_input("📅 Desde", max_d-timedelta(days=90), min_value=min_d, max_value=max_d, key="gs")
with fc2: end   = st.date_input("📅 Hasta", max_d, min_value=min_d, max_value=max_d, key="ads_e")
with fc3:
    plataformas = st.multiselect("💳 Plataforma",
        ["AdSense","MGID","Ad Manager","YouTube"],
        default=["AdSense","MGID","Ad Manager","YouTube"])
st.markdown('</div>', unsafe_allow_html=True)

# ── Filtrar por fecha ─────────────────────────────────────────────────────────
as_f = filter_by_date(adsense,       "Date", start, end) if "AdSense"    in plataformas else pd.DataFrame()
mg_f = filter_by_date(mgid,          "Date", start, end) if "MGID"       in plataformas else pd.DataFrame()
gd_f = filter_by_date(gam["diario"], "DATE", start, end) if "Ad Manager" in plataformas else pd.DataFrame()

# YouTube: filtrar por "Fecha" (columna datetime parseada en data_loader)
yt_gr = pd.DataFrame()
if "YouTube" in plataformas and yt_date_col and not yt_gr_raw.empty:
    yt_gr = filter_by_date(yt_gr_raw, yt_date_col, start, end)

# ── Períodos anteriores ───────────────────────────────────────────────────────
pd_    = (end - start).days or 1
ps, pe = start - timedelta(days=pd_), start - timedelta(days=1)
as_p   = filter_by_date(adsense,       "Date", ps, pe)
mg_p   = filter_by_date(mgid,          "Date", ps, pe)
gd_p   = filter_by_date(gam["diario"], "DATE", ps, pe)
yt_gr_p = filter_by_date(yt_gr_raw, yt_date_col, ps, pe) if yt_date_col and not yt_gr_raw.empty else pd.DataFrame()

# ── Calcular métricas ─────────────────────────────────────────────────────────
rev_as   = _s(as_f,   "Estimated earnings (USD)")
rev_mg   = _s(mg_f,   "Revenue")
rev_gam  = _s(gd_f,   "AD_SERVER_CPM_AND_CPC_REVENUE")
rev_yt   = _s(yt_gr,   yt_rev_col) if yt_rev_col and not yt_gr.empty   else 0
rev_yt_p = _s(yt_gr_p, yt_rev_col) if yt_rev_col and not yt_gr_p.empty else 0

rev_tot   = rev_as + rev_mg + rev_gam + rev_yt
rev_tot_p = (_s(as_p,"Estimated earnings (USD)") + _s(mg_p,"Revenue")
             + _s(gd_p,"AD_SERVER_CPM_AND_CPC_REVENUE") + rev_yt_p)

impr_as  = int(_s(as_f, "Impressions"))
impr_mg  = int(_s(mg_f, "Page views"))
impr_gam = int(_s(gd_f, "AD_SERVER_IMPRESSIONS"))
impr_yt  = int(_s(yt_gr, yt_views_col)) if yt_views_col and not yt_gr.empty else 0
tot_impr   = impr_as + impr_mg + impr_gam
tot_impr_p = int(_s(as_p,"Impressions")) + int(_s(gd_p,"AD_SERVER_IMPRESSIONS"))

cl_as  = int(_s(as_f, "Clicks"))
cl_mg  = int(_s(mg_f, "Ad Clicks"))
cl_gam = int(_s(gd_f, "AD_SERVER_CLICKS"))
tot_cl   = cl_as + cl_mg + cl_gam
tot_cl_p = int(_s(as_p,"Clicks")) + int(_s(gd_p,"AD_SERVER_CLICKS"))

cpms = []
if not as_f.empty  and "Impression RPM (USD)"               in as_f.columns  and impr_as  > 0: cpms.append((_s(as_f,  "Impression RPM (USD)"),                impr_as))
if not gd_f.empty  and "AD_SERVER_WITHOUT_CPD_AVERAGE_ECPM" in gd_f.columns  and impr_gam > 0: cpms.append((_s(gd_f,  "AD_SERVER_WITHOUT_CPD_AVERAGE_ECPM"),  impr_gam))
if not mg_f.empty  and "Ad RPM"                             in mg_f.columns  and impr_mg  > 0: cpms.append((_s(mg_f,  "Ad RPM"),                              impr_mg))
cpm_avg = sum(v/max(w,1)*w for v,w in cpms) / max(sum(w for _,w in cpms), 1) if cpms else 0
ctr_gam = gd_f["AD_SERVER_CTR"].mean()*100 if not gd_f.empty and "AD_SERVER_CTR" in gd_f.columns else 0

# ── MÉTRICAS ──────────────────────────────────────────────────────────────────
sh("📊 Métricas Generales")
m1,m2,m3,m4,m5 = st.columns(5)
m1.metric("💵 Revenue Total",   f"${rev_tot:,.2f}",   _delta(rev_tot,  rev_tot_p))
m2.metric("📈 CPM Promedio",    f"${cpm_avg:.2f}")
m3.metric("👁 Impresiones Ads", fmt_number(tot_impr), _delta(tot_impr, tot_impr_p))
m4.metric("🖱️ Clicks Totales",  fmt_number(tot_cl),   _delta(tot_cl,   tot_cl_p))
m5.metric("📊 CTR Ad Manager",  f"{ctr_gam:.2f}%")

# ── TABLA RESUMEN ─────────────────────────────────────────────────────────────
sh("📊 Resumen por Plataforma")
rows = []
if "AdSense"    in plataformas and not as_f.empty:     rows.append({"Plataforma":"AdSense",    "Revenue":rev_as,  "Impresiones":impr_as,  "Clicks":cl_as,  "CPM":_s(as_f,"Impression RPM (USD)")})
if "MGID"       in plataformas and not mg_f.empty:     rows.append({"Plataforma":"MGID",       "Revenue":rev_mg,  "Impresiones":impr_mg,  "Clicks":cl_mg,  "CPM":_s(mg_f,"Ad RPM")})
if "Ad Manager" in plataformas and not gd_f.empty:     rows.append({"Plataforma":"Ad Manager", "Revenue":rev_gam, "Impresiones":impr_gam, "Clicks":cl_gam, "CPM":_s(gd_f,"AD_SERVER_WITHOUT_CPD_AVERAGE_ECPM")})
if "YouTube"    in plataformas and not yt_gr_raw.empty: rows.append({"Plataforma":"YouTube",   "Revenue":rev_yt,  "Impresiones":impr_yt,  "Clicks":0,      "CPM":0})
if rows:
    r_df = pd.DataFrame(rows)
    st.dataframe(r_df.style.format({"Revenue":"${:,.2f}","Impresiones":"{:,.0f}","Clicks":"{:,.0f}","CPM":"${:,.3f}"}),
        use_container_width=True, hide_index=True)

# ── G1: Revenue por plataforma ────────────────────────────────────────────────
sh("💰 Revenue por Plataforma")
if rows:
    r_df2 = pd.DataFrame([r for r in rows if r["Revenue"] > 0])
    if not r_df2.empty:
        g1, g2 = st.columns(2)
        with g1:
            fb = px.bar(r_df2, x="Plataforma", y="Revenue", text="Revenue",
                color="Plataforma", color_discrete_sequence=C)
            fb.update_traces(texttemplate="$%{text:,.2f}", textposition="outside", textfont_size=10)
            fb.update_layout(showlegend=False); _fig(fb,300); st.plotly_chart(fb,use_container_width=True)
        with g2:
            fp = px.pie(r_df2, names="Plataforma", values="Revenue",
                color_discrete_sequence=C, hole=0.52)
            fp.update_traces(textposition="inside", textinfo="percent+label", textfont_size=12)
            fp.update_layout(showlegend=False); _fig(fp,300); st.plotly_chart(fp,use_container_width=True)

# ── G2: Evolución mensual combinada ───────────────────────────────────────────
sh("📈 Evolución Mensual · Revenue Combinado")
frames = []
for df_, dcol, plat, col_rev in [
    (as_f, "Date",  "AdSense",    "Estimated earnings (USD)"),
    (mg_f, "Date",  "MGID",       "Revenue"),
    (gd_f, "DATE",  "Ad Manager", "AD_SERVER_CPM_AND_CPC_REVENUE"),
]:
    if not df_.empty and dcol in df_.columns and col_rev in df_.columns:
        t = df_.copy(); t["mes"] = pd.to_datetime(t[dcol], errors="coerce").dt.to_period("M").astype(str)
        tmp = t.groupby("mes")[col_rev].sum().reset_index()
        tmp.columns = ["mes","Revenue"]; tmp["Plataforma"] = plat
        frames.append(tmp)

if "YouTube" in plataformas and not yt_gr.empty and yt_date_col and yt_rev_col:
    t = yt_gr.copy()
    t["mes"] = pd.to_datetime(t[yt_date_col], errors="coerce").dt.to_period("M").astype(str)
    tmp = t.groupby("mes")[yt_rev_col].sum().reset_index()
    tmp.columns = ["mes","Revenue"]; tmp["Plataforma"] = "YouTube"
    frames.append(tmp)

if frames:
    comb = pd.concat(frames, ignore_index=True)
    fe = px.bar(comb, x="mes", y="Revenue", color="Plataforma", barmode="stack",
        color_discrete_sequence=C, text="Revenue")
    fe.update_traces(texttemplate="$%{text:,.2f}", textposition="inside", textfont_size=9)
    fe.update_layout(legend=dict(orientation="h",y=1.12), yaxis_tickprefix="$")
    _fig(fe,340); st.plotly_chart(fe,use_container_width=True)

# ── G3: Impresiones vs Sin rellenar · Ad Manager ─────────────────────────────
if "Ad Manager" in plataformas and not gd_f.empty and "DATE" in gd_f.columns:
    sh("📊 Impresiones vs Sin Rellenar · Ad Manager")
    gm = gd_f.copy(); gm["mes"] = gm["DATE"].dt.to_period("M").astype(str)
    ag = {}
    if "AD_SERVER_IMPRESSIONS"             in gm.columns: ag["AD_SERVER_IMPRESSIONS"]             = "sum"
    if "TOTAL_LINE_ITEM_LEVEL_IMPRESSIONS" in gm.columns: ag["TOTAL_LINE_ITEM_LEVEL_IMPRESSIONS"] = "sum"
    if ag:
        gam_m = gm.groupby("mes").agg(ag).reset_index()
        if "TOTAL_LINE_ITEM_LEVEL_IMPRESSIONS" in gam_m.columns and "AD_SERVER_IMPRESSIONS" in gam_m.columns:
            gam_m["Sin rellenar"] = (gam_m["TOTAL_LINE_ITEM_LEVEL_IMPRESSIONS"] - gam_m["AD_SERVER_IMPRESSIONS"]).clip(lower=0)
        fi = go.Figure()
        if "AD_SERVER_IMPRESSIONS" in gam_m.columns:
            fi.add_trace(go.Scatter(x=gam_m["mes"], y=gam_m["AD_SERVER_IMPRESSIONS"],
                name="Servidas", mode="lines+markers", line=dict(color=C[0],width=3), marker=dict(size=7)))
        if "Sin rellenar" in gam_m.columns:
            fi.add_trace(go.Scatter(x=gam_m["mes"], y=gam_m["Sin rellenar"],
                name="Sin rellenar", mode="lines+markers", line=dict(color=C[4],width=2.5,dash="dash"), marker=dict(size=6)))
        fi.update_layout(legend=dict(orientation="h",y=1.12))
        _fig(fi,300); st.plotly_chart(fi,use_container_width=True)

# ── G4: Formatos Ad Manager ───────────────────────────────────────────────────
if "Ad Manager" in plataformas:
    sh("📐 Formatos · Ad Manager")
    gam_fmt = gam["formatos"]
    if not gam_fmt.empty and "CREATIVE_SIZE" in gam_fmt.columns:
        col_map = {"CREATIVE_SIZE":"Formato","AD_SERVER_IMPRESSIONS":"Impresiones",
                   "AD_SERVER_CLICKS":"Clicks","AD_SERVER_CTR":"CTR",
                   "AD_SERVER_WITHOUT_CPD_AVERAGE_ECPM":"eCPM","AD_SERVER_CPM_AND_CPC_REVENUE":"Revenue"}
        show = {k:v for k,v in col_map.items() if k in gam_fmt.columns}
        fd2  = gam_fmt[list(show.keys())].rename(columns=show)
        if "Impresiones" in fd2.columns: fd2 = fd2.sort_values("Impresiones", ascending=False)
        nf = {"Impresiones":"{:,.0f}","Clicks":"{:,.0f}","CTR":"{:.4f}","Revenue":"${:,.2f}","eCPM":"${:,.2f}"}
        st.dataframe(fd2.style.format({k:v for k,v in nf.items() if k in fd2.columns}), use_container_width=True, hide_index=True)
        if "Impresiones" in fd2.columns:
            ff = px.bar(fd2.head(10), x="Impresiones", y="Formato", orientation="h",
                color="Impresiones", color_continuous_scale=["#14143a","#6366f1"], text="Impresiones")
            ff.update_traces(texttemplate="%{text:,.0f}", textposition="outside", textfont_size=9)
            ff.update_layout(yaxis=dict(autorange="reversed"), coloraxis_showscale=False, yaxis_title="")
            _fig(ff,320); st.plotly_chart(ff,use_container_width=True)

# ── G5: AdSense mensual ───────────────────────────────────────────────────────
if "AdSense" in plataformas and not as_f.empty and "Date" in as_f.columns:
    sh("💡 AdSense · Evolución Mensual")
    ac = as_f.copy(); ac["mes"] = ac["Date"].dt.to_period("M").astype(str)
    ag2 = {}
    if "Estimated earnings (USD)" in ac.columns: ag2["Estimated earnings (USD)"] = "sum"
    if "Impressions"              in ac.columns: ag2["Impressions"]              = "sum"
    if "Clicks"                   in ac.columns: ag2["Clicks"]                   = "sum"
    if ag2:
        as_m = ac.groupby("mes").agg(ag2).reset_index()
        fa = go.Figure()
        if "Estimated earnings (USD)" in as_m.columns:
            fa.add_trace(go.Bar(x=as_m["mes"], y=as_m["Estimated earnings (USD)"],
                name="Revenue USD", marker_color=C[3]))
        if "Impressions" in as_m.columns:
            fa.add_trace(go.Scatter(x=as_m["mes"], y=as_m["Impressions"],
                name="Impresiones", mode="lines+markers", line=dict(color=C[1],width=2), yaxis="y2"))
        fa.update_layout(yaxis2=dict(overlaying="y",side="right",showgrid=False),
            legend=dict(orientation="h",y=1.12), yaxis_tickprefix="$")
        _fig(fa,300); st.plotly_chart(fa,use_container_width=True)

# ── G6: MGID detalle ──────────────────────────────────────────────────────────
if "MGID" in plataformas and not mg_f.empty:
    sh("📊 MGID · Detalle del Período")
    cm = {"Date":"Fecha","Page views":"Page Views","Revenue":"Revenue",
          "Ad Clicks":"Clicks","Ad RPM":"RPM","Ad vRPM":"vRPM","Views with visibility":"Vistas Visibles"}
    s2   = {k:v for k,v in cm.items() if k in mg_f.columns}
    mg_s = mg_f[list(s2.keys())].rename(columns=s2)
    if "Fecha" in mg_s.columns: mg_s = mg_s.sort_values("Fecha", ascending=False)
    nf2 = {}
    if "Revenue" in mg_s.columns: nf2["Revenue"] = "${:,.3f}"
    if "RPM"     in mg_s.columns: nf2["RPM"]     = "${:,.3f}"
    if "vRPM"    in mg_s.columns: nf2["vRPM"]    = "${:,.3f}"
    st.dataframe(mg_s.style.format(nf2), use_container_width=True, hide_index=True, height=300)

# ── G7: YouTube · Evolución mensual ───────────────────────────────────────────
if "YouTube" in plataformas:
    sh("▶️ YouTube · Evolución Mensual")
    if yt_gr_raw.empty or not yt_date_col:
        st.info("Sin datos de YouTube disponibles.")
    elif yt_gr.empty:
        st.info("Sin datos de YouTube para el período seleccionado.")
    else:
        ytc = yt_gr.copy()
        ytc["mes"] = pd.to_datetime(ytc[yt_date_col], errors="coerce").dt.to_period("M").astype(str)
        ag_yt = {}
        if yt_views_col and yt_views_col in ytc.columns: ag_yt[yt_views_col] = "sum"
        if yt_rev_col   and yt_rev_col   in ytc.columns: ag_yt[yt_rev_col]   = "sum"
        if ag_yt:
            yt_m = ytc.groupby("mes").agg(ag_yt).reset_index()
            fyt  = go.Figure()
            if yt_views_col and yt_views_col in yt_m.columns:
                fyt.add_trace(go.Bar(x=yt_m["mes"], y=yt_m[yt_views_col],
                    name="Visualizaciones", marker_color=C[4], opacity=0.7))
            if yt_rev_col and yt_rev_col in yt_m.columns:
                fyt.add_trace(go.Scatter(x=yt_m["mes"], y=yt_m[yt_rev_col],
                    name="Revenue", mode="lines+markers",
                    line=dict(color=C[3],width=2.5), yaxis="y2", marker=dict(size=7)))
            fyt.update_layout(
                barmode="overlay",
                yaxis2=dict(overlaying="y", side="right", showgrid=False,
                            tickprefix="$", tickfont=dict(color=C[3])),
                legend=dict(orientation="h", y=1.12))
            _fig(fyt,300); st.plotly_chart(fyt,use_container_width=True)

# ── G8: Dispositivos Ad Manager ───────────────────────────────────────────────
if "Ad Manager" in plataformas:
    sh("📱 Dispositivos · Ad Manager")
    gd = gam["devices"]
    if not gd.empty and "DEVICE_CATEGORY_NAME" in gd.columns:
        gd1, gd2 = st.columns(2)
        with gd1:
            vcol = "AD_SERVER_IMPRESSIONS" if "AD_SERVER_IMPRESSIONS" in gd.columns else gd.columns[2]
            fd3  = px.pie(gd, names="DEVICE_CATEGORY_NAME", values=vcol,
                color_discrete_sequence=C, hole=0.52)
            fd3.update_traces(textposition="inside", textinfo="percent+label", textfont_size=12)
            fd3.update_layout(showlegend=False); _fig(fd3,280); st.plotly_chart(fd3,use_container_width=True)
        with gd2:
            dm = {"DEVICE_CATEGORY_NAME":"Dispositivo","AD_SERVER_IMPRESSIONS":"Impresiones",
                  "AD_SERVER_CLICKS":"Clicks","AD_SERVER_CPM_AND_CPC_REVENUE":"Revenue",
                  "AD_SERVER_WITHOUT_CPD_AVERAGE_ECPM":"eCPM"}
            ds   = {k:v for k,v in dm.items() if k in gd.columns}
            gd_s = gd[list(ds.keys())].rename(columns=ds)
            nf3  = {}
            if "Impresiones" in gd_s.columns: nf3["Impresiones"] = "{:,.0f}"
            if "Revenue"     in gd_s.columns: nf3["Revenue"]     = "${:,.2f}"
            if "eCPM"        in gd_s.columns: nf3["eCPM"]        = "${:,.2f}"
            st.dataframe(gd_s.style.format(nf3), use_container_width=True, hide_index=True)
