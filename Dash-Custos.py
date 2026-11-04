import streamlit as st
import pandas as pd
import plotly.express as px

# 1. Configuração inicial da página
st.set_page_config(page_title="Gestão de Custos", layout="wide")

# Função de Cache para alta performance na leitura de dados
@st.cache_data
def processar_excel(arquivo):
    df = pd.read_excel(arquivo)
    if "Período" in df.columns:
        df["Período"] = df["Período"].astype(str)
    return df

# Inicialização da Memória (Session State)
if "df_direto" not in st.session_state:
    st.session_state["df_direto"] = None
if "df_indireto" not in st.session_state:
    st.session_state["df_indireto"] = None

# ==========================================
# BARRA LATERAL (SIDEBAR) & NAVEGAÇÃO
# ==========================================
# Para colocar a logo real, basta subir a imagem no GitHub e colocar o nome do arquivo aqui, ex: st.sidebar.image("logo_feso.png")
# Por enquanto, deixei um placeholder (imagem de espaço reservado)
st.sidebar.image("https://via.placeholder.com/300x100.png?text=LOGO+DA+FUNDACAO", use_container_width=True)
st.sidebar.title("Navegação")

# Ordem invertida: Dashboard vem primeiro
menu = st.sidebar.radio(
    "Selecione a página:",
    ["📊 Dashboard Principal", "📥 Gerenciar Dados"]
)

# ==========================================
# TELA 1: DASHBOARD PRINCIPAL
# ==========================================
if menu == "📊 Dashboard Principal":
    st.title("📊 Dashboard de Custos Institucionais")

    if st.session_state["df_direto"] is None or st.session_state["df_indireto"] is None:
        st.warning("⚠️ Vá ao menu 'Gerenciar Dados' e carregue os dois arquivos para visualizar o dashboard.")
    else:
        # Prepara e une as bases para os filtros
        df_dir = st.session_state["df_direto"].copy()
        df_dir["Origem"] = "Direto"
        
        df_ind = st.session_state["df_indireto"].copy()
        df_ind["Origem"] = "Rateio"
        
        df_full = pd.concat([df_dir, df_ind], ignore_index=True)

        # 1. Filtros na Barra Lateral
        st.sidebar.header("Filtros Executivos")
        segmentos = st.sidebar.multiselect("Unidade de Negócio", sorted(df_full["Segmento"].dropna().unique()), default=df_full["Segmento"].dropna().unique())
        periodos = st.sidebar.multiselect("Período", sorted(df_full["Período"].dropna().unique()), default=df_full["Período"].dropna().unique())
        classificacoes = st.sidebar.multiselect("Classificação", sorted(df_full["Classificação"].dropna().unique()), default=df_full["Classificação"].dropna().unique())

        # Aplica filtros globais
        df_filtrado = df_full[
            (df_full["Segmento"].isin(segmentos)) & 
            (df_full["Período"].isin(periodos)) & 
            (df_full["Classificação"].isin(classificacoes))
        ]

        # 2. KPIs de Topo
        custo_dir = df_filtrado[df_filtrado["Origem"] == "Direto"]["Valor"].sum()
        custo_ind = df_filtrado[df_filtrado["Origem"] == "Rateio"]["Valor"].sum()
        custo_total = custo_dir + custo_ind

        col1, col2, col3 = st.columns(3)
        col1.metric("Custo Total (Consolidado)", f"R$ {custo_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        col2.metric("Total Custos Diretos", f"R$ {custo_dir:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        col3.metric("Total Rateios Recebidos", f"R$ {custo_ind:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        st.markdown("---")

        # 3. Gráficos de Evolução e Composição
        col_graf1, col_graf2 = st.columns(2)
        
        with col_graf1:
            st.subheader("Evolução Mensal de Custos")
            df_evolucao = df_filtrado.groupby(["Período", "Origem"])["Valor"].sum().reset_index()
            fig_bar = px.bar(
                df_evolucao, 
                x="Período", 
                y="Valor", 
                color="Origem", 
                barmode="group",
                color_discrete_map={"Direto": "#2f6fed", "Rateio": "#f79c42"},
                text_auto='.2s'
            )
            fig_bar.update_layout(xaxis_title="Período", yaxis_title="Custo (R$)")
            st.plotly_chart(fig_bar, use_container_width=True)

        with col_graf2:
            st.subheader("Composição por Unidade (Segmento)")
            df_seg = df_filtrado.groupby("Segmento")["Valor"].sum().reset_index()
            fig_pie = px.pie(
                df_seg, 
                names="Segmento", 
                values="Valor", 
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            fig_pie.update_traces(textinfo='percent+label')
            st.plotly_chart(fig_pie, use_container_width=True)

        st.markdown("---")

        # 4. Tabela de Detalhamento
        st.subheader("Detalhamento por Centro de Custo")
        df_tabela = df_filtrado.groupby(["Centro de Custo", "Segmento", "Tipo", "Origem"])["Valor"].sum().reset_index()
        df_tabela = df_tabela.sort_values("Valor", ascending=False)
        # Formatação financeira para a tabela
        df_tabela["Valor (R$)"] = df_tabela["Valor"].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        
        st.dataframe(df_tabela[["Centro de Custo", "Segmento", "Tipo", "Origem", "Valor (R$)"]], use_container_width=True, hide_index=True)


# ==========================================
# TELA 2: GERENCIAR DADOS (IMPORTAÇÃO E EXCLUSÃO)
# ==========================================
elif menu == "📥 Gerenciar Dados":
    st.title("📥 Gerenciamento de Bases de Custos")
    
    # Sistema de Abas (Tabs)
    tab1, tab2 = st.tabs(["Upload de Arquivos", "Visualizar & Excluir Bases"])
    
    # ABA 1: UPLOAD
    with tab1:
        st.markdown("Faça o upload dos arquivos extraídos do sistema.")
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Custos Diretos")
            arquivo_direto = st.file_uploader("Base de Custos Diretos (.xlsx)", type=["xlsx"], key="direto")
            if arquivo_direto:
                st.session_state["df_direto"] = processar_excel(arquivo_direto)
                st.success("✅ Custos Diretos carregados na memória!")

        with col2:
            st.subheader("Custos Indiretos (Rateios)")
            arquivo_indireto = st.file_uploader("Base de Custos Indiretos (.xlsx)", type=["xlsx"], key="indireto")
            if arquivo_indireto:
                st.session_state["df_indireto"] = processar_excel(arquivo_indireto)
                st.success("✅ Custos Indiretos carregados na memória!")

    # ABA 2: GERENCIAMENTO DAS BASES CARREGADAS
    with tab2:
        st.markdown("Verifique os dados em memória ou exclua uma base específica caso tenha importado o arquivo errado.")
        
        c1, c2 = st.columns(2)
        
        with c1:
            st.subheader("Base Direta")
            if st.session_state["df_direto"] is not None:
                st.dataframe(st.session_state["df_direto"].head(10), use_container_width=True)
                if st.button("🗑️ Excluir Base Direta"):
                    st.session_state["df_direto"] = None
                    st.rerun()
            else:
                st.info("Nenhuma base direta carregada.")
                
        with c2:
            st.subheader("Base Indireta (Rateio)")
            if st.session_state["df_indireto"] is not None:
                st.dataframe(st.session_state["df_indireto"].head(10), use_container_width=True)
                if st.button("🗑️ Excluir Base Indireta"):
                    st.session_state["df_indireto"] = None
                    st.rerun()
            else:
                st.info("Nenhuma base indireta carregada.")
        
        st.markdown("---")
        if st.button("🚨 Limpar Todas as Bases (Esvaziar Memória)"):
            st.cache_data.clear()
            st.session_state["df_direto"] = None
            st.session_state["df_indireto"] = None
            st.rerun()
