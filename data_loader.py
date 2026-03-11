"""
data_loader.py  –  360Radio Analytics v3.1
==========================================
MATCHING Produccion ↔ GA4 — 5 pasos en cascada:
  1. post_id  == último número ≥4 dígitos en pagePath
  2. post_id  == ?p=XXXXX  (legacy WP)
  3. Título exacto normalizado
  4. Slug del pagePath == slug de la URL de producción
  5. Ratio de similitud ≥ 0.82 (Jaccard bigramas) — vectorizado

GA4 — ga4_360radio_completo_v2.xlsx (extractor v3):

  CON date (series temporales — SIN activeUsers):
    10_General_Diario    date, sessions, screenPageViews, userEngagementDuration
    11_Diario_x_Device   date, deviceCategory, sessions, ...
    12_Diario_x_Ciudad   date, city, sessions, ...
    13_Diario_x_Canal    date, sessionDefaultChannelGroup, sessions, ...
    14_Diario_x_Pais     date, country, sessions, ...
    20_URLs_Diario       date, pagePath, screenPageViews, userEngagementDuration, sessions

  SIN date (totales — activeUsers CORRECTO aquí):
    01_General_x_Device  deviceCategory, activeUsers, sessions, ...
    03_General_x_Edad    userAgeBracket, activeUsers, ...
    04_General_x_Ciudad  city, activeUsers, ...
    05_General_x_Canal   sessionDefaultChannelGroup, activeUsers, ...
    06_General_x_Pais    country, activeUsers, ...
    21_URLs_Top          pagePath, activeUsers, sessions, ...
    30_BRANDING_General  brandingInterest, activeUsers, userEngagementDuration
"""
import re, unicodedata
import pandas as pd
import numpy as np
import streamlit as st
from pathlib import Path
from urllib.parse import urlparse


DATA_DIR = Path(".")   # archivos en raíz del proyecto
GA4_FILE = "ga4_360radio_completo_v2.xlsx"


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


def _ga4(sheet: str, date_col: str = "date") -> pd.DataFrame:
    """Lee una hoja del Excel v2 y normaliza fecha + métricas."""
    df = _read_excel(GA4_FILE, sheet)
    if df.empty:
        return df
    if date_col and date_col in df.columns:
        df = _to_dt(df, date_col)
    metrics = ["activeUsers","sessions","screenPageViews","userEngagementDuration"]
    return _safe_numeric(df, *[c for c in metrics if c in df.columns])


# ═══════════════════════════════════════════════════════════════════════════════
# NORMALIZACIÓN DE TEXTO
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
    if m: return int(m.group(1))
    m2 = re.search(r"[?&]p=(\d+)", s)
    return int(m2.group(1)) if m2 else None

def _bigrams(s: str) -> set:
    return set(s[i:i+2] for i in range(len(s)-1))

def _similarity_ratio(a: str, b: str) -> float:
    if not a or not b: return 0.0
    ba, bb = _bigrams(a), _bigrams(b)
    if not ba or not bb: return 0.0
    return len(ba & bb) / len(ba | bb)


# ═══════════════════════════════════════════════════════════════════════════════
# FUZZY MATCHING VECTORIZADO
# ═══════════════════════════════════════════════════════════════════════════════

def _fuzzy_match_vectorized(prod_titles, ga4_titles, ga4_values, threshold=0.82):
    ga4_bg   = [_bigrams(t) for t in ga4_titles]
    ga4_lens = np.array([len(t) for t in ga4_titles])
    results  = []
    for prod_t in prod_titles:
        if not prod_t or len(prod_t) < 10:
            results.append((0, 0, "sin_match")); continue
        lo, hi   = prod_t.__len__() * 0.5, prod_t.__len__() * 1.5
        cands    = np.where((ga4_lens >= lo) & (ga4_lens <= hi))[0]
        if not len(cands):
            results.append((0, 0, "sin_match")); continue
        prod_bg    = _bigrams(prod_t)
        best_score = 0.0; best_idx = -1
        for i in cands:
            bg = ga4_bg[i]
            if not bg: continue
            inter = len(prod_bg & bg)
            if not inter: continue
            score = inter / len(prod_bg | bg)
            if score > best_score:
                best_score = score; best_idx = i
        if best_score >= threshold and best_idx >= 0:
            v, u = ga4_values[best_idx]
            results.append((v, u, f"fuzzy_{best_score:.2f}"))
        else:
            results.append((0, 0, "sin_match"))
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# LOADERS GA4 — nombres exactos del Excel v2
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600)
def load_ga4_general():
    """10_General_Diario — date, sessions, screenPageViews, userEngagementDuration"""
    return _ga4("10_General_Diario")

@st.cache_data(ttl=3600)
def load_ga4_device():
    """01_General_x_Device — deviceCategory, activeUsers, sessions, ...  (sin date)"""
    return _ga4("01_General_x_Device", date_col="")

@st.cache_data(ttl=3600)
def load_ga4_age():
    """03_General_x_Edad — userAgeBracket, activeUsers, ...  (sin date)"""
    return _ga4("03_General_x_Edad", date_col="")

@st.cache_data(ttl=3600)
def load_ga4_city():
    """04_General_x_Ciudad — city, activeUsers, ...  (sin date)"""
    return _ga4("04_General_x_Ciudad", date_col="")

@st.cache_data(ttl=3600)
def load_ga4_channel():
    """05_General_x_Canal — sessionDefaultChannelGroup, activeUsers, ...  (sin date)"""
    return _ga4("05_General_x_Canal", date_col="")

@st.cache_data(ttl=3600)
def load_ga4_country():
    """06_General_x_Pais — country, activeUsers, ...  (sin date)"""
    return _ga4("06_General_x_Pais", date_col="")

@st.cache_data(ttl=3600)
def load_ga4_urls():
    """20_URLs_Diario — date, pagePath, screenPageViews, userEngagementDuration, sessions"""
    return _ga4("20_URLs_Diario")

@st.cache_data(ttl=3600)
def load_ga4_urls_top():
    """21_URLs_Top — pagePath, activeUsers, sessions, screenPageViews  (sin date)"""
    return _ga4("21_URLs_Top", date_col="")

@st.cache_data(ttl=3600)
def load_ga4_interests():
    """30_BRANDING_General — brandingInterest, activeUsers, userEngagementDuration  (sin date)"""
    return _ga4("30_BRANDING_General", date_col="")


# ═══════════════════════════════════════════════════════════════════════════════
# LOADERS — Otros orígenes
# ═══════════════════════════════════════════════════════════════════════════════

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
    df = _to_dt(_to_dt(df, "post_date"), "post_modified")
    if "post_id"    in df.columns: df["post_id"]     = pd.to_numeric(df["post_id"], errors="coerce")
    if "post_title" in df.columns: df["_title_norm"] = df["post_title"].apply(_norm_title)
    if "url"        in df.columns:
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
    if df.empty: return df
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
    if "Tipo de publicación" in df.columns:
        df = df[df["Tipo de publicación"].str.strip() != "Historia de Instagram"].copy()
    return df.reset_index(drop=True)

@st.cache_data(ttl=3600)
def load_instagram_stories():
    df = _read_csv_robust("Instagram Historys.csv")
    if df.empty: return df
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
    return _safe_numeric(df, "Visualizaciones", "Alcance", "Me gusta",
                         "Clics en el enlace", "Respuestas", "Seguidores",
                         "Navegación", "Toques en stickers").reset_index(drop=True)

@st.cache_data(ttl=3600)
def load_facebook():
    df = _read_csv_robust("Post Facebook.csv")
    if df.empty: return df
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
    num_cols = ["Alcance","Visualizaciones de vídeo de 3 segundos",
                "Visualizaciones de vídeo de 1 minuto",
                "Reacciones, comentarios y veces que se ha compartido",
                "Reacciones","Comentarios","Veces que se ha compartido",
                "Segundos reproducidos","Segundos reproducidos de media",
                "Espectadores de 3 segundos","Espectadores de 1 minuto"]
    return _safe_numeric(df, *[c for c in num_cols if c in df.columns]).reset_index(drop=True)


# ═══════════════════════════════════════════════════════════════════════════════
# MATCHING PRODUCCIÓN ↔ GA4
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600)
def load_produccion_con_metricas() -> pd.DataFrame:
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

    # Usar 21_URLs_Top para tener activeUsers por pagePath (sin date → correcto)
    urls_top = load_ga4_urls_top()

    urls_w = urls.copy()
    if "pagePath" in urls_w.columns:
        urls_w["_ga4_post_id"] = urls_w["pagePath"].apply(_post_id_from_path)
        urls_w["_ga4_slug"]    = urls_w["pagePath"].apply(_slug_from_path)
        urls_w["_ga4_clean"]   = urls_w["pagePath"].apply(
            lambda p: str(p).rstrip("/") if pd.notna(p) else "")
    if "pageTitle" in urls_w.columns:
        urls_w["_ga4_title"] = urls_w["pageTitle"].apply(_norm_title)

    # Para vistas: usar 20_URLs_Diario (screenPageViews aditivo)
    # Para usuarios: usar 21_URLs_Top (activeUsers correcto sin date)
    def _agg_views(key_col, rename_to):
        if key_col not in urls_w.columns: return pd.DataFrame()
        sub = urls_w.dropna(subset=[key_col])
        sub = sub[sub[key_col].astype(str) != ""]
        if sub.empty: return pd.DataFrame()
        if "screenPageViews" not in sub.columns: return pd.DataFrame()
        return (sub.groupby(key_col, as_index=False)
                .agg(ga4_views=("screenPageViews","sum"))
                .rename(columns={key_col: rename_to}))

    def _agg_users_top(key_col, rename_to):
        """activeUsers desde 21_URLs_Top (sin date → correcto)."""
        if urls_top.empty or "pagePath" not in urls_top.columns: return pd.DataFrame()
        if key_col == "_ga4_post_id":
            urls_top["_key"] = urls_top["pagePath"].apply(_post_id_from_path)
        elif key_col == "_ga4_slug":
            urls_top["_key"] = urls_top["pagePath"].apply(_slug_from_path)
        elif key_col == "_ga4_clean":
            urls_top["_key"] = urls_top["pagePath"].apply(lambda p: str(p).rstrip("/") if pd.notna(p) else "")
        else:
            return pd.DataFrame()
        sub = urls_top.dropna(subset=["_key"])
        sub = sub[sub["_key"].astype(str) != ""]
        if sub.empty or "activeUsers" not in sub.columns: return pd.DataFrame()
        return (sub.groupby("_key", as_index=False)
                .agg(ga4_users=("activeUsers","sum"))
                .rename(columns={"_key": rename_to}))

    ga4_views_id   = _agg_views("_ga4_post_id", "_key_id")
    ga4_views_slug = _agg_views("_ga4_slug",    "_key_slug")
    ga4_views_path = _agg_views("_ga4_clean",   "_key_path")

    if not ga4_views_id.empty:
        ga4_views_id["_key_id"] = pd.to_numeric(ga4_views_id["_key_id"], errors="coerce")

    def _assign_views(merged_df, key_col, method_name):
        no_match = result["match_method"] == "sin_match"
        hit      = merged_df["ga4_views"].notna() & (merged_df["ga4_views"] > 0)
        cond     = no_match & hit
        if not cond.any(): return
        result.loc[cond, "ga4_views"]    = merged_df.loc[cond, "ga4_views"].values
        result.loc[cond, "match_method"] = method_name

    # Asignar vistas
    if not ga4_views_id.empty and "post_id" in result.columns:
        _assign_views(result[["post_id"]].merge(ga4_views_id, left_on="post_id", right_on="_key_id", how="left"), "_key_id", "post_id")
    if not ga4_views_slug.empty and "_prod_slug" in result.columns:
        _assign_views(result[["_prod_slug"]].merge(ga4_views_slug, left_on="_prod_slug", right_on="_key_slug", how="left"), "_key_slug", "slug")
    if not ga4_views_path.empty and "_prod_path" in result.columns:
        _assign_views(result[["_prod_path"]].merge(ga4_views_path, left_on="_prod_path", right_on="_key_path", how="left"), "_key_path", "path_completo")

    # Asignar usuarios desde urls_top
    for key_col, prod_col, rename_to in [
        ("_ga4_post_id", "post_id",    "_key_id"),
        ("_ga4_slug",    "_prod_slug", "_key_slug"),
        ("_ga4_clean",   "_prod_path", "_key_path"),
    ]:
        if prod_col not in result.columns: continue
        users_df = _agg_users_top(key_col, rename_to)
        if users_df.empty: continue
        if rename_to == "_key_id":
            users_df[rename_to] = pd.to_numeric(users_df[rename_to], errors="coerce")
        merged = result[[prod_col]].merge(users_df, left_on=prod_col, right_on=rename_to, how="left")
        has_user = merged["ga4_users"].notna()
        result.loc[has_user, "ga4_users"] = merged.loc[has_user, "ga4_users"].values

    # Fuzzy matching para los sin_match con título
    if "pageTitle" in urls_w.columns:
        ga4_by_title = (urls_w.dropna(subset=["_ga4_title"])
                        .groupby("_ga4_title", as_index=False)
                        .agg(ga4_views=("screenPageViews","sum")))
        no_match_mask = result["match_method"] == "sin_match"
        if no_match_mask.any() and not ga4_by_title.empty and "_title_norm" in result.columns:
            ga4_titles_list = ga4_by_title["_ga4_title"].fillna("").tolist()
            ga4_values_list = list(zip(ga4_by_title["ga4_views"].fillna(0).tolist(),
                                       [0]*len(ga4_by_title)))
            prod_no_match = result.loc[no_match_mask, "_title_norm"].tolist()
            fuzzy_results = _fuzzy_match_vectorized(prod_no_match, ga4_titles_list, ga4_values_list)
            idxs = result.index[no_match_mask]
            for i, (v, u, method) in enumerate(fuzzy_results):
                if method != "sin_match":
                    result.at[idxs[i], "ga4_views"]    = v
                    result.at[idxs[i], "match_method"] = method

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

def match_stats(prod_df) -> dict:
    if prod_df.empty or "match_method" not in prod_df.columns: return {}
    return prod_df["match_method"].value_counts().to_dict()
