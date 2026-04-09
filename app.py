import streamlit as st
import io
from datetime import datetime, date, timedelta

st.set_page_config(
    page_title="360Radio · Analytics",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=Inter:wght@300;400;500;600&display=swap');
html,body,[class*="css"]     { font-family:'Inter',sans-serif; }
h1,h2,h3,h4                  { font-family:'Syne',sans-serif; }
[data-testid="stSidebarNav"],section[data-testid="stSidebarNav"],
.st-emotion-cache-1cypcdb,ul[data-testid="stSidebarNavItems"]{ display:none !important; }
[data-testid="stSidebar"]{ background:#07071a !important;border-right:1px solid #18183a;width:220px !important; }
[data-testid="stSidebar"] *{ color:#b8c0e0 !important; }
.sb-logo{ font-family:'Syne',sans-serif;font-size:1.45rem;font-weight:800;
  background:linear-gradient(135deg,#6366f1 30%,#06b6d4);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;line-height:1.2; }
.sb-sub{ font-size:0.63rem;color:#2e3460 !important;text-transform:uppercase;letter-spacing:0.14em;margin-top:2px; }
.sb-divider{ border:none;border-top:1px solid #18183a;margin:12px 0; }
[data-testid="stSidebar"] .stRadio > div{ gap:2px; }
[data-testid="stSidebar"] .stRadio label{ display:flex;align-items:center;gap:10px;padding:9px 14px;
  border-radius:10px;cursor:pointer;font-size:0.82rem;font-weight:500;color:#7880a8 !important;
  transition:all .18s;border:1px solid transparent; }
[data-testid="stSidebar"] .stRadio label:hover{ background:#12123a;color:#c8d0f0 !important;border-color:#25254a; }
[data-testid="stSidebar"] .stRadio [data-baseweb="radio"] > div:first-child{ display:none; }
.main .block-container{ padding:1.4rem 2rem 2rem;max-width:1640px; }
.stApp{ background:#080814; }
[data-testid="stMetric"]{ background:linear-gradient(145deg,#0f0f28,#141438);border:1px solid #20204a;
  border-radius:14px;padding:1rem 1.2rem;transition:.2s; }
[data-testid="stMetric"]:hover{ border-color:#4f46e5;box-shadow:0 0 0 1px #4f46e5; }
[data-testid="stMetricValue"]{ color:#e8ecff !important;font-family:'Syne',sans-serif;
  font-size:1.7rem !important;font-weight:700 !important; }
[data-testid="stMetricLabel"]{ color:#4a5280 !important;font-size:0.67rem !important;
  text-transform:uppercase;letter-spacing:.1em; }
[data-testid="stMetricDelta"]{ font-size:0.77rem !important; }
.sec-hdr{ font-family:'Syne',sans-serif;font-size:0.82rem;font-weight:700;color:#818cf8;
  border-left:3px solid #4f46e5;padding:1px 0 1px 10px;margin:1.4rem 0 0.7rem;
  letter-spacing:0.06em;text-transform:uppercase; }
.filter-box{ background:#0c0c24;border:1px solid #1a1a36;border-radius:12px;
  padding:.9rem 1.1rem .4rem;margin-bottom:.9rem; }
.stTabs [data-baseweb="tab-list"]{ gap:2px;background:#0a0a1e;border-radius:10px;
  padding:3px;border:1px solid #181836; }
.stTabs [data-baseweb="tab"]{ border-radius:7px;color:#4a5280 !important;
  font-family:'Syne',sans-serif;font-weight:600;font-size:0.77rem;padding:6px 16px; }
.stTabs [aria-selected="true"]{ background:#4f46e5 !important;color:#fff !important; }
[data-testid="stDataFrame"]{ border-radius:10px;overflow:hidden;border:1px solid #1a1a36; }
.stProgress > div > div{ background:linear-gradient(90deg,#4f46e5,#06b6d4);border-radius:4px; }
.stAlert{ border-radius:10px; }
.page-title{ font-family:'Syne',sans-serif;font-size:1.55rem;font-weight:800;color:#e8ecff;margin-bottom:.15rem; }
.page-subtitle{ font-size:0.75rem;color:#3a4070;margin-bottom:1rem;letter-spacing:.06em; }
[data-testid="stSelectbox"] > div > div,
[data-testid="stDateInput"] input{ background:#0c0c24 !important;border-color:#20204a !important; }
hr{ border-color:#181836 !important;margin:.8rem 0 !important; }
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# PDF GENERATOR
# ═══════════════════════════════════════════════════════════════════════════════
def generate_report_pdf(start_date, end_date):
    import sys, os
    sys.path.insert(0, os.getcwd())

    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, PageBreak
    )
    import pandas as pd

    try:
        from data_loader import (
            load_ga4_general, load_ga4_city, load_ga4_country, load_ga4_channel,
            load_ga4_age, load_ga4_device, load_ga4_urls, load_produccion_con_metricas,
            load_search_console, load_adsense, load_mgid, load_admanager,
            load_youtube, load_instagram_posts, load_instagram_stories, load_facebook,
            load_viads, filter_by_date, fmt_number, safe_sum, pct_delta
        )
        DATA_OK = True
    except Exception as e:
        DATA_OK = False
        _err = str(e)

    s, e = start_date, end_date
    pd_d = max((e - s).days, 1)
    ps, pe = s - timedelta(days=pd_d), s - timedelta(days=1)

    def _fbd(df, col, a, b):
        try: return filter_by_date(df, col, a, b)
        except: return pd.DataFrame()

    def _si(df, col):
        try: return int(safe_sum(df, col))
        except: return 0

    def _sf(df, col):
        try: return float(safe_sum(df, col))
        except: return 0.0

    def _pct(cur, prev):
        try:
            d = pct_delta(cur, prev)
            return f"{d:+.1f}%" if d is not None else "—"
        except: return "—"

    def _fmt(v):
        try: return fmt_number(v)
        except: return str(v)

    # ── Colores ───────────────────────────────────────────────────────────────
    INDIGO  = colors.HexColor("#4f46e5")
    CYAN    = colors.HexColor("#06b6d4")
    DARK    = colors.HexColor("#080814")
    CARD    = colors.HexColor("#0f0f28")
    CARD2   = colors.HexColor("#12122e")
    BOR     = colors.HexColor("#20204a")
    BOR2    = colors.HexColor("#18183a")
    LIGHT   = colors.HexColor("#e8ecff")
    MID     = colors.HexColor("#818cf8")
    DIM     = colors.HexColor("#4a5280")
    GREEN   = colors.HexColor("#10b981")
    RED     = colors.HexColor("#ef4444")
    WHITE   = colors.white

    W, H = A4
    MG = 15 * mm
    UW = W - 2 * MG
    gen_ts  = datetime.now().strftime("%d/%m/%Y %H:%M")
    per_str = f"{s.strftime('%d/%m/%Y')} – {e.strftime('%d/%m/%Y')}"

    # ── Estilos ───────────────────────────────────────────────────────────────
    def P(name, **k): return ParagraphStyle(name, **k)
    PT   = P("pt", fontSize=14, textColor=WHITE, fontName="Helvetica-Bold", spaceBefore=4, spaceAfter=2)
    PS   = P("ps", fontSize=7.5, textColor=DIM, fontName="Helvetica", spaceAfter=4)
    SH   = P("sh", fontSize=7, textColor=MID, fontName="Helvetica-Bold", spaceBefore=7, spaceAfter=2, leftIndent=5)
    TH   = P("th", fontSize=6.5, textColor=MID, fontName="Helvetica-Bold", alignment=TA_CENTER)
    TD   = P("td", fontSize=6.5, textColor=DIM, fontName="Helvetica", alignment=TA_CENTER)
    TDL  = P("tdl", fontSize=6.5, textColor=DIM, fontName="Helvetica", alignment=TA_LEFT)
    MV   = P("mv", fontSize=12, textColor=WHITE, fontName="Helvetica-Bold", alignment=TA_CENTER)
    ML   = P("ml", fontSize=6, textColor=DIM, fontName="Helvetica", alignment=TA_CENTER)
    MD   = P("mdp", fontSize=7, textColor=GREEN, fontName="Helvetica", alignment=TA_CENTER)
    MDN  = P("mdn", fontSize=7, textColor=RED, fontName="Helvetica", alignment=TA_CENTER)
    CT   = P("ct", fontSize=26, textColor=WHITE, fontName="Helvetica-Bold", alignment=TA_CENTER, spaceAfter=4)
    CS   = P("cs", fontSize=10, textColor=MID, fontName="Helvetica-Bold", alignment=TA_CENTER, spaceAfter=2)
    CD   = P("cd", fontSize=8, textColor=DIM, fontName="Helvetica", alignment=TA_CENTER, spaceAfter=2)
    INFO = P("inf", fontSize=7, textColor=CYAN, fontName="Helvetica", spaceAfter=3)
    NOTE = P("nt", fontSize=6, textColor=DIM, fontName="Helvetica", leading=9)

    def hr(): return HRFlowable(width="100%", thickness=0.4, color=BOR2, spaceAfter=3, spaceBefore=2)
    def sec(t): return Paragraph(f"● {t}", SH)
    def nfo(t): return Paragraph(f"ℹ {t}", INFO)

    def mtbl(metrics, n=None):
        if not metrics: return Spacer(1, 2)
        n = n or len(metrics)
        cw = UW / n
        cells = [[
            Paragraph(str(m["label"]).upper(), ML),
            Paragraph(str(m["value"]), MV),
            Paragraph(("▲ " if m.get("pos", True) else "▼ ") + str(m.get("delta", "")),
                      MD if m.get("pos", True) else MDN),
        ] for m in metrics]
        t = Table([cells], colWidths=[cw]*n, rowHeights=[34])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0,0),(-1,-1), CARD),
            ("BOX",        (0,0),(-1,-1), 0.4, BOR),
            ("INNERGRID",  (0,0),(-1,-1), 0.4, BOR),
            ("VALIGN",     (0,0),(-1,-1), "MIDDLE"),
        ]))
        return t

    def dtbl(headers, rows, cws=None, lc=None):
        lc = lc or []
        if not rows: return nfo("Sin datos para el período.")
        if cws is None: cws = [UW / len(headers)] * len(headers)
        data = [[Paragraph(h, TH) for h in headers]]
        for i, row in enumerate(rows[:55]):
            bg = CARD if i % 2 == 0 else CARD2
            data.append([Paragraph(str(c), TDL if j in lc else TD)
                         for j, c in enumerate(row)])
        t = Table(data, colWidths=cws, repeatRows=1)
        bgs = [("BACKGROUND",(0,i),(-1,i), CARD if i%2==1 else CARD2)
               for i in range(1, len(data))]
        t.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0), BOR),
            ("GRID",(0,0),(-1,-1),0.3,BOR2),
            ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
            ("ROWHEIGHT",(0,0),(-1,-1),13),
        ] + bgs))
        return t

    def fmt_val(v, kind="n"):
        if not isinstance(v,(int,float)): return str(v)[:55]
        if kind == "$2": return f"${v:,.2f}"
        if kind == "$3": return f"${v:,.3f}"
        if kind == "%":  return f"{v:.2f}%"
        if kind == "%1": return f"{v:.1f}%"
        return f"{v:,.0f}"

    # ── Cabecera / pie ────────────────────────────────────────────────────────
    def on_cover(cv, doc):
        cv.saveState()
        cv.setFillColor(DARK); cv.rect(0,0,W,H,fill=1,stroke=0)
        cv.setFillColor(INDIGO); cv.rect(0,H-52,W*0.62,52,fill=1,stroke=0)
        cv.setFillColor(CYAN); cv.rect(W*0.62,H-52,W*0.38,52,fill=1,stroke=0)
        cv.setFillColor(CARD); cv.rect(0,0,W,22,fill=1,stroke=0)
        cv.setFont("Helvetica",6.5); cv.setFillColor(DIM)
        cv.drawString(MG,7,"CONFIDENCIAL · Solo uso interno · 360Radio Analytics v3.0")
        cv.drawRightString(W-MG,7,f"Generado: {gen_ts}")
        cv.restoreState()

    def on_page(cv, doc):
        cv.saveState()
        cv.setFillColor(DARK); cv.rect(0,0,W,H,fill=1,stroke=0)
        cv.setFillColor(CARD); cv.rect(0,H-24,W,24,fill=1,stroke=0)
        cv.setFont("Helvetica-Bold",7); cv.setFillColor(MID)
        cv.drawString(MG,H-14,"360Radio · Analytics Dashboard")
        cv.setFont("Helvetica",7); cv.setFillColor(DIM)
        cv.drawCentredString(W/2,H-14,f"Período: {per_str}")
        cv.drawRightString(W-MG,H-14,f"Generado: {gen_ts}")
        cv.setFillColor(CARD); cv.rect(0,0,W,19,fill=1,stroke=0)
        cv.setFont("Helvetica",6.5); cv.setFillColor(DIM)
        cv.drawString(MG,5,"CONFIDENCIAL · Solo uso interno")
        cv.drawRightString(W-MG,5,f"Pág. {doc.page}")
        cv.restoreState()

    # ══════════════════════════════════════════════════════════════════════════
    story = []

    # ── PORTADA ───────────────────────────────────────────────────────────────
    story += [Spacer(1,55), Paragraph("🎙️ 360Radio", CT),
              Paragraph("ANALYTICS DASHBOARD", CS),
              Paragraph("Informe Completo · Todas las Vistas", CD),
              Spacer(1,6),
              Paragraph(f"Período: {per_str}", CD),
              Paragraph(f"Generado: {gen_ts}", CD),
              Spacer(1,22)]

    toc_items = [
        ("01","General · Tráfico y Producción","GA4 · Producción editorial"),
        ("02","Search Console","Queries · Páginas · Dispositivos · Países"),
        ("03","Social Media","Instagram · Facebook · YouTube"),
        ("04","Ads y Monetización","AdSense · MGID · Ad Manager · YouTube Revenue · MOW"),
        ("05","Pauta","Campañas · Orders · Fill Rate · VIADS"),
    ]
    for num, title, sub in toc_items:
        row = [[Paragraph(num, P("tn", fontSize=10, textColor=INDIGO, fontName="Helvetica-Bold", alignment=TA_RIGHT)),
                Paragraph(f"{title}  <font size='7' color='#4a5280'>{sub}</font>",
                          P("tt", fontSize=9, textColor=DIM, fontName="Helvetica"))]]
        t = Table(row, colWidths=[16*mm, UW-16*mm])
        t.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"MIDDLE"),
                                ("ROWHEIGHT",(0,0),(-1,-1),17),
                                ("LINEBELOW",(0,0),(-1,-1),0.3,BOR2)]))
        story.append(t)
    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════════
    # 01 · GENERAL
    # ══════════════════════════════════════════════════════════════════════════
    story += [Paragraph("01 · General · Tráfico y Producción", PT),
              Paragraph("GA4 · Producción editorial", PS), hr()]

    if DATA_OK:
        try:
            ga4_r  = load_ga4_general()
            chan_r = load_ga4_channel()
            cnt_r  = load_ga4_country()
            city_r = load_ga4_city()
            dev_r  = load_ga4_device()
            urls_r = load_ga4_urls()
            prod_r = load_produccion_con_metricas()

            ga4  = _fbd(ga4_r, "date", s, e)
            ga4p = _fbd(ga4_r, "date", ps, pe)
            chan = _fbd(chan_r, "date", s, e)
            cnt  = _fbd(cnt_r, "date", s, e)
            city = _fbd(city_r,"date", s, e)
            dev  = _fbd(dev_r, "date", s, e)
            urls = _fbd(urls_r,"date", s, e)
            prod = _fbd(prod_r,"post_date",s,e) if not prod_r.empty else pd.DataFrame()

            au  = _si(ga4,"activeUsers");      au_p = _si(ga4p,"activeUsers")
            vw  = _si(ga4,"screenPageViews"); vw_p = _si(ga4p,"screenPageViews")
            ss  = _si(ga4,"sessions");        ss_p = _si(ga4p,"sessions")
            dur = (float(ga4["userEngagementDuration"].sum())/max(au,1)
                   if not ga4.empty and "userEngagementDuration" in ga4.columns and au>0 else 0)
            u_ct = urls["pagePath"].nunique() if not urls.empty and "pagePath" in urls.columns else 0
            p_ct = len(prod)

            story.append(sec("📊 Métricas del Período"))
            story.append(mtbl([
                {"label":"Usuarios",       "value":_fmt(au),  "delta":_pct(au,au_p),  "pos":au>=au_p},
                {"label":"Vistas Página",  "value":_fmt(vw),  "delta":_pct(vw,vw_p),  "pos":vw>=vw_p},
                {"label":"Sesiones",       "value":_fmt(ss),  "delta":_pct(ss,ss_p),  "pos":ss>=ss_p},
                {"label":"Tiempo Prom.",   "value":f"{dur/60:.1f}m" if dur else "—","delta":"","pos":True},
                {"label":"URLs c/Tráfico", "value":_fmt(u_ct),"delta":"","pos":True},
                {"label":"Publicaciones",  "value":_fmt(p_ct),"delta":"","pos":True},
            ]))
            story.append(Spacer(1,5))

            # Meta Q1
            ga4_q = _fbd(ga4_r,"date",date(e.year,1,1),date(e.year,3,31))
            q1u   = _si(ga4_q,"activeUsers")
            pct_q = min(q1u/750_000*100,100)
            story.append(sec("🎯 Meta Q1 — 750,000 Usuarios"))
            story.append(Paragraph(
                f"Alcanzado: <b>{_fmt(q1u)}</b> / 750,000 — <b>{pct_q:.1f}%</b>  |  "
                f"Faltan: <b>{_fmt(max(750_000-q1u,0))}</b>",
                P("q1",fontSize=8,textColor=DIM,fontName="Helvetica",spaceAfter=4)))

            # Canales
            if not chan.empty and "sessionDefaultChannelGroup" in chan.columns:
                story.append(sec("📡 Canales de Tráfico"))
                ca = (chan.groupby("sessionDefaultChannelGroup",as_index=False)
                      .agg(U=("activeUsers","sum"),V=("screenPageViews","sum"),S=("sessions","sum"))
                      .sort_values("U",ascending=False))
                story.append(dtbl(["Canal","Usuarios","Vistas","Sesiones"],
                    [[r["sessionDefaultChannelGroup"],f"{r['U']:,.0f}",f"{r['V']:,.0f}",f"{r['S']:,.0f}"]
                     for _,r in ca.iterrows()],
                    cws=[70*mm,36*mm,36*mm,34*mm], lc=[0]))
                story.append(Spacer(1,4))

            # Ciudades
            if not city.empty and "city" in city.columns:
                story.append(sec("🏙️ Top 20 Ciudades"))
                cv = (city[city["city"]!="(not set)"]
                      .groupby("city",as_index=False).agg(U=("activeUsers","sum"))
                      .sort_values("U",ascending=False).head(20))
                rows_c = [[r["city"],f"{r['U']:,.0f}"] for _,r in cv.iterrows()]
                half = len(rows_c)//2 + len(rows_c)%2
                merged = [rows_c[i]+( rows_c[i+half] if i+half<len(rows_c) else ["",""])
                          for i in range(half)]
                story.append(dtbl(["Ciudad","Usuarios","Ciudad","Usuarios"], merged,
                    cws=[50*mm,24*mm,50*mm,24*mm], lc=[0,2]))
                story.append(Spacer(1,4))

            # Países
            if not cnt.empty and "country" in cnt.columns:
                story.append(sec("🌎 Top Países"))
                cv2 = (cnt[cnt["country"]!="(not set)"]
                       .groupby("country",as_index=False).agg(U=("activeUsers","sum"))
                       .sort_values("U",ascending=False).head(15))
                story.append(dtbl(["País","Usuarios"],
                    [[r["country"],f"{r['U']:,.0f}"] for _,r in cv2.iterrows()],
                    cws=[100*mm,76*mm], lc=[0]))
                story.append(Spacer(1,4))

            # Top URLs
            if not urls.empty and "pagePath" in urls.columns:
                story.append(sec("📰 URLs Más Leídas"))
                grp = ["pagePath"]+( ["pageTitle"] if "pageTitle" in urls.columns else [])
                ua = (urls.groupby(grp,as_index=False)
                      .agg(Vistas=("screenPageViews","sum"),Usuarios=("activeUsers","sum"))
                      .sort_values("Vistas",ascending=False).head(30))
                title_col = "pageTitle" if "pageTitle" in ua.columns else "pagePath"
                story.append(dtbl(["Título / Página","Vistas","Usuarios"],
                    [[str(r[title_col])[:65],f"{r['Vistas']:,.0f}",f"{r['Usuarios']:,.0f}"]
                     for _,r in ua.iterrows()],
                    cws=[112*mm,32*mm,32*mm], lc=[0]))
                story.append(Spacer(1,4))

            # Autores
            if not prod.empty and "post_author_name" in prod.columns and "ga4_views" in prod.columns:
                story.append(sec("✍️ Autores Más Leídos"))
                key = "post_id" if "post_id" in prod.columns else ("url" if "url" in prod.columns else None)
                prod_d = prod.drop_duplicates(subset=[key],keep="first") if key else prod
                cnt_col = "post_id" if "post_id" in prod_d.columns else "ga4_views"
                aa = (prod_d.groupby("post_author_name",as_index=False)
                      .agg(Vistas=("ga4_views","sum"),Notas=(cnt_col,"count"))
                      .sort_values("Vistas",ascending=False).head(20))
                story.append(dtbl(["Autor","Vistas","Notas"],
                    [[r["post_author_name"],f"{r['Vistas']:,.0f}",f"{r['Notas']:,.0f}"]
                     for _,r in aa.iterrows()],
                    cws=[90*mm,54*mm,32*mm], lc=[0]))
                story.append(Spacer(1,4))

            # Dispositivos
            if not dev.empty and "deviceCategory" in dev.columns:
                story.append(sec("📱 Dispositivos"))
                da = dev.groupby("deviceCategory",as_index=False).agg(U=("activeUsers","sum"),V=("screenPageViews","sum"))
                story.append(dtbl(["Dispositivo","Usuarios","Vistas"],
                    [[r["deviceCategory"],f"{r['U']:,.0f}",f"{r['V']:,.0f}"] for _,r in da.iterrows()],
                    cws=[80*mm,60*mm,36*mm], lc=[0]))

        except Exception as ex:
            story.append(nfo(f"Error GA4: {ex}"))
    else:
        story.append(nfo(f"data_loader no disponible: {_err}"))
    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════════
    # 02 · SEARCH CONSOLE
    # ══════════════════════════════════════════════════════════════════════════
    story += [Paragraph("02 · Search Console", PT),
              Paragraph("Rendimiento orgánico · Queries · Páginas · Dispositivos · Países", PS), hr()]

    if DATA_OK:
        try:
            sc = load_search_console()
            sc_f = {k: _fbd(v,"date",s,e) for k,v in sc.items()}
            sc_p = {k: _fbd(v,"date",ps,pe) for k,v in sc.items()}
            daily  = sc_f.get("daily",pd.DataFrame())
            dailyp = sc_p.get("daily",pd.DataFrame())

            cl = _si(daily,"clicks");   cl_p = _si(dailyp,"clicks")
            im = _si(daily,"impressions"); im_p = _si(dailyp,"impressions")
            ct = float(daily["ctr"].mean()*100) if not daily.empty and "ctr" in daily.columns else 0
            po = float(daily["position"].mean()) if not daily.empty and "position" in daily.columns else 0
            qdf = sc_f.get("queries",pd.DataFrame())
            nq  = qdf["query"].nunique() if not qdf.empty and "query" in qdf.columns else 0

            story.append(sec("📊 Métricas Generales"))
            story.append(mtbl([
                {"label":"Clicks",        "value":_fmt(cl),"delta":_pct(cl,cl_p),"pos":cl>=cl_p},
                {"label":"Impresiones",   "value":_fmt(im),"delta":_pct(im,im_p),"pos":im>=im_p},
                {"label":"CTR Promedio",  "value":f"{ct:.2f}%","delta":"","pos":True},
                {"label":"Posición Media","value":f"{po:.1f}","delta":"","pos":True},
                {"label":"Queries Únicas","value":_fmt(nq),"delta":"","pos":True},
            ]))
            story.append(Spacer(1,5))

            # Queries
            if not qdf.empty and "query" in qdf.columns:
                story.append(sec("🔑 Top Queries"))
                q_agg = (qdf.groupby("query")
                         .agg(C=("clicks","sum"),I=("impressions","sum"),
                              CT=("ctr","mean"),P=("position","mean"))
                         .reset_index().sort_values("C",ascending=False))
                story.append(dtbl(["Query","Clicks","Impresiones","CTR","Posición"],
                    [[r["query"],f"{r['C']:,.0f}",f"{r['I']:,.0f}",
                      f"{r['CT']*100:.2f}%",f"{r['P']:.1f}"] for _,r in q_agg.head(40).iterrows()],
                    cws=[82*mm,24*mm,32*mm,20*mm,18*mm], lc=[0]))
                story.append(Spacer(1,4))

            # Páginas
            pgdf = sc_f.get("pages",pd.DataFrame())
            if not pgdf.empty and "page" in pgdf.columns:
                story.append(sec("📄 Top Páginas"))
                p_agg = (pgdf.groupby("page")
                         .agg(C=("clicks","sum"),I=("impressions","sum"),
                              CT=("ctr","mean"),P=("position","mean"))
                         .reset_index().sort_values("C",ascending=False))
                story.append(dtbl(["Página","Clicks","Impresiones","CTR","Posición"],
                    [[r["page"],f"{r['C']:,.0f}",f"{r['I']:,.0f}",
                      f"{r['CT']*100:.2f}%",f"{r['P']:.1f}"] for _,r in p_agg.head(30).iterrows()],
                    cws=[82*mm,24*mm,32*mm,20*mm,18*mm], lc=[0]))
                story.append(Spacer(1,4))

            # Países
            cntdf = sc_f.get("country",pd.DataFrame())
            if not cntdf.empty and "country" in cntdf.columns:
                story.append(sec("🌎 Clicks por País"))
                c_agg = (cntdf.groupby("country")
                         .agg(C=("clicks","sum"),I=("impressions","sum"),CT=("ctr","mean"))
                         .reset_index().sort_values("C",ascending=False))
                story.append(dtbl(["País","Clicks","Impresiones","CTR"],
                    [[r["country"],f"{r['C']:,.0f}",f"{r['I']:,.0f}",f"{r['CT']*100:.2f}%"]
                     for _,r in c_agg.head(20).iterrows()],
                    cws=[72*mm,32*mm,38*mm,34*mm], lc=[0]))
                story.append(Spacer(1,4))

            # Dispositivos
            devdf = sc_f.get("device",pd.DataFrame())
            if not devdf.empty and "device" in devdf.columns:
                story.append(sec("📱 Clicks por Dispositivo"))
                d_agg = (devdf.groupby("device")
                         .agg(C=("clicks","sum"),I=("impressions","sum"),CT=("ctr","mean"))
                         .reset_index())
                story.append(dtbl(["Dispositivo","Clicks","Impresiones","CTR"],
                    [[r["device"],f"{r['C']:,.0f}",f"{r['I']:,.0f}",f"{r['CT']*100:.2f}%"]
                     for _,r in d_agg.iterrows()],
                    cws=[62*mm,38*mm,44*mm,32*mm], lc=[0]))

        except Exception as ex:
            story.append(nfo(f"Error Search Console: {ex}"))
    else:
        story.append(nfo("data_loader no disponible."))
    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════════
    # 03 · SOCIAL MEDIA
    # ══════════════════════════════════════════════════════════════════════════
    story += [Paragraph("03 · Social Media", PT),
              Paragraph("Instagram Posts · Instagram Stories · Facebook · YouTube", PS), hr()]

    if DATA_OK:
        try:
            ig_raw  = load_instagram_posts()
            igs_raw = load_instagram_stories()
            fb_raw  = load_facebook()
            yt      = load_youtube()

            ig  = _fbd(ig_raw, "fecha_post",s,e)
            igs = _fbd(igs_raw,"fecha_post",s,e)
            fb  = _fbd(fb_raw, "fecha_post",s,e)
            yt_g = yt.get("grafico",pd.DataFrame())
            yt_t = yt.get("tabla",  pd.DataFrame())
            yt_gf = _fbd(yt_g,"Fecha",s,e) if not yt_g.empty else pd.DataFrame()

            def _s(*args):
                df = args[0]
                for c in args[1:]:
                    if not df.empty and c in df.columns: return _si(df,c)
                return 0

            ig_views = _s(ig,"Visualizaciones"); ig_reach = _s(ig,"Alcance")
            ig_likes = _s(ig,"Me gusta");        ig_comm  = _s(ig,"Comentarios")
            ig_share = _s(ig,"Veces que se ha compartido"); ig_save = _s(ig,"Veces guardado")
            ig_n     = len(ig)

            igs_views = _s(igs,"Visualizaciones"); igs_reach = _s(igs,"Alcance")
            igs_click = _s(igs,"Clics en el enlace"); igs_resp = _s(igs,"Respuestas"); igs_n = len(igs)

            fb_reach = _s(fb,"Alcance")
            fb_v3    = _s(fb,"Visualizaciones de vídeo de 3 segundos")
            fb_v1    = _s(fb,"Visualizaciones de vídeo de 1 minuto")
            fb_react = _s(fb,"Reacciones"); fb_comm = _s(fb,"Comentarios")
            fb_share = _s(fb,"Veces que se ha compartido"); fb_n = len(fb)

            yt_plays = _s(yt_gf,"Visualizaciones") if not yt_gf.empty else 0

            total_v = ig_views+igs_views+fb_v3+yt_plays
            total_r = ig_reach+igs_reach+fb_reach
            total_e = ig_likes+ig_share+igs_resp+fb_react+fb_share+fb_comm
            total_n = ig_n+igs_n+fb_n

            story.append(sec("📊 Métricas Generales"))
            story.append(mtbl([
                {"label":"Impresiones/Plays","value":_fmt(total_v),"delta":"","pos":True},
                {"label":"Alcance Total",    "value":_fmt(total_r),"delta":"","pos":True},
                {"label":"YouTube Plays",    "value":_fmt(yt_plays),"delta":"","pos":True},
                {"label":"Publicaciones",    "value":_fmt(total_n),"delta":"","pos":True},
                {"label":"Engagement Total", "value":_fmt(total_e),"delta":"","pos":True},
            ]))
            story.append(Spacer(1,5))

            # Resumen por red
            story.append(sec("📋 Resumen por Red Social"))
            rows_soc = []
            if ig_n>0: rows_soc.append(["📸 IG Posts",str(ig_n),_fmt(ig_views),_fmt(ig_reach),_fmt(ig_likes),_fmt(ig_comm),_fmt(ig_share),_fmt(ig_save)])
            if igs_n>0: rows_soc.append(["💬 IG Stories",str(igs_n),_fmt(igs_views),_fmt(igs_reach),"—",_fmt(igs_resp),_fmt(igs_click),"—"])
            if fb_n>0: rows_soc.append(["👥 Facebook",str(fb_n),_fmt(fb_v3),_fmt(fb_reach),_fmt(fb_react),_fmt(fb_comm),_fmt(fb_share),"—"])
            if not yt_t.empty: rows_soc.append(["▶️ YouTube",_fmt(_s(yt_t,"Visualizaciones")),_fmt(yt_plays),"—","—","—","—","—"])
            story.append(dtbl(["Red","Posts","Impresiones","Alcance","Likes","Comentarios","Compartidos","Guardados"],
                rows_soc, cws=[28*mm,14*mm,26*mm,22*mm,16*mm,24*mm,24*mm,16*mm], lc=[0]))
            story.append(Spacer(1,5))

            # IG Posts detalle
            if not ig.empty:
                story.append(sec("📸 Instagram Posts · Detalle (por Alcance)"))
                sc_ig = [c for c in ["Descripción","Tipo de publicación","Hora de publicación",
                                     "Alcance","Visualizaciones","Me gusta","Comentarios",
                                     "Veces que se ha compartido","Veces guardado"] if c in ig.columns]
                sort_ig = next((c for c in ["Alcance","Visualizaciones"] if c in ig.columns), None)
                if sc_ig and sort_ig:
                    ig_top = ig[sc_ig].sort_values(sort_ig,ascending=False).head(30)
                    hdrs = [h.replace("Veces que se ha compartido","Compartidos")
                              .replace("Veces guardado","Guardados")
                              .replace("Hora de publicación","Hora")
                              .replace("Tipo de publicación","Tipo")
                              .replace("Visualizaciones","Views") for h in sc_ig]
                    n_h = len(hdrs); cws_ig = [UW/n_h]*n_h
                    if "Descripción" in sc_ig:
                        idx = sc_ig.index("Descripción")
                        cws_ig = [UW*0.28 if i==idx else (UW*0.72)/(n_h-1) for i in range(n_h)]
                    rows_ig = [[str(v)[:55] if isinstance(v,str) else (f"{v:,.0f}" if isinstance(v,(int,float)) else str(v))
                                for v in row] for _,row in ig_top.iterrows()]
                    story.append(dtbl(hdrs, rows_ig, cws=cws_ig, lc=[0]))
                story.append(Spacer(1,4))

            # IG Stories detalle
            if not igs.empty:
                story.append(sec("💬 Instagram Stories · Detalle (por Alcance)"))
                sc_igs = [c for c in ["Descripción","Tipo de publicación","Hora de publicación",
                                      "Visualizaciones","Alcance","Me gusta","Respuestas",
                                      "Clics en el enlace","Seguidores"] if c in igs.columns]
                sort_igs = next((c for c in ["Alcance","Visualizaciones"] if c in igs.columns),None)
                if sc_igs and sort_igs:
                    igs_top = igs[sc_igs].sort_values(sort_igs,ascending=False).head(25)
                    hdrs_s = [h.replace("Hora de publicación","Hora")
                                .replace("Tipo de publicación","Tipo")
                                .replace("Clics en el enlace","Clics") for h in sc_igs]
                    n_s = len(hdrs_s); cws_s = [UW/n_s]*n_s
                    rows_s = [[str(v)[:50] if isinstance(v,str) else (f"{v:,.0f}" if isinstance(v,(int,float)) else str(v))
                               for v in row] for _,row in igs_top.iterrows()]
                    story.append(dtbl(hdrs_s, rows_s, cws=cws_s, lc=[0]))
                story.append(Spacer(1,4))

            # Facebook detalle
            if not fb.empty:
                story.append(sec("👥 Facebook · Detalle (por Alcance)"))
                # Detectar columna título
                import unicodedata
                def norm(x): return "".join(c for c in unicodedata.normalize("NFD",x) if unicodedata.category(c)!="Mn").lower()
                tc_fb = next((c for c in fb.columns if norm(c) in ("titulo","title")), None)
                fb_cols_base = (([tc_fb] if tc_fb else []) +
                    [c for c in ["Hora de publicación","Alcance",
                                 "Visualizaciones de vídeo de 3 segundos",
                                 "Visualizaciones de vídeo de 1 minuto",
                                 "Reacciones","Comentarios",
                                 "Veces que se ha compartido",
                                 "Segundos reproducidos de media"] if c in fb.columns])
                sort_fb = next((c for c in ["Alcance"] if c in fb.columns),None)
                if fb_cols_base and sort_fb:
                    fb_top = fb[fb_cols_base].sort_values(sort_fb,ascending=False).head(25)
                    hdrs_fb = [h.replace("Visualizaciones de vídeo de 3 segundos","Views 3s")
                                .replace("Visualizaciones de vídeo de 1 minuto","Views 1min")
                                .replace("Veces que se ha compartido","Compartidos")
                                .replace("Hora de publicación","Hora")
                                .replace("Segundos reproducidos de media","Seg.Rep") for h in fb_cols_base]
                    n_fb = len(hdrs_fb); cws_fb = [UW/n_fb]*n_fb
                    rows_fb = [[str(v)[:50] if isinstance(v,str) else
                                (f"{v:,.1f}" if isinstance(v,float) else (f"{v:,.0f}" if isinstance(v,int) else str(v)))
                                for v in row] for _,row in fb_top.iterrows()]
                    story.append(dtbl(hdrs_fb, rows_fb, cws=cws_fb, lc=[0]))
                story.append(Spacer(1,4))

            # YouTube
            if not yt_t.empty:
                story.append(sec("▶️ YouTube · Top Vídeos"))
                tc_yt = next((c for c in ["Título del vídeo","Titulo del video","Título"] if c in yt_t.columns),None)
                vc_yt = next((c for c in ["Visualizaciones"] if c in yt_t.columns),None)
                if tc_yt and vc_yt:
                    show_yt = [c for c in [tc_yt,"Hora de publicación del vídeo",vc_yt,
                                           "Tiempo de visualización (horas)",
                                           "Impresiones","Ingresos estimados (USD)"] if c in yt_t.columns]
                    yt_top = yt_t.sort_values(vc_yt,ascending=False).head(25)[show_yt]
                    hdrs_yt = [h.replace("Hora de publicación del vídeo","Hora")
                                .replace("Tiempo de visualización (horas)","Hrs.Vista")
                                .replace("Ingresos estimados (USD)","Revenue") for h in show_yt]
                    n_yt = len(hdrs_yt); cws_yt = [UW/n_yt]*n_yt
                    if tc_yt in show_yt:
                        idx = show_yt.index(tc_yt)
                        cws_yt = [UW*0.32 if i==idx else (UW*0.68)/(n_yt-1) for i in range(n_yt)]
                    rows_yt = []
                    for _,row in yt_top.iterrows():
                        rr = []
                        for i,col in enumerate(show_yt):
                            v = row[col]
                            if "Revenue" in hdrs_yt[i] or "Ingreso" in col: rr.append(f"${v:,.2f}" if isinstance(v,(int,float)) else str(v))
                            elif isinstance(v,(int,float)): rr.append(f"{v:,.0f}")
                            else: rr.append(str(v)[:55])
                        rows_yt.append(rr)
                    story.append(dtbl(hdrs_yt, rows_yt, cws=cws_yt, lc=[0]))

        except Exception as ex:
            story.append(nfo(f"Error Social Media: {ex}"))
    else:
        story.append(nfo("data_loader no disponible."))
    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════════
    # 04 · ADS Y MONETIZACIÓN
    # ══════════════════════════════════════════════════════════════════════════
    story += [Paragraph("04 · Ads y Monetización", PT),
              Paragraph("AdSense · MGID · Ad Manager · YouTube Revenue · MOW", PS), hr()]

    if DATA_OK:
        try:
            adsense = load_adsense(); mgid = load_mgid()
            gam = load_admanager(); yt2 = load_youtube()
            mow_rev = 4.2

            as_f = _fbd(adsense,"Date",s,e); as_p = _fbd(adsense,"Date",ps,pe)
            mg_f = _fbd(mgid,"Date",s,e);    mg_p = _fbd(mgid,"Date",ps,pe)
            gd_f = _fbd(gam["diario"],"DATE",s,e)
            gd_p = _fbd(gam["diario"],"DATE",ps,pe)
            yt_rev = float(yt2.get("rev_total",0))
            yt_tb  = yt2.get("tabla",pd.DataFrame())

            rev_as  = _sf(as_f,"Estimated earnings (USD)")
            rev_mg  = _sf(mg_f,"Revenue")
            rev_gam = _sf(gd_f,"AD_SERVER_CPM_AND_CPC_REVENUE")
            rev_tot = rev_as+rev_mg+rev_gam+yt_rev+mow_rev
            rev_tot_p = _sf(as_p,"Estimated earnings (USD)")+_sf(mg_p,"Revenue")+_sf(gd_p,"AD_SERVER_CPM_AND_CPC_REVENUE")

            impr_as = _si(as_f,"Impressions"); impr_mg = _si(mg_f,"Page views")
            impr_gam= _si(gd_f,"AD_SERVER_IMPRESSIONS")
            tot_impr= impr_as+impr_mg+impr_gam
            tot_impr_p = _si(as_p,"Impressions")+_si(gd_p,"AD_SERVER_IMPRESSIONS")

            cl_as = _si(as_f,"Clicks"); cl_mg = _si(mg_f,"Ad Clicks"); cl_gam = _si(gd_f,"AD_SERVER_CLICKS")
            tot_cl = cl_as+cl_mg+cl_gam
            tot_cl_p = _si(as_p,"Clicks")+_si(gd_p,"AD_SERVER_CLICKS")

            ctr_gam = (gd_f["AD_SERVER_CTR"].mean()*100 if not gd_f.empty and "AD_SERVER_CTR" in gd_f.columns else 0)
            cpms = []
            if not as_f.empty and "Impression RPM (USD)" in as_f.columns and impr_as>0:
                cpms.append((_sf(as_f,"Impression RPM (USD)"),impr_as))
            if not gd_f.empty and "AD_SERVER_WITHOUT_CPD_AVERAGE_ECPM" in gd_f.columns and impr_gam>0:
                cpms.append((_sf(gd_f,"AD_SERVER_WITHOUT_CPD_AVERAGE_ECPM"),impr_gam))
            if not mg_f.empty and "Ad RPM" in mg_f.columns and impr_mg>0:
                cpms.append((_sf(mg_f,"Ad RPM"),impr_mg))
            cpm_avg = sum(v/max(w,1)*w for v,w in cpms)/max(sum(w for _,w in cpms),1) if cpms else 0

            story.append(sec("📊 Métricas Generales"))
            story.append(mtbl([
                {"label":"Revenue Total",   "value":f"${rev_tot:,.2f}","delta":_pct(rev_tot,rev_tot_p),"pos":rev_tot>=rev_tot_p},
                {"label":"CPM Promedio",    "value":f"${cpm_avg:.2f}","delta":"","pos":True},
                {"label":"Impresiones Ads", "value":_fmt(tot_impr),"delta":_pct(tot_impr,tot_impr_p),"pos":tot_impr>=tot_impr_p},
                {"label":"Clicks Totales",  "value":_fmt(tot_cl),"delta":_pct(tot_cl,tot_cl_p),"pos":tot_cl>=tot_cl_p},
                {"label":"CTR Ad Manager",  "value":f"{ctr_gam:.2f}%","delta":"","pos":True},
            ]))
            story.append(Spacer(1,5))

            # Resumen plataformas
            story.append(sec("📊 Resumen por Plataforma"))
            rows_p = []
            if not as_f.empty: rows_p.append(["AdSense",f"${rev_as:,.2f}",f"{impr_as:,.0f}",f"{cl_as:,.0f}",f"${_sf(as_f,'Impression RPM (USD)'):,.3f}"])
            if not mg_f.empty: rows_p.append(["MGID",f"${rev_mg:,.2f}",f"{impr_mg:,.0f}",f"{cl_mg:,.0f}",f"${_sf(mg_f,'Ad RPM'):,.3f}"])
            if not gd_f.empty: rows_p.append(["Ad Manager",f"${rev_gam:,.2f}",f"{impr_gam:,.0f}",f"{cl_gam:,.0f}",f"${_sf(gd_f,'AD_SERVER_WITHOUT_CPD_AVERAGE_ECPM'):,.3f}"])
            if yt_rev>0: rows_p.append(["YouTube",f"${yt_rev:,.2f}","—","—","—"])
            rows_p.append(["MOW",f"${mow_rev:,.2f}","—","—","—"])
            story.append(dtbl(["Plataforma","Revenue","Impresiones","Clicks","CPM"],
                rows_p, cws=[42*mm,34*mm,38*mm,28*mm,34*mm], lc=[0]))
            story.append(Spacer(1,4))

            # Formatos GAM
            gam_fmt = gam.get("formatos",pd.DataFrame())
            if not gam_fmt.empty and "CREATIVE_SIZE" in gam_fmt.columns:
                story.append(sec("📐 Formatos · Ad Manager"))
                cm = {"CREATIVE_SIZE":"Formato","AD_SERVER_IMPRESSIONS":"Impresiones",
                      "AD_SERVER_CLICKS":"Clicks","AD_SERVER_CTR":"CTR",
                      "AD_SERVER_WITHOUT_CPD_AVERAGE_ECPM":"eCPM","AD_SERVER_CPM_AND_CPC_REVENUE":"Revenue"}
                show = {k:v for k,v in cm.items() if k in gam_fmt.columns}
                fd2 = gam_fmt[list(show.keys())].rename(columns=show)
                if "Impresiones" in fd2.columns: fd2 = fd2.sort_values("Impresiones",ascending=False)
                rows_fmt = []
                for _,r in fd2.head(20).iterrows():
                    ro = [str(r.get("Formato",""))]
                    for col in list(show.values())[1:]:
                        if col not in fd2.columns: ro.append("—"); continue
                        v = r[col]
                        if col=="CTR": ro.append(f"{v:.4f}")
                        elif col in ("eCPM","Revenue"): ro.append(f"${v:,.2f}" if isinstance(v,(int,float)) else "—")
                        else: ro.append(f"{v:,.0f}" if isinstance(v,(int,float)) else "—")
                    rows_fmt.append(ro)
                hdrs_fmt = list(show.values())
                n_f = len(hdrs_fmt)
                cws_fmt = [38*mm]+[(UW-38*mm)/(n_f-1)]*(n_f-1)
                story.append(dtbl(hdrs_fmt, rows_fmt, cws=cws_fmt, lc=[0]))
                story.append(Spacer(1,4))

            # MGID detalle
            if not mg_f.empty:
                story.append(sec("📊 MGID · Detalle del Período"))
                cm_mg = {"Date":"Fecha","Page views":"Page Views","Revenue":"Revenue",
                         "Ad Clicks":"Clicks","Ad RPM":"RPM","Ad vRPM":"vRPM","Views with visibility":"Vistas Visibles"}
                s2 = {k:v for k,v in cm_mg.items() if k in mg_f.columns}
                mg_s = mg_f[list(s2.keys())].rename(columns=s2)
                if "Fecha" in mg_s.columns: mg_s = mg_s.sort_values("Fecha",ascending=False)
                rows_mg = []
                for _,r in mg_s.head(30).iterrows():
                    ro = []
                    for col in mg_s.columns:
                        v = r[col]
                        if col in ("Revenue","RPM","vRPM"): ro.append(f"${v:,.3f}" if isinstance(v,(int,float)) else str(v))
                        elif isinstance(v,(int,float)): ro.append(f"{v:,.0f}")
                        else: ro.append(str(v)[:18])
                    rows_mg.append(ro)
                n_mg = len(mg_s.columns)
                story.append(dtbl(list(mg_s.columns), rows_mg, cws=[UW/n_mg]*n_mg, lc=[0]))
                story.append(Spacer(1,4))

            # Dispositivos GAM
            gd = gam.get("devices",pd.DataFrame())
            if not gd.empty and "DEVICE_CATEGORY_NAME" in gd.columns:
                story.append(sec("📱 Dispositivos · Ad Manager"))
                dm = {"DEVICE_CATEGORY_NAME":"Dispositivo","AD_SERVER_IMPRESSIONS":"Impresiones",
                      "AD_SERVER_CLICKS":"Clicks","AD_SERVER_CPM_AND_CPC_REVENUE":"Revenue",
                      "AD_SERVER_WITHOUT_CPD_AVERAGE_ECPM":"eCPM"}
                ds = {k:v for k,v in dm.items() if k in gd.columns}
                gd_s = gd[list(ds.keys())].rename(columns=ds)
                rows_gd = []
                for _,r in gd_s.iterrows():
                    ro = []
                    for col in gd_s.columns:
                        v = r[col]
                        if col in ("Revenue","eCPM"): ro.append(f"${v:,.2f}" if isinstance(v,(int,float)) else str(v))
                        elif isinstance(v,(int,float)): ro.append(f"{v:,.0f}")
                        else: ro.append(str(v))
                    rows_gd.append(ro)
                n_gd = len(gd_s.columns)
                story.append(dtbl(list(gd_s.columns), rows_gd, cws=[UW/n_gd]*n_gd, lc=[0]))
                story.append(Spacer(1,4))

            # YouTube top videos
            if not yt_tb.empty:
                story.append(sec("▶️ YouTube · Top Videos por Revenue"))
                cols_yt = [c for c in ["Título del vídeo","Visualizaciones","Ingresos estimados (USD)",
                                       "Impresiones","Porcentaje de clics de las impresiones (%)"] if c in yt_tb.columns]
                if cols_yt:
                    sv = "Visualizaciones" if "Visualizaciones" in yt_tb.columns else cols_yt[0]
                    top_v = yt_tb[cols_yt].sort_values(sv,ascending=False).head(20)
                    hdrs_ytb = [c.replace("Título del vídeo","Título")
                                 .replace("Ingresos estimados (USD)","Revenue")
                                 .replace("Porcentaje de clics de las impresiones (%)","CTR Imp.") for c in cols_yt]
                    n_yt = len(hdrs_ytb)
                    cws_yt = [UW*0.32 if i==0 else (UW*0.68)/(n_yt-1) for i in range(n_yt)]
                    rows_ytb = []
                    for _,row in top_v.iterrows():
                        ro = []
                        for i,col in enumerate(cols_yt):
                            v = row[col]
                            if "Ingreso" in col: ro.append(f"${v:,.2f}" if isinstance(v,(int,float)) else str(v))
                            elif isinstance(v,(int,float)): ro.append(f"{v:,.0f}")
                            else: ro.append(str(v)[:55])
                        rows_ytb.append(ro)
                    story.append(dtbl(hdrs_ytb, rows_ytb, cws=cws_yt, lc=[0]))

        except Exception as ex:
            story.append(nfo(f"Error Ads/Monetización: {ex}"))
    else:
        story.append(nfo("data_loader no disponible."))
    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════════
    # 05 · PAUTA
    # ══════════════════════════════════════════════════════════════════════════
    story += [Paragraph("05 · Pauta", PT),
              Paragraph("Campañas · Orders · Line Items · Fill Rate · Ad Manager · VIADS", PS), hr()]

    if DATA_OK:
        try:
            gam2  = load_admanager(); viads = load_viads()
            diario= gam2["diario"]; orders = gam2["orders"]; fill = gam2["fill"]
            diario_f = _fbd(diario,"DATE",s,e); diario_p = _fbd(diario,"DATE",ps,pe)
            fill_f   = _fbd(fill,"DATE",s,e)

            impr  = _si(diario_f,"AD_SERVER_IMPRESSIONS"); fill_i = _si(diario_f,"TOTAL_LINE_ITEM_LEVEL_IMPRESSIONS")
            clicks= _si(diario_f,"AD_SERVER_CLICKS");      rev    = _sf(diario_f,"AD_SERVER_CPM_AND_CPC_REVENUE")
            ctr   = (diario_f["AD_SERVER_CTR"].mean()*100 if not diario_f.empty and "AD_SERVER_CTR" in diario_f.columns else 0)
            impr_p= _si(diario_p,"AD_SERVER_IMPRESSIONS"); fill_i_p=_si(diario_p,"TOTAL_LINE_ITEM_LEVEL_IMPRESSIONS")
            clicks_p=_si(diario_p,"AD_SERVER_CLICKS");     rev_p  =_sf(diario_p,"AD_SERVER_CPM_AND_CPC_REVENUE")

            story.append(sec("📊 Métricas del Período"))
            story.append(mtbl([
                {"label":"Impresiones Servidas","value":_fmt(impr),    "delta":_pct(impr,impr_p),     "pos":impr>=impr_p},
                {"label":"Total Line Items",    "value":_fmt(fill_i),  "delta":_pct(fill_i,fill_i_p), "pos":fill_i>=fill_i_p},
                {"label":"Clicks",             "value":_fmt(clicks),  "delta":_pct(clicks,clicks_p), "pos":clicks>=clicks_p},
                {"label":"Revenue",            "value":f"${rev:,.2f}","delta":_pct(rev,rev_p),       "pos":rev>=rev_p},
                {"label":"CTR",                "value":f"{ctr:.2f}%", "delta":"","pos":True},
            ]))
            story.append(Spacer(1,5))

            # Orders
            if not orders.empty:
                story.append(sec("📋 Campañas · Orders & Line Items"))
                col_map_o = {"ORDER_NAME":"Campaña","LINE_ITEM_NAME":"Line Item","LINE_ITEM_TYPE":"Tipo",
                             "AD_SERVER_IMPRESSIONS":"Impresiones","AD_SERVER_CLICKS":"Clicks",
                             "AD_SERVER_CPM_AND_CPC_REVENUE":"Revenue","AD_SERVER_WITHOUT_CPD_AVERAGE_ECPM":"eCPM",
                             "LINE_ITEM_START_DATE_TIME":"Inicio","LINE_ITEM_END_DATE_TIME":"Fin"}
                show_o = {k:v for k,v in col_map_o.items() if k in orders.columns}
                ord_s  = orders[list(show_o.keys())].rename(columns=show_o)
                rows_or = []
                for _,r in ord_s.head(40).iterrows():
                    ro = []
                    for col in ord_s.columns:
                        v = r[col]
                        if col in ("Revenue","eCPM"): ro.append(f"${v:,.2f}" if isinstance(v,(int,float)) else str(v))
                        elif col in ("Impresiones","Clicks"): ro.append(f"{v:,.0f}" if isinstance(v,(int,float)) else str(v))
                        else: ro.append(str(v)[:32])
                    rows_or.append(ro)
                hdrs_or = list(ord_s.columns)
                cws_or = []
                for h in hdrs_or:
                    if h in ("Campaña","Line Item"): cws_or.append(36*mm)
                    elif h in ("Inicio","Fin"): cws_or.append(18*mm)
                    elif h == "Tipo": cws_or.append(16*mm)
                    else: cws_or.append(22*mm)
                # Normalizar si no cuadra
                tot = sum(cws_or)
                if tot > UW: cws_or = [c*UW/tot for c in cws_or]
                story.append(dtbl(hdrs_or, rows_or, cws=cws_or, lc=[0,1]))
                story.append(Spacer(1,4))

            # Fill Rate
            if not fill_f.empty and "FILL_RATE_%" in fill_f.columns and "DATE" in fill_f.columns:
                story.append(sec("📊 Fill Rate · Evolución Mensual"))
                fc2 = fill_f.copy()
                fc2["mes"] = fc2["DATE"].dt.to_period("M").astype(str)
                fill_m = fc2.groupby("mes")["FILL_RATE_%"].mean().reset_index()
                avg_f  = fill_m["FILL_RATE_%"].mean()
                story.append(Paragraph(f"Fill Rate promedio del período: <b>{avg_f:.1f}%</b>",
                    P("fr",fontSize=8,textColor=DIM,fontName="Helvetica",spaceAfter=3)))
                story.append(dtbl(["Mes","Fill Rate Promedio"],
                    [[r["mes"],f"{r['FILL_RATE_%']:.1f}%"] for _,r in fill_m.iterrows()],
                    cws=[80*mm,96*mm]))
                if "AD_UNIT_NAME" in fill_f.columns:
                    agg_d = {"Fill_Rate_Prom":("FILL_RATE_%","mean")}
                    if "AD_SERVER_IMPRESSIONS" in fill_f.columns:
                        agg_d["Impresiones"] = ("AD_SERVER_IMPRESSIONS","sum")
                    u_agg = (fill_f.groupby("AD_UNIT_NAME").agg(**agg_d).reset_index()
                             .sort_values("Fill_Rate_Prom",ascending=False))
                    story.append(Spacer(1,3))
                    story.append(sec("📦 Fill Rate por Ad Unit"))
                    rows_ua = [[r["AD_UNIT_NAME"],f"{r['Fill_Rate_Prom']:.1f}%",
                                f"{r.get('Impresiones',0):,.0f}" if "Impresiones" in u_agg.columns else "—"]
                               for _,r in u_agg.head(25).iterrows()]
                    story.append(dtbl(["Ad Unit","Fill Rate Prom.","Impresiones Servidas"],
                        rows_ua, cws=[92*mm,38*mm,46*mm], lc=[0]))
                story.append(Spacer(1,4))

            # Mensual acumulado
            gam_men = gam2.get("mensual",pd.DataFrame())
            if not gam_men.empty and "YEAR_MONTH" in gam_men.columns:
                story.append(sec("📅 Resumen Mensual Acumulado"))
                cm3 = {"YEAR_MONTH":"Mes","AD_SERVER_IMPRESSIONS":"Impresiones",
                       "AD_SERVER_CLICKS":"Clicks","AD_SERVER_CPM_AND_CPC_REVENUE":"Revenue",
                       "FILL_RATE_%":"Fill Rate %","eCPM_CALCULADO":"eCPM"}
                s3 = {k:v for k,v in cm3.items() if k in gam_men.columns}
                gm_s = gam_men[list(s3.keys())].rename(columns=s3)
                rows_gm = []
                for _,r in gm_s.iterrows():
                    ro = []
                    for col in gm_s.columns:
                        v = r[col]
                        if col=="Revenue": ro.append(f"${v:,.2f}" if isinstance(v,(int,float)) else str(v))
                        elif col=="eCPM": ro.append(f"${v:,.2f}" if isinstance(v,(int,float)) else str(v))
                        elif col=="Fill Rate %": ro.append(f"{v:.1f}%" if isinstance(v,(int,float)) else str(v))
                        elif isinstance(v,(int,float)): ro.append(f"{v:,.0f}")
                        else: ro.append(str(v))
                    rows_gm.append(ro)
                n_gm = len(gm_s.columns)
                story.append(dtbl(list(gm_s.columns), rows_gm, cws=[UW/n_gm]*n_gm))
                story.append(Spacer(1,4))

            # VIADS
            story.append(sec("📡 VIADS · Video Ads"))
            if viads.empty:
                story.append(nfo("Sin datos de VIADS. Coloca el archivo statistics_*.csv en data/."))
            else:
                viads_f2 = _fbd(viads,"date",s,e)
                viads_fp = _fbd(viads,"date",ps,pe)
                if viads_f2.empty:
                    story.append(nfo("Sin datos de VIADS para el período seleccionado."))
                else:
                    v_impr = _si(viads_f2,"impressions"); v_cl = _si(viads_f2,"clicks")
                    v_inc  = _sf(viads_f2,"income")
                    v_cpm  = float(viads_f2["cpm"].mean()) if "cpm" in viads_f2.columns else 0
                    v_ctr  = float(viads_f2["ctr"].mean()) if "ctr" in viads_f2.columns else 0
                    v_impr_p = _si(viads_fp,"impressions"); v_cl_p = _si(viads_fp,"clicks"); v_inc_p = _sf(viads_fp,"income")
                    story.append(mtbl([
                        {"label":"Impresiones","value":_fmt(v_impr),"delta":_pct(v_impr,v_impr_p),"pos":v_impr>=v_impr_p},
                        {"label":"Clicks",     "value":_fmt(v_cl),  "delta":_pct(v_cl,v_cl_p),   "pos":v_cl>=v_cl_p},
                        {"label":"Ingresos",   "value":f"${v_inc:,.2f}","delta":_pct(v_inc,v_inc_p),"pos":v_inc>=v_inc_p},
                        {"label":"CPM Prom.",  "value":f"${v_cpm:.2f}","delta":"","pos":True},
                        {"label":"CTR Prom.",  "value":f"{v_ctr:.2f}%","delta":"","pos":True},
                    ]))
                    story.append(Spacer(1,4))
                    story.append(sec("📄 VIADS · Detalle Diario"))
                    cm_v = {"date":"Fecha","impressions":"Impresiones","clicks":"Clicks",
                            "ctr":"CTR","cpm":"CPM","income":"Ingresos (USD)"}
                    vd = viads_f2[[c for c in cm_v if c in viads_f2.columns]].rename(columns=cm_v)
                    if "Fecha" in vd.columns: vd = vd.sort_values("Fecha",ascending=False)
                    rows_vd = []
                    for _,r in vd.head(40).iterrows():
                        ro = []
                        for col in vd.columns:
                            v = r[col]
                            if col=="Ingresos (USD)": ro.append(f"${v:,.2f}" if isinstance(v,(int,float)) else str(v))
                            elif col=="CPM": ro.append(f"${v:.2f}" if isinstance(v,(int,float)) else str(v))
                            elif col=="CTR": ro.append(f"{v:.2f}%" if isinstance(v,(int,float)) else str(v))
                            elif isinstance(v,(int,float)): ro.append(f"{v:,.0f}")
                            else: ro.append(str(v)[:18])
                        rows_vd.append(ro)
                    n_vd = len(vd.columns)
                    story.append(dtbl(list(vd.columns), rows_vd, cws=[UW/n_vd]*n_vd))

        except Exception as ex:
            story.append(nfo(f"Error Pauta: {ex}"))
    else:
        story.append(nfo("data_loader no disponible."))

    # Nota final
    story += [Spacer(1,10), HRFlowable(width="100%",thickness=0.4,color=BOR2,spaceAfter=4),
              Paragraph(f"Datos del período {per_str}. Generado el {gen_ts} por 360Radio Analytics v3.0. "
                        "Los datos son los mismos cargados por data_loader en el momento de la exportación.", NOTE)]

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
        leftMargin=MG, rightMargin=MG, topMargin=MG+24, bottomMargin=MG+18,
        title="360Radio · Informe Analytics", author="360Radio Analytics v3.0")
    doc.build(story, onFirstPage=on_cover, onLaterPages=on_page)
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════════════════
# PÁGINAS
# ══════════════════════════════════════════════════════════════════════════════
PAGES = {
    "🏠  General · Tráfico":   "views/general.py",
    "🔍  Search Console":       "views/search.py",
    "📱  Social Media":         "views/social.py",
    "💰  Ads y Monetización":   "views/ads.py",
    "📣  Pauta":                "views/pauta.py",
}

with st.sidebar:
    st.markdown('<div class="sb-logo">🎙️ 360Radio</div>', unsafe_allow_html=True)
    st.markdown('<div class="sb-sub">Analytics Dashboard</div>', unsafe_allow_html=True)
    st.markdown('<hr class="sb-divider">', unsafe_allow_html=True)

    selection = st.radio("nav", list(PAGES.keys()), label_visibility="collapsed", key="main_nav")

    st.markdown('<hr class="sb-divider">', unsafe_allow_html=True)

    # ── Exportar PDF ──────────────────────────────────────────────────────────
    st.markdown('<p style="font-size:.65rem;color:#2e3460;text-transform:uppercase;'
                'letter-spacing:.1em;margin-bottom:4px">📄 Exportar Informe</p>',
                unsafe_allow_html=True)
    today = date.today()
    pdf_start = st.date_input("Desde", today - timedelta(days=90), key="pdf_s")
    pdf_end   = st.date_input("Hasta", today, key="pdf_e")

    if st.button("Generar PDF completo", use_container_width=True, key="btn_pdf"):
        with st.spinner("Generando informe… puede tardar unos segundos."):
            try:
                pdf_bytes = generate_report_pdf(pdf_start, pdf_end)
                fname = f"360Radio_{pdf_start.strftime('%Y%m%d')}_{pdf_end.strftime('%Y%m%d')}.pdf"
                st.download_button("⬇️ Descargar PDF", data=pdf_bytes,
                    file_name=fname, mime="application/pdf",
                    use_container_width=True, key="dl_pdf")
                st.success("✅ Listo")
            except Exception as ex:
                st.error(f"Error: {ex}")

    st.markdown('<hr class="sb-divider">', unsafe_allow_html=True)
    st.markdown('<span style="font-size:.62rem;color:#1e2040">v3.0 · 360Radio Analytics</span>',
                unsafe_allow_html=True)

# ── Vista activa ──────────────────────────────────────────────────────────────
page_path = PAGES[selection]
with open(page_path, encoding="utf-8") as fh:
    exec(compile(fh.read(), page_path, "exec"), {"__name__": "__main__"})
