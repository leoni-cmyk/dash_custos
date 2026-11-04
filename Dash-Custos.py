import streamlit as st
import pandas as pd
import plotly.express as px

# 1. Configuração inicial da página
st.set_page_config(page_title="Dashboard de Custos", layout="wide")
st.title("📊 Gestão de Custos Institucionais")
st.markdown("Faça o upload da base Excel exportada do sistema para atualizar os indicadores.")

# 2. Upload do Arquivo
arquivo_excel = st.file_uploader("Selecione a base de custos (.xlsx)", type=["xlsx"])

if arquivo_excel:
    # Leitura dos dados
    df = pd.read_excel(arquivo_excel)
    
    # Tratamento básico de dados (garantir que Período é texto)
    if "Período" in df.columns:
        df["Período"] = df["Período"].astype(str)
        
    st.success("Base carregada com sucesso!")

    # 3. Filtros na Barra Lateral
    st.sidebar.header("Filtros de Análise")
    
    # Criar filtros dinamicamente se as colunas existirem
    if all(col in df.columns for col in ["Período", "Segmento", "Classificação"]):
        periodos = st.sidebar.multiselect("Período", df["Período"].unique(), default=df["Período"].unique())
        segmentos = st.sidebar.multiselect("Segmento", df["Segmento"].unique(), default=df["Segmento"].unique())
        classificacoes = st.sidebar.multiselect("Classificação", df["Classificação"].unique(), default=df["Classificação"].unique())

        # Aplicar filtros
        df_filtrado = df[
            (df["Período"].isin(periodos)) &
            (df["Segmento"].isin(segmentos)) &
            (df["Classificação"].isin(classificacoes))
        ]
    else:
        st.sidebar.warning("As colunas 'Período', 'Segmento' e 'Classificação' não foram encontradas na base.")
        df_filtrado = df

    # 4. Exibição de Dados Básica (Para o 1º teste)
    if "Valor" in df_filtrado.columns:
        total = df_filtrado["Valor"].sum()
        st.metric("Custo Total (Filtrado)", f"R$ {total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    
    st.subheader("Pré-visualização da Base")
    st.dataframe(df_filtrado.head(100), use_container_width=True)

else:
    st.info("Aguardando arquivo de dados...")