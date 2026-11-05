"""
Dashboard de Custos 2026 — versão Streamlit
"""
import inspect
import io
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import custos_core as cc

COR_DIRETO, COR_RATEIO, COR_RATEADO, COR_GRUPO = "#2f6fed", "#f08c2e", "#16a37f", "#8b5cf6"
DATA_DIR = Path(__file__).parent / "dados"

st.set_page_config(page_title="Custos 2026", page_icon="📊", layout="wide")
st.markdown(
    """<style>
    .block-container{padding-top:1.8rem;max-width:1600px}
    [data-testid="stMetricValue"]{font-size:1.35rem}
    [data-testid="stMetricLabel"] p{font-size:.8rem;opacity:.7}
    h3{font-size:1rem!important;margin-bottom:.2rem}
    </style>""",
    unsafe_allow_html=True,
)

# ======================================================================
# Utilitários
# ======================================================================
def mostrar(func, *args, **kw):
    if "width" not in inspect.signature(func).parameters:
        return func(*args, use_container_width=True, **kw)
    try:
        return func(*args, width="stretch", **kw)
    except (TypeError, st.errors.StreamlitAPIException):
        return func(*args, use_container_width=True, **kw)

def chips(label, opcoes, padrao, key, fmt=str):
    if hasattr(st, "pills"):
        v = st.pills(label, opcoes, default=padrao, format_func=fmt, key=key)
        return padrao if v is None else v
    return st.radio(label, opcoes, index=opcoes.index(padrao), format_func=fmt, key=key, horizontal=True)

def tabela(df, fmt=None, altura=None, **kw):
    obj = df.style.format(fmt) if fmt else df
    if altura is None:
        altura = min(36 * (len(df) + 1) + 3, 360)
    return mostrar(st.dataframe, obj, hide_index=True, height=altura, **kw)

def dash(v):
    return cc.brl(v) if v else "–"

@st.cache_data(show_spinner="Lendo planilha…")
def ler_excel(conteudo: bytes) -> pd.DataFrame:
    return pd.read_excel(io.BytesIO(conteudo))

# ======================================================================
# Estado e persistência
# ======================================================================
def _arq(tipo):
    return DATA_DIR / f"{tipo}.pkl"

def salvar_base(tipo, df):
    DATA_DIR.mkdir(exist_ok=True)
    df.to_pickle(_arq(tipo))

def remover_base(tipo):
    _arq(tipo).unlink(missing_ok=True)
    st.session_state[f"df_{tipo}"] = None
    atualizar_cadastro()

def atualizar_cadastro():
    d, i = st.session_state["df_direto"], st.session_state["df_indireto"]
    if d is None or i is None:
        st.session_state["cadastro"], st.session_state["avisos"] = None, []
        return
    cad = cc.montar_cadastro(d, i)
    st.session_state["cadastro"] = cad
    st.session_state["avisos"] = cc.diagnostico(d, i, cad)

def iniciar_estado():
    for tipo in ("direto", "indireto"):
        if f"df_{tipo}" not in st.session_state:
            st.session_state[f"df_{tipo}"] = pd.read_pickle(_arq(tipo)) if _arq(tipo).exists() else None
    if "cadastro" not in st.session_state:
        atualizar_cadastro()

iniciar_estado()

# ======================================================================
# Gráficos
# ======================================================================
def _estilo(fig, altura):
    fig.update_layout(
        height=altura, margin=dict(l=0, r=0, t=10, b=0), separators=",.",
        legend=dict(orientation="h", y=1.15, x=1, xanchor="right", title_text=""),
        xaxis_title=None, yaxis_title=None,
    )
    return fig

def grafico_evolucao(serie, com_rateado):
    x = [cc.rotulo_periodo(p) for p in serie["periodo"]]
    fig = go.Figure()
    fig.add_bar(x=x, y=serie["direto"], name="Direto", marker_color=COR_DIRETO, hovertemplate="%{y:,.0f}")
    fig.add_bar(x=x, y=serie["recebido"], name="Rateio recebido", marker_color=COR_RATEIO, hovertemplate="%{y:,.0f}")
    fig.update_layout(barmode="stack")
    if com_rateado:
        fig.add_scatter(x=x, y=serie["rateado"], name="Rateado p/ outros", mode="lines+markers",
                        line=dict(color=COR_RATEADO, shape="spline"), hovertemplate="%{y:,.0f}")
    fig.update_yaxes(tickformat=".3~s")
    return _estilo(fig, 260)

def grafico_grupos(g):
    fig = go.Figure(go.Bar(x=g["valor"], y=g["grupo"], orientation="h", marker_color=COR_GRUPO, hovertemplate="%{x:,.0f}"))
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(tickformat=".3~s")
    return _estilo(fig, max(140, len(g) * 28 + 50))

# ======================================================================
# Blocos do detalhe
# ======================================================================
def bloco_fluxo(df, titulo_setor, absorvido=None):
    total = df["valor"].sum()
    por_seg = df.groupby("segmento")["valor"].sum().sort_values(ascending=False).reset_index()
    st.caption(" · ".join(f"{k}: {cc.brl(v)}" for k, v in
                          df.groupby("classificacao")["valor"].sum().sort_values(ascending=False).items()))
    st.markdown("**Por segmento**")
    tabela(pd.DataFrame({"Segmento": por_seg["segmento"], "Valor": por_seg["valor"],
                         "%": [cc.pct(v, total) for v in por_seg["valor"]]}), {"Valor": cc.brl})
    st.markdown(f"**{titulo_setor}**")
    t = pd.DataFrame({titulo_setor: df["cc_nome"], "Classificação": df["classificacao"], "Segmento": df["segmento"],
                      "Valor": df["valor"], "% do total": [cc.pct(v, total) for v in df["valor"]]})
    fmt = {"Valor": cc.brl}
    if absorvido is not None:
        tot_origem = df["cc_id"].map(absorvido)
        t["Total rateado pela origem"] = tot_origem
        t["% absorvido da origem"] = [cc.pct(v, o) for v, o in zip(df["valor"], tot_origem)]
        fmt["Total rateado pela origem"] = cc.brl
    tabela(t, fmt, altura=min(36 * (len(t) + 1) + 3, 320))

def painel_detalhe(cc_id, res_all, d, i, cad, periodos, todos, com_origem):
    if cc_id is None:
        with st.container(border=True):
            st.markdown("### Detalhe do centro de custo")
            st.caption("Selecione um centro na tabela para ver a evolução mensal, composição de custos e rateios.")
        return

    c = cad[cad["cc_id"] == cc_id].iloc[0]
    r = res_all[res_all["cc_id"] == cc_id].iloc[0]
    rateia = c["classificacao"] != "Produtivo" and com_origem

    with st.container(border=True):
        st.markdown(f"### {c['cc_nome']}")
        st.caption(f"{c['classificacao']} · {c['segmento']} · {cc_id}")
        cols = st.columns(4 if rateia else 3)
        cols[0].metric("Direto", cc.brl(r["direto"]))
        cols[1].metric("Rateio recebido", cc.brl(r["recebido"]))
        cols[2].metric("Custo total", cc.brl(r["total"]))
        if rateia:
            cols[3].metric("Rateado p/ outros", cc.brl(r["rateado"]))

    with st.container(border=True):
        st.markdown("### Evolução mensal")
        mostrar(st.plotly_chart, grafico_evolucao(cc.serie_mensal(d, i, cc_id, todos), rateia))

    g = cc.direto_por_grupo(d, cc_id, periodos)
    if not g.empty:
        with st.container(border=True):
            st.markdown("### Custo direto por grupo de conta")
            mostrar(st.plotly_chart, grafico_grupos(g))

    if rateia:
        with st.container(border=True):
            st.markdown("### Para quem o custo foi rateado")
            dest = cc.fluxo_do_centro(i, cad, cc_id, periodos, "destino")
            if dest.empty:
                st.caption("Sem movimentação no período.")
            else:
                bloco_fluxo(dest, "Setor de destino")

    if com_origem:
        org = cc.fluxo_do_centro(i, cad, cc_id, periodos, "origem")
        if not org.empty:
            with st.container(border=True):
                st.markdown("### Rateio recebido de")
                bloco_fluxo(org, "Setor de origem", absorvido=cc.total_rateado_pela_origem(i, periodos))

# ======================================================================
# Blocos da visão geral
# ======================================================================
def bloco_segmentos(L, i, cad, periodos, com_origem):
    seg = cc.resumo_segmentos(L)
    with st.container(border=True):
        st.markdown("### Visão por segmento")
        t = pd.DataFrame({
            "Segmento": seg["segmento"], "Direto": seg["direto"], "Rateio recebido": seg["recebido"],
            "Total": seg["total"], "% indireto": [cc.pct(r, t) for r, t in zip(seg["recebido"], seg["total"])],
            "Rateado p/ outros": seg["rateado"],
        })
        tabela(t, {"Direto": cc.brl, "Rateio recebido": cc.brl, "Total": cc.brl, "Rateado p/ outros": dash})

        if not com_origem: return
        mx = cc.matriz_segmentos(i, cad, set(L["cc_id"]), periodos)
        if mx.empty: return
        st.markdown("### Rateio entre segmentos")
        st.caption("Origem (linha) → destino (coluna), % da origem")
        tot = mx.sum(axis=1)
        disp = pd.DataFrame(index=mx.index, columns=mx.columns, dtype=object)
        for a in mx.index:
            for b in mx.columns:
                v = mx.loc[a, b]
                disp.loc[a, b] = f"{cc.brl(v)} ({cc.pct(v, tot[a])})" if v else "–"
        disp["Total rateado"] = tot.map(cc.brl)
        disp.index.name = "Origem \\ Destino"

        def sombra(_):
            est = pd.DataFrame("", index=disp.index, columns=disp.columns)
            for a in mx.index:
                for b in mx.columns:
                    p = mx.loc[a, b] / tot[a] if tot[a] else 0
                    est.loc[a, b] = f"background-color: rgba(47,111,237,{p * 0.45:.2f})"
            return est

        mostrar(st.dataframe, disp.style.apply(sombra, axis=None), height=min(36 * (len(disp) + 1) + 3, 360))

def bloco_centros(L):
    T = L.sort_values("total", ascending=False).reset_index(drop=True)
    with st.container(border=True):
        st.markdown("### Centros de custo — clique na linha para detalhar")
        vis = pd.DataFrame({
            "Centro de custo": T["cc_nome"], "Classificação": T["classificacao"], "Segmento": T["segmento"],
            "Direto": T["direto"], "Rateio recebido": T["recebido"], "Total": T["total"],
            "Rateado p/ outros": T["rateado"],
        })
        evento = mostrar(
            st.dataframe,
            vis.style.format({"Direto": cc.brl, "Rateio recebido": cc.brl, "Total": cc.brl, "Rateado p/ outros": dash}),
            hide_index=True, height=560, on_select="rerun", selection_mode="single-row", key="tbl_centros",
        )
    linhas = evento.selection.rows if evento is not None else []
    return T["cc_id"].iloc[linhas[0]] if linhas and linhas[0] < len(T) else None

# ======================================================================
# PÁGINAS
# ======================================================================
def pagina_dashboard():
    st.title("Custos 2026")
    d, i, cad = st.session_state["df_direto"], st.session_state["df_indireto"], st.session_state["cadastro"]
    if d is None or i is None:
        st.warning("⚠️ Vá ao menu 'Gerenciar Dados' e carregue as bases (direta e indireta) para ver o dashboard.")
        return
    if st.session_state["avisos"]:
        with st.expander("⚠️ Avisos sobre as bases carregadas"):
            for a in st.session_state["avisos"]: st.write("• " + a)

    com_origem = cc.tem_origem(i)
    todos = cc.periodos_disponiveis(d, i)

    sel_p = chips("Período", ["__todos__"] + todos, "__todos__", "f_per",
                  lambda p: "Ano todo" if p == "__todos__" else cc.rotulo_periodo(p))
    periodos = todos if sel_p == "__todos__" else [sel_p]

    existentes = set(cad["classificacao"])
    classifs = ["Todos"] + [c for c in cc.ORDEM_CLASSIF if c in existentes] + sorted(existentes - set(cc.ORDEM_CLASSIF))
    f1, f2, f3 = st.columns([2.2, 3, 2])
    with f1: sel_c = chips("Classificação", classifs, "Todos", "f_cls")
    with f2: sel_s = chips("Segmento", ["Todos"] + sorted(cad["segmento"].unique()), "Todos", "f_seg")
    with f3: busca = st.text_input("Buscar", placeholder="Buscar centro de custo…", label_visibility="collapsed")

    res_all = cc.resumo_centros(d, i, cad, periodos)
    L = cc.filtrar_centros(res_all, sel_c, sel_s, busca)
    k = cc.kpis(L)

    faixa = "Ano todo" if sel_p == "__todos__" else cc.rotulo_periodo(sel_p)
    if sel_p == "__todos__": faixa = f"{cc.rotulo_periodo(todos[0])[:3]}–{cc.rotulo_periodo(todos[-1])}"
    st.caption(f"{faixa} · {len(L)} centros")

    cols = st.columns(5)
    for col, (rot, val) in zip(cols, [
        ("Custo direto", cc.brl(k["direto"])), ("Rateio recebido", cc.brl(k["recebido"])),
        ("Custo total", cc.brl(k["total"])), ("% indireto", f"{k['pct_indireto']:.1f}%".replace(".", ",")),
        ("Rateado p/ outros", cc.brl(k["rateado"])),
    ]):
        with col.container(border=True): st.metric(rot, val)

    if L.empty:
        st.info("Nenhum centro de custo com movimentação.")
        return

    esq, dir_ = st.columns([1.15, 1], gap="medium")
    with esq:
        bloco_segmentos(L, i, cad, periodos, com_origem)
        sel_id = bloco_centros(L)
    with dir_:
        painel_detalhe(sel_id, res_all, d, i, cad, periodos, todos, com_origem)

def bloco_upload(tipo, titulo, campos, normalizar):
    st.subheader(titulo)
    arq = st.file_uploader(f"Planilha (.xlsx) — {titulo.lower()}", type=["xlsx"], key=f"up_{tipo}")
    if arq is None: return
    raw = ler_excel(arq.getvalue())
    auto = cc.auto_mapear(raw.columns, campos)
    faltando = [rot for ch, rot, obr, _ in campos if obr and not auto[ch]]

    opcoes = ["— não usar —"] + [str(c) for c in raw.columns]
    mapa = {}
    with st.expander("Mapeamento de colunas", expanded=bool(faltando)):
        for ch, rot, obr, _ in campos:
            padrao = opcoes.index(str(auto[ch])) if auto[ch] is not None else 0
            esc = st.selectbox(rot + (" *" if obr else ""), opcoes, index=padrao, key=f"map_{tipo}_{ch}_{arq.name}")
            mapa[ch] = None if esc == opcoes[0] else esc

    ainda = [rot for ch, rot, obr, _ in campos if obr and not mapa[ch]]
    if ainda:
        st.error("Faltam colunas: " + ", ".join(ainda))
        return
    st.caption(f"{len(raw):,} linhas lidas.".replace(",", "."))
    if st.button("Carregar base", key=f"btn_{tipo}", type="primary"):
        df = normalizar(raw, mapa)
        st.session_state[f"df_{tipo}"] = df
        salvar_base(tipo, df)
        atualizar_cadastro()
        st.success(f"✅ {len(df):,} linhas carregadas.")

def bloco_base(tipo, titulo):
    st.subheader(titulo)
    df = st.session_state[f"df_{tipo}"]
    if df is None:
        st.info("Nenhuma base carregada.")
        return
    ps = sorted(df["periodo"].unique())
    st.caption(f"{len(df):,} linhas · Total {cc.brl(df['valor'].sum())}")
    mostrar(st.dataframe, df.head(10))
    if st.button("🗑️ Excluir esta base", key=f"del_{tipo}"):
        remover_base(tipo)
        st.rerun()

def pagina_dados():
    st.title("📥 Gerenciamento de bases de custos")
    tab1, tab2 = st.tabs(["Upload de arquivos", "Visualizar & excluir bases"])
    with tab1:
        c1, c2 = st.columns(2)
        with c1: bloco_upload("direto", "Custos diretos", cc.CAMPOS_DIRETO, cc.normalizar_direto)
        with c2: bloco_upload("indireto", "Custos indiretos (rateios)", cc.CAMPOS_INDIRETO, cc.normalizar_indireto)
    with tab2:
        c1, c2 = st.columns(2)
        with c1: bloco_base("direto", "Base direta")
        with c2: bloco_base("indireto", "Base indireta")

# ======================================================================
# Navegação
# ======================================================================
logo = Path(__file__).parent / "logo_feso.png"
if logo.exists(): mostrar(st.sidebar.image, str(logo))
st.sidebar.title("Navegação")
menu = st.sidebar.radio("Selecione a página:", ["📊 Dashboard Principal", "📥 Gerenciar Dados"])
if menu == "📊 Dashboard Principal": pagina_dashboard()
else: pagina_dados()
