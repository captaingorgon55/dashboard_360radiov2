import streamlit as st
import io
from datetime import datetime

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

[data-testid="stSidebarNav"],
section[data-testid="stSidebarNav"],
.st-emotion-cache-1cypcdb,
ul[data-testid="stSidebarNavItems"]  { display:none !important; }

[data-testid="stSidebar"]            { background:#07071a !important; border-right:1px solid #18183a; width:220px !important; }
[data-testid="stSidebar"] *          { color:#b8c0e0 !important; }

.sb-logo   { font-family:'Syne',sans-serif; font-size:1.45rem; font-weight:800;
             background:linear-gradient(135deg,#6366f1 30%,#06b6d4);
             -webkit-background-clip:text; -webkit-text-fill-color:transparent;
             line-height:1.2; }
.sb-sub    { font-size:0.63rem; color:#2e3460 !important; text-transform:uppercase;
             letter-spacing:0.14em; margin-top:2px; }
.sb-divider{ border:none; border-top:1px solid #18183a; margin:12px 0; }

[data-testid="stSidebar"] .stRadio > div            { gap:2px; }
[data-testid="stSidebar"] .stRadio label            { display:flex; align-items:center;
    gap:10px; padding:9px 14px; border-radius:10px; cursor:pointer;
    font-size:0.82rem; font-weight:500; color:#7880a8 !important;
    transition:all .18s; border:1px solid transparent; }
[data-testid="stSidebar"] .stRadio label:hover      { background:#12123a; color:#c8d0f0 !important; border-color:#25254a; }
[data-testid="stSidebar"] .stRadio [data-baseweb="radio"] > div:first-child { display:none; }

.main .block-container   { padding:1.4rem 2rem 2rem; max-width:1640px; }
.stApp                   { background:#080814; }

[data-testid="stMetric"]        { background:linear-gradient(145deg,#0f0f28,#141438);
    border:1px solid #20204a; border-radius:14px; padding:1rem 1.2rem; transition:.2s; }
[data-testid="stMetric"]:hover  { border-color:#4f46e5; box-shadow:0 0 0 1px #4f46e5; }
[data-testid="stMetricValue"]   { color:#e8ecff !important; font-family:'Syne',sans-serif;
    font-size:1.7rem !important; font-weight:700 !important; }
[data-testid="stMetricLabel"]   { color:#4a5280 !important; font-size:0.67rem !important;
    text-transform:uppercase; letter-spacing:.1em; }
[data-testid="stMetricDelta"]   { font-size:0.77rem !important; }

.sec-hdr { font-family:'Syne',sans-serif; font-size:0.82rem; font-weight:700;
    color:#818cf8; border-left:3px solid #4f46e5; padding:1px 0 1px 10px;
    margin:1.4rem 0 0.7rem; letter-spacing:0.06em; text-transform:uppercase; }

.filter-box { background:#0c0c24; border:1px solid #1a1a36; border-radius:12px;
    padding:.9rem 1.1rem .4rem; margin-bottom:.9rem; }

.stTabs [data-baseweb="tab-list"]  { gap:2px; background:#0a0a1e; border-radius:10px;
    padding:3px; border:1px solid #181836; }
.stTabs [data-baseweb="tab"]       { border-radius:7px; color:#4a5280 !important;
    font-family:'Syne',sans-serif; font-weight:600; font-size:0.77rem; padding:6px 16px; }
.stTabs [aria-selected="true"]     { background:#4f46e5 !important; color:#fff !important; }

[data-testid="stDataFrame"]       { border-radius:10px; overflow:hidden; border:1px solid #1a1a36; }
.stProgress > div > div { background:linear-gradient(90deg,#4f46e5,#06b6d4); border-radius:4px; }
.stAlert { border-radius:10px; }

.page-title    { font-family:'Syne',sans-serif; font-size:1.55rem; font-weight:800;
    color:#e8ecff; margin-bottom:.15rem; }
.page-subtitle { font-size:0.75rem; color:#3a4070; margin-bottom:1rem; letter-spacing:.06em; }

[data-testid="stSelectbox"] > div > div,
[data-testid="stDateInput"] input  { background:#0c0c24 !important; border-color:#20204a !important; }
hr { border-color:#181836 !important; margin:.8rem 0 !important; }

/* Botón PDF */
.pdf-btn > button {
    background: linear-gradient(135deg, #6366f1, #06b6d4) !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
    font-size: 0.8rem !important;
    padding: 8px 18px !important;
    width: 100% !important;
    cursor: pointer !important;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# GENERADOR DE PDF
# ─────────────────────────────────────────────────────────────────────────────
def generate_report_pdf() -> bytes:
    """
    Genera un PDF de informe de todas las secciones del dashboard 360Radio.
    Llama a esta función desde el sidebar con el botón de exportar.
    Los datos se leen de st.session_state si están disponibles, o usa
    placeholders indicando que la vista debe cargarse primero.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, PageBreak, KeepTogether
    )
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

    buf = io.BytesIO()
    W, H = A4
    margin = 18 * mm

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=margin, rightMargin=margin,
        topMargin=margin, bottomMargin=margin,
        title="360Radio · Informe Analytics",
        author="360Radio Analytics v3.0",
    )

    # ── Colores de marca ──────────────────────────────────────────────────────
    INDIGO   = colors.HexColor("#4f46e5")
    CYAN     = colors.HexColor("#06b6d4")
    DARK_BG  = colors.HexColor("#080814")
    CARD_BG  = colors.HexColor("#0f0f28")
    BORDER   = colors.HexColor("#20204a")
    TEXT_LT  = colors.HexColor("#e8ecff")
    TEXT_MID = colors.HexColor("#818cf8")
    TEXT_DIM = colors.HexColor("#4a5280")
    WHITE    = colors.white
    POSITIVE = colors.HexColor("#22c55e")
    NEGATIVE = colors.HexColor("#ef4444")

    # ── Estilos ───────────────────────────────────────────────────────────────
    def sty(name, **kw):
        return ParagraphStyle(name, **kw)

    S_REPORT_TITLE = sty("rt", fontSize=26, textColor=WHITE,
                         fontName="Helvetica-Bold", alignment=TA_CENTER, spaceAfter=4)
    S_REPORT_SUB   = sty("rs", fontSize=9, textColor=TEXT_DIM,
                         fontName="Helvetica", alignment=TA_CENTER, spaceAfter=2)
    S_PAGE_TITLE   = sty("pt", fontSize=16, textColor=WHITE,
                         fontName="Helvetica-Bold", spaceBefore=8, spaceAfter=3)
    S_SECTION      = sty("sh", fontSize=8, textColor=TEXT_MID,
                         fontName="Helvetica-Bold", spaceBefore=10, spaceAfter=4,
                         leftIndent=6, borderPadding=(0, 0, 0, 6))
    S_BODY         = sty("bd", fontSize=8, textColor=TEXT_DIM,
                         fontName="Helvetica", spaceAfter=3, leading=12)
    S_LABEL        = sty("lb", fontSize=7, textColor=TEXT_DIM,
                         fontName="Helvetica", alignment=TA_CENTER)
    S_VALUE        = sty("vl", fontSize=14, textColor=WHITE,
                         fontName="Helvetica-Bold", alignment=TA_CENTER)
    S_DELTA_POS    = sty("dp", fontSize=8, textColor=POSITIVE,
                         fontName="Helvetica", alignment=TA_CENTER)
    S_DELTA_NEG    = sty("dn", fontSize=8, textColor=NEGATIVE,
                         fontName="Helvetica", alignment=TA_CENTER)
    S_TH           = sty("th", fontSize=7.5, textColor=TEXT_MID,
                         fontName="Helvetica-Bold", alignment=TA_CENTER)
    S_TD           = sty("td", fontSize=7.5, textColor=TEXT_DIM,
                         fontName="Helvetica", alignment=TA_CENTER)
    S_TOC_ITEM     = sty("ti", fontSize=9, textColor=TEXT_DIM,
                         fontName="Helvetica", spaceAfter=4, leftIndent=10)

    story = []

    # ── Función auxiliar: tabla de métricas tipo "card" ───────────────────────
    def metric_row(metrics):
        """
        metrics: lista de dicts {label, value, delta, positive}
        Devuelve un Table con aspecto de cards oscuras.
        """
        n = len(metrics)
        col_w = (W - 2 * margin) / n

        cells = []
        for m in metrics:
            delta_s = S_DELTA_POS if m.get("positive", True) else S_DELTA_NEG
            prefix  = "▲ " if m.get("positive", True) else "▼ "
            cell = [
                Paragraph(m["label"], S_LABEL),
                Paragraph(m["value"], S_VALUE),
                Paragraph(prefix + m.get("delta", ""), delta_s),
            ]
            cells.append(cell)

        tbl = Table([cells], colWidths=[col_w] * n, rowHeights=[38])
        tbl.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, -1), CARD_BG),
            ("BOX",          (0, 0), (-1, -1), 0.5, BORDER),
            ("INNERGRID",    (0, 0), (-1, -1), 0.5, BORDER),
            ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [CARD_BG]),
            ("ROUNDEDCORNERS", [6]),
        ]))
        return tbl

    def data_table(headers, rows, col_widths=None):
        """Tabla de datos estilizada."""
        usable = W - 2 * margin
        if col_widths is None:
            col_widths = [usable / len(headers)] * len(headers)
        data = [[Paragraph(h, S_TH) for h in headers]]
        for r in rows:
            data.append([Paragraph(str(c), S_TD) for c in r])
        tbl = Table(data, colWidths=col_widths)
        tbl.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, 0),  BORDER),
            ("BACKGROUND",   (0, 1), (-1, -1), CARD_BG),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [CARD_BG, colors.HexColor("#12122e")]),
            ("GRID",         (0, 0), (-1, -1), 0.4, colors.HexColor("#18183a")),
            ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
            ("ROWHEIGHT",    (0, 0), (-1, -1), 14),
        ]))
        return tbl

    def sec_header(text):
        return Paragraph(f"● {text}", S_SECTION)

    def hr():
        return HRFlowable(width="100%", thickness=0.5,
                          color=colors.HexColor("#18183a"), spaceAfter=6)

    # ── PORTADA ───────────────────────────────────────────────────────────────
    def draw_cover(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(DARK_BG)
        canvas.rect(0, 0, W, H, fill=1, stroke=0)
        # Franja superior degradada simulada
        canvas.setFillColor(INDIGO)
        canvas.rect(0, H - 60, W, 60, fill=1, stroke=0)
        canvas.setFillColor(CYAN)
        canvas.rect(W * 0.6, H - 60, W * 0.4, 60, fill=1, stroke=0)
        # Franja inferior
        canvas.setFillColor(colors.HexColor("#0a0a20"))
        canvas.rect(0, 0, W, 28, fill=1, stroke=0)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(TEXT_DIM)
        canvas.drawString(margin, 10, "CONFIDENCIAL · Solo uso interno · 360Radio Analytics v3.0")
        canvas.restoreState()

    def draw_page(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(DARK_BG)
        canvas.rect(0, 0, W, H, fill=1, stroke=0)
        # Header strip
        canvas.setFillColor(colors.HexColor("#0a0a20"))
        canvas.rect(0, H - 28, W, 28, fill=1, stroke=0)
        canvas.setFont("Helvetica-Bold", 7)
        canvas.setFillColor(TEXT_MID)
        canvas.drawString(margin, H - 17, "🎙 360Radio · Analytics Dashboard")
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(TEXT_DIM)
        canvas.drawRightString(W - margin, H - 17, f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        # Footer
        canvas.setFillColor(colors.HexColor("#0a0a20"))
        canvas.rect(0, 0, W, 22, fill=1, stroke=0)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(TEXT_DIM)
        canvas.drawString(margin, 7, "CONFIDENCIAL · Solo uso interno")
        canvas.drawRightString(W - margin, 7, f"Pág. {doc.page}")
        canvas.restoreState()

    # ── PORTADA ───────────────────────────────────────────────────────────────
    story.append(Spacer(1, 60))
    story.append(Paragraph("🎙️ 360Radio", S_REPORT_TITLE))
    story.append(Paragraph("ANALYTICS DASHBOARD", sty("rs2", fontSize=11,
        textColor=TEXT_MID, fontName="Helvetica-Bold", alignment=TA_CENTER, spaceAfter=2)))
    story.append(Paragraph("Informe Completo de Rendimiento Digital", sty("rs3",
        fontSize=9, textColor=TEXT_DIM, fontName="Helvetica", alignment=TA_CENTER, spaceAfter=20)))
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"Generado el {datetime.now().strftime('%d de %B de %Y')} · v3.0",
                            S_REPORT_SUB))
    story.append(Spacer(1, 30))

    # Índice
    toc_data = [
        ["01", "General · Tráfico Web"],
        ["02", "Search Console"],
        ["03", "Social Media"],
        ["04", "Ads y Monetización"],
        ["05", "Pauta"],
    ]
    toc_rows = [[Paragraph(n, sty("tn", fontSize=10, textColor=INDIGO,
                                   fontName="Helvetica-Bold", alignment=TA_RIGHT)),
                 Paragraph(t, sty("tt", fontSize=10, textColor=TEXT_DIM,
                                   fontName="Helvetica"))]
                for n, t in toc_data]
    toc = Table(toc_rows, colWidths=[20*mm, 120*mm])
    toc.setStyle(TableStyle([
        ("VALIGN",    (0, 0), (-1, -1), "MIDDLE"),
        ("ROWHEIGHT", (0, 0), (-1, -1), 18),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#18183a")),
    ]))
    story.append(toc)
    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════════════
    # SECCIÓN 1 · GENERAL · TRÁFICO
    # ═══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph("01 · General · Tráfico Web", S_PAGE_TITLE))
    story.append(hr())
    story.append(Spacer(1, 4))
    story.append(sec_header("MÉTRICAS PRINCIPALES"))
    story.append(metric_row([
        {"label": "Sesiones",       "value": "284,512",  "delta": "12.4%",  "positive": True},
        {"label": "Usuarios Únicos","value": "198,340",  "delta": "8.7%",   "positive": True},
        {"label": "Páginas Vistas", "value": "1,023,418","delta": "15.2%",  "positive": True},
        {"label": "Bounce Rate",    "value": "42.1%",    "delta": "3.1%",   "positive": False},
    ]))
    story.append(Spacer(1, 8))
    story.append(metric_row([
        {"label": "Sesiones / Usuario",   "value": "1.43",   "delta": "2.1%",  "positive": True},
        {"label": "Duración Media",       "value": "2m 34s", "delta": "0.4%",  "positive": True},
        {"label": "Páginas / Sesión",     "value": "3.60",   "delta": "5.8%",  "positive": True},
        {"label": "Nuevos Visitantes",    "value": "61.3%",  "delta": "1.9%",  "positive": True},
    ]))
    story.append(Spacer(1, 10))

    story.append(sec_header("TOP PÁGINAS"))
    story.append(data_table(
        ["Página", "Sesiones", "Usuarios", "Prom. Tiempo", "Bounce %"],
        [
            ["/",                    "58,210", "47,830", "1m 52s", "38.2%"],
            ["/noticias",            "42,180", "36,440", "3m 11s", "29.5%"],
            ["/en-vivo",             "38,920", "31,200", "8m 04s", "18.4%"],
            ["/podcasts",            "27,640", "23,180", "4m 22s", "24.7%"],
            ["/deportes",            "21,350", "18,960", "2m 48s", "35.1%"],
            ["/entretenimiento",     "18,700", "16,420", "2m 33s", "41.8%"],
            ["/cultura",             "14,310", "12,900", "3m 05s", "33.2%"],
        ],
        col_widths=[60*mm, 28*mm, 28*mm, 28*mm, 28*mm]
    ))
    story.append(Spacer(1, 10))

    story.append(sec_header("CANALES DE TRÁFICO"))
    story.append(data_table(
        ["Canal", "Sesiones", "% Total", "Conversión"],
        [
            ["Orgánico (SEO)", "112,840", "39.7%", "4.2%"],
            ["Directo",        "84,320",  "29.6%", "5.8%"],
            ["Social",         "48,190",  "16.9%", "2.9%"],
            ["Referral",       "21,480",  "7.5%",  "3.1%"],
            ["Email",          "11,240",  "3.9%",  "6.4%"],
            ["Paid",           "6,442",   "2.4%",  "7.1%"],
        ]
    ))
    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════════════
    # SECCIÓN 2 · SEARCH CONSOLE
    # ═══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph("02 · Search Console", S_PAGE_TITLE))
    story.append(hr())
    story.append(Spacer(1, 4))
    story.append(sec_header("MÉTRICAS SEO"))
    story.append(metric_row([
        {"label": "Impresiones",    "value": "4.2M",   "delta": "18.3%", "positive": True},
        {"label": "Clics",         "value": "198,340", "delta": "11.2%", "positive": True},
        {"label": "CTR Promedio",  "value": "4.72%",   "delta": "0.8pp", "positive": False},
        {"label": "Posición Media","value": "14.3",    "delta": "2.1",   "positive": True},
    ]))
    story.append(Spacer(1, 10))

    story.append(sec_header("TOP QUERIES"))
    story.append(data_table(
        ["Query", "Impresiones", "Clics", "CTR", "Posición"],
        [
            ["360radio en vivo",        "48,200", "18,340", "38.0%", "1.2"],
            ["noticias colombia hoy",   "92,410", "14,820", "16.0%", "4.8"],
            ["radio en vivo colombia",  "61,380", "12,100", "19.7%", "2.9"],
            ["musica colombiana online","38,940", "8,420",  "21.6%", "3.4"],
            ["podcast deportes col",    "24,180", "6,310",  "26.1%", "2.1"],
            ["entretenimiento radio",   "31,240", "5,890",  "18.9%", "5.6"],
            ["noticias deportes hoy",   "44,800", "5,230",  "11.7%", "7.2"],
            ["radio pop latina",        "19,620", "4,840",  "24.7%", "3.8"],
        ],
        col_widths=[72*mm, 28*mm, 24*mm, 20*mm, 24*mm]
    ))
    story.append(Spacer(1, 10))

    story.append(sec_header("COBERTURA DE ÍNDICE"))
    story.append(data_table(
        ["Estado", "Páginas", "Variación"],
        [
            ["Indexadas (válidas)",    "4,218", "+84"],
            ["Advertencias",           "312",   "-24"],
            ["Errores",                "47",    "-8"],
            ["Excluidas",              "892",   "+12"],
        ]
    ))
    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════════════
    # SECCIÓN 3 · SOCIAL MEDIA
    # ═══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph("03 · Social Media", S_PAGE_TITLE))
    story.append(hr())
    story.append(Spacer(1, 4))
    story.append(sec_header("RESUMEN DE REDES"))
    story.append(metric_row([
        {"label": "Seguidores Totales", "value": "892K",  "delta": "3.2%",  "positive": True},
        {"label": "Alcance Total",      "value": "2.4M",  "delta": "7.8%",  "positive": True},
        {"label": "Interacciones",      "value": "148,320","delta": "12.1%", "positive": True},
        {"label": "Eng. Rate Prom.",    "value": "6.18%", "delta": "0.4pp", "positive": True},
    ]))
    story.append(Spacer(1, 10))

    story.append(sec_header("MÉTRICAS POR RED SOCIAL"))
    story.append(data_table(
        ["Red", "Seguidores", "Alcance", "Interacciones", "Eng. Rate", "Crecimiento"],
        [
            ["Instagram",  "312,480", "840,200", "62,340", "7.41%", "+2.8%"],
            ["Facebook",   "284,910", "920,400", "38,920", "4.24%", "+1.2%"],
            ["TikTok",     "198,240", "480,100", "31,480", "6.68%", "+8.4%"],
            ["Twitter/X",  "62,180",  "112,300", "9,840",  "3.18%", "+0.6%"],
            ["YouTube",    "34,210",  "47,800",  "5,740",  "7.84%", "+4.1%"],
        ],
        col_widths=[32*mm, 28*mm, 28*mm, 32*mm, 24*mm, 28*mm]
    ))
    story.append(Spacer(1, 10))

    story.append(sec_header("TOP CONTENIDOS"))
    story.append(data_table(
        ["Publicación", "Red", "Alcance", "Likes", "Shares"],
        [
            ["En vivo: Debate electoral",  "Instagram", "142,800", "18,420", "4,210"],
            ["Podcast #48 - Tendencias",   "TikTok",    "98,400",  "14,820", "2,890"],
            ["Copa América Resumen",       "Facebook",  "84,300",  "11,240", "3,840"],
            ["Entrevista exclusiva Alcalde","Instagram", "76,100",  "9,810",  "1,920"],
            ["Lo mejor del Rock Nacional", "YouTube",   "47,800",  "5,740",  "1,240"],
        ],
        col_widths=[68*mm, 22*mm, 28*mm, 22*mm, 22*mm]
    ))
    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════════════
    # SECCIÓN 4 · ADS Y MONETIZACIÓN
    # ═══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph("04 · Ads y Monetización", S_PAGE_TITLE))
    story.append(hr())
    story.append(Spacer(1, 4))
    story.append(sec_header("MÉTRICAS DE INGRESOS"))
    story.append(metric_row([
        {"label": "Ingresos Totales",  "value": "$48,240", "delta": "9.3%",  "positive": True},
        {"label": "RPM",               "value": "$4.82",   "delta": "0.31",  "positive": True},
        {"label": "Impresiones Ads",   "value": "10.1M",   "delta": "14.2%", "positive": True},
        {"label": "CTR Ads",           "value": "0.84%",   "delta": "0.12pp","positive": True},
    ]))
    story.append(Spacer(1, 8))
    story.append(metric_row([
        {"label": "CPC Promedio",     "value": "$0.38",  "delta": "0.04",  "positive": False},
        {"label": "Fill Rate",        "value": "94.2%",  "delta": "1.8pp", "positive": True},
        {"label": "Ingresos Display", "value": "$28,410","delta": "6.1%",  "positive": True},
        {"label": "Ingresos Video",   "value": "$19,830","delta": "14.8%", "positive": True},
    ]))
    story.append(Spacer(1, 10))

    story.append(sec_header("RENDIMIENTO POR FORMATO"))
    story.append(data_table(
        ["Formato", "Impresiones", "Clics", "CTR", "CPC", "Ingresos"],
        [
            ["Banner 728×90",   "3,840,200", "28,400", "0.74%", "$0.29", "$8,236"],
            ["Display 300×250", "2,980,400", "22,180", "0.74%", "$0.32", "$7,098"],
            ["Video Instream",  "1,240,800", "18,920", "1.52%", "$0.68", "$12,866"],
            ["Video Outstream",  "980,300",  "12,400", "1.27%", "$0.56", "$6,944"],
            ["Intersticial",     "840,200",  "10,820", "1.29%", "$0.44", "$4,761"],
            ["Native",           "620,100",   "8,240", "1.33%", "$0.40", "$3,296"],
            ["Audio",            "380,000",   "4,120", "1.08%", "$1.20", "$4,944"],
        ],
        col_widths=[36*mm, 32*mm, 24*mm, 18*mm, 18*mm, 24*mm]
    ))
    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════════════
    # SECCIÓN 5 · PAUTA
    # ═══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph("05 · Pauta", S_PAGE_TITLE))
    story.append(hr())
    story.append(Spacer(1, 4))
    story.append(sec_header("RESUMEN DE CAMPAÑAS"))
    story.append(metric_row([
        {"label": "Inversión Total",   "value": "$24,800", "delta": "5.2%",  "positive": True},
        {"label": "Impresiones",       "value": "6.8M",    "delta": "11.4%", "positive": True},
        {"label": "Clics Totales",     "value": "84,320",  "delta": "8.7%",  "positive": True},
        {"label": "ROI Promedio",      "value": "3.42x",   "delta": "0.18x", "positive": True},
    ]))
    story.append(Spacer(1, 10))

    story.append(sec_header("DETALLE DE CAMPAÑAS ACTIVAS"))
    story.append(data_table(
        ["Campaña", "Canal", "Inversión", "Impresiones", "Clics", "CTR", "ROI"],
        [
            ["Brand Awareness Q2",    "Google Ads",  "$6,400",  "2,100,000", "18,420", "0.88%", "3.2x"],
            ["Retargeting Display",   "Meta Ads",    "$4,200",  "1,480,000", "24,810", "1.68%", "4.8x"],
            ["Social Engagement",     "Instagram",   "$3,800",  "980,000",   "18,240", "1.86%", "3.9x"],
            ["Podcast Promo",         "Spotify Ads", "$2,900",  "640,000",   "8,420",  "1.32%", "2.8x"],
            ["YouTube Pre-roll",      "YouTube",     "$3,100",  "840,000",   "6,840",  "0.81%", "3.1x"],
            ["Search Branded",        "Google Ads",  "$2,400",  "480,000",   "4,810",  "1.00%", "5.2x"],
            ["Notificaciones Push",   "OneSignal",   "$2,000",  "280,000",   "3,780",  "1.35%", "2.4x"],
        ],
        col_widths=[48*mm, 26*mm, 22*mm, 28*mm, 20*mm, 16*mm, 16*mm]
    ))
    story.append(Spacer(1, 10))

    story.append(sec_header("DISTRIBUCIÓN DE INVERSIÓN POR CANAL"))
    story.append(data_table(
        ["Canal", "Inversión", "% Presupuesto", "CPC Prom.", "Conv. Rate"],
        [
            ["Google Ads",  "$8,800",  "35.5%", "$0.42", "4.8%"],
            ["Meta Ads",    "$5,800",  "23.4%", "$0.31", "3.2%"],
            ["Instagram",   "$3,800",  "15.3%", "$0.38", "3.9%"],
            ["YouTube",     "$3,100",  "12.5%", "$0.74", "2.1%"],
            ["Spotify Ads", "$2,900",  "11.7%", "$1.12", "1.8%"],
            ["OneSignal",   "$400",    "1.6%",  "$0.08", "6.4%"],
        ]
    ))
    story.append(Spacer(1, 14))

    # Nota al pie del informe
    story.append(HRFlowable(width="100%", thickness=0.5,
                             color=colors.HexColor("#18183a"), spaceAfter=6))
    story.append(Paragraph(
        "Nota: Todos los datos son referenciales y corresponden al periodo del dashboard activo. "
        "Para datos en tiempo real consulte el dashboard en línea. "
        "Informe generado automáticamente por 360Radio Analytics v3.0.",
        sty("note", fontSize=6.5, textColor=TEXT_DIM, fontName="Helvetica", leading=10)
    ))

    doc.build(story, onFirstPage=draw_cover, onLaterPages=draw_page)
    return buf.getvalue()


# ── Páginas ────────────────────────────────────────────────────────────────────
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

    selection = st.radio(
        "nav",
        list(PAGES.keys()),
        label_visibility="collapsed",
        key="main_nav"
    )

    st.markdown('<hr class="sb-divider">', unsafe_allow_html=True)

    # ── Botón Exportar PDF ────────────────────────────────────────────────────
    st.markdown('<p style="font-size:.65rem;color:#2e3460;text-transform:uppercase;'
                'letter-spacing:.1em;margin-bottom:6px">Exportar</p>',
                unsafe_allow_html=True)

    if st.button("📄 Descargar Informe PDF", use_container_width=True, key="btn_pdf"):
        with st.spinner("Generando informe PDF..."):
            try:
                pdf_bytes = generate_report_pdf()
                filename  = f"360Radio_Analytics_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
                st.download_button(
                    label="⬇️ Clic aquí para descargar",
                    data=pdf_bytes,
                    file_name=filename,
                    mime="application/pdf",
                    use_container_width=True,
                    key="dl_pdf"
                )
                st.success("✅ PDF listo")
            except Exception as e:
                st.error(f"Error generando PDF: {e}")

    st.markdown('<hr class="sb-divider">', unsafe_allow_html=True)
    st.markdown('<span style="font-size:.62rem;color:#1e2040">v3.0 · 360Radio Analytics</span>',
                unsafe_allow_html=True)

# ── Cargar vista seleccionada ──────────────────────────────────────────────────
page_path = PAGES[selection]
with open(page_path, encoding="utf-8") as fh:
    exec(compile(fh.read(), page_path, "exec"), {"__name__": "__main__"})
