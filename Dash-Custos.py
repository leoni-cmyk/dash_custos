import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Gestão de Custos", layout="wide")

# ==========================================
# FUNÇÃO DE ALTA PERFORMANCE (CACHE)
# ==========================================
# O @st.cache_data faz o aplicativo ler o Excel pesado apenas uma vez.
@st.cache_data
def processar_excel(arquivo):
    df = pd.read_excel(arquivo)
    # Aqui já garantimos que o período fique como texto para os filtros futuros
    if "Período" in df.columns:
        df["Período"] = df["Período"].astype(str)
    return df

# Inicialização da Memória
if "df_direto" not in st.session_state:
    st.session_state["df_direto"] = None
if "df_indireto" not in st.session_state:
    st.session_state["df_indireto"] = None

# ==========================================
# MENU LATERAL
# ==========================================
st.sidebar.title("Navegação")
menu = st.sidebar.radio(
    "Selecione a página:",
    ["📥 Importação de Dados", "📊 Dashboard Principal"]
)

# ==========================================
# TELA 1: IMPORTAÇÃO DE DADOS
# ==========================================
if menu == "📥 Importação de Dados":
    st.title("📥 Importação das Bases de Custos")
    st.markdown("Faça o upload dos arquivos extraídos do sistema (ERP).")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Custos Diretos")
        arquivo_direto = st.file_uploader("Base de Custos Diretos (.xlsx)", type=["xlsx"], key="direto")
        if arquivo_direto:
            # Usando a função com cache para processamento rápido
            st.session_state["df_direto"] = processar_excel(arquivo_direto)
            st.success("✅ Custos Diretos carregados na memória!")

    with col2:
        st.subheader("Custos Indiretos (Rateios)")
        arquivo_indireto = st.file_uploader("Base de Custos Indiretos (.xlsx)", type=["xlsx"], key="indireto")
        if arquivo_indireto:
            st.session_state["df_indireto"] = processar_excel(arquivo_indireto)
            st.success("✅ Custos Indiretos carregados na memória!")

    st.markdown("---")
    if st.button("🗑️ Limpar Bases Importadas"):
        st.cache_data.clear() # Limpa o cache de alta performance também
        st.session_state["df_direto"] = None
        st.session_state["df_indireto"] = None
        st.rerun()

# ==========================================
# TELA 2: DASHBOARD PRINCIPAL
# ==========================================
elif menu == "📊 Dashboard Principal":
    st.title("📊 Dashboard de Custos Institucionais")

    if st.session_state["df_direto"] is None or st.session_state["df_indireto"] is None:
        st.warning("⚠️ Vá ao menu 'Importação de Dados' e carregue os dois arquivos antes de visualizar o dashboard.")
    
    else:
        df_direto = st.session_state["df_direto"]
        df_indireto = st.session_state["df_indireto"]

        # 1. Filtro Macro de Unidade de Negócio
        st.sidebar.header("Filtros Executivos")
        
        # Tenta identificar a coluna de Unidade de Negócio (você usou 'Segmento' no HTML original)
        coluna_unidade = "Segmento" if "Segmento" in df_direto.columns else None
        
        if coluna_unidade:
            unidades_disponiveis = df_direto[coluna_unidade].unique().tolist()
            unidades_selecionadas = st.sidebar.multiselect(
                "Unidade de Negócio / Segmento", 
                unidades_disponiveis, 
                default=unidades_disponiveis
            )
            
            # Aplica o filtro na base de diretos e indiretos
            df_direto = df_direto[df_direto[coluna_unidade].isin(unidades_selecionadas)]
            if coluna_unidade in df_indireto.columns:
                df_indireto = df_indireto[df_indireto[coluna_unidade].isin(unidades_selecionadas)]

        # 2. Exibição Consolidada
        st.markdown(f"### Visão Atual: {', '.join(unidades_selecionadas) if coluna_unidade and unidades_selecionadas else 'Todas as Unidades'}")
        
        # Resumo Financeiro no Topo
        custo_direto_total = df_direto["Valor"].sum() if "Valor" in df_direto.columns else 0
        custo_indireto_total = df_indireto["Valor"].sum() if "Valor" in df_indireto.columns else 0
        custo_total = custo_direto_total + custo_indireto_total

        col1, col2, col3 = st.columns(3)
        col1.metric("Custo Total (Consolidado)", f"R$ {custo_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        col2.metric("Total Custos Diretos", f"R$ {custo_direto_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        col3.metric("Total Rateios Recebidos", f"R$ {custo_indireto_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

        st.markdown("---")
        st.write("Estrutura base pronta e otimizada para grandes volumes. Próximo passo: gráficos.")
