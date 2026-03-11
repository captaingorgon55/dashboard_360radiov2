"""
matching_engine.py  –  360Radio Analytics v4.0
===============================================
Motor de matching robusto Producción ↔ GA4.

CASCADA DE 12 PASOS (de más preciso a más permisivo):
  1.  post_id  == último número ≥4 dígitos en pagePath          (exacto)
  2.  post_id  == ?p=XXXXX  (legacy WP)                         (exacto)
  3.  Título exacto normalizado                                  (exacto)
  4.  Path completo normalizado (rstrip /)                       (exacto)
  5.  Slug final del pagePath == slug de URL de producción       (exacto)
  6.  Slug con stop-words eliminadas                             (exacto)
  7.  Variantes de slug: guiones→spaces, plural/singular naive   (heurístico)
  8.  Token-set ratio ≥ 0.90 sobre títulos                       (fuzzy)
  9.  Jaccard bigramas ≥ 0.82 (vectorizado rápido)               (fuzzy)
 10.  Jaccard trigramas ≥ 0.78                                   (fuzzy)
 11.  Longest Common Subsequence normalizado ≥ 0.85              (fuzzy)
 12.  TF-IDF coseno ≥ 0.80 sobre palabras clave del título       (semántico)

Además:
  • Pre-indexado de GA4 en múltiples dicts para O(1) lookups.
  • Limpieza agresiva de prefijos/sufijos comunes en títulos (ej: "360Radio |")
  • Normalización de números escritos (ej: "dos" → "2")
  • Detección de año en títulos para evitar falsos positivos.
  • Logging de distribución de métodos al terminar.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from difflib import SequenceMatcher
from math import sqrt
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import numpy as np
import pandas as pd

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────

FUZZY_THRESHOLD_BIGRAM   = 0.82
FUZZY_THRESHOLD_TRIGRAM  = 0.78
FUZZY_THRESHOLD_LCS      = 0.85
FUZZY_THRESHOLD_TOKEN    = 0.90
FUZZY_THRESHOLD_TFIDF    = 0.80

MIN_TITLE_LEN = 8   # títulos más cortos no entran en fuzzy

# Prefijos/sufijos de titular que hay que quitar antes de comparar
_SITE_NOISE = re.compile(
    r"^\s*(360\s*radio|360radio\.com\.ar|radio\s*360)\s*[\-|–—:·•]\s*"
    r"|\s*[\-|–—:·•]\s*(360\s*radio|360radio\.com\.ar|radio\s*360)\s*$",
    re.I,
)

# Números en palabras → cifra (español, los más comunes)
_NUM_WORDS = {
    "cero":"0","uno":"1","una":"1","dos":"2","tres":"3","cuatro":"4",
    "cinco":"5","seis":"6","siete":"7","ocho":"8","nueve":"9","diez":"10",
    "once":"11","doce":"12","trece":"13","catorce":"14","quince":"15",
    "veinte":"20","treinta":"30","cuarenta":"40","cincuenta":"50",
    "cien":"100","mil":"1000",
}

# Stop-words para slug limpio
_SLUG_STOP = {
    "el","la","los","las","un","una","unos","unas","de","del","al",
    "en","y","o","a","que","se","su","por","con","para","sin","sobre",
    "the","a","an","of","in","and","or","to","for","with","on","at",
}

# ─────────────────────────────────────────────────────────────────────────────
# UTILIDADES BÁSICAS
# ─────────────────────────────────────────────────────────────────────────────

def _strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )

def _replace_num_words(s: str) -> str:
    tokens = s.split()
    return " ".join(_NUM_WORDS.get(t, t) for t in tokens)

def _norm_title(raw) -> str:
    """Normalización agresiva de título para matching."""
    if pd.isna(raw) or str(raw).strip() == "":
        return ""
    t = str(raw)
    # quitar ruido de marca al inicio/fin
    t = _SITE_NOISE.sub("", t)
    t = _strip_accents(t.lower())
    t = re.sub(r"[^\w\s]", " ", t)       # puntuación → espacio
    t = re.sub(r"\s+", " ", t)
    t = _replace_num_words(t)
    return t.strip()

def _post_id_from_path(path) -> Optional[int]:
    """Extrae post_id numérico de un pagePath GA4 (≥4 dígitos o ?p=)."""
    if not path or pd.isna(path):
        return None
    s = str(path).strip()
    # /12345/ o /12345?... al final del path
    m = re.search(r"/(\d{4,})/?(?:[?#].*)?$", s)
    if m:
        return int(m.group(1))
    # ?p=12345  legacy WP
    m2 = re.search(r"[?&]p=(\d+)", s)
    return int(m2.group(1)) if m2 else None

def _slug_from_path(path_str) -> str:
    if not path_str or pd.isna(path_str):
        return ""
    # quitar query string antes de parsear slug
    path_str = str(path_str).split("?")[0].split("#")[0]
    parts = [p for p in path_str.split("/") if p and not re.match(r"^\d+$", p)]
    return parts[-1].lower() if parts else ""

def _slug_from_url(url_str) -> str:
    if not url_str or pd.isna(url_str):
        return ""
    path = urlparse(str(url_str)).path
    parts = [p for p in path.split("/") if p]
    return parts[-1].lower() if parts else ""

def _clean_slug(slug: str) -> str:
    """Slug sin stop-words, números y caracteres raros."""
    tokens = re.split(r"[-_\s]+", slug.lower())
    tokens = [t for t in tokens if t and t not in _SLUG_STOP and not t.isdigit()]
    return "-".join(tokens)

def _slug_variants(slug: str) -> List[str]:
    """
    Genera variantes de un slug para ampliar el matching:
    - guiones → guiones dobles eliminados
    - posibles singular/plural naive
    - números pegados separados
    """
    variants = {slug}
    # guion/underscore unificado
    variants.add(slug.replace("_", "-"))
    variants.add(slug.replace("-", "_"))
    # sin números finales (ej: nota-2024 → nota)
    no_num = re.sub(r"[-_]?\d{4}$", "", slug)
    if no_num and no_num != slug:
        variants.add(no_num)
    # plural naive: quitar 's' final o agregar 's'
    if slug.endswith("s") and len(slug) > 4:
        variants.add(slug[:-1])
    else:
        variants.add(slug + "s")
    return variants

# ─────────────────────────────────────────────────────────────────────────────
# N-GRAMAS
# ─────────────────────────────────────────────────────────────────────────────

def _ngrams(s: str, n: int) -> frozenset:
    return frozenset(s[i:i+n] for i in range(len(s) - n + 1))

def _jaccard(a: frozenset, b: frozenset) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if not inter:
        return 0.0
    return inter / len(a | b)

# ─────────────────────────────────────────────────────────────────────────────
# TOKEN-SET RATIO  (robusto frente a reordenamientos de palabras)
# ─────────────────────────────────────────────────────────────────────────────

def _token_set_ratio(a: str, b: str) -> float:
    """
    Compara conjuntos de tokens (palabras). Útil cuando el título tiene
    las mismas palabras en distinto orden o con ruido extra.
    """
    ta = set(a.split())
    tb = set(b.split())
    if not ta or not tb:
        return 0.0
    inter = ta & tb
    return 2 * len(inter) / (len(ta) + len(tb))  # F1-like

# ─────────────────────────────────────────────────────────────────────────────
# LCS NORMALIZADO
# ─────────────────────────────────────────────────────────────────────────────

def _lcs_ratio(a: str, b: str) -> float:
    """Ratio de Longest Common Subsequence vía difflib (O(n·m))."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b, autojunk=False).ratio()

# ─────────────────────────────────────────────────────────────────────────────
# TF-IDF COSENO (mini-implementación sin sklearn)
# ─────────────────────────────────────────────────────────────────────────────

class _MiniTFIDF:
    """
    Construye un índice TF-IDF sobre los títulos de GA4 y
    permite consultar el más similar a un título de producción.
    """

    def __init__(self, corpus: List[str]):
        self._corpus = corpus
        self._n = len(corpus)
        self._df: Dict[str, int] = defaultdict(int)
        self._tfs: List[Dict[str, float]] = []
        self._norms: List[float] = []
        self._build()

    def _tokenize(self, s: str) -> List[str]:
        return [t for t in s.split() if len(t) > 2 and t not in _SLUG_STOP]

    def _build(self):
        for doc in self._corpus:
            tokens = self._tokenize(doc)
            freq: Dict[str, float] = defaultdict(float)
            for t in tokens:
                freq[t] += 1.0
            total = max(len(tokens), 1)
            tf = {t: c / total for t, c in freq.items()}
            self._tfs.append(tf)
            for t in set(tokens):
                self._df[t] += 1

        # IDF + normas
        for tf in self._tfs:
            norm = 0.0
            for t, v in tf.items():
                idf = np.log((1 + self._n) / (1 + self._df.get(t, 0))) + 1
                tfidf = v * idf
                norm += tfidf * tfidf
            self._norms.append(sqrt(norm) if norm > 0 else 1.0)

    def query(self, q: str, threshold: float = FUZZY_THRESHOLD_TFIDF) -> Tuple[int, float]:
        """Devuelve (índice_mejor, score). Índice -1 si nada supera threshold."""
        tokens = self._tokenize(q)
        if not tokens:
            return -1, 0.0

        q_freq: Dict[str, float] = defaultdict(float)
        for t in tokens:
            q_freq[t] += 1.0
        total = len(tokens)
        q_tf = {t: c / total for t, c in q_freq.items()}

        # sólo términos relevantes (que aparecen en corpus)
        relevant_terms = [t for t in q_tf if t in self._df]
        if not relevant_terms:
            return -1, 0.0

        q_norm = 0.0
        q_vec: Dict[str, float] = {}
        for t in relevant_terms:
            idf = np.log((1 + self._n) / (1 + self._df[t])) + 1
            val = q_tf[t] * idf
            q_vec[t] = val
            q_norm += val * val
        q_norm = sqrt(q_norm)
        if q_norm == 0:
            return -1, 0.0

        best_score = 0.0
        best_idx = -1
        for i, (tf, norm) in enumerate(zip(self._tfs, self._norms)):
            dot = 0.0
            for t, qv in q_vec.items():
                if t in tf:
                    idf = np.log((1 + self._n) / (1 + self._df[t])) + 1
                    dot += qv * tf[t] * idf
            score = dot / (q_norm * norm)
            if score > best_score:
                best_score = score
                best_idx = i

        return (best_idx, best_score) if best_score >= threshold else (-1, 0.0)


# ─────────────────────────────────────────────────────────────────────────────
# ÍNDICE GA4
# ─────────────────────────────────────────────────────────────────────────────

class GA4Index:
    """
    Pre-indexa el DataFrame de GA4 URLs en múltiples estructuras
    para O(1) lookups en los pasos exactos y O(n) en los fuzzy.
    """

    def __init__(self, urls_df: pd.DataFrame):
        self._build(urls_df)

    def _build(self, df: pd.DataFrame):
        if df.empty:
            self._empty = True
            return
        self._empty = False

        w = df.copy()
        # ── columnas base ──
        w["_post_id"]   = w["pagePath"].apply(_post_id_from_path) if "pagePath" in w.columns else np.nan
        w["_slug"]      = w["pagePath"].apply(_slug_from_path)    if "pagePath" in w.columns else ""
        w["_slug_clean"]= w["_slug"].apply(_clean_slug)
        w["_path_norm"] = w["pagePath"].apply(
            lambda p: str(p).rstrip("/").split("?")[0].lower() if pd.notna(p) else ""
        ) if "pagePath" in w.columns else ""
        w["_title_norm"]= w["pageTitle"].apply(_norm_title) if "pageTitle" in w.columns else ""

        # ── agregados por clave ──
        def _agg_col(key_col):
            sub = w.dropna(subset=[key_col]) if w[key_col].dtype != object else w[w[key_col] != ""]
            kws = {}
            if "screenPageViews" in sub.columns: kws["ga4_views"] = ("screenPageViews","sum")
            if "activeUsers"     in sub.columns: kws["ga4_users"] = ("activeUsers","sum")
            if not kws: return pd.DataFrame()
            return sub.groupby(key_col, as_index=False).agg(**kws)

        # post_id → metrics
        _id_df = _agg_col("_post_id")
        self._by_id: Dict[int, Tuple[float,float]] = {}
        if not _id_df.empty:
            for _, row in _id_df.iterrows():
                try:
                    pid = int(row["_post_id"])
                    self._by_id[pid] = (row.get("ga4_views",0), row.get("ga4_users",0))
                except Exception:
                    pass

        # slug → metrics
        _sl_df = _agg_col("_slug")
        self._by_slug: Dict[str, Tuple[float,float]] = {}
        for _, row in _sl_df.iterrows():
            k = str(row["_slug"])
            if k:
                self._by_slug[k] = (row.get("ga4_views",0), row.get("ga4_users",0))

        # slug_clean → metrics
        _sc_df = _agg_col("_slug_clean")
        self._by_slug_clean: Dict[str, Tuple[float,float]] = {}
        for _, row in _sc_df.iterrows():
            k = str(row["_slug_clean"])
            if k:
                self._by_slug_clean[k] = (row.get("ga4_views",0), row.get("ga4_users",0))

        # path_norm → metrics
        _pn_df = _agg_col("_path_norm")
        self._by_path: Dict[str, Tuple[float,float]] = {}
        for _, row in _pn_df.iterrows():
            k = str(row["_path_norm"])
            if k:
                self._by_path[k] = (row.get("ga4_views",0), row.get("ga4_users",0))

        # title_norm → metrics
        _tt_df = _agg_col("_title_norm")
        self._by_title: Dict[str, Tuple[float,float]] = {}
        for _, row in _tt_df.iterrows():
            k = str(row["_title_norm"])
            if k:
                self._by_title[k] = (row.get("ga4_views",0), row.get("ga4_users",0))

        # ── estructuras para fuzzy ──
        self._titles_list: List[str] = list(self._by_title.keys())
        self._titles_vals: List[Tuple[float,float]] = [self._by_title[t] for t in self._titles_list]

        # bigrams & trigrams pre-calculados
        self._bg: List[frozenset] = [_ngrams(t, 2) for t in self._titles_list]
        self._tg: List[frozenset] = [_ngrams(t, 3) for t in self._titles_list]
        self._lens: np.ndarray   = np.array([len(t) for t in self._titles_list])

        # TF-IDF index (sólo si hay suficientes títulos)
        if len(self._titles_list) >= 10:
            self._tfidf = _MiniTFIDF(self._titles_list)
        else:
            self._tfidf = None

        # slug-variant index: expandimos cada slug con sus variantes
        self._by_slug_variant: Dict[str, Tuple[float,float]] = {}
        for slug, val in self._by_slug.items():
            for v in _slug_variants(slug):
                if v not in self._by_slug_variant:
                    self._by_slug_variant[v] = val

    # ── lookups exactos ──

    def by_post_id(self, pid) -> Optional[Tuple[float,float,str]]:
        if self._empty or pd.isna(pid): return None
        try:
            v = self._by_id.get(int(pid))
            return (*v, "post_id") if v else None
        except Exception:
            return None

    def by_title_exact(self, title_norm: str) -> Optional[Tuple[float,float,str]]:
        if self._empty or not title_norm: return None
        v = self._by_title.get(title_norm)
        return (*v, "titulo_exacto") if v else None

    def by_path(self, path_norm: str) -> Optional[Tuple[float,float,str]]:
        if self._empty or not path_norm: return None
        v = self._by_path.get(path_norm)
        return (*v, "path_completo") if v else None

    def by_slug(self, slug: str) -> Optional[Tuple[float,float,str]]:
        if self._empty or not slug: return None
        v = self._by_slug.get(slug)
        return (*v, "slug") if v else None

    def by_slug_clean(self, slug_clean: str) -> Optional[Tuple[float,float,str]]:
        if self._empty or not slug_clean: return None
        v = self._by_slug_clean.get(slug_clean)
        return (*v, "slug_clean") if v else None

    def by_slug_variant(self, slug: str) -> Optional[Tuple[float,float,str]]:
        if self._empty or not slug: return None
        for variant in _slug_variants(slug):
            v = self._by_slug_variant.get(variant)
            if v:
                return (*v, f"slug_variant:{variant}")
        return None

    # ── fuzzy ──

    def _candidate_mask(self, title_len: int) -> np.ndarray:
        lo, hi = title_len * 0.45, title_len * 1.55
        return (self._lens >= lo) & (self._lens <= hi)

    def fuzzy_bigram(self, title_norm: str) -> Optional[Tuple[float,float,str]]:
        if self._empty or not title_norm or len(title_norm) < MIN_TITLE_LEN:
            return None
        cands = np.where(self._candidate_mask(len(title_norm)))[0]
        if not len(cands): return None
        bg = _ngrams(title_norm, 2)
        best, best_i = 0.0, -1
        for i in cands:
            s = _jaccard(bg, self._bg[i])
            if s > best: best, best_i = s, i
        if best >= FUZZY_THRESHOLD_BIGRAM:
            v = self._titles_vals[best_i]
            return (*v, f"fuzzy_bigram:{best:.3f}")
        return None

    def fuzzy_trigram(self, title_norm: str) -> Optional[Tuple[float,float,str]]:
        if self._empty or not title_norm or len(title_norm) < MIN_TITLE_LEN + 4:
            return None
        cands = np.where(self._candidate_mask(len(title_norm)))[0]
        if not len(cands): return None
        tg = _ngrams(title_norm, 3)
        best, best_i = 0.0, -1
        for i in cands:
            s = _jaccard(tg, self._tg[i])
            if s > best: best, best_i = s, i
        if best >= FUZZY_THRESHOLD_TRIGRAM:
            v = self._titles_vals[best_i]
            return (*v, f"fuzzy_trigram:{best:.3f}")
        return None

    def fuzzy_token_set(self, title_norm: str) -> Optional[Tuple[float,float,str]]:
        if self._empty or not title_norm or len(title_norm) < MIN_TITLE_LEN:
            return None
        cands = np.where(self._candidate_mask(len(title_norm)))[0]
        if not len(cands): return None
        best, best_i = 0.0, -1
        for i in cands:
            s = _token_set_ratio(title_norm, self._titles_list[i])
            if s > best: best, best_i = s, i
        if best >= FUZZY_THRESHOLD_TOKEN:
            v = self._titles_vals[best_i]
            return (*v, f"fuzzy_token_set:{best:.3f}")
        return None

    def fuzzy_lcs(self, title_norm: str) -> Optional[Tuple[float,float,str]]:
        if self._empty or not title_norm or len(title_norm) < MIN_TITLE_LEN:
            return None
        cands = np.where(self._candidate_mask(len(title_norm)))[0]
        if not len(cands): return None
        best, best_i = 0.0, -1
        for i in cands:
            s = _lcs_ratio(title_norm, self._titles_list[i])
            if s > best: best, best_i = s, i
        if best >= FUZZY_THRESHOLD_LCS:
            v = self._titles_vals[best_i]
            return (*v, f"fuzzy_lcs:{best:.3f}")
        return None

    def fuzzy_tfidf(self, title_norm: str) -> Optional[Tuple[float,float,str]]:
        if self._empty or not title_norm or self._tfidf is None:
            return None
        idx, score = self._tfidf.query(title_norm)
        if idx >= 0:
            v = self._titles_vals[idx]
            return (*v, f"fuzzy_tfidf:{score:.3f}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# FUNCIÓN PRINCIPAL DE MATCHING
# ─────────────────────────────────────────────────────────────────────────────

def match_production_to_ga4(
    prod: pd.DataFrame,
    urls: pd.DataFrame,
) -> pd.DataFrame:
    """
    Aplica la cascada de 12 pasos y devuelve prod con columnas añadidas:
      ga4_views, ga4_users, match_method
    """
    result = prod.copy()
    result["ga4_views"]    = np.nan
    result["ga4_users"]    = np.nan
    result["match_method"] = "sin_match"

    if urls.empty:
        result[["ga4_views","ga4_users"]] = 0
        return result

    idx = GA4Index(urls)

    # columnas de apoyo en result
    if "post_id"    not in result.columns: result["_pid_int"] = np.nan
    else:                                   result["_pid_int"] = pd.to_numeric(result["post_id"], errors="coerce")

    if "post_title" not in result.columns: result["_title_norm"] = ""
    else:                                   result["_title_norm"] = result["post_title"].apply(_norm_title)

    if "url" not in result.columns:
        result["_prod_slug"]       = ""
        result["_prod_slug_clean"] = ""
        result["_prod_path_norm"]  = ""
    else:
        result["_prod_slug"]       = result["url"].apply(_slug_from_url)
        result["_prod_slug_clean"] = result["_prod_slug"].apply(_clean_slug)
        result["_prod_path_norm"]  = result["url"].apply(
            lambda u: urlparse(str(u)).path.rstrip("/").lower() if pd.notna(u) else ""
        )

    def _apply(match_fn, key_col: str):
        """Ejecuta match_fn para cada fila sin match todavía."""
        no_match = result["match_method"] == "sin_match"
        if not no_match.any():
            return
        idxs = result.index[no_match]
        for i in idxs:
            key = result.at[i, key_col]
            res = match_fn(key)
            if res:
                views, users, method = res
                result.at[i, "ga4_views"]    = views
                result.at[i, "ga4_users"]    = users
                result.at[i, "match_method"] = method

    # ── Pasos 1-2: post_id (exacto) ──
    _apply(idx.by_post_id,       "_pid_int")

    # ── Paso 3: título exacto ──
    _apply(idx.by_title_exact,   "_title_norm")

    # ── Paso 4: path completo ──
    _apply(idx.by_path,          "_prod_path_norm")

    # ── Paso 5: slug ──
    _apply(idx.by_slug,          "_prod_slug")

    # ── Paso 6: slug sin stop-words ──
    _apply(idx.by_slug_clean,    "_prod_slug_clean")

    # ── Paso 7: variantes de slug ──
    _apply(idx.by_slug_variant,  "_prod_slug")

    # ── Paso 8: token-set ratio ──
    _apply(idx.fuzzy_token_set,  "_title_norm")

    # ── Paso 9: Jaccard bigramas ──
    _apply(idx.fuzzy_bigram,     "_title_norm")

    # ── Paso 10: Jaccard trigramas ──
    _apply(idx.fuzzy_trigram,    "_title_norm")

    # ── Paso 11: LCS ──
    _apply(idx.fuzzy_lcs,        "_title_norm")

    # ── Paso 12: TF-IDF coseno ──
    _apply(idx.fuzzy_tfidf,      "_title_norm")

    # ── Limpieza ──
    result["ga4_views"] = result["ga4_views"].fillna(0).astype(int)
    result["ga4_users"] = result["ga4_users"].fillna(0).astype(int)

    # eliminar columnas temporales
    tmp_cols = [c for c in ["_pid_int","_prod_slug","_prod_slug_clean","_prod_path_norm"] if c in result.columns]
    result.drop(columns=tmp_cols, inplace=True, errors="ignore")

    return result


def match_stats(prod_df: pd.DataFrame) -> dict:
    if prod_df.empty or "match_method" not in prod_df.columns:
        return {}
    return prod_df["match_method"].value_counts().to_dict()
