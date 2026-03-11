"""
data_loader.py  –  360Radio Analytics
======================================
Matching Produccion ↔ GA4 (4 pasos en orden de precisión):
  1. post_id == último segmento numérico del pagePath  (ej: /slug/185001/)
  2. post_id == ?p=185001  (query param legacy)
  3. título normalizado
  4. path completo de la URL de producción
"""
import re
import pandas as pd
import numpy as np
import streamlit as st
from pathlib import Path
from urllib.parse import urlparse

DATA_DIR = Path("data")

# ── helpers I/O ────────────────────────────────────────────────────────────────
def _read_excel(fname: str, sheet: str) -> pd.DataFrame:
    path = DATA_DIR / fname
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_excel(path, sheet_name=sheet)
    except Exception:
        return pd.DataFrame()

def _read_csv(fname: str, **kwargs) -> pd.DataFrame:
    path = DATA_DIR / fname
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, **kwargs)
    except Exception:
        return pd.DataFrame()

def _parse_dates(df: pd.DataFrame, col: str) -> pd.DataFrame:
    if not df.empty and col in df.columns:
        df = df.copy()
        df[col] = pd.to_datetime(df[col], errors="coerce")
    return df

# ── helpers matching ──────────────────────────────────────────────────────────
def _id_from_path(path) -> int | None:
    """
    Extrae el post_id del pagePath de GA4.
    /aumento-salarial/185001/  → 185001
    /aumento-salarial/185001   → 185001
    /?p=185001                  → 185001
    Solo acepta IDs de 4+ dígitos para evitar falsos positivos.
    """
    if not path or pd.isna(path):
        return None
    s = str(path).strip()
    # Último segmento numérico ≥ 4 dígitos antes del fin o query string
    m = re.search(r'/(\d{4,})/?(?:\?.*)?$', s)
    if m:
        return int(m.group(1))
    # Fallback: ?p=XXXX
    m2 = re.search(r'[?&]p=(\d+)', s)
    if m2:
        return int(m2.group(1))
    return None

def _norm(s) -> str:
    if pd.isna(s):
        return ""
    t = str(s).lower()
    t = re.sub(r'[^\w\s]', ' ', t)
    return re.sub(r'\s+', ' ', t).strip()

# ── loaders individuales ───────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def load_ga4_general():
    return _parse_dates(_read_excel("ga4_360radio_completo.xlsx", "📊_General_Diario"), "date")

@st.cache_data(ttl=3600)
def load_ga4_device():
    return _parse_dates(_read_excel("ga4_360radio_completo.xlsx", "📱_General_x_Device"), "date")

@st.cache_data(ttl=3600)
def load_ga4_age():
    return _parse_dates(_read_excel("ga4_360radio_completo.xlsx", "👤_General_x_Edad"), "date")

@st.cache_data(ttl=3600)
def load_ga4_city():
    return _parse_dates(_read_excel("ga4_360radio_completo.xlsx", "🏙️_General_x_Ciudad"), "date")

@st.cache_data(ttl=3600)
def load_ga4_channel():
    return _parse_dates(_read_excel("ga4_360radio_completo.xlsx", "🔗_General_x_Canal"), "date")

@st.cache_data(ttl=3600)
def load_ga4_country():
    return _parse_dates(_read_excel("ga4_360radio_completo.xlsx", "🌎_General_x_Pais"), "date")

@st.cache_data(ttl=3600)
def load_ga4_urls_daily():
    for fname, sheet in [
        ("ga4_360radio_completo.xlsx",  "URLs_x_Fecha_Diaria"),
        ("ga4_data_360radio_urls.xlsx", "URLs_x_Fecha_Diaria"),
    ]:
        df = _read_excel(fname, sheet)
        if not df.empty:
            return _parse_dates(df, "date")
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
        "daily":   _parse_dates(_read_excel(base, "📅_GSC_Diario"),  "date"),
        "queries": _parse_dates(_read_excel(base, "🔍_GSC_Queries"), "date"),
        "pages":   _parse_dates(_read_excel(base, "🌐_GSC_Paginas"), "date"),
        "country": _parse_dates(_read_excel(base, "🌎_GSC_Pais"),    "date"),
        "device":  _parse_dates(_read_excel(base, "📱_GSC_Device"),  "date"),
    }

@st.cache_data(ttl=3600)
def load_produccion():
    df = _read_csv("Produccion.csv")
    if df.empty:
        return df
    df = _parse_dates(df, "post_date")
    df = _parse_dates(df, "post_modified")
    if "post_id" in df.columns:
        df["post_id"] = pd.to_numeric(df["post_id"], errors="coerce")
    if "post_title" in df.columns:
        df["_title_norm"] = df["post_title"].apply(_norm)
    return df

@st.cache_data(ttl=3600)
def load_adsense():
    return _parse_dates(_read_csv("Adsense.csv"), "Date")

@st.cache_data(ttl=3600)
def load_mgid():
    return _parse_dates(_read_csv("MGID.csv"), "Date")

@st.cache_data(ttl=3600)
def load_admanager():
    base = "admanager_360radio.xlsx"
    return {
        "diario":   _parse_dates(_read_excel(base, "GAM_Diario"),         "DATE"),
        "mensual":  _read_excel(base, "GAM_Mensual"),
        "formatos": _read_excel(base, "GAM_Formatos"),
        "devices":  _read_excel(base, "GAM_Dispositivos"),
        "fill":     _parse_dates(_read_excel(base, "GAM_Fill_Rate"),      "DATE"),
        "orders":   _read_excel(base, "GAM_Orders_LineItems"),
    }

@st.cache_data(ttl=3600)
def load_youtube():
    base = "Youtube histórico.xlsx"
    return {
        "tabla":   _read_excel(base, "Datos de la tabla"),
        "grafico": _parse_dates(_read_excel(base, "Datos del gráfico"), "Fecha"),
        "totales": _parse_dates(_read_excel(base, "Totales"),           "Fecha"),
    }

@st.cache_data(ttl=3600)
def load_instagram_posts():
    return _parse_dates(_read_csv("Post Instagram.csv"), "Fecha")

@st.cache_data(ttl=3600)
def load_instagram_stories():
    return _parse_dates(_read_csv("Instagram Historys.csv"), "Fecha")

@st.cache_data(ttl=3600)
def load_facebook():
    return _parse_dates(_read_csv("Post Facebook.csv"), "Fecha")


# ── MATCHING PRODUCCIÓN ↔ GA4 ─────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def load_produccion_con_metricas() -> pd.DataFrame:
    """
    Enriquece Produccion.csv con métricas GA4 acumuladas (todo el histórico).
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

    urls = urls.copy()

    # Precalcular claves en el DF de GA4
    if "pagePath" in urls.columns:
        urls["_path_id"]    = urls["pagePath"].apply(_id_from_path)
        urls["_clean_path"] = urls["pagePath"].apply(
            lambda p: str(p).rstrip("/") if pd.notna(p) else ""
        )
    if "pageTitle" in urls.columns:
        urls["_title_norm"] = urls["pageTitle"].apply(_norm)

    # Agregar por cada clave
    def _agg_by(key_col):
        if key_col not in urls.columns:
            return pd.DataFrame()
        return (
            urls.dropna(subset=[key_col])
              .groupby(key_col, as_index=False)
              .agg(ga4_views=("screenPageViews","sum"),
                   ga4_users=("activeUsers","sum"))
        )

    ga4_id    = _agg_by("_path_id")
    ga4_title = _agg_by("_title_norm")
    ga4_path  = _agg_by("_clean_path")

    if not ga4_id.empty:
        ga4_id["_path_id"] = pd.to_numeric(ga4_id["_path_id"], errors="coerce")

    # URL path de producción
    if "url" in result.columns:
        result["_prod_path"] = result["url"].apply(
            lambda u: urlparse(str(u)).path.rstrip("/") if pd.notna(u) else ""
        )

    # ── Paso 1: post_id ─────────────────────────────────────────────────────
    if not ga4_id.empty and "post_id" in result.columns:
        m = result[["post_id"]].merge(
            ga4_id, left_on="post_id", right_on="_path_id", how="left"
        )
        hit = m["ga4_views"].notna()
        result.loc[hit.values, "ga4_views"]    = m.loc[hit, "ga4_views"].values
        result.loc[hit.values, "ga4_users"]    = m.loc[hit, "ga4_users"].values
        result.loc[hit.values, "match_method"] = "post_id"

    # ── Paso 2: título ──────────────────────────────────────────────────────
    if not ga4_title.empty and "_title_norm" in result.columns:
        no_match = result["match_method"] == "sin_match"
        if no_match.any():
            sub = result.loc[no_match, ["_title_norm"]].merge(
                ga4_title, on="_title_norm", how="left"
            )
            hit = sub["ga4_views"].notna().values
            idx = result[no_match].index[hit]
            result.loc[idx, "ga4_views"]    = sub.loc[hit, "ga4_views"].values
            result.loc[idx, "ga4_users"]    = sub.loc[hit, "ga4_users"].values
            result.loc[idx, "match_method"] = "titulo"

    # ── Paso 3: path URL completo ───────────────────────────────────────────
    if not ga4_path.empty and "_prod_path" in result.columns:
        no_match = result["match_method"] == "sin_match"
        if no_match.any():
            sub = result.loc[no_match, ["_prod_path"]].merge(
                ga4_path, left_on="_prod_path", right_on="_clean_path", how="left"
            )
            hit = sub["ga4_views"].notna().values
            idx = result[no_match].index[hit]
            result.loc[idx, "ga4_views"]    = sub.loc[hit, "ga4_views"].values
            result.loc[idx, "ga4_users"]    = sub.loc[hit, "ga4_users"].values
            result.loc[idx, "match_method"] = "path_url"

    result["ga4_views"] = result["ga4_views"].fillna(0).astype(int)
    result["ga4_users"] = result["ga4_users"].fillna(0).astype(int)

    # Flag IA
    tags_col = result["tags"] if "tags" in result.columns else pd.Series("", index=result.index)
    result["is_ia"] = tags_col.apply(
        lambda x: bool(re.search(r'\bIA\b|\binteligencia[\s_-]?artificial\b', str(x), re.I))
    )

    return result


# ── UTILIDADES ────────────────────────────────────────────────────────────────
def filter_by_date(df, date_col, start, end):
    """
    Filtra un DataFrame por rango de fechas.
    Convierte start/end a pd.Timestamp para evitar TypeError en pandas >= 2.x
    """
    if df is None or df.empty or date_col not in df.columns:
        return pd.DataFrame() if df is None else df
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    # Normalizar start/end a pd.Timestamp (evita TypeError con dt.date en pandas 2.x+)
    ts_start = pd.Timestamp(start)
    ts_end   = pd.Timestamp(end) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    mask = (df[date_col] >= ts_start) & (df[date_col] <= ts_end)
    return df[mask].reset_index(drop=True)

def pct_delta(current, previous):
    if previous == 0 or pd.isna(previous) or pd.isna(current):
        return None
    return (current - previous) / abs(previous) * 100

def fmt_number(n) -> str:
    if pd.isna(n):
        return "0"
    n = int(n)
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)

def safe_sum(df, col) -> float:
    if df is None or df.empty or col not in df.columns:
        return 0.0
    return float(df[col].sum())

def get_date_range(df, col):
    from datetime import date as _d
    if df is None or df.empty or col not in df.columns:
        return _d(2024, 1, 1), _d.today()
    s = pd.to_datetime(df[col], errors="coerce").dropna()
    if s.empty:
        return _d(2024, 1, 1), _d.today()
    return s.min().date(), s.max().date()
