import sys, os; sys.path.insert(0, os.getcwd())
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta

from data_loader import (
    load_ga4_general, load_ga4_city, load_ga4_country, load_ga4_channel,
    load_ga4_age, load_ga4_device, load_ga4_interests,
    load_notas_trafico,  # 👈 NUEVO
    filter_by_date, fmt_number, safe_sum, get_date_range, _delta_str
)

C   = ["#6366f1","#06b6d4","#10b981","#f59e0b","#ef4444","#8b5cf6","#ec4899","#14b8a6"]
PBG = "#0d0d20"

def _fig(fig, h=340):
    fig.update_layout(
        height=h, paper_bgcolor=PBG, plot_bgcolor=PBG,
        font=dict(family="Inter", color="#8890b8", size=11),
        margin=dict(l=6, r=6, t=36, b=6),
    )
    return fig

def sh(t):
    st.markdown(f"### {t}")

# ════════════════════════════════════════
# CARGA
# ════════════════════════════════════════
with st.spinner("Cargando datos..."):
    ga4_r  = load_ga4_general()
    city_r = load_ga4_city()
    chan_r = load_ga4_channel()
    prod_r = load_notas_trafico()  # 🔥 NUEVO CORE

min_d, max_d = get_date_range(ga4_r, "date")

# ════════════════════════════════════════
# FILTROS
# ════════════════════════════════════════
st.markdown("## ⚙️ Filtros")

c1, c2, c3, c4 = st.columns(4)

with c1:
    start = st.date_input("Desde", max_d - timedelta(days=30))
with c2:
    end = st.date_input("Hasta", max_d)

auth_list = ["Todos"] + sorted(prod_r["post_author_name"].dropna().unique())
cat_list = ["Todas"] + list(
    prod_r["categories"]
    .fillna("")
    .str.split(",")
    .explode()
    .str.strip()
    .value_counts()
    .head(20)
    .index
)

with c3:
    sel_aut = st.selectbox("Autor", auth_list)
with c4:
    sel_cat = st.selectbox("Sección", cat_list)

# ════════════════════════════════════════
# FILTRADO
# ════════════════════════════════════════
prod = filter_by_date(prod_r, "post_date", start, end)

if sel_aut != "Todos":
    prod = prod[prod["post_author_name"] == sel_aut]

if sel_cat != "Todas":
    prod = prod[
        prod["categories"].fillna("").str.contains(sel_cat)
    ]

# ════════════════════════════════════════
# MÉTRICAS
# ════════════════════════════════════════
st.markdown("## 📊 Métricas")

au = int(prod["activeUsers"].sum())
vw = int(prod["screenPageViews"].sum())
posts = len(prod)

m1, m2, m3 = st.columns(3)
m1.metric("Usuarios", fmt_number(au))
m2.metric("Vistas", fmt_number(vw))
m3.metric("Publicaciones", posts)

# ════════════════════════════════════════
# EVOLUCIÓN
# ════════════════════════════════════════
st.markdown("## 📈 Evolución")

if not prod.empty:
    ev = prod.copy()
    ev["mes"] = ev["post_date"].dt.to_period("M").astype(str)

    mo = ev.groupby("mes", as_index=False).agg(
        U=("activeUsers", "sum"),
        V=("screenPageViews", "sum")
    )

    fig = go.Figure()
    fig.add_bar(x=mo["mes"], y=mo["V"], name="Vistas")
    fig.add_scatter(x=mo["mes"], y=mo["U"], name="Usuarios")

    _fig(fig)
    st.plotly_chart(fig, use_container_width=True)

# ════════════════════════════════════════
# TOP NOTAS
# ════════════════════════════════════════
st.markdown("## 📰 Top Notas")

top = prod.sort_values("screenPageViews", ascending=False).head(20)

st.dataframe(
    top[["post_title", "post_author_name", "screenPageViews", "activeUsers"]]
    .rename(columns={
        "post_title": "Título",
        "post_author_name": "Autor",
        "screenPageViews": "Vistas",
        "activeUsers": "Usuarios"
    })
    .style.format({"Vistas": "{:,.0f}", "Usuarios": "{:,.0f}"}),
    use_container_width=True
)

# ════════════════════════════════════════
# AUTORES
# ════════════════════════════════════════
st.markdown("## ✍️ Autores")

aa = prod.groupby("post_author_name", as_index=False).agg(
    Vistas=("screenPageViews", "sum"),
    Usuarios=("activeUsers", "sum"),
    Notas=("post_id", "count")
).sort_values("Vistas", ascending=False)

st.dataframe(
    aa.rename(columns={"post_author_name": "Autor"})
    .style.format({"Vistas": "{:,.0f}", "Usuarios": "{:,.0f}"}),
    use_container_width=True
)

# ════════════════════════════════════════
# SECCIONES
# ════════════════════════════════════════
st.markdown("## 📂 Secciones")

sp = prod.copy()
sp["cat"] = sp["categories"].fillna("Sin cat").str.split(",").str[0]

sa = sp.groupby("cat", as_index=False).agg(
    Vistas=("screenPageViews", "sum"),
    Usuarios=("activeUsers", "sum")
).sort_values("Vistas", ascending=False)

st.dataframe(
    sa.rename(columns={"cat": "Sección"})
    .style.format({"Vistas": "{:,.0f}", "Usuarios": "{:,.0f}"}),
    use_container_width=True
)
