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

st.set_page_config(page_title="Custos Feso", page_icon="📊", layout="wide")
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
    if "width" not in inspect.signature(func).parameters: return func(*args, use_container_width=True, **kw)
    try: return func(*args, width="stretch", **kw)
    except (TypeError, st.errors.StreamlitAPIException): return func(*args, use_container_width=True, **kw)

def tabela(df, fmt=None, altura=None, **kw):
    obj = df.style.format(fmt) if fmt else df
    return mostrar(st.dataframe, obj, hide_index=True, height=altura or min(36 * (len(df) + 1) + 3, 360), **kw)

def dash(v): return cc.brl(v) if v else "–"

@st.cache_data(show_spinner="Lendo planilha…")
def ler_excel(conteudo: bytes) -> pd.DataFrame: return pd.read_excel(io.BytesIO(conteudo))

# ======================================================================
# Estado e persistência
# ======================================================================
def _arq(tipo): return DATA_DIR / f"{tipo}.pkl"
def salvar_base(tipo, df): DATA_DIR.mkdir(exist_ok=True); df.to_pickle(_arq(tipo))
def remover_base(tipo): _arq(tipo).unlink(missing_ok=True); st.session_state[f"df_{tipo}"] = None; atualizar_cadastro()

def atualizar_cadastro():
    d, i = st.session_state.get("df_direto"), st.session_state.get("df_indireto")
    if d is None or i is None: st.session_state["cadastro"], st.session_state["avisos"] = None, []; return
    cad = cc.montar_cadastro(d, i)
    st.session_state["cadastro"] = cad
    st.session_state["avisos"] = cc.diagnostico(d, i, cad)

def iniciar_estado():
    for tipo in ("direto", "indireto"):
        if f"df_{tipo}" not in st.session_state:
            st.session_state[f"df_{tipo}"] = pd.read_pickle(_arq(tipo)) if _arq(tipo).exists() else None
    if "cadastro" not in st.session_state: atualizar_cadastro()

iniciar_estado()

# ======================================================================
# Blocos Visuais do Dashboard
# ======================================================================
def _estilo(fig, altura):
    fig.update_layout(height=altura, margin=dict(l=0, r=0, t=10, b=0), separators=",.",
                      legend=dict(orientation="h", y=1.15, x=1, xanchor="right", title_text=""))
    return fig

def grafico_evolucao(serie, com_rateado):
    x = [cc.rotulo_periodo(p) for p in serie["periodo"]]
    fig = go.Figure()
    fig.add_bar(x=x, y=serie["direto"], name="Direto", marker_color=COR_DIRETO, hovertemplate="%{y:,.0f}")
    fig.add_bar(x=x, y=serie["recebido"], name="Rateio recebido", marker_color=COR_RATEIO, hovertemplate="%{y:,.0f}")
    fig.update_layout(barmode="stack")
    if com_rateado: fig.add_scatter(x=x, y=serie["rateado"], name="Rateado p/ outros", mode="lines+markers", line=dict(color=COR_RATEADO))
    return _estilo(fig, 260)

def grafico_grupos(g):
    fig = go.Figure(go.Bar(x=g["valor"], y=g["grupo"], orientation="h", marker_color=COR_GRUPO, hovertemplate="%{x:,.0f}"))
    fig.update_yaxes(autorange="reversed")
    return _estilo(fig, max(140, len(g) * 28 + 50))

def bloco_fluxo(df, titulo_setor, absorvido=None):
    total = df["valor"].sum()
    por_seg = df.groupby("segmento")["valor"].sum().sort_values(ascending=False).reset_index()
    st.markdown("**Por segmento**")
    tabela(pd.DataFrame({"Segmento": por_seg["segmento"], "Valor": por_seg["valor"], "%": [cc.pct(v, total) for v in por_seg["valor"]]}), {"Valor": cc.brl})
    st.markdown(f"**{titulo_setor}**")
    t = pd.DataFrame({titulo_setor: df["cc_nome"], "Classif": df["classificacao"], "Valor": df["valor"], "%": [cc.pct(v, total) for v in df["valor"]]})
    fmt = {"Valor": cc.brl}
    if absorvido is not None:
        t["Total origem"] = df["cc_id"].map(absorvido)
        t["% absorvido"] = [cc.pct(v, o) for v, o in zip(df["valor"], t["Total origem"])]
        fmt["Total origem"] = cc.brl
    tabela(t, fmt)

def painel_detalhe(cc_id, res_all, d, i, cad, periodos, todos, com_origem):
    if cc_id is None:
        with st.container(border=True):
            st.markdown("### Detalhe do centro de custo")
            st.caption("Selecione um centro na tabela para ver a evolução mensal e composição.")
        return

    c = cad[cad["cc_id"] == cc_id].iloc[0]
    rateia = c["classificacao"] != "Produtivo" and com_origem

    with st.container(border=True):
        st.markdown(f"### {c['cc_nome']}")
        st.caption(f"{c['classificacao']} · {c['segmento']} · {cc_id}")
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
            if dest.empty: st.caption("Sem movimentação.")
            else: bloco_fluxo(dest, "Setor de destino")

    if com_origem:
        org = cc.fluxo_do_centro(i, cad, cc_id, periodos, "origem")
        if not org.empty:
            with st.container(border=True):
                st.markdown("### Rateio recebido de")
                bloco_fluxo(org, "Setor de origem", absorvido=cc.total_rateado_pela_origem(i, periodos))

def bloco_segmentos(L, i, cad, periodos, com_origem):
    seg = cc.resumo_segmentos(L)
    with st.container(border=True):
        st.markdown("### Visão por segmento")
        t = pd.DataFrame({"Segmento": seg["segmento"], "Direto": seg["direto"], "Recebido": seg["recebido"], "Total": seg["total"], "Rateado": seg["rateado"]})
        tabela(t, {"Direto": cc.brl, "Recebido": cc.brl, "Total": cc.brl, "Rateado": dash})

        if not com_origem: return
        mx = cc.matriz_segmentos(i, cad, set(L["cc_id"]), periodos)
        if mx.empty: return
        st.markdown("### Rateio entre segmentos")
        tot = mx.sum(axis=1)
        disp = pd.DataFrame(index=mx.index, columns=mx.columns, dtype=object)
        for a in mx.index:
            for b in mx.columns:
                v = mx.loc[a, b]
                disp.loc[a, b] = f"{cc.brl(v)} ({cc.pct(v, tot[a])})" if v else "–"
        disp["Total rateado"] = tot.map(cc.brl)
        
        def sombra(_):
            est = pd.DataFrame("", index=disp.index, columns=disp.columns)
            for a in mx.index:
                for b in mx.columns:
                    p = mx.loc[a, b] / tot[a] if tot[a] else 0
                    est.loc[a, b] = f"background-color: rgba(47,111,237,{p * 0.45:.2f})"
            return est
        mostrar(st.dataframe, disp.style.apply(sombra, axis=None))

def bloco_centros(L):
    T = L.sort_values("total", ascending=False).reset_index(drop=True)
    with st.container(border=True):
        st.markdown("### Centros de custo — clique para detalhar")
        vis = pd.DataFrame({"Centro de custo": T["cc_nome"], "Classificação": T["classificacao"], "Segmento": T["segmento"], "Direto": T["direto"], "Recebido": T["recebido"], "Total": T["total"]})
        
        # A tabela agora armazena a seleção usando a key "tbl_centros"
        evento = mostrar(
            st.dataframe,
            vis.style.format({"Direto": cc.brl, "Recebido": cc.brl, "Total": cc.brl}),
            hide_index=True, height=560, on_select="rerun", selection_mode="single-row", key="tbl_centros"
        )
    return T

# ======================================================================
# PÁGINAS
# ======================================================================
def pagina_dashboard():
    st.title("📊 Dashboard Analítico")
    d, i, cad = st.session_state["df_direto"], st.session_state["df_indireto"], st.session_state["cadastro"]
    if d is None or i is None: return st.warning("Vá em 'Gerenciar Dados' e carregue as bases (direta e indireta).")

    com_origem = cc.tem_origem(i)
    todos = cc.periodos_disponiveis(d, i)
    dict_anos = cc.ano_mes_dict(todos)
    anos_disp = list(dict_anos.keys())
    
    # 1. Filtros Separados de Ano e Mês
    f1, f2, f3, f4, f5 = st.columns([1, 2, 2, 2, 3])
    with f1: ano_sel = st.selectbox("Ano", anos_disp)
    with f2: mes_sel = st.multiselect("Meses (vazio = ano todo)", options=dict_anos[ano_sel], format_func=cc.rotulo_mes)
    
    periodos = [cc.formatar_periodo(ano_sel, m) for m in mes_sel] if mes_sel else [cc.formatar_periodo(ano_sel, m) for m in dict_anos.get(ano_sel, [])]
    
    existentes = set(cad["classificacao"])
    op_cls = [c for c in cc.ORDEM_CLASSIF if c in existentes] + sorted(existentes - set(cc.ORDEM_CLASSIF))
    with f3: sel_c = st.multiselect("Classificações", options=op_cls, default=op_cls)
    with f4: sel_s = st.multiselect("Segmentos", options=sorted(cad["segmento"].unique()), default=sorted(cad["segmento"].unique()))
    with f5: busca = st.text_input("Buscar", placeholder="Nome ou código do centro...")

    res_all = cc.resumo_centros(d, i, cad, periodos)
    L = cc.filtrar_centros(res_all, sel_c, sel_s, busca)
    
    # Lógica de Captura do Selecionado (Para tornar os KPIs inteligentes)
    T_ordenado = L.sort_values("total", ascending=False).reset_index(drop=True)
    sel_id = None
    estado_tbl = st.session_state.get("tbl_centros")
    if estado_tbl and estado_tbl.get("selection") and estado_tbl["selection"]["rows"]:
        linha = estado_tbl["selection"]["rows"][0]
        if linha < len(T_ordenado): sel_id = T_ordenado["cc_id"].iloc[linha]

    # 2. KPIs Dinâmicos (Mudam se você clicar na tabela)
    L_kpi = L[L["cc_id"] == sel_id] if sel_id else L
    k = cc.kpis(L_kpi)
    
    st.markdown(f"#### {'Resumo: ' + cad[cad['cc_id']==sel_id].iloc[0]['cc_nome'] if sel_id else 'Visão Global'}")
    cols = st.columns(5)
    for col, (rot, val) in zip(cols, [
        ("Custo direto", cc.brl(k["direto"])), ("Rateio recebido", cc.brl(k["recebido"])),
        ("Custo total", cc.brl(k["total"])), ("% indireto", f"{k['pct_indireto']:.1f}%".replace(".", ",")),
        ("Rateado p/ outros", cc.brl(k["rateado"])),
    ]):
        with col.container(border=True): st.metric(rot, val)

    if L.empty: return st.info("Nenhum dado encontrado para estes filtros.")
    st.markdown("---")
    
    esq, dir_ = st.columns([1.15, 1], gap="medium")
    with esq:
        bloco_segmentos(L, i, cad, periodos, com_origem)
        bloco_centros(L)  # Aqui a tabela é desenhada
    with dir_:
        painel_detalhe(sel_id, res_all, d, i, cad, periodos, todos, com_origem)

def pagina_relatorio():
    st.title("📄 Relatório Consolidado (Excel)")
    d, i, cad = st.session_state["df_direto"], st.session_state["df_indireto"], st.session_state["cadastro"]
    if d is None or i is None: return st.warning("Dados não carregados.")

    todos = cc.periodos_disponiveis(d, i)
    anos_disp = list(cc.ano_mes_dict(todos).keys())
    
    c1, c2, c3 = st.columns([1.5, 4, 1.5])
    with c1: ano_sel = st.selectbox("Ano de Análise", anos_disp)
    with c2: 
        opcoes_busca = cad["cc_id"] + " - " + cad["cc_nome"]
        cc_buscado = st.selectbox("Selecione o Centro de Custo", options=[""] + list(opcoes_busca))
    
    if not cc_buscado: return st.info("⬆️ Selecione um centro de custo acima para gerar o relatório matricial.")
        
    cc_id = cc_buscado.split(" - ")[0]
    info = cad[cad["cc_id"] == cc_id].iloc[0]
    
    st.markdown(f"## {info['cc_nome']}")
    st.caption(f"Código: {cc_id} | Classificação: {info['classificacao']} | Segmento: {info['segmento']}")
    st.markdown("---")
    
    # 3. Matriz Estilo Excel
    st.subheader("1. Evolução do Custo Direto")
    pv = cc.relatorio_direto_pivot(d, cc_id, ano_sel)
    if pv.empty:
        st.caption("Sem custos diretos registrados neste ano.")
    else:
        fmt = {c: cc.brl for c in pv.columns}
        st.dataframe(pv.style.format(fmt), use_container_width=True, height=min(38 * (len(pv) + 1) + 3, 700))
        
    st.markdown("<br>", unsafe_allow_html=True)
    
    # 4. Drill-Down do Indireto
    st.subheader("2. Origens do Custo Indireto (Rateio Recebido)")
    ind_data = cc.relatorio_indireto_drilldown(i, cc_id, ano_sel)
    
    if ind_data.empty:
        st.caption("Este centro não recebeu rateios indiretos neste ano.")
    else:
        por_seg = ind_data.groupby("origem_segmento")["valor"].sum().sort_values(ascending=False)
        for seg, tot_seg in por_seg.items():
            with st.expander(f"🏢 Rateio vindo do Segmento: **{seg}** — Total Absorvido: **{cc.brl(tot_seg)}**"):
                detalhes = ind_data[ind_data["origem_segmento"] == seg].sort_values("valor", ascending=False)
                for _, row in detalhes.iterrows():
                    st.write(f"▪ **{row['origem_nome']}** `(CC: {row['origem_id']})` repassou **{cc.brl(row['valor'])}**")

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
    if ainda: return st.error("Faltam colunas: " + ", ".join(ainda))
    st.caption(f"{len(raw):,} linhas lidas.")
    if st.button("Carregar base", key=f"btn_{tipo}", type="primary"):
        df = normalizar(raw, mapa)
        st.session_state[f"df_{tipo}"] = df
        salvar_base(tipo, df)
        atualizar_cadastro()
        st.success("✅ Base carregada com sucesso!")

def bloco_base(tipo, titulo):
    st.subheader(titulo)
    df = st.session_state[f"df_{tipo}"]
    if df is None: return st.info("Nenhuma base carregada.")
    st.caption(f"{len(df):,} linhas · Total {cc.brl(df['valor'].sum())}")
    mostrar(st.dataframe, df.head(10))
    if st.button("🗑️ Excluir esta base", key=f"del_{tipo}"): remover_base(tipo); st.rerun()

def pagina_dados():
    st.title("📥 Gerenciamento de bases de custos")
    t1, t2 = st.tabs(["Upload de arquivos", "Visualizar & excluir bases"])
    with t1:
        c1, c2 = st.columns(2)
        with c1: bloco_upload("direto", "Custos diretos", cc.CAMPOS_DIRETO, cc.normalizar_direto)
        with c2: bloco_upload("indireto", "Custos indiretos (rateios)", cc.CAMPOS_INDIRETO, cc.normalizar_indireto)
    with t2:
        c1, c2 = st.columns(2)
        with c1: bloco_base("direto", "Base direta")
        with c2: bloco_base("indireto", "Base indireta")

# ======================================================================
# Navegação
# ======================================================================
logo = Path(__file__).parent / "logo_feso.png"
if logo.exists(): mostrar(st.sidebar.image, str(logo))
st.sidebar.title("Navegação")
menu = st.sidebar.radio("Selecione a página:", ["📊 Dashboard Analítico", "📄 Relatório Consolidado", "📥 Gerenciar Dados"])
if menu == "📊 Dashboard Analítico": pagina_dashboard()
elif menu == "📄 Relatório Consolidado": pagina_relatorio()
else: pagina_dados()
