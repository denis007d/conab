import streamlit as st
import pandas as pd

# Configuração da página
st.set_page_config(
    page_title="Portal de Convocação IBGE 2026",
    page_icon="🔍",
    layout="centered"
)

# Título do Portal
st.title("🔍 Portal de Consulta - Convocação IBGE 2026")
st.markdown("Consulte sua posição na fila de chamadas oficiais de forma simples e rápida.")
st.write("---")

# Função para carregar os dados
@st.cache_data
def carregar_dados():
    try:
        df = pd.read_csv('lista_convocacao_final_simplificada.csv')
        # Adiciona a ordem de chamada exata (posição da linha) dentro de cada cidade
        df['ordem_de_chamada'] = df.groupby(['estado', 'cidade']).cumcount() + 1
        return df
    except FileNotFoundError:
        return None

df = carregar_dados()

if df is None:
    st.error("❌ Arquivo 'lista_convocacao_final_simplificada.csv' não encontrado!")
    st.info("Certifique-se de rodar o algoritmo de convocação primeiro para gerar a planilha na mesma pasta deste site.")
else:
    # --- SEÇÃO 1: CONSULTA INDIVIDUAL ---
    st.subheader("👤 Consulte sua Situação")
    termo_busca = st.text_input("Digite seu Nome ou Número de Inscrição:", placeholder="Ex: Mateus Dos Santos ou 466036401").strip()

    if termo_busca:
        # Garante a busca textual mesmo se a inscrição for tratada como número
        df['inscricao_str'] = df['inscricao'].astype(str)
        
        # Realiza o filtro
        resultados = df[
            df['nome'].str.contains(termo_busca, case=False, na=False) |
            df['inscricao_str'].str.contains(termo_busca, case=False, na=False)
        ]

        if not resultados.empty:
            st.success(f"Encontrado(s) {len(resultados)} registro(s)!")
            
            for _, candidato in resultados.iterrows():
                with st.container():
                    st.markdown(f"### **{candidato['nome']}**")
                    
                    # Painel visual com os dados cruciais do candidato
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"📍 **Localidade:** {candidato['estado']} - {candidato['cidade']}")
                        st.markdown(f"📝 **Inscrição:** {candidato['inscricao']}")
                        st.markdown(f"🎯 **Nota Final:** {candidato['nota_final']}")
                    with col2:
                        st.markdown(f"🏆 **Posição na Fila Geral da Cidade:** `{candidato['ordem_de_chamada']}º a ser chamado`")
                        st.markdown(f"📊 **Classif. Ampla (AC):** {candidato['classificacao_geral_ac']}")
                        st.markdown(f"🏅 **Classif. na Cota ({candidato['cota_inscricao']}):** {candidato['classificacao_na_cota']}")
                    
                    # Alerta destacado sobre o tipo de vaga ocupada
                    st.info(f"💡 **Status atual da vaga:** Ocupando vaga reservada para **{candidato['vaga_ocupada']}**")
                    st.markdown("---")
        else:
            st.warning("⚠️ Nenhum candidato encontrado com este Nome ou Inscrição. Verifique a grafia.")

    # --- SEÇÃO 2: VISUALIZAÇÃO POR MUNICÍPIO ---
    st.subheader("📁 Lista de Convocação Completa por Região")
    
    col_est, col_cid = st.columns(2)
    with col_est:
        estados_disponiveis = sorted(df['estado'].unique())
        estado_sel = st.selectbox("Selecione o Estado:", estados_disponiveis)
    with col_cid:
        cidades_disponiveis = sorted(df[df['estado'] == estado_sel]['cidade'].unique())
        cidade_sel = st.selectbox("Selecione a Cidade:", cidades_disponiveis)

    # Filtra a tabela do município selecionado
    df_filtrado = df[(df['estado'] == estado_sel) & (df['cidade'] == city_sel if 'city_sel' in locals() else df['cidade'] == cidade_sel)].copy()
    
    # Organiza colunas para exibição na tabela
    tabela_exibicao = df_filtrado[[
        'ordem_de_chamada', 'nome', 'nota_final', 
        'classificacao_geral_ac', 'classificacao_na_cota', 'vaga_ocupada'
    ]]
    
    tabela_exibicao.columns = [
        'Ordem de Convocação', 'Nome do Candidato', 'Nota Final', 
        'Classif. Geral AC', 'Classif. Cota', 'Vaga Ocupada'
    ]

    st.dataframe(
        tabela_exibicao, 
        use_container_width=True, 
        hide_index=True
    )
