"""
data_loader.py  –  360Radio Analytics v2.2
===========================================
Matching Produccion ↔ GA4 en 3 pasos:
  1. último segmento numérico ≥4 dígitos del pagePath  → /slug/185001/
  2. título normalizado (pageTitle vs post_title)
  3. path completo de la URL de producción vs pagePath
"""
import re
import pandas as pd
import numpy as np
import streamlit as st
from pathlib import Path
from urllib.parse import urlparse

DATA_DIR = Path("data")

# ── I/O ───────────────────────────────────────────────────────────────────────
def _read_excel(fname: str, sheet: str) -> pd.DataFrame:
    path = DATA_DIR / fname
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_excel(path, sheet_name=sheet)
    except Exception:
        return pd.DataFrame()

def _read_csv(fname: str, **kw) -> pd.DataFrame:
    path = DATA_DIR / fname
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, **kw)
    except Exception:
        return pd.DataFrame()

def _to_dt(df: pd.DataFrame, col: str) -> pd.DataFrame:
    if not df.empty and col in df.columns:
        df = df.copy()
        df[col] = pd.to_datetime(df[col], errors="coerce")
    return df

# ── Matching helpers ──────────────────────────────────────────────────────────
def _id_from_path(path) -> int | None:
    """Extrae el post_id del pagePath: /slug-nota/185001/  →  185001"""
    if not path or pd.isna(path):
        return None
    s = str(path).strip()
    # Último segmento numérico ≥ 4 dígitos antes de fin o query string
    m = re.search(r'/(\d{4,})/?(?:\?.*)?$', s)
    if m:
        return int(m.group(1))
    # Fallback ?p=XXXXX
    m2 = re.search(r'[?&]p=(\d+)', s)
    if m2:
        return int(m2.group(1))
    return None

def _norm(s) -> str:
    """Normaliza texto para comparar títulos."""
    if pd.isna(s):
        return ""
    t = re.sub(r'[^\w\s]', ' ', str(s).lower())
    return re.sub(r'\s+', ' ', t).strip()

# ── Loaders individuales ──────────────────────────────────────────────────────
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
def load_ga4_urls_daily():
    for fname, sheet in [
        ("ga4_360radio_completo.xlsx",  "URLs_x_Fecha_Diaria"),
        ("ga4_data_360radio_urls.xlsx", "URLs_x_Fecha_Diaria"),
    ]:
        df = _read_excel(fname, sheet)
        if not df.empty:
            return _to_dt(df, "date")
    return pd.DataFrame()

@st.cache_data(ttl=3600)
def load_ga4_interests():
    for fname, sheet in [
        ("ga4_360radio_completo.xlsx",  "Intereses_Audiencia"),
        ("ga4_data_360radio_urls.xlsx", "Intereses_Audiencia"),
    ]:
        df = _read_excel(fname, sheet)
        if not df.empty:
            return df
    return pd.DataFrame()

@st.cache_data(ttl=3600)
def load_search_console():
    base = "search_console_360radio.xlsx"
    return {
        "daily":   _to_dt(_read_excel(base, "📅_GSC_Diario"),  "date"),
        "queries": _to_dt(_read_excel(base, "🔍_GSC_Queries"), "date"),
        "pages":   _to_dt(_read_excel(base, "🌐_GSC_Paginas"), "date"),
        "country": _to_dt(_read_excel(base, "🌎_GSC_Pais"),    "date"),
        "device":  _to_dt(_read_excel(base, "📱_GSC_Device"),  "date"),
    }

@st.cache_data(ttl=3600)
def load_produccion():
    df = _read_csv("Produccion.csv")
    if df.empty:
        return df
    df = _to_dt(df, "post_date")
    df = _to_dt(df, "post_modified")
    if "post_id" in df.columns:
        df["post_id"] = pd.to_numeric(df["post_id"], errors="coerce")
    if "post_title" in df.columns:
        df["_title_norm"] = df["post_title"].apply(_norm)
    return df

@st.cache_data(ttl=3600)
def load_adsense():
    return _to_dt(_read_csv("Adsense.csv"), "Date")

@st.cache_data(ttl=3600)
def load_mgid():
    return _to_dt(_read_csv("MGID.csv"), "Date")

@st.cache_data(ttl=3600)
def load_admanager():
    base = "admanager_360radio.xlsx"
    return {
        "diario":   _to_dt(_read_excel(base, "GAM_Diario"),         "DATE"),
        "mensual":  _read_excel(base, "GAM_Mensual"),
        "formatos": _read_excel(base, "GAM_Formatos"),
        "devices":  _read_excel(base, "GAM_Dispositivos"),
        "fill":     _to_dt(_read_excel(base, "GAM_Fill_Rate"),      "DATE"),
        "orders":   _read_excel(base, "GAM_Orders_LineItems"),
    }

@st.cache_data(ttl=3600)
def load_youtube():
    base = "Youtube histórico.xlsx"
    return {
        "tabla":   _read_excel(base, "Datos de la tabla"),
        "grafico": _to_dt(_read_excel(base, "Datos del gráfico"), "Fecha"),
        "totales": _to_dt(_read_excel(base, "Totales"), "Fecha"),
    }

@st.cache_data(ttl=3600)
def load_instagram_posts():
    df = _read_csv("Post Instagram.csv")
    # Intentar varios separadores si viene vacío
    if df.empty or len(df.columns) <= 1:
        for sep in [";", "\t", ","]:
            df = _read_csv("Post Instagram.csv", sep=sep)
            if not df.empty and len(df.columns) > 1:
                break
    return _to_dt(df, "Fecha")

@st.cache_data(ttl=3600)
def load_instagram_stories():
    df = _read_csv("Instagram Historys.csv")
    if df.empty or len(df.columns) <= 1:
        for sep in [";", "\t", ","]:
            df = _read_csv("Instagram Historys.csv", sep=sep)
            if not df.empty and len(df.columns) > 1:
                break
    return _to_dt(df, "Fecha")

@st.cache_data(ttl=3600)
def load_facebook():
    df = _read_csv("Post Facebook.csv")
    if df.empty or len(df.columns) <= 1:
        for sep in [";", "\t", ","]:
            df = _read_csv("Post Facebook.csv", sep=sep)
            if not df.empty and len(df.columns) > 1:
                break
    return _to_dt(df, "Fecha")

# ── MATCHING Producción ↔ GA4 ─────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def load_produccion_con_metricas() -> pd.DataFrame:
    """
    Enriquece Produccion.csv con métricas GA4 acumuladas.
    Columnas añadidas: ga4_views, ga4_users, match_method, is_ia
    """
    prod = load_produccion()
    urls = load_ga4_urls_daily()

    if prod.empty:
        return prod

    result = prod.copy()
    result["ga4_views"]    = np.nan
    result["ga4_users"]    = np.nan
    result["match_method"] = "sin_match"

    if urls.empty:
        result["ga4_views"]  = 0
        result["ga4_users"]  = 0
        result["is_ia"] = False
        return result

    urls_w = urls.copy()

    # ── Precalcular claves en GA4 ───────────────────────────────────────────
    if "pagePath" in urls_w.columns:
        urls_w["_path_id"]    = urls_w["pagePath"].apply(_id_from_path)
        urls_w["_clean_path"] = urls_w["pagePath"].apply(
            lambda p: str(p).rstrip("/") if pd.notna(p) else "")
    if "pageTitle" in urls_w.columns:
        urls_w["_title_norm"] = urls_w["pageTitle"].apply(_norm)

    # ── Agregar GA4 por cada clave ──────────────────────────────────────────
    def _agg(key_col):
        if key_col not in urls_w.columns:
            return pd.DataFrame()
        sub = urls_w.dropna(subset=[key_col])
        if sub.empty:
            return pd.DataFrame()
        agg_kw = {}
        if "screenPageViews" in sub.columns: agg_kw["ga4_views"] = ("screenPageViews","sum")
        if "activeUsers"     in sub.columns: agg_kw["ga4_users"] = ("activeUsers","sum")
        if not agg_kw:
            return pd.DataFrame()
        return sub.groupby(key_col, as_index=False).agg(**agg_kw)

    ga4_id    = _agg("_path_id")
    ga4_title = _agg("_title_norm")
    ga4_path  = _agg("_clean_path")

    if not ga4_id.empty:
        ga4_id["_path_id"] = pd.to_numeric(ga4_id["_path_id"], errors="coerce")

    # URL path de producción
    if "url" in result.columns:
        result["_prod_path"] = result["url"].apply(
            lambda u: urlparse(str(u)).path.rstrip("/") if pd.notna(u) else "")

    # ── PASO 1: post_id ─────────────────────────────────────────────────────
    if not ga4_id.empty and "post_id" in result.columns:
        m1 = result[["post_id"]].merge(
            ga4_id, left_on="post_id", right_on="_path_id", how="left")
        hit = m1["ga4_views"].notna().values
        if hit.any():
            result.loc[hit, "ga4_views"]    = m1.loc[hit, "ga4_views"].values
            result.loc[hit, "ga4_users"]    = m1.loc[hit, "ga4_users"].fillna(0).values
            result.loc[hit, "match_method"] = "post_id"

    # ── PASO 2: título ──────────────────────────────────────────────────────
    if not ga4_title.empty and "_title_norm" in result.columns:
        no_match = result["match_method"] == "sin_match"
        if no_match.any():
            sub2 = result.loc[no_match, ["_title_norm"]].merge(
                ga4_title, on="_title_norm", how="left")
            hit2 = sub2["ga4_views"].notna().values
            idx2 = result.index[no_match][hit2]
            if len(idx2):
                result.loc[idx2, "ga4_views"]    = sub2.loc[hit2, "ga4_views"].values
                result.loc[idx2, "ga4_users"]    = sub2.loc[hit2, "ga4_users"].fillna(0).values
                result.loc[idx2, "match_method"] = "titulo"

    # ── PASO 3: path URL completo ───────────────────────────────────────────
    if not ga4_path.empty and "_prod_path" in result.columns:
        no_match = result["match_method"] == "sin_match"
        if no_match.any():
            sub3 = result.loc[no_match, ["_prod_path"]].merge(
                ga4_path, left_on="_prod_path", right_on="_clean_path", how="left")
            hit3 = sub3["ga4_views"].notna().values
            idx3 = result.index[no_match][hit3]
            if len(idx3):
                result.loc[idx3, "ga4_views"]    = sub3.loc[hit3, "ga4_views"].values
                result.loc[idx3, "ga4_users"]    = sub3.loc[hit3, "ga4_users"].fillna(0).values
                result.loc[idx3, "match_method"] = "path_url"

    result["ga4_views"] = result["ga4_views"].fillna(0).astype(int)
    result["ga4_users"] = result["ga4_users"].fillna(0).astype(int)

    tags_col = result["tags"] if "tags" in result.columns else pd.Series("", index=result.index)
    result["is_ia"] = tags_col.apply(
        lambda x: bool(re.search(r'\bIA\b|\binteligencia[\s_-]?artificial\b', str(x), re.I)))

    return result


# ── UTILIDADES ────────────────────────────────────────────────────────────────
def filter_by_date(df, date_col, start, end):
    """
    Filtra un DataFrame por rango de fechas.
    Usa pd.Timestamp para evitar TypeError en pandas 2.x con dt.date.
    """
    if df is None or df.empty or date_col not in df.columns:
        return df if df is not None else pd.DataFrame()
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    # Convertir a Timestamp para comparación segura en pandas 2.x
    ts_start = pd.Timestamp(start)
    ts_end   = pd.Timestamp(end) + pd.Timedelta(hours=23, minutes=59, seconds=59)
    mask = (df[date_col] >= ts_start) & (df[date_col] <= ts_end)
    return df[mask].reset_index(drop=True)


def pct_delta(current, previous):
    try:
        if previous == 0 or pd.isna(previous) or pd.isna(current):
            return None
        return (current - previous) / abs(previous) * 100
    except Exception:
        return None


def fmt_number(n) -> str:
    try:
        if pd.isna(n):
            return "0"
        n = int(n)
        if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
        if n >= 1_000:     return f"{n/1_000:.1f}K"
        return str(n)
    except Exception:
        return "0"


def safe_sum(df, col) -> float:
    try:
        if df is None or df.empty or col not in df.columns:
            return 0.0
        return float(pd.to_numeric(df[col], errors="coerce").sum())
    except Exception:
        return 0.0


def get_date_range(df, col):
    from datetime import date as _d
    try:
        if df is None or df.empty or col not in df.columns:
            return _d(2024, 1, 1), _d.today()
        s = pd.to_datetime(df[col], errors="coerce").dropna()
        if s.empty:
            return _d(2024, 1, 1), _d.today()
        return s.min().date(), s.max().date()
    except Exception:
        return _d(2024, 1, 1), _d.today()


def _delta_str(cur, prev):
    """Devuelve string de variación para st.metric delta."""
    d = pct_delta(cur, prev)
    return f"{d:+.1f}%" if d is not None else None
