import streamlit as st
import pandas as pd
import plotly.express as px

# 1. Configuração inicial da página
st.set_page_config(page_title="Gestão de Custos", layout="wide")

# 2. Inicialização da "Memória" do aplicativo (Session State)
# Isso garante que ao trocar de tela no menu, os dados não sejam perdidos
if "df_direto" not in st.session_state:
    st.session_state["df_direto"] = None
if "df_indireto" not in st.session_state:
    st.session_state["df_indireto"] = None

# 3. Criação do Menu Lateral
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
    st.markdown("Faça o upload dos arquivos extraídos do sistema.")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Custos Diretos")
        arquivo_direto = st.file_uploader("Base de Custos Diretos (.xlsx)", type=["xlsx"], key="direto")
        if arquivo_direto:
            st.session_state["df_direto"] = pd.read_excel(arquivo_direto)
            st.success("✅ Custos Diretos carregados na memória!")

    with col2:
        st.subheader("Custos Indiretos (Rateios)")
        arquivo_indireto = st.file_uploader("Base de Custos Indiretos (.xlsx)", type=["xlsx"], key="indireto")
        if arquivo_indireto:
            st.session_state["df_indireto"] = pd.read_excel(arquivo_indireto)
            st.success("✅ Custos Indiretos carregados na memória!")

    # Botão para limpar a memória caso você suba o arquivo errado
    st.markdown("---")
    if st.button("🗑️ Limpar Bases Importadas"):
        st.session_state["df_direto"] = None
        st.session_state["df_indireto"] = None
        st.rerun()

# ==========================================
# TELA 2: DASHBOARD PRINCIPAL
# ==========================================
elif menu == "📊 Dashboard Principal":
    st.title("📊 Dashboard de Custos Institucionais")

    # Verifica se as bases foram importadas
    if st.session_state["df_direto"] is None or st.session_state["df_indireto"] is None:
        st.warning("⚠️ Dados incompletos. Por favor, vá ao menu 'Importação de Dados' e carregue os dois arquivos antes de visualizar o dashboard.")
    
    else:
        # Recupera as bases da memória
        df_direto = st.session_state["df_direto"]
        df_indireto = st.session_state["df_indireto"]

        st.success("Bases conectadas com sucesso! O Dashboard será renderizado aqui.")
        
        # Só para testarmos se ele leu certinho:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Prévia - Custos Diretos**")
            st.dataframe(df_direto.head(), use_container_width=True)
        with col2:
            st.markdown("**Prévia - Custos Indiretos**")
            st.dataframe(df_indireto.head(), use_container_width=True)
            
        # (Nos próximos commits, colocaremos toda a lógica de filtros e gráficos aqui)
