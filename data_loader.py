"""
data_loader.py - 360Radio Analytics v5.0
========================================
Flujo v5.0:
- Producción ya no se matchea dentro del loader.
- Se lee un Excel final de producción enriquecido externamente.
- Se normalizan columnas del nuevo Excel para mantener compatibilidad
  con el dashboard actual, especialmente con general-5.py.

Columnas esperadas en el nuevo Excel:
    post_id
    post_title
    post_date
    post_modified
    post_status
    post_author_name
    categories
    tags
    url
    permalink
    post_author
    screenPageViews
    activeUsers
    userEngagementDuration
    _match_type
"""

import re
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

import numpy as np
import pandas as pd
import streamlit as st

DATA_DIR = Path("data")
CACHE_DIR = Path(".parquet_cache")
CACHE_DIR.mkdir(exist_ok=True)

PRODUCCION_DESDE = pd.Timestamp("2025-01-01")


# =============================================================================
# HELPERS I/O
# =============================================================================

def _parquet_path(fname: str, sheet: str) -> Path:
    safe = re.sub(r"[^\w]", "_", f"{fname}__{sheet}")
    return CACHE_DIR / f"{safe}.parquet"


def _read_excel(fname: str, sheet) -> pd.DataFrame:
    """
    Lee un sheet de Excel.
    Si existe un parquet más reciente que el Excel, lo usa.
    """
    src = DATA_DIR / fname
    if not src.exists():
        return pd.DataFrame()

    pq = _parquet_path(fname, str(sheet))
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


def _safe_numeric(df: pd.DataFrame, cols) -> pd.DataFrame:
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    return df


# =============================================================================
# HELPERS TEXTO / NORMALIZACIÓN
# =============================================================================

DATE_FORMATS = [
    "%m/%d/%Y %H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%Y-%m-%d",
]


def _parse_fecha(series: pd.Series) -> pd.Series:
    result = pd.Series(pd.NaT, index=series.index)
    pending = series.copy()

    for fmt in DATE_FORMATS:
        mask = result.isna() & pending.notna()
        if not mask.any():
            break
        parsed = pd.to_datetime(pending[mask], format=fmt, errors="coerce")
        result.loc[mask] = parsed

    still_na = result.isna() & pending.notna()
    if still_na.any():
        result.loc[still_na] = pd.to_datetime(pending[still_na], errors="coerce")

    return result


def _strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


def _norm_title(s) -> str:
    if pd.isna(s) or not str(s).strip():
        return ""
    t = _strip_accents(str(s).lower())
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def _slug_from_url(urlstr) -> str:
    if not urlstr or pd.isna(urlstr):
        return ""
    path = urlparse(str(urlstr)).path
    parts = [p for p in path.split("/") if p]
    return parts[-1].lower() if parts else ""


NAN_STRINGS = {"nan", "none", "null", "na", "n/a", "<na>"}


def _clean_str(val) -> str:
    if val is None:
        return ""
    if isinstance(val, float) and val != val:
        return ""
    s = str(val).strip()
    return "" if s.lower() in NAN_STRINGS else s


AUTHOR_ALIASES = {
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

IS_360RADIO_AUTHOR = re.compile(r"(360\s*radio|radio\s*360|^360radio$)", re.I)


def _is_generic_author(author_str) -> bool:
    s = _clean_str(author_str)
    if not s:
        return True
    return bool(IS_360RADIO_AUTHOR.search(s))


def _resolve_author(author_str, tags_str) -> str:
    author_clean = _clean_str(author_str)
    tags_clean = _clean_str(tags_str)

    if not _is_generic_author(author_clean):
        return author_clean

    if not tags_clean:
        return author_clean or "360 Radio"

    tags_norm = _strip_accents(tags_clean.lower())

    for alias, nombre_real in AUTHOR_ALIASES.items():
        if _strip_accents(alias.lower()) in tags_norm:
            return nombre_real

    return author_clean or "360 Radio"


def _tags_contain_author(tags_str: str, author_str: str) -> bool:
    tags_clean = _clean_str(tags_str)
    author_clean = _clean_str(author_str)

    if not tags_clean or not author_clean:
        return False

    tags_norm = _strip_accents(tags_clean.lower())
    tokens = [t.strip() for t in re.split(r"\s+", author_clean) if len(t.strip()) >= 2]

    return any(_strip_accents(t.lower()) in tags_norm for t in tokens)


# =============================================================================
# CARGAS GA4 / GSC / ADS
# =============================================================================

@st.cache_data(ttl=3600)
def load_ga4_general():
    return _to_dt(_read_excel("ga4-360radio-completo.xlsx", "GeneralDiario"), "date")


@st.cache_data(ttl=3600)
def load_ga4_device():
    return _to_dt(_read_excel("ga4-360radio-completo.xlsx", "GeneralxDevice"), "date")


@st.cache_data(ttl=3600)
def load_ga4_age():
    return _to_dt(_read_excel("ga4-360radio-completo.xlsx", "GeneralxEdad"), "date")


@st.cache_data(ttl=3600)
def load_ga4_city():
    return _to_dt(_read_excel("ga4-360radio-completo.xlsx", "GeneralxCiudad"), "date")


@st.cache_data(ttl=3600)
def load_ga4_channel():
    return _to_dt(_read_excel("ga4-360radio-completo.xlsx", "GeneralxCanal"), "date")


@st.cache_data(ttl=3600)
def load_ga4_country():
    return _to_dt(_read_excel("ga4-360radio-completo.xlsx", "GeneralxPais"), "date")


@st.cache_data(ttl=3600)
def load_ga4_urls():
    for fname, sheet in [
        ("ga4-data-360radio-urls.xlsx", "URLsxFechaDiaria"),
        ("ga4-360radio-completo.xlsx", "URLsxFechaDiaria"),
    ]:
        df = _read_excel(fname, sheet)
        if not df.empty and "pagePath" in df.columns:
            return _safe_numeric(_to_dt(df, "date"), ["screenPageViews", "activeUsers", "sessions", "userEngagementDuration"])
    return pd.DataFrame()


@st.cache_data(ttl=3600)
def load_ga4_interests():
    for fname, sheet in [
        ("ga4-data-360radio-urls.xlsx", "InteresesAudiencia"),
        ("ga4-360radio-completo.xlsx", "InteresesAudiencia"),
    ]:
        df = _read_excel(fname, sheet)
        if not df.empty:
            return _safe_numeric(df, ["activeUsers", "sessions", "screenPageViews"])
    return pd.DataFrame()


@st.cache_data(ttl=3600)
def load_search_console():
    base = "searchconsole-360radio.xlsx"
    sheets = {
        "daily": ("GSCDiario", "date"),
        "queries": ("GSCQueries", "date"),
        "pages": ("GSCPaginas", "date"),
        "country": ("GSCPais", "date"),
        "device": ("GSCDevice", "date"),
    }

    result = {}
    for k, (s, dcol) in sheets.items():
        df = _read_excel(base, s)
        result[k] = _to_dt(df, dcol) if not df.empty else pd.DataFrame()

    return result


# =============================================================================
# PRODUCCIÓN FINAL DESDE EXCEL
# =============================================================================

@st.cache_data(ttl=3600)
def load_produccion():
    """
    Lee el Excel final de producción ya enriquecido externamente.
    Ya no se hace matching aquí.
    """

    candidatos_excel = [
        "Produccion.xlsx",
        "Producción.xlsx",
        "produccion.xlsx",
        "producción.xlsx",
    ]

    df = pd.DataFrame()

    for fname in candidatos_excel:
        src = DATA_DIR / fname
        if not src.exists():
            continue

        for sheet in [0, "Sheet1", "Hoja1"]:
            try:
                if isinstance(sheet, int):
                    df = pd.read_excel(src, sheet_name=sheet)
                else:
                    df = _read_excel(fname, sheet)
                if not df.empty:
                    break
            except Exception:
                continue

        if not df.empty:
            break

    if df.empty:
        df = _read_csv_robust("Produccion.csv")

    if df.empty:
        return df

    df.columns = [str(c).strip() for c in df.columns]
    df = df.loc[:, ~df.columns.duplicated()].copy()

    rename_map = {
        "_match_type": "match_method",
        "screenPageViews": "ga4_views",
        "activeUsers": "ga4_users",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    if "post_date" in df.columns:
        df["post_date"] = _parse_fecha(df["post_date"].astype(str).replace("nan", pd.NA))
    if "post_modified" in df.columns:
        df["post_modified"] = _parse_fecha(df["post_modified"].astype(str).replace("nan", pd.NA))

    if "post_date" in df.columns:
        df = df[df["post_date"] >= PRODUCCION_DESDE].copy().reset_index(drop=True)

    if "post_id" in df.columns:
        df["post_id"] = pd.to_numeric(df["post_id"], errors="coerce")

    if "post_author" in df.columns:
        df["post_author"] = pd.to_numeric(df["post_author"], errors="coerce")

    for col in ["ga4_views", "ga4_users", "userEngagementDuration"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    text_cols = [
        "post_title",
        "post_status",
        "post_author_name",
        "categories",
        "tags",
        "url",
        "permalink",
        "match_method",
    ]
    for col in text_cols:
        if col in df.columns:
            df[col] = df[col].map(_clean_str)

    if "post_author_name" not in df.columns and "author_resolved" in df.columns:
        df["post_author_name"] = df["author_resolved"]

    if "post_title" in df.columns:
        df["_title_norm"] = df["post_title"].apply(_norm_title)

    source_url_col = None
    if "url" in df.columns and df["url"].astype(str).str.strip().ne("").any():
        source_url_col = "url"
    elif "permalink" in df.columns and df["permalink"].astype(str).str.strip().ne("").any():
        source_url_col = "permalink"

    if source_url_col:
        df["_prod_slug"] = df[source_url_col].apply(_slug_from_url)
        df["_prod_path"] = df[source_url_col].apply(
            lambda u: urlparse(str(u)).path.rstrip("/").lower() if pd.notna(u) and str(u).strip() else ""
        )
        if "url" not in df.columns or not df["url"].astype(str).str.strip().ne("").any():
            df["url"] = df[source_url_col]
    else:
        df["_prod_slug"] = ""
        df["_prod_path"] = ""

    if "match_method" not in df.columns or df["match_method"].astype(str).str.strip().eq("").all():
        df["match_method"] = "excel_final"

    raw_tags = df["tags"] if "tags" in df.columns else pd.Series("", index=df.index)
    raw_author = df["post_author_name"] if "post_author_name" in df.columns else pd.Series("", index=df.index)

    tags_clean = raw_tags.map(_clean_str)
    author_clean = raw_author.map(_clean_str)

    df["author_resolved"] = [
        _resolve_author(a, t)
        for a, t in zip(author_clean, tags_clean)
    ]

    df["is_ia"] = tags_clean.apply(
        lambda x: bool(re.search(r"s[ií]ntesis", x, re.I)) if x else False
    )

    df["is_360radio"] = [
        _tags_contain_author(t, a)
        for t, a in zip(tags_clean, author_clean)
    ]

    if "post_author_name" in df.columns:
        df["post_author_name"] = df["post_author_name"].replace("", np.nan)
        df["post_author_name"] = df["post_author_name"].fillna(df["author_resolved"])
        df["post_author_name"] = df["post_author_name"].fillna("360 Radio")
    else:
        df["post_author_name"] = df["author_resolved"].replace("", "360 Radio")

    if "categories" in df.columns:
        df["categories"] = df["categories"].fillna("").astype(str).str.strip()

    if "tags" in df.columns:
        df["tags"] = df["tags"].fillna("").astype(str).str.strip()

    return df.reset_index(drop=True)


@st.cache_data(ttl=3600)
def load_produccion_con_metricas() -> pd.DataFrame:
    """
    Compatibilidad con el dashboard actual.
    Ya no hace matching: devuelve producción final enriquecida.
    """
    return load_produccion()


def match_stats(prod_df: pd.DataFrame) -> dict:
    """
    Diagnóstico simple basado en match_method del Excel final.
    """
    if prod_df is None or prod_df.empty or "match_method" not in prod_df.columns:
        return {}
    return prod_df["match_method"].fillna("sin_match").value_counts().to_dict()


def match_production_to_ga4(prod: pd.DataFrame, urls: pd.DataFrame) -> pd.DataFrame:
    """
    Compatibilidad retro.
    Ya no hace nada porque el match viene resuelto en el Excel final.
    """
    return load_produccion() if prod is None or prod.empty else prod.copy()


# =============================================================================
# OTRAS FUENTES
# =============================================================================

@st.cache_data(ttl=3600)
def load_adsense():
    df = _read_csv_robust("Adsense.csv")
    return _to_dt(_safe_numeric(df, ["Estimated earnings (USD)", "Impressions", "Clicks", "Impression RPM (USD)"]), "Date")


@st.cache_data(ttl=3600)
def load_mgid():
    df = _read_csv_robust("MGID.csv")
    return _to_dt(_safe_numeric(df, ["Revenue", "Page views", "Ad Clicks", "Ad RPM", "Ad vRPM"]), "Date")


@st.cache_data(ttl=3600)
def load_admanager():
    base = "admanager-360radio.xlsx"
    return {
        "diario": _to_dt(_read_excel(base, "GAMDiario"), "DATE"),
        "mensual": _read_excel(base, "GAMMensual"),
        "formatos": _read_excel(base, "GAMFormatos"),
        "devices": _read_excel(base, "GAMDispositivos"),
        "fill": _to_dt(_read_excel(base, "GAMFillRate"), "DATE"),
        "orders": _read_excel(base, "GAMOrdersLineItems"),
    }


@st.cache_data(ttl=3600)
def load_viads() -> pd.DataFrame:
    candidates = [
        DATA_DIR / "statistics-2025-01-01-2026-04-01.csv",
        DATA_DIR / "viads.csv",
        DATA_DIR / "Viads.csv",
    ]

    if DATA_DIR.exists():
        candidates += sorted(DATA_DIR.glob("statistics*.csv"))

    df = pd.DataFrame()
    for path in candidates:
        if path.exists():
            try:
                tmp = pd.read_csv(path, sep=",", low_memory=False)
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

    df = _safe_numeric(df, [
        "Visualizaciones",
        "Impresiones",
        "Suscriptores",
        "Ingresos estimados (USD)",
        "Tiempo de visualización (horas)",
        "Porcentaje de clics de las impresiones",
    ])

    fecha_col = "Hora de publicación del vídeo"
    if fecha_col in df.columns:
        raw = df[fecha_col].astype(str).str.strip()
        raw = raw.str.replace(r",", "", regex=True)
        parsed = pd.to_datetime(raw, format="%b %d, %Y", errors="coerce")
        mask = parsed.isna()
        if mask.any():
            parsed.loc[mask] = pd.to_datetime(raw.loc[mask], errors="coerce", dayfirst=False)
        df[fecha_col] = parsed
        df["Fecha"] = parsed

    return {"tabla": df, "grafico": df, "totales": pd.DataFrame()}


def _load_social_base(fname: str, numcols: list, idcol: str = "identificador de la publicación") -> pd.DataFrame:
    df = _read_csv_robust(fname)
    if df.empty:
        return df

    for candidate in [
        idcol,
        "identificador de la publicación",
        "identificador de la publicacion",
        "Identificador de la pieza de vídeo",
        "Identificador de la pieza de video",
        "identificador",
    ]:
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
    df = _safe_numeric(df, [c for c in numcols if c in df.columns])

    return df.reset_index(drop=True)


@st.cache_data(ttl=3600)
def load_instagram_posts() -> pd.DataFrame:
    df = _load_social_base(
        "Post Instagram.csv",
        [
            "Visualizaciones",
            "Alcance",
            "Me gusta",
            "Comentarios",
            "Veces que se ha compartido",
            "Veces guardado",
            "Seguidores",
        ],
        idcol="identificador de la publicación",
    )
    if not df.empty:
        for tipo_col in ["Tipo de publicación", "Tipo de publicacion"]:
            if tipo_col in df.columns:
                df = df[df[tipo_col].astype(str).str.strip() != "Historia de Instagram"].copy()
                break
    return df.reset_index(drop=True)


@st.cache_data(ttl=3600)
def load_instagram_stories() -> pd.DataFrame:
    return _load_social_base(
        "Instagram Historys.csv",
        [
            "Visualizaciones",
            "Alcance",
            "Me gusta",
            "Clics en el enlace",
            "Respuestas",
            "Seguidores",
            "Navegación",
            "Navegacion",
            "Toques en stickers",
            "Visitas al perfil",
        ],
        idcol="identificador de la publicación",
    )


@st.cache_data(ttl=3600)
def load_facebook() -> pd.DataFrame:
    return _load_social_base(
        "Post Facebook.csv",
        [
            "Alcance",
            "Visualizaciones de vídeo de 3 segundos",
            "Visualizaciones de vídeo de 1 minuto",
            "Visualizaciones de video de 3 segundos",
            "Visualizaciones de video de 1 minuto",
            "Reacciones, comentarios y veces que se ha compartido",
            "Reacciones",
            "Comentarios",
            "Veces que se ha compartido",
            "Segundos reproducidos",
            "Segundos reproducidos de media",
            "Espectadores de 3 segundos",
            "Espectadores de 1 minuto",
        ],
        idcol="Identificador de la pieza de vídeo",
    )


# =============================================================================
# UTILIDADES
# =============================================================================

def filter_by_date(df: pd.DataFrame, datecol: str, start, end) -> pd.DataFrame:
    if df is None or df.empty or datecol not in df.columns:
        return df if df is not None else pd.DataFrame()

    col = pd.to_datetime(df[datecol], errors="coerce")
    tss = pd.Timestamp(start)
    tse = pd.Timestamp(end) + pd.Timedelta(hours=23, minutes=59, seconds=59)

    return df.loc[(col >= tss) & (col <= tse)].copy().reset_index(drop=True)


def get_date_range(df: pd.DataFrame, col: str):
    from datetime import date as d
    try:
        if df is None or df.empty or col not in df.columns:
            return d(2024, 1, 1), d.today()
        s = pd.to_datetime(df[col], errors="coerce").dropna()
        return (s.min().date(), s.max().date()) if not s.empty else (d(2024, 1, 1), d.today())
    except Exception:
        from datetime import date as d2
        return d2(2024, 1, 1), d2.today()


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
            return f"{n / 1_000_000:.1f}M"
        if n >= 1_000:
            return f"{n / 1_000:.1f}K"
        return str(n)
    except Exception:
        return "0"


def pct_delta(cur, prev):
    try:
        if prev == 0 or pd.isna(prev) or pd.isna(cur):
            return None
        return (cur - prev) / abs(prev) * 100
    except Exception:
        return None


def delta_str(cur, prev):
    d = pct_delta(cur, prev)
    return f"{d:+.1f}%" if d is not None else None


# =============================================================================
# ALIASES COMPATIBLES CON EL DASHBOARD EXISTENTE
# =============================================================================

loadga4general = load_ga4_general
loadga4device = load_ga4_device
loadga4age = load_ga4_age
loadga4city = load_ga4_city
loadga4channel = load_ga4_channel
loadga4country = load_ga4_country
loadga4urls = load_ga4_urls
loadga4interests = load_ga4_interests
loadsearchconsole = load_search_console
loadproduccion = load_produccion
loadproduccionconmetricas = load_produccion_con_metricas
loadadsense = load_adsense
loadmgid = load_mgid
loadadmanager = load_admanager
loadviads = load_viads
loadyoutube = load_youtube
loadinstagramposts = load_instagram_posts
loadinstagramstories = load_instagram_stories
loadfacebook = load_facebook

filterbydate = filter_by_date
getdaterange = get_date_range
safesum = safe_sum
fmtnumber = fmt_number
deltastr = delta_str
matchstats = match_stats
matchproductiontoga4 = match_production_to_ga4
