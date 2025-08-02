import streamlit as st
import pandas as pd
import json
from datetime import datetime

# Configuração da página
st.set_page_config(
    page_title="Sistema de Classificação CONAB",
    layout="wide"
)

# Arquivo JSON para salvar os dados
JSON_FILE = 'candidatos_conab.json'
CARGOS_FILE = 'cargos.json'

# Configuração das matérias por tipo de cargo (CORRIGIDA CONFORME EDITAL)
MATERIAS_CONFIG = {
    "ANALISTA_COMUM": {
        "materias": ["lp", "nmrl", "nbi", "nbop", "gp", "ct", "nppl", "ce", "discursiva"],
        "labels": {
            "lp": "LÍNGUA PORTUGUESA",
            "nmrl": "NOÇÕES DE MATEMÁTICA E RACIOCÍNIO LÓGICO",
            "nbi": "NOÇÕES BÁSICAS DE INFORMÁTICA",
            "nbop": "NOÇÕES BÁSICAS DE ORÇAMENTO PÚBLICO",
            "gp": "GESTÃO DE PROJETOS",
            "ct": "CONHECIMENTOS TRANSVERSAIS",
            "nppl": "NOÇÕES DE POLÍTICAS PÚBLICAS E LEGISLAÇÃO APLICADA À CONAB",
            "ce": "CONHECIMENTOS ESPECÍFICOS",
            "discursiva": "PROVA DISCURSIVA"
        },
        "pesos": {"lp": 2, "nmrl": 1, "nbi": 1, "nbop": 1, "gp": 1, "ct": 1, "nppl": 2, "ce": 2, "discursiva": 1},
        "questoes": {"lp": 5, "nmrl": 4, "nbi": 4, "nbop": 4, "gp": 4, "ct": 4, "nppl": 5, "ce": 50, "discursiva": 1},
        "max_pontos": {"lp": 10, "nmrl": 4, "nbi": 4, "nbop": 4, "gp": 4, "ct": 4, "nppl": 10, "ce": 100, "discursiva": 60},
        "notas_minimas": {"basicos": 16, "ce": 50, "discursiva": 30},
        "total_maximo": 200 # Este valor não será mais usado no cálculo total
    },
    "ANALISTA_TI": {
        "materias": ["lp", "nmrl", "nbop", "gp", "ct", "nppl", "ce", "discursiva"],
        "labels": {
            "lp": "LÍNGUA PORTUGUESA",
            "nmrl": "NOÇÕES DE MATEMÁTICA E RACIOCÍNIO LÓGICO",
            "nbop": "NOÇÕES BÁSICAS DE ORÇAMENTO PÚBLICO",
            "gp": "GESTÃO DE PROJETOS",
            "ct": "CONHECIMENTOS TRANSVERSAIS",
            "nppl": "NOÇÕES DE POLÍTICAS PÚBLICAS E LEGISLAÇÃO APLICADA À CONAB",
            "ce": "CONHECIMENTOS ESPECÍFICOS",
            "discursiva": "PROVA DISCURSIVA"
        },
        "pesos": {"lp": 2, "nmrl": 1, "nbop": 1, "gp": 1, "ct": 1, "nppl": 2, "ce": 2, "discursiva": 1},
        "questoes": {"lp": 5, "nmrl": 5, "nbop": 5, "gp": 5, "ct": 5, "nppl": 5, "ce": 50, "discursiva": 1},
        "max_pontos": {"lp": 10, "nmrl": 5, "nbop": 5, "gp": 5, "ct": 5, "nppl": 10, "ce": 100, "discursiva": 60},
        "notas_minimas": {"basicos": 16, "ce": 50, "discursiva": 30},
        "total_maximo": 200 # Este valor não será mais usado no cálculo total
    },
    "ASSISTENTE_COMUM": {
        "materias": ["lp", "nmrl", "nbi", "ct", "nppl", "ce"],
        "labels": {
            "lp": "LÍNGUA PORTUGUESA",
            "nmrl": "NOÇÕES DE MATEMÁTICA E RACIOCÍNIO LÓGICO",
            "nbi": "NOÇÕES BÁSICAS DE INFORMÁTICA",
            "ct": "CONHECIMENTOS TRANSVERSAIS",
            "nppl": "NOÇÕES DE POLÍTICAS PÚBLICAS E LEGISLAÇÃO APLICADA À CONAB",
            "ce": "CONHECIMENTOS ESPECÍFICOS"
        },
        "pesos": {"lp": 2, "nmrl": 2, "nbi": 1, "ct": 1, "nppl": 1, "ce": 2},
        "questoes": {"lp": 14, "nmrl": 6, "nbi": 6, "ct": 7, "nppl": 7, "ce": 60},
        "max_pontos": {"lp": 28, "nmrl": 12, "nbi": 6, "ct": 7, "nppl": 7, "ce": 120},
        "notas_minimas": {"basicos": 24, "ce": 48},
        "total_maximo": 180 # Este valor não será mais usado no cálculo total
    },
    "ASSISTENTE_TI": {
        "materias": ["lp", "nmrl", "gp", "ct", "nppl", "ce"],
        "labels": {
            "lp": "LÍNGUA PORTUGUESA",
            "nmrl": "NOÇÕES DE MATEMÁTICA E RACIOCÍNIO LÓGICO",
            "gp": "GESTÃO DE PROJETOS",
            "ct": "CONHECIMENTOS TRANSVERSAIS",
            "nppl": "NOÇÕES DE POLÍTICAS PÚBLICAS E LEGISLAÇÃO APLICADA À CONAB",
            "ce": "CONHECIMENTOS ESPECÍFICOS"
        },
        "pesos": {"lp": 2, "nmrl": 2, "gp": 1, "ct": 1, "nppl": 1, "ce": 2},
        "questoes": {"lp": 14, "nmrl": 6, "gp": 6, "ct": 7, "nppl": 7, "ce": 60},
        "max_pontos": {"lp": 28, "nmrl": 12, "gp": 6, "ct": 7, "nppl": 7, "ce": 120},
        "notas_minimas": {"basicos": 24, "ce": 48},
        "total_maximo": 180 # Este valor não será mais usado no cálculo total
    }
}

# Função para carregar dados do JSON
def carregar_dados():
    try:
        with open(JSON_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

# Função para carregar cargos do JSON
def carregar_cargos():
    try:
        with open(CARGOS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        st.error(f"Arquivo {CARGOS_FILE} não encontrado. Crie o arquivo com os cargos disponíveis.")
        return {}

# Função para salvar dados no JSON
def salvar_dados(dados):
    with open(JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

# Função para verificar se candidato já existe
def candidato_existe(nome, candidatos):
    return any(c['nome'].lower() == nome.lower() for c in candidatos)

# Função para determinar tipo de cargo
# Corrigido o typo na condição para ASSISTENTE_TI
def determinar_tipo_cargo(nome_cargo):
    nome_upper = nome_cargo.upper()
    if "ANALISTA" in nome_upper and "TECNOLOGIA DA INFORMAÇÃO" in nome_upper:
        return "ANALISTA_TI"
    elif "ASSISTENTE" in nome_upper and "TI" in nome_upper: # Corrigido
        return "ASSISTENTE_TI"
    elif "ASSISTENTE" in nome_upper:
        return "ASSISTENTE_COMUM"
    else:
        return "ANALISTA_COMUM"

# Função para calcular nota total SEM pesos
def calcular_nota_total(notas, cargo_nome):
    # Esta função agora soma as notas diretamente, sem multiplicar pelos pesos
    total = 0
    for nota in notas.values():
        total += nota
    return total

# Função para verificar aprovação (mantém a lógica original dos pesos para verificar mínimos)
def verificar_aprovacao(notas, cargo_nome):
    tipo_cargo = determinar_tipo_cargo(cargo_nome)
    config = MATERIAS_CONFIG[tipo_cargo]
    # Verificar nota mínima em conhecimentos básicos (ainda usa pesos para verificação)
    nota_basicos = 0
    materias_basicas = [m for m in config["materias"] if m not in ["ce", "discursiva"]]
    for materia in materias_basicas:
        if materia in notas:
            nota_basicos += notas[materia] * config["pesos"][materia]
    aprovado_basicos = nota_basicos >= config["notas_minimas"]["basicos"]
    # Verificar nota mínima em conhecimentos específicos (ainda usa pesos para verificação)
    aprovado_ce = notas.get("ce", 0) * config["pesos"]["ce"] >= config["notas_minimas"]["ce"]
    # Verificar discursiva (apenas para nível superior) (ainda usa pesos para verificação)
    aprovado_discursiva = True
    if "discursiva" in config["materias"]:
        aprovado_discursiva = notas.get("discursiva", 0) * config["pesos"]["discursiva"] >= config["notas_minimas"]["discursiva"]
    return aprovado_basicos and aprovado_ce and aprovado_discursiva

# Inicializar dados
if 'candidatos' not in st.session_state:
    st.session_state.candidatos = carregar_dados()

# Carregar cargos
cargos = carregar_cargos()

# Navegação entre páginas
st.sidebar.title("Navegação")
pagina = st.sidebar.radio("Selecione a página:", ["Cadastro", "Classificação"])

if pagina == "Cadastro":
    st.title("Cadastro de Candidato")
    if not cargos:
        st.error("Nenhum cargo carregado. Verifique o arquivo cargos.json")
    else:
        # Primeiro, seleção do cargo FORA do formulário para reagir às mudanças
        st.subheader("Seleção do Cargo")
        opcoes_cargo = [f"{codigo} - {info['nome']}" for codigo, info in cargos.items()]
        cargo_selecionado = st.selectbox("Cargo:", opcoes_cargo, key="cargo_select")
        codigo_cargo = cargo_selecionado.split(" - ")[0] if cargo_selecionado else ""
        nome_cargo = cargos[codigo_cargo]['nome'] if codigo_cargo in cargos else ""
        # Determinar tipo de cargo e configuração
        tipo_cargo = determinar_tipo_cargo(nome_cargo)
        config = MATERIAS_CONFIG[tipo_cargo]
        # Mostrar informações do cargo selecionado
        # Atualizado para refletir que o total não é mais ponderado
        st.info(f"**Tipo de Cargo:** {tipo_cargo.replace('_', ' ')}")
        # Agora o formulário com as matérias dinâmicas
        with st.form("form_candidato"):
            nome_candidato = st.text_input("Nome do Candidato")
            st.subheader("Notas por Matéria")
            # Campos de nota baseados no tipo de cargo
            notas = {}
            for materia in config["materias"]:
                label = config["labels"][materia]
                # peso = config["pesos"][materia] # Peso não é mais usado para entrada ou exibição de pontos
                questoes = config["questoes"][materia]
                max_pontos = config["max_pontos"][materia]
                # --- REMOVIDO: col1, col2 = st.columns([3, 1]) ---
                # --- REMOVIDO: with col1: ---
                # Campo de nota sem a coluna de pontos
                notas[materia] = st.number_input(
                    f"{label}",
                    min_value=0,   # Valor mínimo inteiro
                    max_value=int(max_pontos), # Garantir que max_pontos também seja int
                    step=1,        # Passo inteiro - Restringe a entrada a inteiros
                    key=f"nota_{materia}_{tipo_cargo}",
                    help=f"Questões: {questoes} | Máximo: {max_pontos} pontos"
                )
                # --- REMOVIDO: with col2: ---
                # --- REMOVIDO: st.metric("Pontos", f"{pontos_ponderados:.1f}") ---
            cota = st.selectbox("Tipo de Cota:", ["AMPLA", "PDC", "PPP"])
            # Mostrar total calculado em tempo real (SEM pesos)
            total_temp = sum(notas.values()) # Soma direta das notas
            # Atualizado para mostrar o máximo possível sem pesos
            max_possivel = sum(config["max_pontos"][m] for m in config["materias"])
            st.markdown(f"**Total Calculado (sem pesos): {total_temp} / {max_possivel} pontos**")
            submitted = st.form_submit_button("Adicionar Candidato")
            if submitted:
                if not nome_candidato:
                    st.error("Digite o nome do candidato.")
                elif candidato_existe(nome_candidato, st.session_state.candidatos):
                    st.error("Este candidato já foi cadastrado.")
                else:
                    total_pontos = calcular_nota_total(notas, nome_cargo) # Chama a nova função
                    aprovado = verificar_aprovacao(notas, nome_cargo)
                    candidato = {
                        'nome': nome_candidato,
                        'cargo_codigo': codigo_cargo,
                        'cargo_nome': nome_cargo,
                        'tipo_cargo': tipo_cargo,
                        **notas,  # Adiciona todas as notas
                        'total': total_pontos, # Total sem pesos
                        'aprovado': aprovado,
                        'cota': cota,
                        'data_cadastro': datetime.now().strftime("%d/%m/%Y %H:%M")
                    }
                    st.session_state.candidatos.append(candidato)
                    salvar_dados(st.session_state.candidatos)
                    status = "✅ APROVADO" if aprovado else "❌ REPROVADO"
                    st.success(f"Candidato {nome_candidato} adicionado com sucesso!")
                    st.info(f"Total: {total_pontos} pontos | Status: {status}") # Exibe total sem decimais
                    st.rerun()

# --- MODIFICAÇÃO PRINCIPAL NA PÁGINA DE CLASSIFICAÇÃO ---
elif pagina == "Classificação":
    st.title("Classificação")
    if st.session_state.candidatos:
        # Criar DataFrame primeiro
        df = pd.DataFrame(st.session_state.candidatos)
        # Campo de pesquisa no topo
        st.subheader("Buscar Candidato")
        busca = st.text_input("Digite o nome do candidato para buscar:")
        if busca:
            resultado = df[df['nome'].str.contains(busca, case=False, na=False)]
            if not resultado.empty:
                st.write(f"Encontrado(s) {len(resultado)} candidato(s):")
                resultado_sorted = resultado.sort_values('total', ascending=False)
                # Para busca, manter colunas básicas
                colunas_busca = ['posicao', 'nome', 'cargo_nome', 'total', 'aprovado', 'cota']
                # Criar coluna de posição para o resultado da busca também
                resultado_sorted = resultado_sorted.reset_index(drop=True)
                resultado_sorted['posicao'] = range(1, len(resultado_sorted) + 1)
                resultado_display = resultado_sorted[colunas_busca].copy()
                resultado_display.columns = ['Posição', 'Nome', 'Cargo', 'Total', 'Aprovado', 'Cota']
                st.dataframe(resultado_display, use_container_width=True, hide_index=True)
            else:
                st.write("Candidato não encontrado.")
        st.markdown("---")
        # Filtros
        col1, col2, col3 = st.columns(3)
        with col1:
            # Filtro por cargo
            cargos_candidatos = list(set([c.get('cargo_codigo', 'SEM_CARGO') for c in st.session_state.candidatos if 'cargo_codigo' in c]))
            cargos_opcoes = ["Todos"] + [f"{codigo} - {cargos.get(codigo, {}).get('nome', 'Cargo não encontrado')}" for codigo in sorted(cargos_candidatos)]
            cargo_filtro = st.selectbox("Filtrar por Cargo:", cargos_opcoes)
        with col2:
            # Filtro por cota
            cota_filtro = st.selectbox("Filtrar por Cota:", ["Todas", "AMPLA", "PDC", "PPP"])
        with col3:
            # Filtro por aprovação
            aprovacao_filtro = st.selectbox("Filtrar por Status:", ["Todos", "Apenas Aprovados", "Apenas Reprovados"])
        # Aplicar filtros
        df_filtrado = df.copy()
        if cargo_filtro != "Todos":
            codigo_filtro = cargo_filtro.split(" - ")[0]
            df_filtrado = df_filtrado[df_filtrado.get('cargo_codigo', 'SEM_CARGO') == codigo_filtro]
        if cota_filtro != "Todas":
            df_filtrado = df_filtrado[df_filtrado['cota'] == cota_filtro]
        if aprovacao_filtro == "Apenas Aprovados":
            df_filtrado = df_filtrado[df_filtrado.get('aprovado', False) == True]
        elif aprovacao_filtro == "Apenas Reprovados":
            df_filtrado = df_filtrado[df_filtrado.get('aprovado', False) == False]
        if not df_filtrado.empty:
            # Ordenar por nota total
            df_sorted = df_filtrado.sort_values('total', ascending=False).reset_index(drop=True)
            df_sorted['posicao'] = range(1, len(df_sorted) + 1)
            # --- LÓGICA PARA EXIBIR MATÉRIAS RELEVANTES ---
            # Determinar quais matérias exibir com base no filtro de cargo
            materias_para_exibir = []
            if cargo_filtro != "Todos":
                # Se um cargo específico foi filtrado, usar as matérias desse cargo
                codigo_filtro = cargo_filtro.split(" - ")[0]
                nome_cargo_filtro = cargos.get(codigo_filtro, {}).get('nome', '')
                tipo_cargo_filtro = determinar_tipo_cargo(nome_cargo_filtro)
                materias_para_exibir = MATERIAS_CONFIG[tipo_cargo_filtro]["materias"]
            else:
                # Se não há filtro de cargo ("Todos"), exibir matérias de todos os cargos presentes no df_filtrado
                # Obter tipos de cargo únicos no dataframe filtrado
                tipos_cargo_unicos = df_sorted['tipo_cargo'].unique()
                # Unir todas as matérias desses tipos de cargo
                materias_para_exibir_set = set()
                for tipo in tipos_cargo_unicos:
                    if tipo in MATERIAS_CONFIG:
                        materias_para_exibir_set.update(MATERIAS_CONFIG[tipo]["materias"])
                # Ordenar as matérias de forma consistente (opcional)
                ordem_padrao = ['lp', 'nmrl', 'nbi', 'nbop', 'gp', 'ct', 'nppl', 'ce', 'discursiva']
                materias_para_exibir = [m for m in ordem_padrao if m in materias_para_exibir_set]
            # Preparar dados para exibição
            colunas_basicas = ['posicao', 'nome']
            if 'cargo_nome' in df_sorted.columns:
                colunas_basicas.append('cargo_nome')
            # Filtrar apenas as matérias que realmente existem no DataFrame (para evitar KeyError)
            materias_presentes_no_df = [m for m in materias_para_exibir if m in df_sorted.columns]
            colunas_exibir = colunas_basicas + materias_presentes_no_df + ['total', 'aprovado', 'cota']
            df_display = df_sorted[colunas_exibir].copy()
            # Renomear colunas
            nomes_colunas = ['Posição', 'Nome']
            if 'cargo_nome' in df_sorted.columns:
                nomes_colunas.append('Cargo')
            # Adicionar nomes das matérias
            nomes_materias = {
                'lp': 'LP', 'nmrl': 'NMRL', 'nbi': 'NBI', 'nbop': 'NBOP',
                'gp': 'GP', 'ct': 'CT', 'nppl': 'NPPL', 'ce': 'CE', 'discursiva': 'DISC'
            }
            for materia in materias_presentes_no_df:
                nomes_colunas.append(nomes_materias.get(materia, materia.upper()))
            nomes_colunas.extend(['Total', 'Aprovado', 'Cota'])
            df_display.columns = nomes_colunas
            # Exibir tabela
            st.dataframe(df_display, use_container_width=True, hide_index=True)
            # --- FIM DA MODIFICAÇÃO ---
        else:
            st.write("Nenhum candidato encontrado com os filtros aplicados.")
    else:
        st.write("Nenhum candidato cadastrado ainda.")
# --- FIM DA MODIFICAÇÃO ---
