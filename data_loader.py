"""
data_loader.py  –  360Radio Analytics v3.1
==========================================
MATCHING Produccion ↔ GA4 — 5 pasos en cascada:
  1. post_id  == último número ≥4 dígitos en pagePath   /slug/185001/
  2. post_id  == ?p=XXXXX  (legacy WP)
  3. Título exacto normalizado  (strip acentos, minúsculas, puntuación)
  4. Slug del pagePath == slug de la URL de producción
  5. Ratio de similitud ≥ 0.82 (Jaccard bigramas) — vectorizado con numpy

GA4 — Soporte automático extractor v3 (nuevo) y v1 (existente):
  El loader detecta qué archivos y hojas están disponibles y usa el mejor.

  Extractor v3 → ga4_360radio_completo_v2.xlsx:
    10_General_Diario   → load_ga4_general()   [sessions, views, tiempo — SIN activeUsers]
    04_General_x_Ciudad → load_ga4_city()       [activeUsers correcto, sin date]
    05_General_x_Canal  → load_ga4_channel()    [activeUsers correcto, sin date]
    06_General_x_Pais   → load_ga4_country()    [activeUsers correcto, sin date]
    01_General_x_Device → load_ga4_device()     [activeUsers correcto, sin date]
    03_General_x_Edad   → load_ga4_age()        [activeUsers correcto, sin date]
    20_URLs_Diario      → load_ga4_urls()       [views, tiempo, sessions — SIN activeUsers]
    30_BRANDING_General → load_ga4_interests()  [activeUsers correcto, sin date]

  Extractor v1 → ga4_360radio_completo.xlsx (fallback):
    📊_General_Diario / 📱_General_x_Device / 👤_General_x_Edad
    🏙️_General_x_Ciudad / 🔗_General_x_Canal / 🌎_General_x_Pais
    URLs_x_Fecha_Diaria / Intereses_Audiencia

VELOCIDAD:
  - Paso 5 vectorizado: 10x más rápido que loop Python puro
  - Todos los loaders con @st.cache_data(ttl=3600)
"""
import re, unicodedata
import pandas as pd
import numpy as np
import streamlit as st
from pathlib import Path
from urllib.parse import urlparse


DATA_DIR = Path(".")   # archivos en raíz del proyecto


# ── Detección automática del archivo GA4 disponible ─────────────────────────
_GA4_V3 = DATA_DIR / "ga4_360radio_completo_v2.xlsx"
_GA4_V1 = DATA_DIR / "ga4_360radio_completo.xlsx"

def _ga4_file() -> str:
    """Devuelve el nombre del Excel GA4 disponible (v3 tiene prioridad)."""
    if _GA4_V3.exists(): return str(_GA4_V3)
    if _GA4_V1.exists(): return str(_GA4_V1)
    return str(_GA4_V3)   # no existe: deja que _read_excel devuelva vacío

# Hojas por loader: lista en orden de prioridad [v3, v1_emoji, ...]
_SHEETS = {
    "general":   ["10_General_Diario",     "01_General_Diario",   "📊_General_Diario"],
    "device":    ["01_General_x_Device",   "02_General_x_Device", "📱_General_x_Device"],
    "age":       ["03_General_x_Edad",     "04_General_x_Edad",   "👤_General_x_Edad"],
    "city":      ["04_General_x_Ciudad",   "05_General_x_Ciudad", "🏙️_General_x_Ciudad"],
    "channel":   ["05_General_x_Canal",    "06_General_x_Canal",  "🔗_General_x_Canal"],
    "country":   ["06_General_x_Pais",     "07_General_x_Pais",   "🌎_General_x_Pais"],
    "urls":      ["20_URLs_Diario",        "10_URLs_Diario",      "URLs_x_Fecha_Diaria"],
    "interests": ["30_BRANDING_General",   "15_BRANDING_General", "Intereses_Audiencia"],
}

@st.cache_resource
def _available_sheets() -> set:
    """Lee las hojas del Excel GA4 una sola vez."""
    path = _ga4_file()
    try:
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        names = set(wb.sheetnames)
        wb.close()
        return names
    except Exception:
        return set()

def _best_sheet(key: str) -> str:
    """Devuelve el primer nombre de hoja disponible en el Excel."""
    available = _available_sheets()
    for name in _SHEETS.get(key, []):
        if name in available:
            return name
    return _SHEETS.get(key, [key])[0]


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
    path = Path(fname) if Path(fname).is_absolute() else DATA_DIR / fname
    # Admitir también rutas absolutas devueltas por _ga4_file()
    if not Path(fname).exists() and not path.exists():
        return pd.DataFrame()
    target = Path(fname) if Path(fname).exists() else path
    try:
        return pd.read_excel(target, sheet_name=sheet)
    except Exception:
        try:
            return pd.read_excel(target, sheet_name=sheet, engine="openpyxl")
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


def _load_ga4(key: str, date_col: str = "date") -> pd.DataFrame:
    """
    Loader genérico GA4: detecta archivo + hoja automáticamente,
    convierte fecha y métricas numéricas.
    """
    sheet = _best_sheet(key)
    df    = _read_excel(_ga4_file(), sheet)
    if df.empty:
        return df
    if date_col and date_col in df.columns:
        df = _to_dt(df, date_col)
    metric_cols = ["activeUsers","sessions","screenPageViews",
                   "userEngagementDuration","newUsers","totalUsers"]
    return _safe_numeric(df, *[c for c in metric_cols if c in df.columns])


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
# FUZZY MATCHING VECTORIZADO (Paso 5)
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
# LOADERS GA4
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600)
def load_ga4_general():
    """Serie temporal — date, sessions, screenPageViews, userEngagementDuration."""
    return _load_ga4("general")

@st.cache_data(ttl=3600)
def load_ga4_device():
    """Por dispositivo — activeUsers correcto (sin date en v3)."""
    return _load_ga4("device")

@st.cache_data(ttl=3600)
def load_ga4_age():
    """Por edad — activeUsers correcto (sin date en v3)."""
    return _load_ga4("age")

@st.cache_data(ttl=3600)
def load_ga4_city():
    """Por ciudad — activeUsers correcto (sin date en v3)."""
    return _load_ga4("city")

@st.cache_data(ttl=3600)
def load_ga4_channel():
    """Por canal — activeUsers correcto (sin date en v3)."""
    return _load_ga4("channel")

@st.cache_data(ttl=3600)
def load_ga4_country():
    """Por país — activeUsers correcto (sin date en v3)."""
    return _load_ga4("country")

@st.cache_data(ttl=3600)
def load_ga4_urls():
    """
    URLs con fecha — screenPageViews, userEngagementDuration, sessions.
    Fallback: ga4_data_360radio_urls.xlsx si no hay v3/v1.
    """
    df = _load_ga4("urls")
    if not df.empty and "pagePath" in df.columns:
        return df
    # Fallback archivo legacy separado
    legacy = _read_excel("ga4_data_360radio_urls.xlsx", "URLs_x_Fecha_Diaria")
    if not legacy.empty and "pagePath" in legacy.columns:
        return _safe_numeric(_to_dt(legacy, "date"),
                             "screenPageViews", "activeUsers", "userEngagementDuration")
    return pd.DataFrame()

@st.cache_data(ttl=3600)
def load_ga4_interests():
    """
    Branding/intereses — activeUsers correcto (sin date en v3).
    Fallback: archivo legacy.
    """
    df = _load_ga4("interests")
    if not df.empty and "brandingInterest" in df.columns:
        return df
    legacy = _read_excel("ga4_data_360radio_urls.xlsx", "Intereses_Audiencia")
    if not legacy.empty:
        return _safe_numeric(legacy, "activeUsers", "sessions", "screenPageViews")
    return pd.DataFrame()


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

    urls_w = urls.copy()
    if "pagePath" in urls_w.columns:
        urls_w["_ga4_post_id"] = urls_w["pagePath"].apply(_post_id_from_path)
        urls_w["_ga4_slug"]    = urls_w["pagePath"].apply(_slug_from_path)
        urls_w["_ga4_clean"]   = urls_w["pagePath"].apply(
            lambda p: str(p).rstrip("/") if pd.notna(p) else "")
    if "pageTitle" in urls_w.columns:
        urls_w["_ga4_title"] = urls_w["pageTitle"].apply(_norm_title)

    def _agg(key_col, rename_to):
        if key_col not in urls_w.columns: return pd.DataFrame()
        sub = urls_w.dropna(subset=[key_col])
        sub = sub[sub[key_col].astype(str) != ""]
        if sub.empty: return pd.DataFrame()
        kws = {}
        if "screenPageViews" in sub.columns: kws["ga4_views"] = ("screenPageViews","sum")
        if "activeUsers"     in sub.columns: kws["ga4_users"] = ("activeUsers","sum")
        if not kws: return pd.DataFrame()
        return sub.groupby(key_col, as_index=False).agg(**kws).rename(columns={key_col: rename_to})

    ga4_by_id    = _agg("_ga4_post_id", "_key_id")
    ga4_by_title = _agg("_ga4_title",   "_key_title")
    ga4_by_slug  = _agg("_ga4_slug",    "_key_slug")
    ga4_by_path  = _agg("_ga4_clean",   "_key_path")
    if not ga4_by_id.empty:
        ga4_by_id["_key_id"] = pd.to_numeric(ga4_by_id["_key_id"], errors="coerce")

    def _assign(merged_df, method_name):
        no_match = result["match_method"] == "sin_match"
        hit      = merged_df["ga4_views"].notna()
        cond     = no_match & hit
        if not cond.any(): return
        result.loc[cond, "ga4_views"]    = merged_df.loc[cond, "ga4_views"].values
        result.loc[cond, "ga4_users"]    = merged_df.loc[cond, "ga4_users"].fillna(0).values
        result.loc[cond, "match_method"] = method_name

    if not ga4_by_id.empty    and "post_id"     in result.columns:
        _assign(result[["post_id"]].merge(ga4_by_id,    left_on="post_id",     right_on="_key_id",    how="left"), "post_id")
    if not ga4_by_title.empty and "_title_norm" in result.columns:
        _assign(result[["_title_norm"]].merge(ga4_by_title, left_on="_title_norm", right_on="_key_title", how="left"), "titulo_exacto")
    if not ga4_by_slug.empty  and "_prod_slug"  in result.columns:
        _assign(result[["_prod_slug"]].merge(ga4_by_slug,  left_on="_prod_slug",  right_on="_key_slug",  how="left"), "slug")
    if not ga4_by_path.empty  and "_prod_path"  in result.columns:
        _assign(result[["_prod_path"]].merge(ga4_by_path,  left_on="_prod_path",  right_on="_key_path",  how="left"), "path_completo")

    no_match_mask = result["match_method"] == "sin_match"
    if no_match_mask.any() and not ga4_by_title.empty and "_title_norm" in result.columns:
        ga4_titles_list = ga4_by_title["_key_title"].fillna("").tolist()
        ga4_values_list = list(zip(
            ga4_by_title["ga4_views"].fillna(0).tolist(),
            ga4_by_title.get("ga4_users", pd.Series(0, index=ga4_by_title.index)).fillna(0).tolist()
        ))
        prod_no_match = result.loc[no_match_mask, "_title_norm"].tolist()
        fuzzy_results = _fuzzy_match_vectorized(prod_no_match, ga4_titles_list, ga4_values_list)
        idxs = result.index[no_match_mask]
        for i, (v, u, method) in enumerate(fuzzy_results):
            if method != "sin_match":
                result.at[idxs[i], "ga4_views"]    = v
                result.at[idxs[i], "ga4_users"]    = u
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
