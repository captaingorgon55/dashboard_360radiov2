"""
data_loader.py  -  360Radio Analytics v4.4  (FAST I/O)
=======================================================
Optimizaciones v4.2:
  * _read_excel: convierte Excel -> Parquet la primera vez (10-50x mas rapido
    en lecturas siguientes). El parquet se invalida si el Excel cambia (mtime).
  * load_ga4_urls + load_produccion corren en paralelo (ThreadPoolExecutor)
    antes del matching, ahorrando el tiempo del mas lento.
  * Produccion.csv filtrado desde 2025-01-01 para reducir volumen.
  * Matching engine v4.1 con early-exit y fuzzy vectorizado.

Fix v4.3:
  * _clean_str: normaliza "nan", None y vacíos a "" antes de cualquier
    comparación de autor/tags — evita que el string literal "nan" rompa
    _resolve_author y _tags_contain_author.
  * _is_generic_author: acepta también autor vacío/nan como genérico
    cuando post_author_name no viene relleno.
  * _tags_contain_author: umbral de longitud de token bajado de >3 a >=2
    para no descartar apellidos cortos (Gil, Paz, etc.).
  * load_produccion_con_metricas: limpia tags y author antes de pasarlos
    a las funciones de resolución.
"""
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

import numpy as np
import pandas as pd
import streamlit as st

# Matching deshabilitado: la producción ya trae las métricas en el Excel
_HAS_MATCHING = False
_match_prod_fn = None
_match_stats_fn = None

DATA_DIR  = Path("data")
CACHE_DIR = Path(".parquet_cache")
CACHE_DIR.mkdir(exist_ok=True)

PRODUCCION_DESDE = pd.Timestamp("2025-01-01")


# =============================================================================
# HELPERS I/O  —  con cache parquet para Excel
# =============================================================================

def _parquet_path(fname: str, sheet: str) -> Path:
    safe = re.sub(r"[^\w]", "_", f"{fname}__{sheet}")
    return CACHE_DIR / f"{safe}.parquet"


def _read_excel(fname: str, sheet: str) -> pd.DataFrame:
    """
    Lee un sheet de Excel. Si ya existe un parquet mas reciente que el Excel,
    lo usa directamente (10-50x mas rapido). Si no, lee el Excel y guarda parquet.
    """
    src = DATA_DIR / fname
    if not src.exists():
        return pd.DataFrame()

    pq = _parquet_path(fname, sheet)
    src_mtime = src.stat().st_mtime

    if pq.exists() and pq.stat().st_mtime >= src_mtime:
        try:
            return pd.read_parquet(pq)
        except Exception:
            pq.unlink(missing_ok=True)

    df = pd.DataFrame()
    for engine in [None, "openpyxl", "xlrd"]:
        try:
            kw = {"engine": engine} if engine else {}
            df = pd.read_excel(src, sheet_name=sheet, **kw)
            break
        except Exception:
            continue

    if not df.empty:
        try:
            df = df.loc[:, ~df.columns.duplicated()]
            for col in df.select_dtypes(include="object").columns:
                df[col] = df[col].astype(str)
            df.to_parquet(pq, index=False)
        except Exception:
            pass

    return df


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


# =============================================================================
# PARSER DE FECHA  —  multi-formato robusto
# =============================================================================

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


# =============================================================================
# NORMALIZACION DE TEXTO
# =============================================================================

def _strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


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


# =============================================================================
# LIMPIEZA DE STRINGS
# =============================================================================

_NAN_STRINGS = {"nan", "none", "null", "na", "n/a", "<na>"}

def _clean_str(val) -> str:
    if val is None:
        return ""
    if isinstance(val, float) and (val != val):
        return ""
    s = str(val).strip()
    return "" if s.lower() in _NAN_STRINGS else s


# =============================================================================
# HELPERS AUTOR
# =============================================================================

_AUTHOR_ALIASES = {
    "andres m": "Andrés Martín",
    "andresm": "Andrés Martín",
    "andres martin": "Andrés Martín",
    "andrés martin": "Andrés Martín",
    "andrés m": "Andrés Martín",
    "julieth b": "Julieth Barbosa",
    "juliethb": "Julieth Barbosa",
    "julieth barbosa": "Julieth Barbosa",
    "juan camilo ocampo": "Juan Camilo Ocampo",
    "juan camilo": "Juan Camilo Ocampo",
    "juan o": "Juan Camilo Ocampo",
    "juanocampo": "Juan Camilo Ocampo",
    "juan ocampo": "Juan Camilo Ocampo",
    "daniel g": "Daniel García",
    "daniel garcia": "Daniel García",
    "daniel garcía": "Daniel García",
    "jorge g": "Jorge González",
    "jorge gonzalez": "Jorge González",
    "jorge gonzález": "Jorge González",
    "miguel v": "Miguel Vélez",
    "miguel velez": "Miguel Vélez",
    "miguel vélez": "Miguel Vélez",
    "katherine aranda": "Katherine Aranda",
    "katherine a": "Katherine Aranda",
    "camilo jaimes": "Camilo Jaimes",
    "camilo j": "Camilo Jaimes",
    "simon zapata": "Simón Zapata",
    "simón zapata": "Simón Zapata",
    "saul hernandez": "Saúl Hernández",
    "saúl hernández": "Saúl Hernández",
}

_IS_360RADIO_AUTHOR = re.compile(r"360\s*radio|radio\s*360|360radio", re.I)


def _is_generic_author(author_str) -> bool:
    s = _clean_str(author_str)
    if not s:
        return True
    return bool(_IS_360RADIO_AUTHOR.search(s))


def _resolve_author(author_str, tags_str) -> str:
    author_clean = _clean_str(author_str)
    tags_clean   = _clean_str(tags_str)

    if not _is_generic_author(author_clean):
        return author_clean

    if not tags_clean:
        return author_clean or "360 Radio"

    tags_norm = _strip_accents(tags_clean.lower())
    for alias, nombre_real in _AUTHOR_ALIASES.items():
        if _strip_accents(alias.lower()) in tags_norm:
            return nombre_real

    return author_clean or "360 Radio"


def _tags_contain_author(tags_str: str, author_str: str) -> bool:
    tags_clean   = _clean_str(tags_str)
    author_clean = _clean_str(author_str)

    if not tags_clean or not author_clean:
        return False

    tags_norm = _strip_accents(tags_clean.lower())
    tokens = [
        t.strip()
        for t in re.split(r"[\s,]+", author_clean)
        if len(t.strip()) >= 2
    ]
    return any(_strip_accents(t.lower()) in tags_norm for t in tokens)


# =============================================================================
# LOADERS  —  GA4
# =============================================================================

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


# =============================================================================
# LOADERS  —  Search Console, Produccion, AdSense, MGID, AdManager, YouTube
# =============================================================================

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


@st.cache_data(ttl=3600)
def load_produccion():
    """
    Carga producción directamente desde Produccion.xlsx, hoja 'Notas + Trafico'.
    No hace matching contra GA4: el Excel ya trae screenPageViews, activeUsers,
    userEngagementDuration y _match_type.
    Normaliza nombres de columnas para que General funcione sin cambios.
    """
    df = _read_excel("Produccion.xlsx", "Notas + Trafico")
    if df.empty:
        return df

    rename_map = {}
    for c in df.columns:
        s = str(c).strip()
        k = s.lower().replace(" ", "").replace("_", "")
        if k == "postauthorname":
            rename_map[c] = "post_author_name"
        elif k == "posttitle":
            rename_map[c] = "post_title"
        elif k == "postdate":
            rename_map[c] = "post_date"
        elif k == "postmodified":
            rename_map[c] = "post_modified"
        elif k == "poststatus":
            rename_map[c] = "post_status"
        elif k == "postid":
            rename_map[c] = "post_id"
        elif k == "postauthor":
            rename_map[c] = "post_author"
        elif k == "screenpageviews":
            rename_map[c] = "screenPageViews"
        elif k == "activeusers":
            rename_map[c] = "activeUsers"
        elif k == "userengagementduration":
            rename_map[c] = "userEngagementDuration"
        elif k in {"matchtype", "_matchtype"}:
            rename_map[c] = "_match_type"
        elif k == "permalink":
            rename_map[c] = "permalink"
        elif k == "url":
            rename_map[c] = "url"
        elif k == "categories":
            rename_map[c] = "categories"
        elif k == "tags":
            rename_map[c] = "tags"
    if rename_map:
        df = df.rename(columns=rename_map)

    df = _to_dt(_to_dt(df, "post_date"), "post_modified")

    if "post_date" in df.columns:
        df = df[df["post_date"] >= PRODUCCION_DESDE].copy().reset_index(drop=True)

    if "post_id" in df.columns:
        df["post_id"] = pd.to_numeric(df["post_id"], errors="coerce")

    df = _safe_numeric(df, "screenPageViews", "activeUsers", "userEngagementDuration")

    if "post_title" in df.columns:
        df["_title_norm"] = df["post_title"].apply(_norm_title)

    url_col = "url" if "url" in df.columns else ("permalink" if "permalink" in df.columns else None)
    if url_col is not None:
        if url_col != "url":
            df["url"] = df[url_col].astype(str)
        df["_prod_slug"] = df["url"].apply(_slug_from_url)
        df["_prod_path"] = df["url"].apply(
            lambda u: urlparse(str(u)).path.rstrip("/").lower() if pd.notna(u) else ""
        )

    if "screenPageViews" in df.columns and "ga4_views" not in df.columns:
        df["ga4_views"] = df["screenPageViews"]
    if "activeUsers" in df.columns and "ga4_users" not in df.columns:
        df["ga4_users"] = df["activeUsers"]
    if "_match_type" in df.columns and "match_method" not in df.columns:
        df["match_method"] = df["_match_type"].astype(str)
    elif "match_method" not in df.columns:
        df["match_method"] = "excel_notas_trafico"

    for c in ["post_author_name", "categories", "tags", "post_title", "url"]:
        if c not in df.columns:
            df[c] = ""

    return df


@st.cache_data(ttl=3600)
def load_adsense():
    df = _read_csv_robust("Adsense.csv")
    return _to_dt(
        _safe_numeric(df, "Estimated earnings (USD)", "Impressions", "Clicks", "Impression RPM (USD)"),
        "Date"
    )

@st.cache_data(ttl=3600)
def load_mgid():
    df = _read_csv_robust("MGID.csv")
    return _to_dt(
        _safe_numeric(df, "Revenue", "Page views", "Ad Clicks", "Ad RPM", "Ad vRPM"),
        "Date"
    )

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
def load_viads() -> pd.DataFrame:
    candidates = [
        DATA_DIR / "statistics_2025-01-01_2026-04-01.csv",
        DATA_DIR / "viads.csv",
        DATA_DIR / "Viads.csv",
    ]
    if DATA_DIR.exists():
        candidates += sorted(DATA_DIR.glob("statistics_*.csv"))

    df = pd.DataFrame()
    for path in candidates:
        if path.exists():
            try:
                tmp = pd.read_csv(path, sep=";", low_memory=False)
                if len(tmp.columns) > 1:
                    df = tmp
                    break
            except Exception:
                continue

    if df.empty:
        return df

    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], format="%d.%m.%Y", errors="coerce")
        df = df[df["Date"].notna()].copy()
        df = df.sort_values("Date").reset_index(drop=True)

    for col in ["Impressions", "Clicks", "CTR", "CPM", "Income"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    return df


@st.cache_data(ttl=3600)
def load_youtube():
    base = "Youtube histórico.xlsx"
    src = DATA_DIR / base
    if not src.exists():
        return {"tabla": pd.DataFrame(), "grafico": pd.DataFrame(), "totales": pd.DataFrame()}
    try:
        df = pd.read_excel(src, sheet_name=0)
    except Exception:
        try:
            df = pd.read_excel(src, sheet_name=0, engine="openpyxl")
        except Exception:
            df = pd.DataFrame()
    df = _safe_numeric(
        df,
        "Visualizaciones", "Impresiones", "Suscriptores",
        "Ingresos estimados (USD)", "Tiempo de visualización (horas)",
        "Porcentaje de clics de las impresiones (%)"
    )
    fecha_col = "Hora de publicación del vídeo"
    if fecha_col in df.columns:
        raw = df[fecha_col].astype(str).str.strip()
        raw = raw.str.replace(r"\s*,\s*", ", ", regex=True)
        parsed = pd.to_datetime(raw, format="%b %d, %Y", errors="coerce")
        mask = parsed.isna()
        if mask.any():
            parsed[mask] = pd.to_datetime(raw[mask], errors="coerce", dayfirst=False)
        df[fecha_col] = parsed
        df["Fecha"] = parsed

    return {"tabla": df, "grafico": df, "totales": pd.DataFrame()}


# =============================================================================
# LOADERS  —  Redes Sociales
# =============================================================================

def _load_social_base(fname: str, num_cols: list,
                      id_col: str = "identificador de la publicación") -> pd.DataFrame:
    df = _read_csv_robust(fname)
    if df.empty:
        return df
    for candidate in [id_col,
                      "identificador de la publicación",
                      "identificador de la publicacion",
                      "Identificador de la pieza de vídeo",
                      "Identificador de la pieza de video",
                      "identificador"]:
        if candidate in df.columns and candidate != "id_post":
            df = df.rename(columns={candidate: "id_post"})
            break
    for hora_col in ["Hora de publicación", "Hora de publicacion"]:
        if hora_col in df.columns:
            df["fecha_post"] = _parse_fecha(df[hora_col].astype(str).replace("nan", pd.NA))
            break
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
        id_col="identificador de la publicación",
    )
    if not df.empty:
        for tipo_col in ["Tipo de publicación", "Tipo de publicacion"]:
            if tipo_col in df.columns:
                df = df[df[tipo_col].str.strip() != "Historia de Instagram"].copy()
                break
    return df.reset_index(drop=True)


@st.cache_data(ttl=3600)
def load_instagram_stories() -> pd.DataFrame:
    return _load_social_base(
        "Instagram Historys.csv",
        ["Visualizaciones", "Alcance", "Me gusta", "Clics en el enlace",
         "Respuestas", "Seguidores", "Navegación", "Navegacion",
         "Toques en stickers", "Visitas al perfil"],
        id_col="identificador de la publicación",
    )


@st.cache_data(ttl=3600)
def load_facebook() -> pd.DataFrame:
    df = _load_social_base(
        "Post Facebook.csv",
        ["Alcance",
         "Visualizaciones de vídeo de 3 segundos",
         "Visualizaciones de vídeo de 1 minuto",
         "Visualizaciones de video de 3 segundos",
         "Visualizaciones de video de 1 minuto",
         "Reacciones, comentarios y veces que se ha compartido",
         "Reacciones", "Comentarios", "Veces que se ha compartido",
         "Segundos reproducidos", "Segundos reproducidos de media",
         "Espectadores de 3 segundos", "Espectadores de 1 minuto"],
        id_col="Identificador de la pieza de vídeo",
    )
    return df.reset_index(drop=True)


# =============================================================================
# MATCHING PRODUCCION  <->  GA4
# =============================================================================

@st.cache_data(ttl=3600)
def load_produccion_con_metricas() -> pd.DataFrame:
    """
    Devuelve producción usando únicamente el Excel de 'Notas + Trafico'.
    No ejecuta matching con GA4; solo limpia y normaliza columnas derivadas.
    """
    result = load_produccion().copy()
    if result.empty:
        return result

    raw_tags   = result["tags"] if "tags" in result.columns else pd.Series("", index=result.index)
    raw_author = result["post_author_name"] if "post_author_name" in result.columns else pd.Series("", index=result.index)

    tags_clean   = raw_tags.map(_clean_str)
    author_clean = raw_author.map(_clean_str)

    result["author_resolved"] = [
        _resolve_author(a, t)
        for a, t in zip(author_clean, tags_clean)
    ]

    result["is_ia"] = tags_clean.apply(
        lambda x: bool(re.search(r"s[ii]ntesis", x, re.I)) if x else False
    )

    result["is_360radio"] = [
        _tags_contain_author(t, a)
        for t, a in zip(tags_clean, author_clean)
    ]

    return result


# =============================================================================
# REEXPORTS PÚBLICOS
# =============================================================================

def match_stats(prod_df: pd.DataFrame) -> dict:
    if prod_df is None or prod_df.empty or "match_method" not in prod_df.columns:
        return {}
    return prod_df["match_method"].astype(str).value_counts().to_dict()


def match_production_to_ga4(prod: pd.DataFrame, urls: pd.DataFrame) -> pd.DataFrame:
    result = prod.copy()
    if "ga4_views" not in result.columns:
        result["ga4_views"] = 0
    if "ga4_users" not in result.columns:
        result["ga4_users"] = 0
    if "match_method" not in result.columns:
        result["match_method"] = "excel_notas_trafico"
    return result


# =============================================================================
# UTILIDADES
# =============================================================================

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
            return _d(2024, 1, 1), _d.today()
        s = pd.to_datetime(df[col], errors="coerce").dropna()
        return (s.min().date(), s.max().date()) if not s.empty else (_d(2024, 1, 1), _d.today())
    except Exception:
        from datetime import date as _d2
        return _d2(2024, 1, 1), _d2.today()


def safe_sum(df, col) -> float:
    try:
        if df is None or df.empty or col not in df.columns:
            return 0.0
        return float(pd.to_numeric(df[col], errors="coerce").sum())
    except Exception:
        return 0.0


def fmt_number(n) -> str:
    try:
        if pd.isna(n):
            return "0"
        n = int(n)
        if n >= 1_000_000:
            return f"{n/1_000_000:.1f}M"
        if n >= 1_000:
            return f"{n/1_000:.1f}K"
        return str(n)
    except Exception:
        return "0"


def pct_delta(cur, prev) -> "float | None":
    try:
        if prev == 0 or pd.isna(prev) or pd.isna(cur):
            return None
        return (cur - prev) / abs(prev) * 100
    except Exception:
        return None


def _delta_str(cur, prev) -> "str | None":
    d = pct_delta(cur, prev)
    return f"{d:+.1f}%" if d is not None else None
