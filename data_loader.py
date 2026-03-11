"""
data_loader.py  –  360Radio Analytics v4.0
==========================================
SOCIAL MEDIA: Lee Post Instagram.csv / Instagram Historys.csv / Post Facebook.csv
generados por merge_social_csvs.py. Admite múltiples formatos de fecha.

MATCHING Produccion ↔ GA4 — 12 pasos en cascada (ver matching_engine.py):
  1.  post_id  == último número ≥4 dígitos en pagePath          (exacto)
  2.  post_id  == ?p=XXXXX  (legacy WP)                         (exacto)
  3.  Título exacto normalizado                                  (exacto)
  4.  Path completo normalizado                                  (exacto)
  5.  Slug final del pagePath == slug de URL de producción       (exacto)
  6.  Slug sin stop-words                                        (exacto)
  7.  Variantes de slug (guiones, plural/singular naive)         (heurístico)
  8.  Token-set ratio ≥ 0.90 sobre títulos                       (fuzzy)
  9.  Jaccard bigramas ≥ 0.82                                    (fuzzy)
 10.  Jaccard trigramas ≥ 0.78                                   (fuzzy)
 11.  LCS normalizado ≥ 0.85                                     (fuzzy)
 12.  TF-IDF coseno ≥ 0.80                                       (semántico)
"""
import re, unicodedata
import pandas as pd
import numpy as np
import streamlit as st
from pathlib import Path
from urllib.parse import urlparse

from matching_engine import match_production_to_ga4, match_stats  # noqa: F401

DATA_DIR = Path("data")

# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS I/O
# ═══════════════════════════════════════════════════════════════════════════════

def _read_csv_robust(fname: str) -> pd.DataFrame:
    path = DATA_DIR / fname
    if not path.exists():
        return pd.DataFrame()
    for enc in ["utf-8", "utf-8-sig", "latin-1", "cp1252"]:
        for sep in [",", ";", "\t", "|"]:
            try:
                df = pd.read_csv(path, encoding=enc, sep=sep, low_memory=False)
                if len(df.columns) > 1:
                    return df.copy()
            except Exception:
                continue
    try:
        return pd.read_csv(path, encoding="latin-1", on_bad_lines="skip").copy()
    except Exception:
        return pd.DataFrame()


def _read_excel(fname: str, sheet: str) -> pd.DataFrame:
    path = DATA_DIR / fname
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_excel(path, sheet_name=sheet)
    except Exception:
        try:
            return pd.read_excel(path, sheet_name=sheet, engine="openpyxl")
        except Exception:
            return pd.DataFrame()


def _to_dt(df: pd.DataFrame, col: str) -> pd.DataFrame:
    if not df.empty and col in df.columns:
        df = df.copy()
        df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def _safe_numeric(df: pd.DataFrame, *cols) -> pd.DataFrame:
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    return df


# ═══════════════════════════════════════════════════════════════════════════════
# PARSER DE FECHA — multi-formato robusto
# ═══════════════════════════════════════════════════════════════════════════════

_DATE_FORMATS = [
    "%m/%d/%Y %H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%Y-%m-%d",
]

def _parse_fecha(series: pd.Series) -> pd.Series:
    result  = pd.Series(pd.NaT, index=series.index)
    pending = series.copy()
    for fmt in _DATE_FORMATS:
        mask = result.isna() & pending.notna()
        if not mask.any():
            break
        parsed = pd.to_datetime(pending[mask], format=fmt, errors="coerce")
        result[mask] = parsed
    still_na = result.isna() & pending.notna()
    if still_na.any():
        result[still_na] = pd.to_datetime(pending[still_na], errors="coerce")
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# NORMALIZACIÓN DE TEXTO (helpers locales, los completos están en matching_engine)
# ═══════════════════════════════════════════════════════════════════════════════

def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")

def _norm_title(s) -> str:
    if pd.isna(s) or str(s).strip() == "":
        return ""
    t = _strip_accents(str(s).lower())
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()

def _slug_from_url(url_str) -> str:
    if not url_str or pd.isna(url_str):
        return ""
    path = urlparse(str(url_str)).path
    parts = [p for p in path.split("/") if p]
    return parts[-1].lower() if parts else ""


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS — is_360radio / is_ia
# ═══════════════════════════════════════════════════════════════════════════════

def _tags_contain_author(tags_str: str, author_str: str) -> bool:
    if not tags_str or not author_str or pd.isna(tags_str) or pd.isna(author_str):
        return False
    tags_norm = _strip_accents(str(tags_str).lower())
    tokens = [t.strip() for t in re.split(r"[\s,]+", str(author_str)) if len(t.strip()) > 3]
    return any(tok in tags_norm for tok in [_strip_accents(t.lower()) for t in tokens])


# ═══════════════════════════════════════════════════════════════════════════════
# LOADERS — GA4, Search Console, Producción, AdSense, MGID, AdManager, YouTube
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600)
def load_ga4_general():
    return _to_dt(_read_excel("ga4_360radio_completo.xlsx", "📊_General_Diario"), "date")

@st.cache_data(ttl=3600)
def load_ga4_device():
    return _to_dt(_read_excel("ga4_360radio_completo.xlsx", "📱_General_x_Device"), "date")

@st.cache_data(ttl=3600)
def load_ga4_age():
    return _to_dt(_read_excel("ga4_360radio_completo.xlsx", "👤_General_x_Edad"), "date")

@st.cache_data(ttl=3600)
def load_ga4_city():
    return _to_dt(_read_excel("ga4_360radio_completo.xlsx", "🏙️_General_x_Ciudad"), "date")

@st.cache_data(ttl=3600)
def load_ga4_channel():
    return _to_dt(_read_excel("ga4_360radio_completo.xlsx", "🔗_General_x_Canal"), "date")

@st.cache_data(ttl=3600)
def load_ga4_country():
    return _to_dt(_read_excel("ga4_360radio_completo.xlsx", "🌎_General_x_Pais"), "date")

@st.cache_data(ttl=3600)
def load_ga4_urls():
    for fname, sheet in [
        ("ga4_data_360radio_urls.xlsx", "URLs_x_Fecha_Diaria"),
        ("ga4_360radio_completo.xlsx",  "URLs_x_Fecha_Diaria"),
    ]:
        df = _read_excel(fname, sheet)
        if not df.empty and "pagePath" in df.columns:
            return _safe_numeric(_to_dt(df, "date"), "screenPageViews", "activeUsers")
    return pd.DataFrame()

@st.cache_data(ttl=3600)
def load_ga4_interests():
    for fname, sheet in [
        ("ga4_data_360radio_urls.xlsx", "Intereses_Audiencia"),
        ("ga4_360radio_completo.xlsx",  "Intereses_Audiencia"),
    ]:
        df = _read_excel(fname, sheet)
        if not df.empty:
            return _safe_numeric(df, "activeUsers", "sessions", "screenPageViews")
    return pd.DataFrame()

@st.cache_data(ttl=3600)
def load_search_console():
    base   = "search_console_360radio.xlsx"
    sheets = {
        "daily":   ("📅_GSC_Diario",  "date"),
        "queries": ("🔍_GSC_Queries", "date"),
        "pages":   ("🌐_GSC_Paginas", "date"),
        "country": ("🌎_GSC_Pais",    "date"),
        "device":  ("📱_GSC_Device",  "date"),
    }
    result = {}
    for k, (s, d) in sheets.items():
        df = _read_excel(base, s)
        result[k] = _to_dt(df, d) if not df.empty else pd.DataFrame()
    return result

PRODUCCION_DESDE = pd.Timestamp("2025-01-01")

@st.cache_data(ttl=3600)
def load_produccion():
    df = _read_csv_robust("Produccion.csv")
    if df.empty:
        return df
    df = _to_dt(_to_dt(df, "post_date"), "post_modified")
    # Filtrar solo desde 2025-01-01 para reducir volumen de matching
    if "post_date" in df.columns:
        df = df[df["post_date"] >= PRODUCCION_DESDE].copy().reset_index(drop=True)
    if "post_id"    in df.columns: df["post_id"]      = pd.to_numeric(df["post_id"], errors="coerce")
    if "post_title" in df.columns: df["_title_norm"]  = df["post_title"].apply(_norm_title)
    if "url"        in df.columns:
        df["_prod_slug"] = df["url"].apply(_slug_from_url)
        df["_prod_path"] = df["url"].apply(lambda u: urlparse(str(u)).path.rstrip("/") if pd.notna(u) else "")
    return df

@st.cache_data(ttl=3600)
def load_adsense():
    df = _read_csv_robust("Adsense.csv")
    return _to_dt(_safe_numeric(df, "Estimated earnings (USD)", "Impressions", "Clicks", "Impression RPM (USD)"), "Date")

@st.cache_data(ttl=3600)
def load_mgid():
    df = _read_csv_robust("MGID.csv")
    return _to_dt(_safe_numeric(df, "Revenue", "Page views", "Ad Clicks", "Ad RPM", "Ad vRPM"), "Date")

@st.cache_data(ttl=3600)
def load_admanager():
    base = "admanager_360radio.xlsx"
    return {
        "diario":   _to_dt(_read_excel(base, "GAM_Diario"),    "DATE"),
        "mensual":  _read_excel(base, "GAM_Mensual"),
        "formatos": _read_excel(base, "GAM_Formatos"),
        "devices":  _read_excel(base, "GAM_Dispositivos"),
        "fill":     _to_dt(_read_excel(base, "GAM_Fill_Rate"), "DATE"),
        "orders":   _read_excel(base, "GAM_Orders_LineItems"),
    }

@st.cache_data(ttl=3600)
def load_youtube():
    base = "Youtube histórico.xlsx"
    return {
        "tabla":   _safe_numeric(_read_excel(base, "Datos de la tabla"),
                                 "Visualizaciones", "Impresiones", "Suscriptores", "Ingresos estimados (USD)"),
        "grafico": _to_dt(_read_excel(base, "Datos del gráfico"), "Fecha"),
        "totales": _to_dt(_read_excel(base, "Totales"), "Fecha"),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# LOADERS REDES SOCIALES
# ═══════════════════════════════════════════════════════════════════════════════

def _load_social_base(fname: str, num_cols: list, id_col: str = "identificador de la publicación") -> pd.DataFrame:
    df = _read_csv_robust(fname)
    if df.empty:
        return df
    for old in [id_col, "identificador de la publicación", "identificador"]:
        if old in df.columns and old != "id_post":
            df = df.rename(columns={old: "id_post"}); break
    hora_col = "Hora de publicación"
    if hora_col in df.columns:
        df["fecha_post"] = _parse_fecha(df[hora_col])
    else:
        df["fecha_post"] = pd.NaT
    df = df[df["fecha_post"].notna()].copy()
    df = _safe_numeric(df, *[c for c in num_cols if c in df.columns])
    return df.reset_index(drop=True)

@st.cache_data(ttl=3600)
def load_instagram_posts() -> pd.DataFrame:
    df = _load_social_base(
        "Post Instagram.csv",
        ["Visualizaciones", "Alcance", "Me gusta", "Comentarios",
         "Veces que se ha compartido", "Veces guardado", "Seguidores"],
    )
    if not df.empty and "Tipo de publicación" in df.columns:
        df = df[df["Tipo de publicación"].str.strip() != "Historia de Instagram"].copy()
    return df.reset_index(drop=True)

@st.cache_data(ttl=3600)
def load_instagram_stories() -> pd.DataFrame:
    return _load_social_base(
        "Instagram Historys.csv",
        ["Visualizaciones", "Alcance", "Me gusta", "Clics en el enlace",
         "Respuestas", "Seguidores", "Navegación", "Toques en stickers",
         "Visitas al perfil"],
    )

@st.cache_data(ttl=3600)
def load_facebook() -> pd.DataFrame:
    df = _load_social_base(
        "Post Facebook.csv",
        ["Alcance", "Visualizaciones de vídeo de 3 segundos",
         "Visualizaciones de vídeo de 1 minuto",
         "Reacciones, comentarios y veces que se ha compartido",
         "Reacciones", "Comentarios", "Veces que se ha compartido",
         "Segundos reproducidos", "Segundos reproducidos de media",
         "Espectadores de 3 segundos", "Espectadores de 1 minuto"],
        id_col="Identificador de la pieza de vídeo",
    )
    if not df.empty and "Identificador de la pieza de vídeo" in df.columns:
        df = df.rename(columns={"Identificador de la pieza de vídeo": "id_post"})
    return df.reset_index(drop=True)


# ═══════════════════════════════════════════════════════════════════════════════
# MATCHING PRODUCCIÓN ↔ GA4  (usa el motor robusto de matching_engine.py)
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600)
def load_produccion_con_metricas() -> pd.DataFrame:
    prod = load_produccion()
    urls = load_ga4_urls()

    if prod.empty:
        return prod

    # ── Motor de matching robusto (12 pasos en cascada) ──
    result = match_production_to_ga4(prod, urls)

    # ── Flags is_ia / is_360radio ──
    tags_col   = result["tags"]             if "tags"             in result.columns else pd.Series("", index=result.index)
    author_col = result["post_author_name"] if "post_author_name" in result.columns else pd.Series("", index=result.index)

    result["is_ia"] = tags_col.apply(
        lambda x: bool(re.search(r"s[ií]ntesis", str(x), re.I)))

    result["is_360radio"] = [
        _tags_contain_author(t, a)
        for t, a in zip(tags_col, author_col)
    ]

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# UTILIDADES
# ═══════════════════════════════════════════════════════════════════════════════

def filter_by_date(df: pd.DataFrame, date_col: str, start, end) -> pd.DataFrame:
    if df is None or df.empty or date_col not in df.columns:
        return df if df is not None else pd.DataFrame()
    col  = pd.to_datetime(df[date_col], errors="coerce")
    ts_s = pd.Timestamp(start)
    ts_e = pd.Timestamp(end) + pd.Timedelta(hours=23, minutes=59, seconds=59)
    return df.loc[(col >= ts_s) & (col <= ts_e)].copy().reset_index(drop=True)

def get_date_range(df: pd.DataFrame, col: str):
    from datetime import date as _d
    try:
        if df is None or df.empty or col not in df.columns:
            return _d(2024,1,1), _d.today()
        s = pd.to_datetime(df[col], errors="coerce").dropna()
        return (s.min().date(), s.max().date()) if not s.empty else (_d(2024,1,1), _d.today())
    except Exception:
        from datetime import date as _d2
        return _d2(2024,1,1), _d2.today()

def safe_sum(df, col) -> float:
    try:
        if df is None or df.empty or col not in df.columns: return 0.0
        return float(pd.to_numeric(df[col], errors="coerce").sum())
    except Exception:
        return 0.0

def fmt_number(n) -> str:
    try:
        if pd.isna(n): return "0"
        n = int(n)
        if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
        if n >= 1_000:     return f"{n/1_000:.1f}K"
        return str(n)
    except Exception:
        return "0"

def pct_delta(cur, prev) -> "float | None":
    try:
        if prev == 0 or pd.isna(prev) or pd.isna(cur): return None
        return (cur - prev) / abs(prev) * 100
    except Exception:
        return None

def _delta_str(cur, prev) -> "str | None":
    d = pct_delta(cur, prev)
    return f"{d:+.1f}%" if d is not None else None
