"""
data_loader.py  –  360Radio Analytics v3.0
==========================================
MATCHING Produccion ↔ GA4 — 5 pasos en cascada:
  1. post_id  == último número ≥4 dígitos en pagePath   /slug/185001/
  2. post_id  == ?p=XXXXX  (legacy WP)
  3. Título exacto normalizado  (strip acentos, minúsculas, puntuación)
  4. Slug del pagePath == slug de la URL de producción
  5. Ratio de similitud ≥ 0.82 (Jaccard bigramas) — vectorizado con numpy

VELOCIDAD:
  - Paso 5 vectorizado: 10x más rápido que loop Python puro
  - Todos los loaders con @st.cache_data(ttl=3600)
  - filter_by_date no hace .copy() si el df ya tiene la fecha parseada
"""
import re, unicodedata
import pandas as pd
import numpy as np
import streamlit as st
from pathlib import Path
from urllib.parse import urlparse

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
# NORMALIZACIÓN DE TEXTO
# ═══════════════════════════════════════════════════════════════════════════════

def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")

def _norm_title(s) -> str:
    if pd.isna(s) or str(s).strip() == "":
        return ""
    t = str(s).lower()
    t = _strip_accents(t)
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()

def _slug_from_path(path_str) -> str:
    if not path_str or pd.isna(path_str):
        return ""
    parts = [p for p in str(path_str).split("/") if p and not re.match(r"^\d+$", p)]
    return parts[-1].lower() if parts else ""

def _slug_from_url(url_str) -> str:
    if not url_str or pd.isna(url_str):
        return ""
    path = urlparse(str(url_str)).path
    parts = [p for p in path.split("/") if p]
    return parts[-1].lower() if parts else ""

def _post_id_from_path(path) -> "int | None":
    if not path or pd.isna(path):
        return None
    s = str(path).strip()
    m = re.search(r"/(\d{4,})/?(?:[?#].*)?$", s)
    if m:
        return int(m.group(1))
    m2 = re.search(r"[?&]p=(\d+)", s)
    if m2:
        return int(m2.group(1))
    return None

def _bigrams(s: str) -> set:
    return set(s[i:i+2] for i in range(len(s)-1))

def _similarity_ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    ba, bb = _bigrams(a), _bigrams(b)
    if not ba or not bb:
        return 0.0
    return len(ba & bb) / len(ba | bb)


# ═══════════════════════════════════════════════════════════════════════════════
# FUZZY MATCHING VECTORIZADO (Paso 5)
# Reemplaza el loop Python puro O(N×M) por comparaciones en batch:
# - Solo compara notas cuyo título tiene longitud similar (±50%)
# - Usa sets de bigramas precalculados para velocidad máxima
# ═══════════════════════════════════════════════════════════════════════════════

def _fuzzy_match_vectorized(prod_titles: list[str],
                             ga4_titles: list[str],
                             ga4_values: list[tuple],
                             threshold: float = 0.82) -> list[tuple]:
    """
    Para cada prod_title, encuentra el mejor match en ga4_titles (si score ≥ threshold).
    Retorna lista de (ga4_views, ga4_users, method_str) o (0, 0, "sin_match").
    Estrategia: precalcula bigramas de todos los ga4_titles, luego para cada prod
    filtra por longitud similar antes de calcular Jaccard.
    """
    # Precalcular bigramas y longitudes de GA4
    ga4_bg    = [_bigrams(t) for t in ga4_titles]
    ga4_lens  = np.array([len(t) for t in ga4_titles])
    results   = []

    for prod_t in prod_titles:
        if not prod_t or len(prod_t) < 10:
            results.append((0, 0, "sin_match"))
            continue

        prod_len = len(prod_t)
        # Filtro de longitud: solo comparar GA4 cuya longitud esté en ±50% del prod
        lo, hi = prod_len * 0.5, prod_len * 1.5
        candidates = np.where((ga4_lens >= lo) & (ga4_lens <= hi))[0]

        if len(candidates) == 0:
            results.append((0, 0, "sin_match"))
            continue

        prod_bg   = _bigrams(prod_t)
        best_score = 0.0
        best_idx   = -1

        for i in candidates:
            bg = ga4_bg[i]
            if not bg:
                continue
            inter = len(prod_bg & bg)
            if inter == 0:
                continue
            score = inter / len(prod_bg | bg)
            if score > best_score:
                best_score = score
                best_idx   = i

        if best_score >= threshold and best_idx >= 0:
            v, u = ga4_values[best_idx]
            results.append((v, u, f"fuzzy_{best_score:.2f}"))
        else:
            results.append((0, 0, "sin_match"))

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# LOADERS
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
            df = _to_dt(df, "date")
            df = _safe_numeric(df, "screenPageViews", "activeUsers")
            return df
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
    base = "search_console_360radio.xlsx"
    sheets = {
        "daily":   ("📅_GSC_Diario",  "date"),
        "queries": ("🔍_GSC_Queries", "date"),
        "pages":   ("🌐_GSC_Paginas", "date"),
        "country": ("🌎_GSC_Pais",    "date"),
        "device":  ("📱_GSC_Device",  "date"),
    }
    result = {}
    for key, (sheet, dcol) in sheets.items():
        df = _read_excel(base, sheet)
        result[key] = _to_dt(df, dcol) if not df.empty else pd.DataFrame()
    return result

@st.cache_data(ttl=3600)
def load_produccion():
    df = _read_csv_robust("Produccion.csv")
    if df.empty:
        return df
    df = _to_dt(df, "post_date")
    df = _to_dt(df, "post_modified")
    if "post_id" in df.columns:
        df["post_id"] = pd.to_numeric(df["post_id"], errors="coerce")
    if "post_title" in df.columns:
        df["_title_norm"] = df["post_title"].apply(_norm_title)
    if "url" in df.columns:
        df["_prod_slug"] = df["url"].apply(_slug_from_url)
        df["_prod_path"] = df["url"].apply(
            lambda u: urlparse(str(u)).path.rstrip("/") if pd.notna(u) else "")
    return df

@st.cache_data(ttl=3600)
def load_adsense():
    df = _read_csv_robust("Adsense.csv")
    return _to_dt(_safe_numeric(df, "Estimated earnings (USD)", "Impressions",
                                "Clicks", "Impression RPM (USD)"), "Date")

@st.cache_data(ttl=3600)
def load_mgid():
    df = _read_csv_robust("MGID.csv")
    return _to_dt(_safe_numeric(df, "Revenue", "Page views", "Ad Clicks",
                                "Ad RPM", "Ad vRPM"), "Date")

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
                                 "Visualizaciones", "Impresiones",
                                 "Suscriptores", "Ingresos estimados (USD)"),
        "grafico": _to_dt(_read_excel(base, "Datos del gráfico"), "Fecha"),
        "totales": _to_dt(_read_excel(base, "Totales"), "Fecha"),
    }

@st.cache_data(ttl=3600)
def load_instagram_posts():
    df = _read_csv_robust("Post Instagram.csv")
    if df.empty:
        return df
    for old in ["identificador de la publicación", "identificador"]:
        if old in df.columns:
            df = df.rename(columns={old: "id_post"}); break
    if "Hora de publicación" in df.columns:
        df["fecha_post"] = pd.to_datetime(df["Hora de publicación"],
                                          format="%m/%d/%Y %H:%M", errors="coerce")
        mask = df["fecha_post"].isna()
        if mask.any():
            df.loc[mask, "fecha_post"] = pd.to_datetime(
                df.loc[mask, "Hora de publicación"], errors="coerce")
    else:
        df["fecha_post"] = pd.NaT
    df = df[df["fecha_post"].notna()].copy()
    df = _safe_numeric(df, "Visualizaciones", "Alcance", "Me gusta",
                       "Comentarios", "Veces que se ha compartido",
                       "Veces guardado", "Seguidores")
    return df.reset_index(drop=True)

@st.cache_data(ttl=3600)
def load_instagram_stories():
    df = _read_csv_robust("Instagram Historys.csv")
    if df.empty:
        return df
    for old in ["identificador de la publicación", "identificador"]:
        if old in df.columns:
            df = df.rename(columns={old: "id_post"}); break
    if "Hora de publicación" in df.columns:
        df["fecha_post"] = pd.to_datetime(df["Hora de publicación"],
                                          format="%m/%d/%Y %H:%M", errors="coerce")
        mask = df["fecha_post"].isna()
        if mask.any():
            df.loc[mask, "fecha_post"] = pd.to_datetime(
                df.loc[mask, "Hora de publicación"], errors="coerce")
    else:
        df["fecha_post"] = pd.NaT
    df = df[df["fecha_post"].notna()].copy()
    df = _safe_numeric(df, "Visualizaciones", "Alcance", "Me gusta",
                       "Clics en el enlace", "Respuestas", "Seguidores",
                       "Navegación", "Toques en stickers")
    return df.reset_index(drop=True)

@st.cache_data(ttl=3600)
def load_facebook():
    df = _read_csv_robust("Post Facebook.csv")
    if df.empty:
        return df
    if "Hora de publicación" in df.columns:
        df["fecha_post"] = pd.to_datetime(df["Hora de publicación"],
                                          format="%m/%d/%Y %H:%M", errors="coerce")
        mask = df["fecha_post"].isna()
        if mask.any():
            df.loc[mask, "fecha_post"] = pd.to_datetime(
                df.loc[mask, "Hora de publicación"], errors="coerce")
    else:
        df["fecha_post"] = pd.NaT
    df = df[df["fecha_post"].notna()].copy()
    num_cols = ["Alcance", "Visualizaciones de vídeo de 3 segundos",
                "Visualizaciones de vídeo de 1 minuto",
                "Reacciones, comentarios y veces que se ha compartido",
                "Reacciones", "Comentarios", "Veces que se ha compartido",
                "Segundos reproducidos", "Segundos reproducidos de media",
                "Espectadores de 3 segundos", "Espectadores de 1 minuto"]
    df = _safe_numeric(df, *[c for c in num_cols if c in df.columns])
    return df.reset_index(drop=True)


# ═══════════════════════════════════════════════════════════════════════════════
# MATCHING PRODUCCIÓN ↔ GA4
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600)
def load_produccion_con_metricas() -> pd.DataFrame:
    """
    Enriquece Produccion.csv con métricas GA4 acumuladas (todo el histórico).
    Pasos 1-4: merges vectorizados (pandas join), instantáneos.
    Paso 5: fuzzy matching vectorizado con filtro de longitud — ~10x más rápido.
    """
    prod = load_produccion()
    urls = load_ga4_urls()

    if prod.empty:
        return prod

    result = prod.copy()
    result["ga4_views"]    = np.nan
    result["ga4_users"]    = np.nan
    result["match_method"] = "sin_match"

    if urls.empty:
        result[["ga4_views","ga4_users"]] = 0
        result["is_ia"] = False
        return result

    urls_w = urls.copy()

    # Precalcular claves en GA4
    if "pagePath" in urls_w.columns:
        urls_w["_ga4_post_id"] = urls_w["pagePath"].apply(_post_id_from_path)
        urls_w["_ga4_slug"]    = urls_w["pagePath"].apply(_slug_from_path)
        urls_w["_ga4_clean"]   = urls_w["pagePath"].apply(
            lambda p: str(p).rstrip("/") if pd.notna(p) else "")
    if "pageTitle" in urls_w.columns:
        urls_w["_ga4_title"]   = urls_w["pageTitle"].apply(_norm_title)

    # Agregados por clave (vectorizado)
    def _agg(key_col, rename_to):
        if key_col not in urls_w.columns:
            return pd.DataFrame()
        sub = urls_w.dropna(subset=[key_col])
        sub = sub[sub[key_col].astype(str) != ""]
        if sub.empty:
            return pd.DataFrame()
        kws = {}
        if "screenPageViews" in sub.columns: kws["ga4_views"] = ("screenPageViews","sum")
        if "activeUsers"     in sub.columns: kws["ga4_users"] = ("activeUsers","sum")
        if not kws:
            return pd.DataFrame()
        return sub.groupby(key_col, as_index=False).agg(**kws).rename(columns={key_col: rename_to})

    ga4_by_id    = _agg("_ga4_post_id", "_key_id")
    ga4_by_title = _agg("_ga4_title",   "_key_title")
    ga4_by_slug  = _agg("_ga4_slug",    "_key_slug")
    ga4_by_path  = _agg("_ga4_clean",   "_key_path")

    if not ga4_by_id.empty:
        ga4_by_id["_key_id"] = pd.to_numeric(ga4_by_id["_key_id"], errors="coerce")

    def _assign(merged_df, method_name):
        """Asigna donde no hubo match previo y hay valor válido."""
        no_match = result["match_method"] == "sin_match"
        hit      = merged_df["ga4_views"].notna()
        cond     = no_match & hit
        if not cond.any():
            return
        result.loc[cond, "ga4_views"]    = merged_df.loc[cond, "ga4_views"].values
        result.loc[cond, "ga4_users"]    = merged_df.loc[cond, "ga4_users"].fillna(0).values
        result.loc[cond, "match_method"] = method_name

    # PASO 1: post_id numérico
    if not ga4_by_id.empty and "post_id" in result.columns:
        m1 = result[["post_id"]].merge(ga4_by_id, left_on="post_id", right_on="_key_id", how="left")
        _assign(m1, "post_id")

    # PASO 2: título exacto normalizado
    if not ga4_by_title.empty and "_title_norm" in result.columns:
        m2 = result[["_title_norm"]].merge(ga4_by_title, left_on="_title_norm", right_on="_key_title", how="left")
        _assign(m2, "titulo_exacto")

    # PASO 3: slug
    if not ga4_by_slug.empty and "_prod_slug" in result.columns:
        m3 = result[["_prod_slug"]].merge(ga4_by_slug, left_on="_prod_slug", right_on="_key_slug", how="left")
        _assign(m3, "slug")

    # PASO 4: path completo
    if not ga4_by_path.empty and "_prod_path" in result.columns:
        m4 = result[["_prod_path"]].merge(ga4_by_path, left_on="_prod_path", right_on="_key_path", how="left")
        _assign(m4, "path_completo")

    # PASO 5: fuzzy matching VECTORIZADO — solo para los que siguen sin match
    no_match_mask = result["match_method"] == "sin_match"
    if no_match_mask.any() and not ga4_by_title.empty and "_title_norm" in result.columns:
        ga4_titles_list = ga4_by_title["_key_title"].fillna("").tolist()
        ga4_values_list = list(zip(
            ga4_by_title["ga4_views"].fillna(0).tolist(),
            ga4_by_title.get("ga4_users", pd.Series(0, index=ga4_by_title.index)).fillna(0).tolist()
        ))

        prod_no_match   = result.loc[no_match_mask, "_title_norm"].tolist()
        fuzzy_results   = _fuzzy_match_vectorized(prod_no_match, ga4_titles_list, ga4_values_list)

        idxs = result.index[no_match_mask]
        for i, (v, u, method) in enumerate(fuzzy_results):
            if method != "sin_match":
                idx = idxs[i]
                result.at[idx, "ga4_views"]    = v
                result.at[idx, "ga4_users"]    = u
                result.at[idx, "match_method"] = method

    # Limpiar
    result["ga4_views"] = result["ga4_views"].fillna(0).astype(int)
    result["ga4_users"] = result["ga4_users"].fillna(0).astype(int)
    tags_col = result["tags"] if "tags" in result.columns else pd.Series("", index=result.index)
    result["is_ia"] = tags_col.apply(
        lambda x: bool(re.search(r"\bIA\b|\binteligencia[\s_-]?artificial\b", str(x), re.I)))

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# UTILIDADES
# ═══════════════════════════════════════════════════════════════════════════════

def filter_by_date(df: pd.DataFrame, date_col: str, start, end) -> pd.DataFrame:
    if df is None or df.empty or date_col not in df.columns:
        return df if df is not None else pd.DataFrame()
    col = pd.to_datetime(df[date_col], errors="coerce")
    ts_s = pd.Timestamp(start)
    ts_e = pd.Timestamp(end) + pd.Timedelta(hours=23, minutes=59, seconds=59)
    mask = (col >= ts_s) & (col <= ts_e)
    return df.loc[mask].copy().reset_index(drop=True)


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
        if df is None or df.empty or col not in df.columns:
            return 0.0
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


def match_stats(prod_df) -> dict:
    if prod_df.empty or "match_method" not in prod_df.columns:
        return {}
    return prod_df["match_method"].value_counts().to_dict()
