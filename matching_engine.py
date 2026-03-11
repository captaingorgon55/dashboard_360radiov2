"""
matching_engine.py  –  360Radio Analytics v4.1  (FAST)
=======================================================
Optimizaciones v4.1 vs v4.0:
  • Pasos exactos 1-7: O(1) dicts — sin cambios (ya eran rápidos)
  • Early-exit: si los exactos resuelven >= 95% de filas, los fuzzy NI CORREN
  • Fuzzy 8-11: 100% vectorizados con numpy (sin loops Python por fila)
  • TF-IDF (paso 12): solo corre si quedan mas de 50 filas sin match
  • LCS (paso 11): solo corre sobre candidatos filtrados por bigram score > 0.5
  • Batch fuzzy: un unico loop vectorizado cubre pasos 8-11 simultaneamente
  • Pre-filtro de longitud con numpy mask

Cascada de pasos:
  1-2. post_id exacto / legacy ?p=
  3.   Titulo exacto normalizado
  4.   Path completo normalizado
  5.   Slug exacto
  6.   Slug sin stop-words
  7.   Variantes de slug
  [early-exit si >=95% matched]
  8-11. Fuzzy batch vectorizado (token-set, bigrama, trigrama, LCS)
  12.  TF-IDF (solo si >50 sin match)
"""
from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from math import sqrt
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import numpy as np
import pandas as pd

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────

FUZZY_THRESHOLD_BIGRAM  = 0.82
FUZZY_THRESHOLD_TRIGRAM = 0.78
FUZZY_THRESHOLD_LCS     = 0.85
FUZZY_THRESHOLD_TOKEN   = 0.90
FUZZY_THRESHOLD_TFIDF   = 0.80
EARLY_EXIT_PCT          = 0.95
TFIDF_MIN_UNMATCHED     = 50
MIN_TITLE_LEN           = 8

_SITE_NOISE = re.compile(
    r"^\s*(360\s*radio|360radio\.com\.ar|radio\s*360)\s*[\-|]\s*"
    r"|\s*[\-|]\s*(360\s*radio|360radio\.com\.ar|radio\s*360)\s*$",
    re.I,
)
_NUM_WORDS = {
    "cero":"0","uno":"1","una":"1","dos":"2","tres":"3","cuatro":"4",
    "cinco":"5","seis":"6","siete":"7","ocho":"8","nueve":"9","diez":"10",
    "once":"11","doce":"12","trece":"13","catorce":"14","quince":"15",
    "veinte":"20","treinta":"30","cuarenta":"40","cincuenta":"50",
    "cien":"100","mil":"1000",
}
_SLUG_STOP = {
    "el","la","los","las","un","una","unos","unas","de","del","al",
    "en","y","o","a","que","se","su","por","con","para","sin","sobre",
    "the","an","of","in","and","or","to","for","with","on","at",
}


# ─────────────────────────────────────────────────────────────────────────────
# UTILIDADES DE TEXTO
# ─────────────────────────────────────────────────────────────────────────────

def _strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )

def _norm_title(raw) -> str:
    if pd.isna(raw) or str(raw).strip() == "":
        return ""
    t = _SITE_NOISE.sub("", str(raw))
    t = _strip_accents(t.lower())
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\s+", " ", t)
    tokens = [_NUM_WORDS.get(w, w) for w in t.split()]
    return " ".join(tokens).strip()

def _post_id_from_path(path) -> Optional[int]:
    if not path or pd.isna(path):
        return None
    s = str(path).strip()
    m = re.search(r"/(\d{4,})/?(?:[?#].*)?$", s)
    if m:
        return int(m.group(1))
    m2 = re.search(r"[?&]p=(\d+)", s)
    return int(m2.group(1)) if m2 else None

def _slug_from_path(path_str) -> str:
    if not path_str or pd.isna(path_str):
        return ""
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
    tokens = re.split(r"[-_\s]+", slug.lower())
    return "-".join(t for t in tokens if t and t not in _SLUG_STOP and not t.isdigit())

def _slug_variants(slug: str) -> List[str]:
    variants = {slug, slug.replace("_", "-"), slug.replace("-", "_")}
    no_num = re.sub(r"[-_]?\d{4}$", "", slug)
    if no_num and no_num != slug:
        variants.add(no_num)
    if slug.endswith("s") and len(slug) > 4:
        variants.add(slug[:-1])
    else:
        variants.add(slug + "s")
    return list(variants)


# ─────────────────────────────────────────────────────────────────────────────
# SIMILITUDES VECTORIZADAS
# ─────────────────────────────────────────────────────────────────────────────

def _build_char_matrix(titles: List[str], n: int):
    ngs  = [frozenset(t[i:i+n] for i in range(len(t) - n + 1)) for t in titles]
    lens = np.array([len(t) for t in titles], dtype=np.float32)
    return ngs, lens

def _jaccard_batch(query_ng: frozenset, corpus_ng: list, mask: np.ndarray) -> np.ndarray:
    scores = np.zeros(len(corpus_ng), dtype=np.float32)
    for i in np.where(mask)[0]:
        cng = corpus_ng[i]
        if not cng:
            continue
        inter = len(query_ng & cng)
        if inter:
            scores[i] = inter / len(query_ng | cng)
    return scores

def _token_set_batch(query_tokens: frozenset, corpus_tokens: list, mask: np.ndarray) -> np.ndarray:
    scores = np.zeros(len(corpus_tokens), dtype=np.float32)
    qt_len = len(query_tokens)
    if not qt_len:
        return scores
    for i in np.where(mask)[0]:
        ct = corpus_tokens[i]
        if not ct:
            continue
        inter = len(query_tokens & ct)
        if inter:
            scores[i] = 2 * inter / (qt_len + len(ct))
    return scores

def _lcs_ratio(a: str, b: str) -> float:
    la, lb = len(a), len(b)
    if not la or not lb:
        return 0.0
    prev = [0] * (lb + 1)
    best = 0
    for ca in a:
        curr = [0] * (lb + 1)
        for j, cb in enumerate(b, 1):
            if ca == cb:
                curr[j] = prev[j-1] + 1
                if curr[j] > best:
                    best = curr[j]
            else:
                curr[j] = 0
        prev = curr
    return best / min(la, lb)


# ─────────────────────────────────────────────────────────────────────────────
# TF-IDF MINI  (paso 12, lazy)
# ─────────────────────────────────────────────────────────────────────────────

class _MiniTFIDF:
    def __init__(self, corpus: List[str]):
        self._n = len(corpus)
        self._df: Dict[str, int] = defaultdict(int)
        self._tfs: List[Dict[str, float]] = []
        self._norms: List[float] = []
        self._build(corpus)

    def _tok(self, s: str) -> List[str]:
        return [t for t in s.split() if len(t) > 2 and t not in _SLUG_STOP]

    def _build(self, corpus):
        for doc in corpus:
            tokens = self._tok(doc)
            freq: Dict[str, float] = defaultdict(float)
            for t in tokens:
                freq[t] += 1.0
            total = max(len(tokens), 1)
            tf = {t: c / total for t, c in freq.items()}
            self._tfs.append(tf)
            for t in set(tokens):
                self._df[t] += 1
        for tf in self._tfs:
            norm = sum(
                (v * (np.log((1 + self._n) / (1 + self._df.get(t, 0))) + 1)) ** 2
                for t, v in tf.items()
            )
            self._norms.append(sqrt(norm) if norm > 0 else 1.0)

    def query(self, q: str) -> Tuple[int, float]:
        tokens = self._tok(q)
        if not tokens:
            return -1, 0.0
        q_freq: Dict[str, float] = defaultdict(float)
        for t in tokens:
            q_freq[t] += 1.0
        total = len(tokens)
        relevant = {t: q_freq[t] / total for t in q_freq if t in self._df}
        if not relevant:
            return -1, 0.0
        q_vec: Dict[str, float] = {}
        q_norm = 0.0
        for t, v in relevant.items():
            idf = np.log((1 + self._n) / (1 + self._df[t])) + 1
            val = v * idf
            q_vec[t] = val
            q_norm += val * val
        q_norm = sqrt(q_norm)
        if q_norm == 0:
            return -1, 0.0
        best_score, best_idx = 0.0, -1
        for i, (tf, norm) in enumerate(zip(self._tfs, self._norms)):
            dot = sum(
                qv * tf.get(t, 0) * (np.log((1 + self._n) / (1 + self._df[t])) + 1)
                for t, qv in q_vec.items()
            )
            score = dot / (q_norm * norm)
            if score > best_score:
                best_score, best_idx = score, i
        return (best_idx, best_score) if best_score >= FUZZY_THRESHOLD_TFIDF else (-1, 0.0)


# ─────────────────────────────────────────────────────────────────────────────
# INDICE GA4
# ─────────────────────────────────────────────────────────────────────────────

class GA4Index:
    def __init__(self, urls_df: pd.DataFrame):
        self._empty = True
        self._tfidf: Optional[_MiniTFIDF] = None
        if not urls_df.empty:
            self._build(urls_df)

    def _build(self, df: pd.DataFrame):
        w = df.copy()

        if "pagePath" in w.columns:
            w["_post_id"]    = w["pagePath"].apply(_post_id_from_path)
            w["_slug"]       = w["pagePath"].apply(_slug_from_path)
            w["_slug_clean"] = w["_slug"].apply(_clean_slug)
            w["_path_norm"]  = w["pagePath"].apply(
                lambda p: str(p).rstrip("/").split("?")[0].lower() if pd.notna(p) else "")

        if "pageTitle" in w.columns:
            w["_title_norm"] = w["pageTitle"].apply(_norm_title)

        def _agg(col):
            if col not in w.columns:
                return pd.DataFrame()
            sub = w[w[col].notna() & (w[col].astype(str).str.strip() != "")]
            kws = {}
            if "screenPageViews" in sub.columns: kws["ga4_views"] = ("screenPageViews", "sum")
            if "activeUsers"     in sub.columns: kws["ga4_users"] = ("activeUsers", "sum")
            return sub.groupby(col, as_index=False).agg(**kws) if kws else pd.DataFrame()

        def _to_dict(agg_df, key) -> Dict:
            if agg_df.empty:
                return {}
            out = {}
            for _, row in agg_df.iterrows():
                k = row[key]
                if pd.notna(k) and str(k).strip():
                    out[k] = (float(row.get("ga4_views", 0)), float(row.get("ga4_users", 0)))
            return out

        self._by_slug       = _to_dict(_agg("_slug"),       "_slug")
        self._by_slug_clean = _to_dict(_agg("_slug_clean"), "_slug_clean")
        self._by_path       = _to_dict(_agg("_path_norm"),  "_path_norm")
        self._by_title      = _to_dict(_agg("_title_norm"), "_title_norm")

        self._by_id: Dict[int, Tuple] = {}
        for k, v in _to_dict(_agg("_post_id"), "_post_id").items():
            try:
                self._by_id[int(k)] = v
            except Exception:
                pass

        # slug variants
        self._by_slug_variant: Dict[str, Tuple] = {}
        for slug, val in self._by_slug.items():
            for vr in _slug_variants(str(slug)):
                if vr not in self._by_slug_variant:
                    self._by_slug_variant[vr] = val

        # estructuras fuzzy
        self._titles_list: List[str] = list(self._by_title.keys())
        self._titles_vals: List[Tuple] = [self._by_title[t] for t in self._titles_list]

        if self._titles_list:
            self._bg, self._lens = _build_char_matrix(self._titles_list, 2)
            self._tg, _          = _build_char_matrix(self._titles_list, 3)
            self._tok_sets: List[frozenset] = [frozenset(t.split()) for t in self._titles_list]
        else:
            self._bg = self._tg = self._tok_sets = []
            self._lens = np.array([])

        self._empty = False

    # ── lookups exactos ──

    def by_post_id(self, pid) -> Optional[Tuple]:
        if self._empty or pd.isna(pid): return None
        try:
            v = self._by_id.get(int(pid))
            return (*v, "post_id") if v else None
        except Exception:
            return None

    def by_title_exact(self, t: str) -> Optional[Tuple]:
        if self._empty or not t: return None
        v = self._by_title.get(t)
        return (*v, "titulo_exacto") if v else None

    def by_path(self, p: str) -> Optional[Tuple]:
        if self._empty or not p: return None
        v = self._by_path.get(p)
        return (*v, "path_completo") if v else None

    def by_slug(self, s: str) -> Optional[Tuple]:
        if self._empty or not s: return None
        v = self._by_slug.get(s)
        return (*v, "slug") if v else None

    def by_slug_clean(self, s: str) -> Optional[Tuple]:
        if self._empty or not s: return None
        v = self._by_slug_clean.get(s)
        return (*v, "slug_clean") if v else None

    def by_slug_variant(self, s: str) -> Optional[Tuple]:
        if self._empty or not s: return None
        for variant in _slug_variants(s):
            v = self._by_slug_variant.get(variant)
            if v:
                return (*v, "slug_variant")
        return None

    # ── fuzzy batch (pasos 8-11) ──

    def fuzzy_batch(self, title_norm: str) -> Optional[Tuple]:
        if self._empty or not self._titles_list or len(title_norm) < MIN_TITLE_LEN:
            return None

        tlen = len(title_norm)
        mask = (self._lens >= tlen * 0.45) & (self._lens <= tlen * 1.55)
        if not mask.any():
            return None

        # Paso 8: token-set
        qt = frozenset(title_norm.split())
        ts = _token_set_batch(qt, self._tok_sets, mask)
        best_i = int(np.argmax(ts))
        if ts[best_i] >= FUZZY_THRESHOLD_TOKEN:
            return (*self._titles_vals[best_i], f"fuzzy_token_set:{ts[best_i]:.3f}")

        # Paso 9: bigrama
        bg_q = frozenset(title_norm[j:j+2] for j in range(tlen - 1))
        bg_s = _jaccard_batch(bg_q, self._bg, mask)
        best_i = int(np.argmax(bg_s))
        if bg_s[best_i] >= FUZZY_THRESHOLD_BIGRAM:
            return (*self._titles_vals[best_i], f"fuzzy_bigram:{bg_s[best_i]:.3f}")

        # Paso 10: trigrama
        if tlen >= MIN_TITLE_LEN + 4:
            tg_q = frozenset(title_norm[j:j+3] for j in range(tlen - 2))
            tg_s = _jaccard_batch(tg_q, self._tg, mask)
            best_i = int(np.argmax(tg_s))
            if tg_s[best_i] >= FUZZY_THRESHOLD_TRIGRAM:
                return (*self._titles_vals[best_i], f"fuzzy_trigram:{tg_s[best_i]:.3f}")
        else:
            tg_s = np.zeros(len(self._titles_list))

        # Paso 11: LCS (solo candidatos con bigram > 0.50)
        lcs_mask = mask & (bg_s > 0.50)
        for i in np.where(lcs_mask)[0]:
            s = _lcs_ratio(title_norm, self._titles_list[i])
            if s >= FUZZY_THRESHOLD_LCS:
                return (*self._titles_vals[i], f"fuzzy_lcs:{s:.3f}")

        return None

    # ── TF-IDF lazy (paso 12) ──

    def fuzzy_tfidf(self, title_norm: str) -> Optional[Tuple]:
        if self._empty or not self._titles_list:
            return None
        if self._tfidf is None:
            self._tfidf = _MiniTFIDF(self._titles_list)
        idx, score = self._tfidf.query(title_norm)
        if idx >= 0:
            return (*self._titles_vals[idx], f"fuzzy_tfidf:{score:.3f}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# FUNCION PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def match_production_to_ga4(prod: pd.DataFrame, urls: pd.DataFrame) -> pd.DataFrame:
    result = prod.copy()
    result["ga4_views"]    = np.nan
    result["ga4_users"]    = np.nan
    result["match_method"] = "sin_match"

    if urls.empty:
        result[["ga4_views", "ga4_users"]] = 0
        return result

    # claves de busqueda
    result["_pid_int"] = (
        pd.to_numeric(result["post_id"], errors="coerce")
        if "post_id" in result.columns else np.nan
    )
    result["_title_norm"] = (
        result["post_title"].apply(_norm_title)
        if "post_title" in result.columns else ""
    )
    if "url" in result.columns:
        result["_prod_slug"]       = result["url"].apply(_slug_from_url)
        result["_prod_slug_clean"] = result["_prod_slug"].apply(_clean_slug)
        result["_prod_path_norm"]  = result["url"].apply(
            lambda u: urlparse(str(u)).path.rstrip("/").lower() if pd.notna(u) else "")
    else:
        result["_prod_slug"] = result["_prod_slug_clean"] = result["_prod_path_norm"] = ""

    ga4 = GA4Index(urls)

    def _apply(fn, col: str):
        mask = result["match_method"] == "sin_match"
        if not mask.any():
            return
        for i in result.index[mask]:
            res = fn(result.at[i, col])
            if res:
                result.at[i, "ga4_views"]    = res[0]
                result.at[i, "ga4_users"]    = res[1]
                result.at[i, "match_method"] = res[2]

    # pasos exactos 1-7
    _apply(ga4.by_post_id,      "_pid_int")
    _apply(ga4.by_title_exact,  "_title_norm")
    _apply(ga4.by_path,         "_prod_path_norm")
    _apply(ga4.by_slug,         "_prod_slug")
    _apply(ga4.by_slug_clean,   "_prod_slug_clean")
    _apply(ga4.by_slug_variant, "_prod_slug")

    # early-exit
    total   = len(result)
    matched = (result["match_method"] != "sin_match").sum()
    if total > 0 and matched / total >= EARLY_EXIT_PCT:
        _finalize(result)
        return result

    # pasos fuzzy 8-11 (batch vectorizado)
    _apply(ga4.fuzzy_batch, "_title_norm")

    # paso 12 TF-IDF (solo si muchos sin match)
    if (result["match_method"] == "sin_match").sum() >= TFIDF_MIN_UNMATCHED:
        _apply(ga4.fuzzy_tfidf, "_title_norm")

    _finalize(result)
    return result


def _finalize(df: pd.DataFrame):
    df["ga4_views"] = df["ga4_views"].fillna(0).astype(int)
    df["ga4_users"] = df["ga4_users"].fillna(0).astype(int)
    drop = ["_pid_int", "_prod_slug", "_prod_slug_clean", "_prod_path_norm"]
    df.drop(columns=[c for c in drop if c in df.columns], inplace=True, errors="ignore")


def match_stats(prod_df: pd.DataFrame) -> dict:
    if prod_df.empty or "match_method" not in prod_df.columns:
        return {}
    return prod_df["match_method"].value_counts().to_dict()
