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
st.sidebar.image("logo_feso.png", use_container_width=True)
st.sidebar.title("Navegação")

# Ordem invertida: Dashboard vem primeiro
menu = st.sidebar.radio(
    "Selecione a página:",
    ["📊 Dashboard Principal", "📥 Gerenciar Dados"]
)

# ==========================================
# TELA 1: DASHBOARD PRINCIPAL
# ==========================================
if menu == "📊 Dashboard Principal":  # Ajustado de elif para if
    st.title("Dashboard de Custos 2026")

    if st.session_state["df_direto"] is None or st.session_state["df_indireto"] is None:
        st.warning("⚠️ Vá ao menu 'Gerenciar Dados' e carregue os dois arquivos para visualizar o dashboard.")
    else:
        # Prepara e une as bases para os filtros
        df_dir = st.session_state["df_direto"].copy()
        df_dir["Origem_Dado"] = "Direto"
        
        df_ind = st.session_state["df_indireto"].copy()
        df_ind["Origem_Dado"] = "Rateio Recebido"
        
        df_full = pd.concat([df_dir, df_ind], ignore_index=True)

        # 1. Filtros estilo "Pílulas"
        col_f1, col_f2, col_f3 = st.columns([1, 2, 2])
        with col_f1:
            segmentos = st.multiselect("Segmento", sorted(df_full["Segmento"].dropna().unique()), default=df_full["Segmento"].dropna().unique())
        with col_f2:
            periodos = st.multiselect("Período", sorted(df_full["Período"].dropna().unique()), default=df_full["Período"].dropna().unique())
        with col_f3:
            classificacoes = st.multiselect("Classificação", sorted(df_full["Classificação"].dropna().unique()), default=df_full["Classificação"].dropna().unique())

        # Aplica filtros globais
        df_filtrado = df_full[
            (df_full["Segmento"].isin(segmentos)) & 
            (df_full["Período"].isin(periodos)) & 
            (df_full["Classificação"].isin(classificacoes))
        ]

        # 2. KPIs de Topo
        custo_dir = df_filtrado[df_filtrado["Origem_Dado"] == "Direto"]["Valor"].sum()
        custo_ind = df_filtrado[df_filtrado["Origem_Dado"] == "Rateio Recebido"]["Valor"].sum()
        custo_total = custo_dir + custo_ind
        perc_indireto = (custo_ind / custo_total * 100) if custo_total > 0 else 0
        
        # Placeholder para "Rateado p/ outros" até termos a base de origem-destino
        rateado_outros = 0.00 

        st.markdown("---")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Custo direto", f"R$ {custo_dir:,.0f}".replace(",", "X").replace(".", ",").replace("X", "."))
        c2.metric("Rateio recebido", f"R$ {custo_ind:,.0f}".replace(",", "X").replace(".", ",").replace("X", "."))
        c3.metric("Custo total", f"R$ {custo_total:,.0f}".replace(",", "X").replace(".", ",").replace("X", "."))
        c4.metric("% indireto", f"{perc_indireto:.1f}%".replace(".", ","))
        c5.metric("Rateado p/ outros", f"R$ {rateado_outros:,.0f}".replace(",", "X").replace(".", ",").replace("X", "."))
        st.markdown("---")

        # 3. Visões Estratégicas
        col_view1, col_view2 = st.columns([1, 1])
        
        with col_view1:
            st.markdown("### Visão por segmento")
            # Tabela dinâmica replicando o HTML
            df_seg = df_filtrado.groupby(["Segmento", "Origem_Dado"])["Valor"].sum().unstack(fill_value=0).reset_index()
            # Garante que as colunas existam mesmo se o filtro excluir uma delas
            if "Direto" not in df_seg.columns: df_seg["Direto"] = 0
            if "Rateio Recebido" not in df_seg.columns: df_seg["Rateio Recebido"] = 0
            
            df_seg["Total"] = df_seg["Direto"] + df_seg["Rateio Recebido"]
            df_seg["% indireto"] = (df_seg["Rateio Recebido"] / df_seg["Total"]) * 100
            
            # Formatação
            df_seg_display = df_seg.copy()
            for col in ["Direto", "Rateio Recebido", "Total"]:
                df_seg_display[col] = df_seg_display[col].apply(lambda x: f"R$ {x:,.0f}".replace(",", "X").replace(".", ",").replace("X", "."))
            df_seg_display["% indireto"] = df_seg_display["% indireto"].apply(lambda x: f"{x:.1f}%".replace(".", ","))
            
            st.dataframe(df_seg_display, use_container_width=True, hide_index=True)

        with col_view2:
            st.markdown("### Evolução mensal")
            df_evolucao = df_filtrado.groupby(["Período", "Origem_Dado"])["Valor"].sum().reset_index()
            
            # Gráfico de barras empilhadas
            fig_bar = px.bar(
                df_evolucao, 
                x="Período", 
                y="Valor", 
                color="Origem_Dado", 
                barmode="stack",
                color_discrete_map={"Direto": "#2f6fed", "Rateio Recebido": "#f79c42"}
            )
            fig_bar.update_layout(
                xaxis_title="", 
                yaxis_title="", 
                legend_title="",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        st.markdown("---")
        
        # 4. Busca e Detalhamento de Centro de Custo
        st.markdown("### Centros de Custo — Busca de Detalhes")
        cc_selecionado = st.selectbox("Buscar centro de custo...", ["Selecione..."] + sorted(df_filtrado["Centro de Custo"].dropna().unique()))
        
        if cc_selecionado != "Selecione...":
            df_cc = df_filtrado[df_filtrado["Centro de Custo"] == cc_selecionado]
            st.dataframe(df_cc, use_container_width=True)
            st.info("💡 Quando integrarmos a base de Rateios com Origem e Destino, renderizaremos aqui as tabelas de 'Rateio Recebido de' e 'Rateado para'.")


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
