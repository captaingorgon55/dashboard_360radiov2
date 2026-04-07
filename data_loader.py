"""
data_loader.py  -  360Radio Analytics v5.0  (Excel consolidado)
================================================================
v5.0:
  * load_produccion_con_metricas: lee directamente del Excel
    "notas_con_trafico.xlsx" (sheet "Notas + Tráfico") que ya trae
    screenPageViews, activeUsers y userEngagementDuration incorporados.
    Se eliminó el matching engine y la carga paralela de GA4 URLs.
  * load_por_autor / load_por_categoria: nuevas funciones que leen
    los sheets "Por Autor" y "Por Categoría" del mismo Excel.
  * Se conservan todos los demás loaders y utilidades sin cambios.
  * _resolve_author, _tags_contain_author y helpers de autor siguen
    disponibles para compatibilidad con vistas existentes.
"""
import re
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

import numpy as np
import pandas as pd
import streamlit as st

DATA_DIR  = Path("data")
CACHE_DIR = Path(".parquet_cache")
CACHE_DIR.mkdir(exist_ok=True)

# Nombre del Excel consolidado (colócalo en data/)
NOTAS_EXCEL = "Produccion.xlsx"

PRODUCCION_DESDE = pd.Timestamp("2025-01-01")


# =============================================================================
# HELPERS I/O
# =============================================================================

def _parquet_path(fname: str, sheet: str) -> Path:
    safe = re.sub(r"[^\w]", "_", f"{fname}__{sheet}")
    return CACHE_DIR / f"{safe}.parquet"


def _read_excel(fname: str, sheet: str) -> pd.DataFrame:
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
# PARSER DE FECHA
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
# HELPERS  is_360radio / is_ia / resolucion de autor
# =============================================================================

_AUTHOR_ALIASES = {
    "andres m":              "Andrés Martín",
    "andresm":               "Andrés Martín",
    "andres martin":         "Andrés Martín",
    "andrés martin":         "Andrés Martín",
    "andrés m":              "Andrés Martín",
    "julieth b":             "Julieth Barbosa",
    "juliethb":              "Julieth Barbosa",
    "julieth barbosa":       "Julieth Barbosa",
    "juan camilo ocampo":    "Juan Camilo Ocampo",
    "juan camilo":           "Juan Camilo Ocampo",
    "juan o":                "Juan Camilo Ocampo",
    "juanocampo":            "Juan Camilo Ocampo",
    "juan ocampo":           "Juan Camilo Ocampo",
    "daniel g":              "Daniel García",
    "daniel garcia":         "Daniel García",
    "daniel garcía":         "Daniel García",
    "jorge g":               "Jorge González",
    "jorge gonzalez":        "Jorge González",
    "jorge gonzález":        "Jorge González",
    "miguel v":              "Miguel Vélez",
    "miguel velez":          "Miguel Vélez",
    "miguel vélez":          "Miguel Vélez",
    "katherine aranda":      "Katherine Aranda",
    "katherine a":           "Katherine Aranda",
    "camilo jaimes":         "Camilo Jaimes",
    "camilo j":              "Camilo Jaimes",
    "simon zapata":          "Simón Zapata",
    "simón zapata":          "Simón Zapata",
    "saul hernandez":        "Saúl Hernández",
    "saúl hernández":        "Saúl Hernández",
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
# LOADERS  —  Search Console, AdSense, MGID, AdManager, YouTube
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
    for base in ["Youtube.xlsx", "Youtube histórico.xlsx"]:
        src = DATA_DIR / base
        if src.exists():
            break
    else:
        return {"tabla": pd.DataFrame(), "grafico": pd.DataFrame(), "totales": pd.DataFrame()}

    try:
        df = pd.read_excel(src, sheet_name=0)
    except Exception:
        try:
            df = pd.read_excel(src, sheet_name=0, engine="openpyxl")
        except Exception:
            return {"tabla": pd.DataFrame(), "grafico": pd.DataFrame(), "totales": pd.DataFrame()}

    df.columns = [str(c).strip() for c in df.columns]
    df = _safe_numeric(
        df,
        "Visualizaciones", "Impresiones", "Suscriptores",
        "Ingresos estimados (USD)", "Ingresos",
        "Ingresos estimados", "Revenue", "Revenue (USD)",
        "Tiempo de visualización (horas)",
        "Porcentaje de clics de las impresiones (%)"
    )

    fecha_col = None
    for c in ["Hora de publicación del vídeo", "Fecha", "Date", "DATE"]:
        if c in df.columns:
            fecha_col = c
            break

    if fecha_col:
        raw = df[fecha_col].astype(str).str.strip()
        parsed = pd.to_datetime(raw, errors="coerce")
        df["Fecha"] = parsed
        if fecha_col != "Fecha":
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
# LOADER PRINCIPAL  —  Producción con métricas (desde Excel consolidado)
# =============================================================================

@st.cache_data(ttl=3600)
def load_produccion_con_metricas() -> pd.DataFrame:
    """
    Lee el sheet "Notas + Tráfico" del Excel consolidado.
    Las métricas GA4 (screenPageViews, activeUsers, userEngagementDuration)
    ya vienen incorporadas — no se requiere matching engine.
    """
    src = DATA_DIR / NOTAS_EXCEL
    if not src.exists():
        return pd.DataFrame()

    df = _read_excel(NOTAS_EXCEL, "Notas + Tráfico")
    if df.empty:
        return df

    # Fechas
    df = _to_dt(_to_dt(df, "post_date"), "post_modified")

    # Métricas numéricas
    df = _safe_numeric(df, "screenPageViews", "activeUsers",
                       "userEngagementDuration", "post_id")

    # Columnas de compatibilidad con vistas existentes
    df["ga4_views"]    = df.get("screenPageViews", pd.Series(0, index=df.index))
    df["ga4_users"]    = df.get("activeUsers",     pd.Series(0, index=df.index))
    df["match_method"] = df.get("_match_type",     pd.Series("excel", index=df.index))

    # Slugs y paths para filtros por URL
    if "url" in df.columns:
        df["_prod_slug"] = df["url"].apply(_slug_from_url)
        df["_prod_path"] = df["url"].apply(
            lambda u: urlparse(str(u)).path.rstrip("/").lower()
            if _clean_str(u) else ""
        )

    # Título normalizado
    if "post_title" in df.columns:
        df["_title_norm"] = df["post_title"].apply(_norm_title)

    # Limpiar tags y autor
    tags_clean   = df.get("tags",             pd.Series("", index=df.index)).map(_clean_str)
    author_clean = df.get("post_author_name", pd.Series("", index=df.index)).map(_clean_str)

    # Resolver autor real (alias en tags → nombre canónico)
    df["author_resolved"] = [
        _resolve_author(a, t)
        for a, t in zip(author_clean, tags_clean)
    ]

    # Flags
    df["is_ia"] = tags_clean.apply(
        lambda x: bool(re.search(r"s[ii]ntesis", x, re.I)) if x else False
    )
    df["is_360radio"] = [
        _tags_contain_author(t, a)
        for t, a in zip(tags_clean, author_clean)
    ]

    return df


@st.cache_data(ttl=3600)
def load_por_autor() -> pd.DataFrame:
    """Sheet 'Por Autor' del Excel consolidado."""
    df = _read_excel(NOTAS_EXCEL, "Por Autor")
    return _safe_numeric(df, "screenPageViews", "activeUsers", "userEngagementDuration")


@st.cache_data(ttl=3600)
def load_por_categoria() -> pd.DataFrame:
    """Sheet 'Por Categoría' del Excel consolidado."""
    df = _read_excel(NOTAS_EXCEL, "Por Categoría")
    return _safe_numeric(df, "screenPageViews", "activeUsers", "userEngagementDuration")


# =============================================================================
# Stub load_produccion  —  compatibilidad con código que la importe
# =============================================================================

@st.cache_data(ttl=3600)
def load_produccion() -> pd.DataFrame:
    """
    Alias de compatibilidad. Devuelve el mismo DataFrame que
    load_produccion_con_metricas() pero sin los campos ga4_*.
    """
    return load_produccion_con_metricas()


# =============================================================================
# Stubs de matching  —  compatibilidad con vistas que los importen
# =============================================================================

def match_stats(prod_df: pd.DataFrame) -> dict:
    if prod_df is None or prod_df.empty or "match_method" not in prod_df.columns:
        return {}
    return prod_df["match_method"].value_counts().to_dict()


def match_production_to_ga4(prod: pd.DataFrame, urls: pd.DataFrame) -> pd.DataFrame:
    """No-op: el Excel ya trae las métricas integradas."""
    result = prod.copy()
    if "screenPageViews" in result.columns:
        result["ga4_views"] = result["screenPageViews"]
    else:
        result["ga4_views"] = 0
    if "activeUsers" in result.columns:
        result["ga4_users"] = result["activeUsers"]
    else:
        result["ga4_users"] = 0
    result["match_method"] = result.get("_match_type", "excel")
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
