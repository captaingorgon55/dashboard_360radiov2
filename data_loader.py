import pandas as pd
import numpy as np
import re
import streamlit as st
from pathlib import Path
from urllib.parse import urlparse

DATA_DIR = Path("data")

# ─── helpers ───────────────────────────────────────────────────────────────────

def _read_excel(fname, sheet):
    try:
        return pd.read_excel(DATA_DIR / fname, sheet_name=sheet)
    except Exception as e:
        return pd.DataFrame()

def _read_csv(fname, **kwargs):
    try:
        return pd.read_csv(DATA_DIR / fname, **kwargs)
    except Exception:
        return pd.DataFrame()

def _parse_dates(df, col):
    if col in df.columns:
        df[col] = pd.to_datetime(df[col], errors="coerce")
    return df

def _extract_post_id_from_url(url_series):
    def _extract(u):
        if pd.isna(u): return None
        u = str(u)
        m = re.search(r'[/?&]p[=/](\d+)', u)
        if m: return int(m.group(1))
        m = re.search(r'/(\d+)/?(?:\?|$)', u)
        if m: return int(m.group(1))
        return None
    return url_series.apply(_extract)

def _normalize_title(s):
    if pd.isna(s): return ""
    return re.sub(r'\s+', ' ', str(s).lower().strip())

# ─── loaders individuales ──────────────────────────────────────────────────────

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
    df = _read_excel("ga4_360radio_completo.xlsx", "URLs_x_Fecha_Diaria")
    if df.empty:
        df = _read_excel("ga4_data_360radio_urls.xlsx", "URLs_x_Fecha_Diaria") if (DATA_DIR / "ga4_data_360radio_urls.xlsx").exists() else pd.DataFrame()
    return _parse_dates(df, "date")

@st.cache_data(ttl=3600)
def load_ga4_interests():
    df = _read_excel("ga4_360radio_completo.xlsx", "Intereses_Audiencia")
    if df.empty:
        df = _read_excel("ga4_data_360radio_urls.xlsx", "Intereses_Audiencia") if (DATA_DIR / "ga4_data_360radio_urls.xlsx").exists() else pd.DataFrame()
    return df

@st.cache_data(ttl=3600)
def load_search_console():
    daily   = _parse_dates(_read_excel("search_console_360radio.xlsx", "📅_GSC_Diario"), "date")
    queries = _parse_dates(_read_excel("search_console_360radio.xlsx", "🔍_GSC_Queries"), "date")
    pages   = _parse_dates(_read_excel("search_console_360radio.xlsx", "🌐_GSC_Paginas"), "date")
    country = _parse_dates(_read_excel("search_console_360radio.xlsx", "🌎_GSC_Pais"), "date")
    device  = _parse_dates(_read_excel("search_console_360radio.xlsx", "📱_GSC_Device"), "date")
    return {"daily": daily, "queries": queries, "pages": pages, "country": country, "device": device}

@st.cache_data(ttl=3600)
def load_produccion():
    df = _read_csv("Produccion.csv")
    if df.empty: return df
    df = _parse_dates(df, "post_date")
    df = _parse_dates(df, "post_modified")
    if "post_title" in df.columns:
        df["_title_norm"] = df["post_title"].apply(_normalize_title)
    return df

@st.cache_data(ttl=3600)
def load_adsense():
    df = _read_csv("Adsense.csv")
    return _parse_dates(df, "Date")

@st.cache_data(ttl=3600)
def load_mgid():
    df = _read_csv("MGID.csv")
    return _parse_dates(df, "Date")

@st.cache_data(ttl=3600)
def load_admanager():
    diario   = _parse_dates(_read_excel("admanager_360radio.xlsx", "GAM_Diario"), "DATE")
    mensual  = _read_excel("admanager_360radio.xlsx", "GAM_Mensual")
    formatos = _read_excel("admanager_360radio.xlsx", "GAM_Formatos")
    devices  = _read_excel("admanager_360radio.xlsx", "GAM_Dispositivos")
    fill     = _parse_dates(_read_excel("admanager_360radio.xlsx", "GAM_Fill_Rate"), "DATE")
    orders   = _read_excel("admanager_360radio.xlsx", "GAM_Orders_LineItems")
    return {"diario": diario, "mensual": mensual, "formatos": formatos,
            "devices": devices, "fill": fill, "orders": orders}

@st.cache_data(ttl=3600)
def load_youtube():
    tabla   = _read_excel("Youtube histórico.xlsx", "Datos de la tabla")
    grafico = _parse_dates(_read_excel("Youtube histórico.xlsx", "Datos del gráfico"), "Fecha")
    totales = _parse_dates(_read_excel("Youtube histórico.xlsx", "Totales"), "Fecha")
    return {"tabla": tabla, "grafico": grafico, "totales": totales}

@st.cache_data(ttl=3600)
def load_instagram_posts():
    return _parse_dates(_read_csv("Post Instagram.csv"), "Fecha")

@st.cache_data(ttl=3600)
def load_instagram_stories():
    return _parse_dates(_read_csv("Instagram Historys.csv"), "Fecha")

@st.cache_data(ttl=3600)
def load_facebook():
    return _parse_dates(_read_csv("Post Facebook.csv"), "Fecha")

# ─── matching producción ↔ GA4 ─────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def load_produccion_con_metricas():
    prod = load_produccion()
    urls = load_ga4_urls_daily()
    if prod.empty: return prod

    result = prod.copy()
    result["ga4_views"] = 0
    result["ga4_users"] = 0

    if urls.empty:
        result["is_ia"] = False
        return result

    urls = urls.copy()
    if "pagePath" in urls.columns:
        urls["_post_id_from_url"] = _extract_post_id_from_url(urls["pagePath"])
    if "pageTitle" in urls.columns:
        urls["_title_norm"] = urls["pageTitle"].apply(_normalize_title)

    # Agregar GA4 por post_id
    if "_post_id_from_url" in urls.columns:
        ga4_by_id = (
            urls.dropna(subset=["_post_id_from_url"])
            .groupby("_post_id_from_url", as_index=False)
            .agg(ga4_views=("screenPageViews", "sum"), ga4_users=("activeUsers", "sum"))
        )
        ga4_by_id["_post_id_from_url"] = ga4_by_id["_post_id_from_url"].astype(float)
    else:
        ga4_by_id = pd.DataFrame()

    # Agregar GA4 por título
    if "_title_norm" in urls.columns:
        ga4_by_title = (
            urls[urls["_title_norm"] != ""]
            .groupby("_title_norm", as_index=False)
            .agg(ga4_views=("screenPageViews", "sum"), ga4_users=("activeUsers", "sum"))
        )
    else:
        ga4_by_title = pd.DataFrame()

    # Match por post_id
    if not ga4_by_id.empty and "post_id" in result.columns:
        result["post_id_num"] = pd.to_numeric(result["post_id"], errors="coerce")
        m = result[["post_id_num"]].merge(ga4_by_id, left_on="post_id_num", right_on="_post_id_from_url", how="left")
        result["ga4_views"] = m["ga4_views"].fillna(0).astype(int).values
        result["ga4_users"] = m["ga4_users"].fillna(0).astype(int).values

    # Match por título donde no hubo match
    if not ga4_by_title.empty and "_title_norm" in result.columns:
        mask = result["ga4_views"] == 0
        if mask.any():
            sub = result[mask][["_title_norm"]].merge(ga4_by_title, on="_title_norm", how="left")
            result.loc[mask, "ga4_views"] = sub["ga4_views"].fillna(0).astype(int).values
            result.loc[mask, "ga4_users"] = sub["ga4_users"].fillna(0).astype(int).values

    # Match por path de URL
    if "url" in result.columns and "pagePath" in urls.columns:
        ga4_by_path = urls.groupby("pagePath", as_index=False).agg(
            ga4_views_p=("screenPageViews", "sum"), ga4_users_p=("activeUsers", "sum")
        )
        result["_path"] = result["url"].apply(lambda u: urlparse(str(u)).path if pd.notna(u) else "")
        mask2 = result["ga4_views"] == 0
        if mask2.any():
            sub2 = result[mask2][["_path"]].merge(ga4_by_path, left_on="_path", right_on="pagePath", how="left")
            result.loc[mask2, "ga4_views"] = sub2["ga4_views_p"].fillna(0).astype(int).values
            result.loc[mask2, "ga4_users"] = sub2["ga4_users_p"].fillna(0).astype(int).values

    tags_col = result.get("tags", pd.Series("", index=result.index))
    result["is_ia"] = tags_col.apply(lambda x: bool(re.search(r'\bIA\b|\binteligencia.artificial\b', str(x), re.I)))

    return result

# ─── utilidades ────────────────────────────────────────────────────────────────

def filter_by_date(df, date_col, start, end):
    if df.empty or date_col not in df.columns: return df
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    return df[(df[date_col].dt.date >= start) & (df[date_col].dt.date <= end)]

def pct_change_label(current, previous):
    if previous == 0 or pd.isna(previous): return "N/A", "neutral"
    delta = (current - previous) / abs(previous) * 100
    return f"{delta:+.1f}%", ("green" if delta >= 0 else "red")

def fmt_number(n):
    if pd.isna(n): return "0"
    n = int(n)
    if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
    if n >= 1_000: return f"{n/1_000:.1f}K"
    return str(n)

def safe_sum(df, col):
    if df.empty or col not in df.columns: return 0
    return df[col].sum()
