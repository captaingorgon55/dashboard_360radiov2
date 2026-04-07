import re
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import streamlit as st

DATA_DIR = Path("data")
CACHE_DIR = Path(".parquet_cache")
CACHE_DIR.mkdir(exist_ok=True)
PRODUCCION_DESDE = pd.Timestamp("2025-01-01")


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
        for sep in [",", ";", "	", "|"]:
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


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


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


_NAN_STRINGS = {"nan", "none", "null", "na", "n/a", "<na>", ""}


def _clean_str(val) -> str:
    if val is None:
        return ""
    if isinstance(val, float) and (val != val):
        return ""
    s = str(val).strip()
    return "" if s.lower() in _NAN_STRINGS else s


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
    tags_clean = _clean_str(tags_str)
    if not _is_generic_author(author_clean):
        return author_clean
    if not tags_clean:
        return author_clean or "Sin autor"
    tags_norm = _strip_accents(tags_clean.lower())
    for alias, nombre_real in _AUTHOR_ALIASES.items():
        if _strip_accents(alias.lower()) in tags_norm:
            return nombre_real
    return author_clean or "Sin autor"


def _tags_contain_author(tags_str: str, author_str: str) -> bool:
    tags_clean = _clean_str(tags_str)
    author_clean = _clean_str(author_str)
    if not tags_clean or not author_clean:
        return False
    tags_norm = _strip_accents(tags_clean.lower())
    tokens = [t.strip() for t in re.split(r"[\s,]+", author_clean) if len(t.strip()) >= 2]
    return any(_strip_accents(t.lower()) in tags_norm for t in tokens)


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
        ("ga4_360radio_completo.xlsx", "URLs_x_Fecha_Diaria"),
    ]:
        df = _read_excel(fname, sheet)
        if not df.empty and "pagePath" in df.columns:
            return _safe_numeric(_to_dt(df, "date"), "screenPageViews", "activeUsers", "sessions", "userEngagementDuration")
    return pd.DataFrame()


@st.cache_data(ttl=3600)
def load_ga4_interests():
    for fname, sheet in [
        ("ga4_data_360radio_urls.xlsx", "Intereses_Audiencia"),
        ("ga4_360radio_completo.xlsx", "Intereses_Audiencia"),
    ]:
        df = _read_excel(fname, sheet)
        if not df.empty:
            return _safe_numeric(df, "activeUsers", "sessions", "screenPageViews")
    return pd.DataFrame()


@st.cache_data(ttl=3600)
def load_search_console():
    base = "search_console_360radio.xlsx"
    sheets = {
        "daily": ("📅_GSC_Diario", "date"),
        "queries": ("🔍_GSC_Queries", "date"),
        "pages": ("🌐_GSC_Paginas", "date"),
        "country": ("🌎_GSC_Pais", "date"),
        "device": ("📱_GSC_Device", "date"),
    }
    result = {}
    for k, (s, d) in sheets.items():
        df = _read_excel(base, s)
        result[k] = _to_dt(df, d) if not df.empty else pd.DataFrame()
    return result


@st.cache_data(ttl=3600)
def load_produccion():
    df = _read_excel("Produccion.xlsx", "Notas + Trafico")
    if df.empty:
        return df

    rename_map = {}
    for c in df.columns:
        raw = str(c).strip()
        key = _strip_accents(raw.lower())
        key = re.sub(r"[^a-z0-9]", "", key)
        if key in {"postauthorname", "autor", "author", "nombreautor", "postauthor"}:
            rename_map[c] = "post_author_name"
        elif key in {"authorresolved", "autorresuelto"}:
            rename_map[c] = "author_resolved"
        elif key in {"posttitle", "titulo", "title", "headline"}:
            rename_map[c] = "post_title"
        elif key in {"postdate", "fecha", "fecha_publicacion", "fechapublicacion"}:
            rename_map[c] = "post_date"
        elif key in {"postmodified", "fechamodificacion"}:
            rename_map[c] = "post_modified"
        elif key in {"poststatus", "status", "estado"}:
            rename_map[c] = "post_status"
        elif key in {"postid", "id", "post"}:
            rename_map[c] = "post_id"
        elif key in {"screenpageviews", "views", "pageviews", "vistas"}:
            rename_map[c] = "screenPageViews"
        elif key in {"activeusers", "users", "usuarios"}:
            rename_map[c] = "activeUsers"
        elif key in {"userengagementduration", "engagement", "duracionengagement"}:
            rename_map[c] = "userEngagementDuration"
        elif key in {"matchtype", "_matchtype", "origenmatch"}:
            rename_map[c] = "_match_type"
        elif key in {"permalink", "link", "enlace"}:
            rename_map[c] = "permalink"
        elif key in {"url", "path", "ruta"}:
            rename_map[c] = "url"
        elif key in {"categories", "category", "categoria", "categorias", "seccion", "secciones"}:
            rename_map[c] = "categories"
        elif key in {"tags", "etiquetas"}:
            rename_map[c] = "tags"
    if rename_map:
        df = df.rename(columns=rename_map)

    if "url" not in df.columns and "permalink" in df.columns:
        df["url"] = df["permalink"]

    df = _to_dt(_to_dt(df, "post_date"), "post_modified")
    if "post_date" in df.columns:
        df = df[df["post_date"] >= PRODUCCION_DESDE].copy().reset_index(drop=True)

    if "post_id" not in df.columns:
        df["post_id"] = range(1, len(df) + 1)
    else:
        df["post_id"] = pd.to_numeric(df["post_id"], errors="coerce")
        miss = df["post_id"].isna()
        if miss.any():
            start_id = int(df["post_id"].dropna().max()) + 1 if df["post_id"].notna().any() else 1
            df.loc[miss, "post_id"] = range(start_id, start_id + miss.sum())

    for c in ["post_author_name", "author_resolved", "categories", "tags", "post_title", "url"]:
        if c not in df.columns:
            df[c] = ""
        df[c] = df[c].map(_clean_str)

    df = _safe_numeric(df, "screenPageViews", "activeUsers", "userEngagementDuration")
    if "post_title" in df.columns:
        df["_title_norm"] = df["post_title"].apply(_norm_title)

    if "url" in df.columns:
        df["_prod_slug"] = df["url"].apply(_slug_from_url)
        df["_prod_path"] = df["url"].apply(lambda u: urlparse(str(u)).path.rstrip("/").lower() if pd.notna(u) else "")

    df["author_resolved"] = [
        _resolve_author(a, t) if not _clean_str(r) else _clean_str(r)
        for a, t, r in zip(df["post_author_name"], df["tags"], df["author_resolved"])
    ]
    df["post_author_name"] = df["author_resolved"].replace("", "Sin autor").fillna("Sin autor")

    if "screenPageViews" in df.columns:
        df["ga4_views"] = df["screenPageViews"]
    else:
        df["ga4_views"] = 0
    if "activeUsers" in df.columns:
        df["ga4_users"] = df["activeUsers"]
    else:
        df["ga4_users"] = 0
    if "_match_type" in df.columns:
        df["match_method"] = df["_match_type"].astype(str)
    else:
        df["match_method"] = "excel_notas_trafico"

    df["is_ia"] = df["tags"].apply(lambda x: bool(re.search(r"s[ii]ntesis", x, re.I)) if x else False)
    df["is_360radio"] = [_tags_contain_author(t, a) for t, a in zip(df["tags"], df["post_author_name"])]
    return df


@st.cache_data(ttl=3600)
def load_produccion_con_metricas() -> pd.DataFrame:
    return load_produccion().copy()


def match_stats(prod_df: pd.DataFrame) -> dict:
    if prod_df is None or prod_df.empty or "match_method" not in prod_df.columns:
        return {}
    return prod_df["match_method"].astype(str).value_counts().to_dict()


def match_production_to_ga4(prod: pd.DataFrame, urls: pd.DataFrame) -> pd.DataFrame:
    return load_produccion().copy()


def filter_by_date(df: pd.DataFrame, date_col: str, start, end) -> pd.DataFrame:
    if df is None or df.empty or date_col not in df.columns:
        return df if df is not None else pd.DataFrame()
    col = pd.to_datetime(df[date_col], errors="coerce")
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
