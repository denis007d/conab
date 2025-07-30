#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Detector Simples de Marcações - Gabarito CONAB
Versão Corrigida - Apenas Detecção e Resultado

Funcionalidades:
- Detecção automática de bolinhas marcadas
- Exibição dos resultados por questão
- Interface web minimalista

Autor: Protheus AI
"""

import streamlit as st
import cv2
import numpy as np
import tempfile
import os
from typing import Dict, List, Tuple, Optional
from PIL import Image, ImageDraw
import io
import json
from collections import defaultdict, Counter
import pandas as pd
from datetime import datetime
import uuid

# Carregar o JSON com tratamento de erro
def carregar_dados_gabarito():
    """Carrega os dados do gabarito oficial"""
    try:
        with open('gabarito_oficial.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        st.error("❌ Arquivo 'gabarito_oficial.json' não encontrado!")
        st.info("Certifique-se de que o arquivo está no diretório do projeto.")
        return {}
    except json.JSONDecodeError:
        st.error("❌ Erro ao decodificar o arquivo JSON!")
        return {}
    except Exception as e:
        st.error(f"❌ Erro ao carregar gabarito: {e}")
        return {}

# ============================================================================
# CLASSE PRINCIPAL DE DETECÇÃO
# ============================================================================

class DetectorMarcacoes:
    """Detector avançado de marcações em gabaritos usando múltiplas técnicas de CV"""
    
    def __init__(self):
        # Configurações para detecção CONAB (2338x1653 pixels)
        self.config = {
            'largura_esperada': 2338,
            'altura_esperada': 1653,
            'regioes_questoes': {
                'coluna1': {'x': 842, 'y': 580, 'w': 218, 'h': 860},
                'coluna2': {'x': 1125, 'y': 580, 'w': 215, 'h': 860},
                'coluna3': {'x': 1400, 'y': 580, 'w': 220, 'h': 860},
                'coluna4': {'x': 1683, 'y': 580, 'w': 217, 'h': 860},
                'coluna5': {'x': 1960, 'y': 580, 'w': 210, 'h': 860}
            },
            'espacamento_questoes': 44,  # Espaçamento vertical entre questões
            'espacamento_alternativas': 43,  # Espaçamento horizontal entre alternativas
            'offset_primeira_questao': 10,  # Offset da primeira questão
            'total_questoes': 60  # Padrão
        }
        
        # Parâmetros do detector de bolinhas pretas
        self.min_radius = 8
        self.max_radius = 14
        self.param1 = 50
        self.param2 = 20
        self.min_dist = 20
        self.darkness_threshold = 120
        self.circularity_threshold = 0.6
        
        # Pontos fixos de referência para algoritmo de vetor de distância
        self.pontos_referencia = self._calcular_pontos_referencia()
    
    def preprocess_image(self, image: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Pré-processamento da imagem para melhorar a detecção"""
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        # Aplicar filtro Gaussian para reduzir ruído
        blurred = cv2.GaussianBlur(gray, (5, 5), 1)
        
        # Equalização de histograma adaptativa
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(blurred)
        
        return gray, enhanced
    
    def detect_circles_in_region(self, image: np.ndarray, x: int, y: int, w: int, h: int) -> List[Tuple[int, int, int]]:
        """Detecta círculos em uma região específica da imagem"""
        # Extrai região de interesse
        roi = image[y:y+h, x:x+w]
        
        # Detecta círculos usando HoughCircles
        circles = cv2.HoughCircles(
            roi,
            cv2.HOUGH_GRADIENT,
            dp=1,
            minDist=self.min_dist,
            param1=self.param1,
            param2=self.param2,
            minRadius=self.min_radius,
            maxRadius=self.max_radius
        )
        
        detected_circles = []
        if circles is not None:
            circles = np.round(circles[0, :]).astype("int")
            for (cx, cy, r) in circles:
                # Converte coordenadas para imagem completa
                abs_x = x + cx
                abs_y = y + cy
                
                # Valida se é uma bolinha preta
                if self.validate_black_circle(image, abs_x, abs_y, r):
                    detected_circles.append((abs_x, abs_y, r))
        
        return detected_circles
    
    def validate_black_circle(self, image: np.ndarray, x: int, y: int, radius: int) -> bool:
        """Valida se o círculo detectado é realmente uma bolinha preta"""
        # Criar máscara circular
        mask = np.zeros(image.shape[:2], dtype=np.uint8)
        cv2.circle(mask, (x, y), radius, 255, -1)
        
        # Calcular intensidade média dentro do círculo
        mean_intensity = cv2.mean(image, mask=mask)[0]
        
        # Verificar se é suficientemente escura
        return mean_intensity < self.darkness_threshold
    
    def _calcular_pontos_referencia(self) -> Dict[str, List[Tuple[int, int]]]:
        """Calcula pontos fixos de referência para cada questão e alternativa"""
        pontos = {'questoes': [], 'alternativas': {}}
        
        # Para cada coluna, calcula os pontos de referência das questões
        for col_idx, (nome_coluna, regiao) in enumerate(self.config['regioes_questoes'].items()):
            x_base = regiao['x']
            y_base = regiao['y'] + self.config['offset_primeira_questao']
            
            # Calcula pontos para cada questão na coluna (máximo 25 questões por coluna)
            for q in range(25):
                y_questao = y_base + (q * self.config['espacamento_questoes'])
                
                # Ponto de referência da questão (centro da linha)
                ponto_questao = (x_base + regiao['w'] // 2, y_questao)
                pontos['questoes'].append({
                    'ponto': ponto_questao,
                    'coluna': col_idx,
                    'questao_na_coluna': q
                })
                
                # Pontos de referência das alternativas A, B, C, D, E
                for alt_idx, alternativa in enumerate(['A', 'B', 'C', 'D', 'E']):
                    x_alternativa = x_base + (alt_idx * self.config['espacamento_alternativas'])
                    ponto_alternativa = (x_alternativa, y_questao)
                    
                    chave = f"{col_idx}_{q}_{alternativa}"
                    pontos['alternativas'][chave] = {
                        'ponto': ponto_alternativa,
                        'coluna': col_idx,
                        'questao_na_coluna': q,
                        'alternativa': alternativa
                    }
        
        return pontos
    
    def _calcular_distancia_euclidiana(self, p1: Tuple[int, int], p2: Tuple[int, int]) -> float:
        """Calcula distância euclidiana entre dois pontos"""
        return np.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)
    
    def map_circles_to_answers(self, circles: List[Tuple[int, int, int]], total_questoes: int) -> Dict[int, str]:
        """Mapeia círculos detectados usando algoritmo de vetor de distância"""
        marcacoes_detectadas = {}
        
        # Calcula distribuição de questões por coluna
        questoes_por_coluna = total_questoes // 5
        resto = total_questoes % 5
        
        for circle_x, circle_y, circle_r in circles:
            ponto_circulo = (circle_x, circle_y)
            
            # Encontra a alternativa mais próxima usando vetor de distância
            menor_distancia = float('inf')
            melhor_match = None
            
            for chave, ref_data in self.pontos_referencia['alternativas'].items():
                ponto_ref = ref_data['ponto']
                distancia = self._calcular_distancia_euclidiana(ponto_circulo, ponto_ref)
                
                # Verifica se está dentro de um raio aceitável (tolerância)
                if distancia < menor_distancia and distancia <= 30:  # 30 pixels de tolerância
                    coluna = ref_data['coluna']
                    questao_na_coluna = ref_data['questao_na_coluna']
                    
                    # Calcula quantas questões esta coluna deve ter
                    questoes_nesta_coluna = questoes_por_coluna + (1 if coluna < resto else 0)
                    
                    # Verifica se a questão está dentro do limite da coluna
                    if questao_na_coluna < questoes_nesta_coluna:
                        # Calcula número absoluto da questão
                        questao_numero = (coluna * questoes_por_coluna) + questao_na_coluna + 1
                        
                        # Ajusta para colunas extras quando há resto
                        if coluna > 0:
                            questao_numero += min(coluna, resto)
                        
                        if questao_numero <= total_questoes:
                            menor_distancia = distancia
                            melhor_match = {
                                'questao': questao_numero,
                                'alternativa': ref_data['alternativa'],
                                'distancia': distancia
                            }
            
            # Adiciona a melhor correspondência encontrada
            if melhor_match and melhor_match['questao'] not in marcacoes_detectadas:
                marcacoes_detectadas[melhor_match['questao']] = melhor_match['alternativa']
        
        return marcacoes_detectadas
    
    def detectar_marcacoes(self, caminho_imagem: str, total_questoes: int = 60) -> Dict[int, str]:
        """Detecta marcações na imagem usando técnicas avançadas de CV"""
        try:
            # Carrega a imagem com máxima qualidade
            img = cv2.imread(caminho_imagem, cv2.IMREAD_COLOR)
            if img is None:
                raise ValueError("Não foi possível carregar a imagem")
            
            # Redimensiona se necessário usando interpolação de alta qualidade
            altura, largura = img.shape[:2]
            if largura != self.config['largura_esperada'] or altura != self.config['altura_esperada']:
                # Usa INTER_LANCZOS4 para máxima qualidade no redimensionamento
                img = cv2.resize(img, (self.config['largura_esperada'], self.config['altura_esperada']), 
                                interpolation=cv2.INTER_LANCZOS4)
            
            # Pré-processamento
            gray, enhanced = self.preprocess_image(img)
            
            # Detecta círculos em cada coluna
            all_circles = []
            
            for nome_coluna, regiao in self.config['regioes_questoes'].items():
                x, y, w, h = regiao['x'], regiao['y'], regiao['w'], regiao['h']
                circles_in_region = self.detect_circles_in_region(enhanced, x, y, w, h)
                all_circles.extend(circles_in_region)
            
            # Mapeia círculos para questões e alternativas
            marcacoes_detectadas = self.map_circles_to_answers(all_circles, total_questoes)
            
            return marcacoes_detectadas
            
        except Exception as e:
            st.error(f"Erro na detecção: {e}")
            return {}

# ============================================================================
# FUNÇÕES AUXILIARES
# ============================================================================

def calcular_nota_conab(questoes_ordenadas, cargo_selecionado, dados):
    """
    Calcula a nota baseada nas regras específicas do concurso CONAB
    Compara as respostas detectadas com o gabarito oficial
    """
    # Definir estruturas de prova por tipo de cargo
    estruturas_prova = {
        # Nível Superior (exceto TI)
        'superior_geral': {
            'conhecimentos_basicos': {
                'lingua_portuguesa': {'questoes': list(range(1, 6)), 'peso': 2},
                'matematica_raciocinio': {'questoes': list(range(6, 10)), 'peso': 1},
                'informatica': {'questoes': list(range(10, 14)), 'peso': 1},
                'orcamento_publico': {'questoes': list(range(14, 18)), 'peso': 1},
                'gestao_projetos': {'questoes': list(range(18, 22)), 'peso': 1},
                'conhecimentos_transversais': {'questoes': list(range(22, 26)), 'peso': 1},
                'politicas_publicas': {'questoes': list(range(26, 31)), 'peso': 2}
            },
            'conhecimentos_especificos': {
                'especificos': {'questoes': list(range(31, 81)), 'peso': 2}
            },
            'notas_minimas': {'basicos': 16, 'especificos': 50}
        },
        # Nível Superior - TI
        'superior_ti': {
            'conhecimentos_basicos': {
                'lingua_portuguesa': {'questoes': list(range(1, 6)), 'peso': 2},
                'matematica_raciocinio': {'questoes': list(range(6, 11)), 'peso': 1},
                'orcamento_publico': {'questoes': list(range(11, 16)), 'peso': 1},
                'gestao_projetos': {'questoes': list(range(16, 21)), 'peso': 1},
                'conhecimentos_transversais': {'questoes': list(range(21, 26)), 'peso': 1},
                'politicas_publicas': {'questoes': list(range(26, 31)), 'peso': 2}
            },
            'conhecimentos_especificos': {
                'especificos': {'questoes': list(range(31, 81)), 'peso': 2}
            },
            'notas_minimas': {'basicos': 16, 'especificos': 50}
        },
        # Nível Médio (exceto TI)
        'medio_geral': {
            'conhecimentos_basicos': {
                'lingua_portuguesa': {'questoes': list(range(1, 15)), 'peso': 2},
                'matematica_raciocinio': {'questoes': list(range(15, 21)), 'peso': 2},
                'informatica': {'questoes': list(range(21, 27)), 'peso': 1},
                'conhecimentos_transversais': {'questoes': list(range(27, 34)), 'peso': 1},
                'politicas_publicas': {'questoes': list(range(34, 41)), 'peso': 1}
            },
            'conhecimentos_especificos': {
                'especificos': {'questoes': list(range(41, 101)), 'peso': 2}
            },
            'notas_minimas': {'basicos': 24, 'especificos': 48}
        },
        # Nível Médio - TI
        'medio_ti': {
            'conhecimentos_basicos': {
                'lingua_portuguesa': {'questoes': list(range(1, 15)), 'peso': 2},
                'matematica_raciocinio': {'questoes': list(range(15, 21)), 'peso': 2},
                'gestao_projetos': {'questoes': list(range(21, 27)), 'peso': 1},
                'conhecimentos_transversais': {'questoes': list(range(27, 34)), 'peso': 1},
                'politicas_publicas': {'questoes': list(range(34, 41)), 'peso': 1}
            },
            'conhecimentos_especificos': {
                'especificos': {'questoes': list(range(41, 101)), 'peso': 2}
            },
            'notas_minimas': {'basicos': 24, 'especificos': 48}
        }
    }
    
    # Determinar tipo de cargo baseado no nome
    nome_cargo = dados[cargo_selecionado]['nome'].lower()
    
    if 'analista' in nome_cargo:
        if 'tecnologia' in nome_cargo or 'informação' in nome_cargo:
            estrutura = estruturas_prova['superior_ti']
            tipo_cargo = 'Nível Superior - Analista de TI'
        else:
            estrutura = estruturas_prova['superior_geral']
            tipo_cargo = 'Nível Superior - Analista'
    else:
        if 'tecnologia' in nome_cargo or 'informação' in nome_cargo:
            estrutura = estruturas_prova['medio_ti']
            tipo_cargo = 'Nível Médio - Assistente de TI'
        else:
            estrutura = estruturas_prova['medio_geral']
            tipo_cargo = 'Nível Médio - Assistente'
    
    # Obter gabarito oficial
    gabarito_oficial = None
    if dados and cargo_selecionado in dados:
        provas = dados[cargo_selecionado].get('provas', {})
        if provas:
            primeira_prova = list(provas.keys())[0]
            gabarito_oficial = provas[primeira_prova]
    
    # Calcular pontuações por área
    resultados = {
        'tipo_cargo': tipo_cargo,
        'conhecimentos_basicos': {},
        'conhecimentos_especificos': {},
        'totais': {},
        'aprovacao': {}
    }
    
    # Calcular conhecimentos básicos
    total_basicos = 0
    for materia, config in estrutura['conhecimentos_basicos'].items():
        acertos = 0
        total_questoes = len(config['questoes'])
        
        for questao in config['questoes']:
            resposta_candidato = questoes_ordenadas.get(questao, 'Não respondida')
            
            # Comparar com gabarito oficial se disponível
            if gabarito_oficial:
                resposta_oficial = gabarito_oficial.get(str(questao), '')
                # Questões anuladas são consideradas corretas para todos e recebem peso
                if resposta_oficial == "Anulada":
                    acertos += 1
                elif resposta_candidato != 'Não respondida' and resposta_candidato == resposta_oficial:
                    acertos += 1
            elif resposta_candidato != 'Não respondida' and not gabarito_oficial:
                # Fallback: assumir correto se foi detectada (modo compatibilidade)
                acertos += 1
        
        pontos = acertos * config['peso']
        total_basicos += pontos
        
        resultados['conhecimentos_basicos'][materia] = {
            'acertos': acertos,
            'total_questoes': total_questoes,
            'peso': config['peso'],
            'pontos': pontos,
            'percentual': (acertos / total_questoes) * 100 if total_questoes > 0 else 0
        }
    
    # Calcular conhecimentos específicos
    total_especificos = 0
    for materia, config in estrutura['conhecimentos_especificos'].items():
        acertos = 0
        total_questoes = len(config['questoes'])
        
        for questao in config['questoes']:
            resposta_candidato = questoes_ordenadas.get(questao, 'Não respondida')
            
            # Comparar com gabarito oficial se disponível
            if gabarito_oficial:
                resposta_oficial = gabarito_oficial.get(str(questao), '')
                # Questões anuladas são consideradas corretas para todos e recebem peso
                if resposta_oficial == "Anulada":
                    acertos += 1
                elif resposta_candidato != 'Não respondida' and resposta_candidato == resposta_oficial:
                    acertos += 1
            elif resposta_candidato != 'Não respondida' and not gabarito_oficial:
                # Fallback: assumir correto se foi detectada (modo compatibilidade)
                acertos += 1
        
        pontos = acertos * config['peso']
        total_especificos += pontos
        
        resultados['conhecimentos_especificos'][materia] = {
            'acertos': acertos,
            'total_questoes': total_questoes,
            'peso': config['peso'],
            'pontos': pontos,
            'percentual': (acertos / total_questoes) * 100 if total_questoes > 0 else 0
        }
    
    # Totais e aprovação
    resultados['totais'] = {
        'conhecimentos_basicos': total_basicos,
        'conhecimentos_especificos': total_especificos,
        'total_geral': total_basicos + total_especificos
    }
    
    resultados['aprovacao'] = {
        'basicos_aprovado': total_basicos >= estrutura['notas_minimas']['basicos'],
        'especificos_aprovado': total_especificos >= estrutura['notas_minimas']['especificos'],
        'aprovado_geral': (total_basicos >= estrutura['notas_minimas']['basicos'] and 
                          total_especificos >= estrutura['notas_minimas']['especificos']),
        'nota_minima_basicos': estrutura['notas_minimas']['basicos'],
        'nota_minima_especificos': estrutura['notas_minimas']['especificos']
    }
    
    return resultados

def salvar_resultado_candidato(nome_candidato, cargo, modalidade, resultado_conab, questoes_ordenadas):
    """
    Salva o resultado de um candidato no sistema de classificação
    """
    # Arquivo para armazenar os resultados dos candidatos
    arquivo_resultados = 'resultados_candidatos.json'
    
    # Carregar resultados existentes ou criar novo arquivo
    try:
        with open(arquivo_resultados, 'r', encoding='utf-8') as f:
            resultados = json.load(f)
    except FileNotFoundError:
        resultados = []
    
    # Criar registro do candidato
    registro_candidato = {
        'id': str(uuid.uuid4()),
        'nome': nome_candidato,
        'cargo': cargo,
        'modalidade': modalidade,
        'data_analise': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'pontuacao': {
            'conhecimentos_basicos': resultado_conab['totais']['conhecimentos_basicos'],
            'conhecimentos_especificos': resultado_conab['totais']['conhecimentos_especificos'],
            'total': resultado_conab['totais']['total_geral']
        },
        'aprovacao': {
            'aprovado_basicos': resultado_conab['aprovacao']['basicos_aprovado'],
            'aprovado_especificos': resultado_conab['aprovacao']['especificos_aprovado'],
            'aprovado_geral': resultado_conab['aprovacao']['aprovado_geral']
        },
        'detalhes_materias': {
            'conhecimentos_basicos': resultado_conab['conhecimentos_basicos'],
            'conhecimentos_especificos': resultado_conab['conhecimentos_especificos']
        },
        'respostas': questoes_ordenadas
    }
    
    # Verificar se candidato já existe (mesmo nome e cargo)
    candidato_existente = None
    for i, candidato in enumerate(resultados):
        if candidato['nome'] == nome_candidato and candidato['cargo'] == cargo:
            candidato_existente = i
            break
    
    if candidato_existente is not None:
        # Atualizar registro existente
        resultados[candidato_existente] = registro_candidato
    else:
        # Adicionar novo registro
        resultados.append(registro_candidato)
    
    # Salvar arquivo atualizado
    with open(arquivo_resultados, 'w', encoding='utf-8') as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)
    
    return registro_candidato['id']

def carregar_resultados_candidatos():
    """
    Carrega todos os resultados dos candidatos
    """
    arquivo_resultados = 'resultados_candidatos.json'
    try:
        with open(arquivo_resultados, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def gerar_classificacao_por_modalidade(cargo_filtro=None):
    """
    Gera classificação dos candidatos por modalidade (Ampla, PCD, PPP)
    """
    resultados = carregar_resultados_candidatos()
    
    # Filtrar por cargo se especificado
    if cargo_filtro:
        resultados = [r for r in resultados if r['cargo'] == cargo_filtro]
    
    # Separar por modalidade
    classificacoes = {
        'Ampla Concorrência': [],
        'PCD': [],
        'PPP': []
    }
    
    for resultado in resultados:
        modalidade = resultado['modalidade']
        if modalidade in classificacoes:
            classificacoes[modalidade].append(resultado)
    
    # Ordenar cada modalidade por pontuação total (decrescente)
    for modalidade in classificacoes:
        classificacoes[modalidade].sort(
            key=lambda x: x['pontuacao']['total'], 
            reverse=True
        )
        
        # Adicionar posição no ranking
        for i, candidato in enumerate(classificacoes[modalidade]):
            candidato['posicao'] = i + 1
    
    return classificacoes

def salvar_classificacao_json(cargo_filtro=None):
    """
    Salva a classificação completa em arquivo JSON
    """
    classificacoes = gerar_classificacao_por_modalidade(cargo_filtro)
    
    # Preparar dados para salvamento
    dados_classificacao = {
        'data_geracao': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'cargo_filtro': cargo_filtro if cargo_filtro else 'Todos os Cargos',
        'total_candidatos': sum(len(candidatos) for candidatos in classificacoes.values()),
        'classificacoes': {}
    }
    
    # Processar cada modalidade
    for modalidade, candidatos in classificacoes.items():
        if candidatos:  # Só inclui modalidades com candidatos
            dados_classificacao['classificacoes'][modalidade] = {
                'total_candidatos': len(candidatos),
                'candidatos_aprovados': len([c for c in candidatos if c['aprovacao']['aprovado_geral']]),
                'media_pontuacao': sum(c['pontuacao']['total'] for c in candidatos) / len(candidatos),
                'candidatos': []
            }
            
            # Adicionar dados de cada candidato
            for candidato in candidatos:
                dados_candidato = {
                    'posicao': candidato['posicao'],
                    'nome': candidato['nome'],
                    'cargo': candidato['cargo'],
                    'pontuacao': {
                        'conhecimentos_basicos': candidato['pontuacao']['conhecimentos_basicos'],
                        'conhecimentos_especificos': candidato['pontuacao']['conhecimentos_especificos'],
                        'total': candidato['pontuacao']['total']
                    },
                    'aprovacao': {
                        'aprovado_basicos': candidato['aprovacao']['aprovado_basicos'],
                        'aprovado_especificos': candidato['aprovacao']['aprovado_especificos'],
                        'aprovado_geral': candidato['aprovacao']['aprovado_geral']
                    },
                    'data_analise': candidato['data_analise']
                }
                dados_classificacao['classificacoes'][modalidade]['candidatos'].append(dados_candidato)
    
    # Salvar arquivo JSON
    nome_arquivo = f"classificacao_conab_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    try:
        with open(nome_arquivo, 'w', encoding='utf-8') as f:
            json.dump(dados_classificacao, f, ensure_ascii=False, indent=2)
        return nome_arquivo, dados_classificacao
    except Exception as e:
        raise Exception(f"Erro ao salvar classificação: {str(e)}")

def aplicar_mascara(imagem_pil):
    """Aplica máscara de censura na imagem mantendo alta qualidade"""
    # Preserva o modo original da imagem para manter qualidade
    modo_original = imagem_pil.mode
    
    # Converte para RGB apenas se necessário, preservando qualidade
    if modo_original not in ['RGB', 'RGBA']:
        img_trabalho = imagem_pil.convert('RGB')
    else:
        img_trabalho = imagem_pil.copy()
    
    # Cria draw object com anti-aliasing desabilitado para preservar nitidez
    desenho = ImageDraw.Draw(img_trabalho)
    
    # Cor branca exata para preservar qualidade
    cor_branca = (255, 255, 255) if img_trabalho.mode == 'RGB' else (255, 255, 255, 255)
    
    # Áreas a cobrir com branco (coordenadas otimizadas para CONAB)
    # Usando outline=None para evitar bordas que podem afetar a qualidade
    desenho.rectangle([250, 50, 2140, 530], fill=cor_branca, outline=None)    # Cabeçalho
    desenho.rectangle([230, 550, 770, 1550], fill=cor_branca, outline=None)   # Coluna esquerda
    desenho.rectangle([250, 1450, 2120, 1580], fill=cor_branca, outline=None) # Rodapé
    desenho.rectangle([770, 550, 842, 1440], fill=cor_branca, outline=None)   # Separadores
    desenho.rectangle([1060, 540, 1125, 1440], fill=cor_branca, outline=None)
    desenho.rectangle([1340, 540, 1400, 1440], fill=cor_branca, outline=None)
    desenho.rectangle([1620, 540, 1683, 1440], fill=cor_branca, outline=None)
    desenho.rectangle([1900, 540, 1960, 1440], fill=cor_branca, outline=None)
    desenho.rectangle([770, 540, 2170, 580], fill=cor_branca, outline=None)   # Linha superior
    
    return img_trabalho

def comparar_com_gabarito(marcacoes: Dict[int, str], gabarito_oficial: Dict[str, str]) -> Tuple[int, int, int, int]:
    """Compara as marcações detectadas com o gabarito oficial"""
    acertos = 0
    erros = 0
    nao_respondidas = 0
    anuladas = 0
    
    # Converte chaves do gabarito para int para comparação
    gabarito_int = {int(k): v for k, v in gabarito_oficial.items()}
    
    for questao_num in gabarito_int.keys():
        resposta_oficial = gabarito_int[questao_num]
        resposta_candidato = marcacoes.get(questao_num)
        
        if resposta_oficial == "Anulada":
            anuladas += 1
        elif resposta_candidato is None:
            nao_respondidas += 1
        elif resposta_candidato == resposta_oficial:
            acertos += 1
        else:
            erros += 1
    
    return acertos, erros, nao_respondidas, anuladas

def exibir_comparacao_detalhada(marcacoes: Dict[int, str], gabarito_oficial: Dict[str, str]):
    """Exibe comparação detalhada questão por questão"""
    gabarito_int = {int(k): v for k, v in gabarito_oficial.items()}
    
    # Organiza em colunas
    num_colunas = 4
    cols = st.columns(num_colunas)
    
    questoes_ordenadas = sorted(gabarito_int.keys())
    
    for i, questao_num in enumerate(questoes_ordenadas):
        with cols[i % num_colunas]:
            resposta_oficial = gabarito_int[questao_num]
            resposta_candidato = marcacoes.get(questao_num, "Não respondida")
            
            if resposta_oficial == "Anulada":
                emoji = "🚫"
                cor = "orange"
            elif resposta_candidato == "Não respondida":
                emoji = "⚪"
                cor = "gray"
            elif resposta_candidato == resposta_oficial:
                emoji = "✅"
                cor = "green"
            else:
                emoji = "❌"
                cor = "red"
            
            st.markdown(f"**Q{questao_num:02d}:** {emoji}")
            st.markdown(f"<small style='color: {cor}'>Oficial: {resposta_oficial}<br>Candidato: {resposta_candidato}</small>", unsafe_allow_html=True)

def gerar_relatorio_completo(nome_candidato: str, marcacoes: Dict[int, str], 
                           gabarito_oficial: Dict[str, str], codigo_cargo: str, 
                           prova: str, nome_cargo: str) -> str:
    """Gera relatório completo com comparação"""
    from datetime import datetime
    
    gabarito_int = {int(k): v for k, v in gabarito_oficial.items()}
    acertos, erros, nao_respondidas, anuladas = comparar_com_gabarito(marcacoes, gabarito_oficial)
    total_questoes = len(gabarito_int)
    
    relatorio = f"""RELATÓRIO DE ANÁLISE DE GABARITO - CONCURSO CONAB
{'='*60}

DADOS DO CANDIDATO:
Nome: {nome_candidato}
Data/Hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}

DADOS DO CONCURSO:
Cargo: {nome_cargo}
Código: {codigo_cargo}
Prova: {prova}

RESUMO DOS RESULTADOS:
{'='*30}
Total de questões: {total_questoes}
Acertos: {acertos} ({(acertos/total_questoes)*100:.1f}%)
Erros: {erros} ({(erros/total_questoes)*100:.1f}%)
Não respondidas: {nao_respondidas} ({(nao_respondidas/total_questoes)*100:.1f}%)
Anuladas: {anuladas} ({(anuladas/total_questoes)*100:.1f}%)

COMPARAÇÃO QUESTÃO POR QUESTÃO:
{'='*40}
Questão | Oficial | Candidato | Status
--------|---------|-----------|--------"""
    
    for questao_num in sorted(gabarito_int.keys()):
        resposta_oficial = gabarito_int[questao_num]
        resposta_candidato = marcacoes.get(questao_num, "N/R")
        
        if resposta_oficial == "Anulada":
            status = "ANULADA"
        elif resposta_candidato == "N/R":
            status = "NÃO RESP"
        elif resposta_candidato == resposta_oficial:
            status = "ACERTO"
        else:
            status = "ERRO"
        
        relatorio += f"\n   {questao_num:02d}   |    {resposta_oficial:^3}   |     {resposta_candidato:^3}     | {status}"
    
    relatorio += f"\n\n{'='*60}\nRelatório gerado automaticamente pelo Sistema de Análise CONAB"
    
    return relatorio

# ============================================================================
# INTERFACE STREAMLIT PRINCIPAL
# ============================================================================

def main():
    """Interface principal com comparação de gabarito"""
    
    # Configuração da página
    st.set_page_config(
        page_title="Analisador de Gabarito CONAB",
        page_icon="",
        layout="wide",
        initial_sidebar_state="expanded",
        menu_items={
            'Get Help': None,
            'Report a bug': None,
            'About': None
        }
    )
    
    # # Ocultar elementos padrão do Streamlit
    # hide_streamlit_style = """
    # <style>
    # #MainMenu {visibility: none;}
    # footer {visibility: hidden;}
    # header {visibility: hidden;}
    # .stDeployButton {display:none;}
    # .stDecoration {display:none;}
    # </style>
    # """
    # st.markdown(hide_streamlit_style, unsafe_allow_html=True)
    
    # Título
    st.title(" Analisador de Gabarito - Concurso CONAB")
    st.markdown("**Detecção automática e comparação com gabarito oficial**")
    st.markdown("---")
    
    # Menu principal
    menu_opcao = st.sidebar.selectbox(
        "🔧 Selecione a Funcionalidade",
        ["📊 Análise de Gabarito", "🏆 Classificação Geral", "👤 Meu Resultado"]
    )
    
    # Carrega dados do gabarito
    dados = carregar_dados_gabarito()
    
    # Configurações padrão (não visíveis ao candidato)
    aplicar_mascara_opcao = True
    comparar_gabarito = True
    nome_candidato = "Candidato"
    
    if menu_opcao == "📊 Análise de Gabarito":
        # Funcionalidade original de análise de gabarito
        if not dados:
            st.warning("⚠️ Não foi possível carregar os dados do gabarito oficial.")
            st.info("O sistema funcionará apenas no modo de detecção de marcações.")
            # Valores padrão para modo básico
            cargo_selecionado = None
            prova_selecionada = None
            gabarito_oficial = {}
            total_questoes = 80  # Padrão
        else:
            # Sidebar para seleção de cargo e prova
            with st.sidebar:
                st.header(" Configurações do Concurso")
                
                # Seletor de cargo
                cargos_disponiveis = list(dados.keys())
                cargo_selecionado = st.selectbox(
                    "Selecione o Cargo:",
                    options=cargos_disponiveis,
                    format_func=lambda x: f"{x} - {dados[x]['nome'][:50]}..."
                )
                
                # Seletor de prova
                if cargo_selecionado:
                    provas_disponiveis = list(dados[cargo_selecionado]['provas'].keys())
                    prova_selecionada = st.selectbox(
                        "Selecione a Prova:",
                        options=provas_disponiveis,
                        format_func=lambda x: f"Prova {x}"
                    )
                    
                    # Informações do cargo selecionado
                    st.info(f"**Cargo:** {dados[cargo_selecionado]['nome']}")
                    st.info(f"**Código:** {cargo_selecionado}")
                    st.info(f"**Prova:** {prova_selecionada}")
                    
                    # Determina número de questões baseado no gabarito
                    gabarito_oficial = dados[cargo_selecionado]['provas'][prova_selecionada]
                    total_questoes = len(gabarito_oficial)
                    st.success(f"**Total de questões:** {total_questoes}")
                else:
                    prova_selecionada = None
                    gabarito_oficial = {}
                    total_questoes = 80
        

        
        # Upload da imagem
        st.subheader("📷 Upload da Imagem")
        imagem_file = st.file_uploader(
            "Faça upload da imagem do cartão resposta:",
            type=['png', 'jpg', 'jpeg'],
            help="Dimensões recomendadas: 2338x1653 pixels"
        )
        
        # Processamento
        if imagem_file:
            # Mostrar preview da imagem original preservando qualidade
            st.subheader("📋 Preview da Imagem")
            # Preserva o modo de cor original
            imagem_original = Image.open(imagem_file)
            if imagem_original.mode not in ['RGB', 'RGBA']:
                imagem_original = imagem_original.convert('RGB')
            
            col_preview1, col_preview2 = st.columns(2)
            
            with col_preview1:
                st.markdown("**Imagem Original:**")
                st.image(imagem_original, caption="Imagem carregada", use_container_width=True)
            
            if aplicar_mascara_opcao:
                with col_preview2:
                    st.markdown("**Com Máscara Aplicada:**")
                    imagem_mascarada = aplicar_mascara(imagem_original.copy())
                    st.image(imagem_mascarada, caption="Áreas censuradas", use_container_width=True)
                    
                    # Opção de download da imagem mascarada com alta qualidade
                    buf = io.BytesIO()
                    # Salva em PNG com máxima qualidade (sem compressão)
                    imagem_mascarada.save(buf, format="PNG", optimize=False, compress_level=0)
                    byte_im = buf.getvalue()
                    
                    st.download_button(
                        label="📥 Baixar imagem censurada (Alta Qualidade)",
                        data=byte_im,
                        file_name=f"gabarito_censurado_hq_{nome_candidato.replace(' ', '_') or 'anonimo'}.png",
                        mime="image/png",
                        help="Imagem salva em PNG sem compressão para máxima qualidade"
                    )
            
            st.markdown("---")
            
            if st.button("🔍 Verificar", type="primary", use_container_width=True):
                with st.spinner("Analisando imagem e detectando marcações..."):
                    try:
                        # Prepara a imagem para processamento
                        imagem_para_processar = imagem_mascarada if aplicar_mascara_opcao else imagem_original
                        
                        # Salva arquivo temporário
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_imagem:
                            imagem_para_processar.save(tmp_imagem.name, format='PNG')
                            imagem_path = tmp_imagem.name
                        
                        # Detecta marcações
                        detector = DetectorMarcacoes()
                        marcacoes = detector.detectar_marcacoes(imagem_path, total_questoes)
                        
                        # Remove arquivo temporário
                        os.unlink(imagem_path)
                        
                        # Exibe resultados
                        if marcacoes:
                            st.success(f"✅ Detectadas {len(marcacoes)} marcações!")
                            
                            # Análise de comparação se solicitada
                            if comparar_gabarito and cargo_selecionado and prova_selecionada:
                                acertos, erros, nao_respondidas, anuladas = comparar_com_gabarito(
                                    marcacoes, gabarito_oficial
                                )
                                
                                # ============ CÁLCULO DE NOTAS CONAB ============
                                st.subheader(" Análise por Critérios CONAB")
                                
                                # Calcular notas usando as regras CONAB
                                questoes_ordenadas = {q: marcacoes.get(q, 'Não respondida') for q in range(1, total_questoes + 1)}
                                resultado_conab = calcular_nota_conab(questoes_ordenadas, cargo_selecionado, dados)
                                
                                # Exibir tipo de cargo
                                st.info(f"**Tipo de Cargo:** {resultado_conab['tipo_cargo']}")
                                
                                # Métricas principais de aprovação
                                col1, col2, col3 = st.columns(3)
                                
                                with col1:
                                    basicos_aprovado = "✅" if resultado_conab['aprovacao']['basicos_aprovado'] else "❌"
                                    st.metric(
                                        f"{basicos_aprovado} Conhecimentos Básicos",
                                        f"{resultado_conab['totais']['conhecimentos_basicos']} pts",
                                        delta=f"Mín: {resultado_conab['aprovacao']['nota_minima_basicos']} pts"
                                    )
                                
                                with col2:
                                    especificos_aprovado = "✅" if resultado_conab['aprovacao']['especificos_aprovado'] else "❌"
                                    st.metric(
                                        f"{especificos_aprovado} Conhecimentos Específicos",
                                        f"{resultado_conab['totais']['conhecimentos_especificos']} pts",
                                        delta=f"Mín: {resultado_conab['aprovacao']['nota_minima_especificos']} pts"
                                    )
                                
                                with col3:
                                    aprovado_geral = "✅ APROVADO" if resultado_conab['aprovacao']['aprovado_geral'] else "❌ REPROVADO"
                                    st.metric(
                                        f"{aprovado_geral}",
                                        f"{resultado_conab['totais']['total_geral']} pts",
                                        delta="Total Geral"
                                    )
                                
                                # Detalhamento por matéria - Conhecimentos Básicos
                                st.subheader("📚 Detalhamento - Conhecimentos Básicos")
                                
                                materias_basicas = []
                                for materia, dados_materia in resultado_conab['conhecimentos_basicos'].items():
                                    materias_basicas.append({
                                        "Matéria": materia.replace('_', ' ').title(),
                                        "Acertos": f"{dados_materia['acertos']}/{dados_materia['total_questoes']}",
                                        "Peso": dados_materia['peso'],
                                        "Pontos": dados_materia['pontos'],
                                        "Percentual": f"{dados_materia['percentual']:.1f}%"
                                    })
                                
                                if materias_basicas:
                                    df_basicas = pd.DataFrame(materias_basicas)
                                    st.dataframe(df_basicas, use_container_width=True, hide_index=True)
                                
                                # Detalhamento por matéria - Conhecimentos Específicos  
                                st.subheader("🔬 Detalhamento - Conhecimentos Específicos")
                                
                                materias_especificas = []
                                for materia, dados_materia in resultado_conab['conhecimentos_especificos'].items():
                                    materias_especificas.append({
                                        "Matéria": materia.replace('_', ' ').title(),
                                        "Acertos": f"{dados_materia['acertos']}/{dados_materia['total_questoes']}",
                                        "Peso": dados_materia['peso'],
                                        "Pontos": dados_materia['pontos'],
                                        "Percentual": f"{dados_materia['percentual']:.1f}%"
                                    })
                                
                                if materias_especificas:
                                    df_especificas = pd.DataFrame(materias_especificas)
                                    st.dataframe(df_especificas, use_container_width=True, hide_index=True)
                                
                                st.markdown("---")
                                
                                # ============ SALVAR RESULTADO DO CANDIDATO ============
                                if dados and gabarito_oficial:
                                    st.subheader("💾 Salvar Resultado")
                                    
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        nome_candidato_save = st.text_input("Nome do Candidato:", key="nome_save", value=nome_candidato)
                                    with col2:
                                        modalidade_concurso = st.selectbox(
                                            "Modalidade de Concurso:",
                                            ["Ampla Concorrência", "PCD", "PPP"]
                                        )
                                    
                                    if st.button("💾 Salvar Meu Resultado", type="primary"):
                                        if nome_candidato_save.strip():
                                            try:
                                                candidato_id = salvar_resultado_candidato(
                                                    nome_candidato_save.strip(),
                                                    cargo_selecionado,
                                                    modalidade_concurso,
                                                    resultado_conab,
                                                    questoes_ordenadas
                                                )
                                                st.success(f"✅ Resultado salvo com sucesso! ID: {candidato_id[:8]}...")
                                                st.info("Agora você pode acompanhar sua classificação na seção '🏆 Classificação Geral'")
                                                
                                                # Exibir classificação imediatamente após salvar
                                                st.markdown("---")
                                                st.subheader("🏆 Sua Posição na Classificação")
                                                
                                                classificacoes = gerar_classificacao_por_modalidade(cargo_selecionado)
                                                if modalidade_concurso in classificacoes:
                                                    candidatos = classificacoes[modalidade_concurso]
                                                    
                                                    # Encontrar posição do candidato atual
                                                    posicao_atual = None
                                                    for pos, candidato in enumerate(candidatos):
                                                        if candidato['id'] == candidato_id:
                                                            posicao_atual = pos + 1
                                                            break
                                                    
                                                    if posicao_atual:
                                                        col1, col2, col3 = st.columns(3)
                                                        with col1:
                                                            st.metric("Sua Posição", f"{posicao_atual}º")
                                                        with col2:
                                                            st.metric("Total de Candidatos", len(candidatos))
                                                        with col3:
                                                            percentil = ((len(candidatos) - posicao_atual + 1) / len(candidatos)) * 100
                                                            st.metric("Percentil", f"{percentil:.1f}%")
                                                        
                                                        # Mostrar top 10 da modalidade
                                                        st.write(f"**🏅 Top 10 - {modalidade_concurso}:**")
                                                        top_10 = candidatos[:10]
                                                        dados_top = []
                                                        for i, candidato in enumerate(top_10):
                                                            destaque = "🔥" if candidato['id'] == candidato_id else ""
                                                            dados_top.append({
                                                                "Pos": f"{i+1}º {destaque}",
                                                                "Nome": candidato['nome'],
                                                                "Total": candidato['pontuacao']['total'],
                                                                "Aprovado": "✅" if candidato['aprovacao']['aprovado_geral'] else "❌"
                                                            })
                                                        
                                                        df_top = pd.DataFrame(dados_top)
                                                        st.dataframe(df_top, use_container_width=True, hide_index=True)
                                            except Exception as e:
                                                st.error(f"❌ Erro ao salvar resultado: {str(e)}")
                                        else:
                                            st.warning("⚠️ Por favor, informe seu nome para salvar o resultado.")
                                
                                # Métricas com comparação
                                st.subheader("📈 Métricas Gerais")
                                col1, col2, col3, col4, col5 = st.columns(5)
                                with col1:
                                    st.metric("Total de Questões", total_questoes)
                                with col2:
                                    st.metric("✅ Acertos", acertos, delta=f"{(acertos/total_questoes)*100:.1f}%")
                                with col3:
                                    st.metric("❌ Erros", erros, delta=f"{(erros/total_questoes)*100:.1f}%")
                                with col4:
                                    st.metric("⚪ Não Respondidas", nao_respondidas)
                                with col5:
                                    st.metric("🚫 Anuladas", anuladas)
                            else:
                                # Métricas básicas
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    st.metric("Total de Questões", total_questoes)
                                with col2:
                                    st.metric("Questões Respondidas", len(marcacoes))
                                with col3:
                                    percentual = (len(marcacoes) / total_questoes) * 100
                                    st.metric("Percentual Respondido", f"{percentual:.1f}%")
                            
                            st.markdown("---")
                            
                            # Resultados por questão
                            if comparar_gabarito and cargo_selecionado and prova_selecionada:
                                st.subheader("📊 Comparação Detalhada")
                                exibir_comparacao_detalhada(marcacoes, gabarito_oficial)
                            else:
                                st.subheader("📋 Marcações Detectadas")
                                
                                # Organiza em colunas para melhor visualização
                                num_colunas = 5
                                cols = st.columns(num_colunas)
                                
                                questoes_ordenadas = sorted(marcacoes.items())
                                
                                for i, (questao, resposta) in enumerate(questoes_ordenadas):
                                    with cols[i % num_colunas]:
                                        st.write(f"**Q{questao:02d}:** {resposta}")
                            
                            # Lista completa em formato texto
                            st.markdown("---")
                            
                            with st.expander("📄 Ver Lista Completa"):
                                if comparar_gabarito and cargo_selecionado and prova_selecionada:
                                    resultado_texto = gerar_relatorio_completo(
                                        nome_candidato, marcacoes, gabarito_oficial, 
                                        cargo_selecionado, prova_selecionada, dados[cargo_selecionado]['nome']
                                    )
                                else:
                                    resultado_texto = f"Resultados para {nome_candidato}\n\n"
                                    resultado_texto += "Questão | Resposta\n"
                                    resultado_texto += "--------|----------\n"
                                    
                                    questoes_ordenadas_list = sorted(marcacoes.items())
                                    for questao, resposta in questoes_ordenadas_list:
                                        resultado_texto += f"   {questao:02d}   |    {resposta}\n"
                                    
                                    resultado_texto += f"\nTotal: {len(marcacoes)} questões respondidas de {total_questoes}"
                                
                                st.text(resultado_texto)
                                
                                # Download dos resultados
                                arquivo_nome = f"analise_{nome_candidato.replace(' ', '_')}_{cargo_selecionado}_{prova_selecionada}.txt" if comparar_gabarito else f"marcacoes_{nome_candidato.replace(' ', '_')}.txt"
                                st.download_button(
                                    label="💾 Baixar Resultados",
                                    data=resultado_texto,
                                    file_name=arquivo_nome,
                                    mime="text/plain"
                                )
                            
                            # Questões não respondidas
                            questoes_respondidas = set(marcacoes.keys())
                            questoes_nao_respondidas = [q for q in range(1, total_questoes + 1) if q not in questoes_respondidas]
                            
                            if questoes_nao_respondidas:
                                with st.expander(f"⚠️ Questões Não Detectadas ({len(questoes_nao_respondidas)})"):
                                    st.write("Questões sem marcação detectada:")
                                    
                                    # Mostra em colunas
                                    cols_nao_resp = st.columns(10)
                                    for i, questao in enumerate(questoes_nao_respondidas):
                                        with cols_nao_resp[i % 10]:
                                            if comparar_gabarito and cargo_selecionado and prova_selecionada:
                                                gabarito_q = gabarito_oficial.get(str(questao), "?")
                                                st.write(f"Q{questao:02d} ({gabarito_q})")
                                            else:
                                                st.write(f"Q{questao:02d}")
                        
                        else:
                            st.warning("⚠️ Nenhuma marcação foi detectada na imagem.")
                            
                            st.info("""
                            **Dicas para melhorar a detecção:**
                            - Verifique se a imagem está nas dimensões corretas (2338x1653)
                            - Certifique-se de que as marcações estão bem visíveis e escuras
                            - A imagem deve estar bem iluminada e sem sombras
                            - Evite imagens borradas ou com baixa resolução
                            - Use caneta preta ou lápis bem marcado
                            """)
                    
                    except Exception as e:
                        st.error(f"Erro no processamento: {e}")
                        st.info("""
                        **Possíveis soluções:**
                        - Verifique se o arquivo é uma imagem válida
                        - Tente uma imagem com melhor qualidade
                        - Certifique-se de que a imagem não está corrompida
                        """)
    
    elif menu_opcao == "🏆 Classificação Geral":
        st.header("🏆 Sistema de Classificação CONAB")
        
        # Carregar dados
        resultados_todos = carregar_resultados_candidatos()
        if not resultados_todos:
            st.info("📊 Nenhum resultado foi salvo ainda. Analise seu gabarito primeiro na seção '📊 Análise de Gabarito'.")
            return
        
        # ============ PAINEL DE CONTROLE ============
        st.subheader("⚙️ Filtros e Configurações")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Filtro por cargo
            cargos_com_resultados = list(set([r['cargo'] for r in resultados_todos]))
            cargo_filtro = st.selectbox(
                "🎯 Filtrar por Cargo:",
                ["Todos os Cargos"] + cargos_com_resultados
            )
        
        with col2:
            # Filtro por modalidade
            modalidades_disponiveis = ["Todas", "Ampla Concorrência", "PCD", "PPP"]
            modalidade_filtro = st.selectbox(
                "👥 Filtrar por Modalidade:",
                modalidades_disponiveis
            )
        
        with col3:
            # Filtro por status de aprovação
            status_filtro = st.selectbox(
                "✅ Status de Aprovação:",
                ["Todos", "Apenas Aprovados", "Apenas Reprovados"]
            )
        
        # ============ ESTATÍSTICAS GERAIS ============
        st.markdown("---")
        st.subheader("📊 Estatísticas Gerais")
        
        # Aplicar filtros
        resultados_filtrados = resultados_todos.copy()
        
        if cargo_filtro != "Todos os Cargos":
            resultados_filtrados = [r for r in resultados_filtrados if r['cargo'] == cargo_filtro]
        
        if modalidade_filtro != "Todas":
            resultados_filtrados = [r for r in resultados_filtrados if r['modalidade'] == modalidade_filtro]
        
        if status_filtro == "Apenas Aprovados":
            resultados_filtrados = [r for r in resultados_filtrados if r['pontuacao']['aprovacao']['aprovado_geral']]
        elif status_filtro == "Apenas Reprovados":
            resultados_filtrados = [r for r in resultados_filtrados if not r['pontuacao']['aprovacao']['aprovado_geral']]
        
        # Calcular estatísticas
        total_candidatos = len(resultados_filtrados)
        aprovados = sum(1 for r in resultados_filtrados if r['pontuacao']['aprovacao']['aprovado_geral'])
        reprovados = total_candidatos - aprovados
        
        if total_candidatos > 0:
            media_total = sum(r['pontuacao']['total'] for r in resultados_filtrados) / total_candidatos
            media_basicos = sum(r['pontuacao']['conhecimentos_basicos'] for r in resultados_filtrados) / total_candidatos
            media_especificos = sum(r['pontuacao']['conhecimentos_especificos'] for r in resultados_filtrados) / total_candidatos
            
            # Exibir métricas
            col1, col2, col3, col4, col5 = st.columns(5)
            
            with col1:
                st.metric("👥 Total de Candidatos", total_candidatos)
            with col2:
                st.metric("✅ Aprovados", aprovados, delta=f"{(aprovados/total_candidatos)*100:.1f}%")
            with col3:
                st.metric("❌ Reprovados", reprovados, delta=f"{(reprovados/total_candidatos)*100:.1f}%")
            with col4:
                st.metric("📈 Média Geral", f"{media_total:.1f}")
            with col5:
                maior_nota = max(r['pontuacao']['total'] for r in resultados_filtrados)
                st.metric("🏆 Maior Nota", f"{maior_nota:.1f}")
        
        # ============ CLASSIFICAÇÃO POR MODALIDADE ============
        st.markdown("---")
        st.subheader("🏅 Ranking por Modalidade")
        
        cargo_para_filtro = None if cargo_filtro == "Todos os Cargos" else cargo_filtro
        classificacoes = gerar_classificacao_por_modalidade(cargo_para_filtro)
        
        if not classificacoes:
            st.warning("⚠️ Nenhum resultado encontrado para os filtros selecionados.")
            return
        
        # ============ TABS POR MODALIDADE ============
        modalidades_com_dados = {k: v for k, v in classificacoes.items() if v}
        
        if not modalidades_com_dados:
            st.info("📭 Nenhum candidato encontrado com os filtros aplicados.")
            return
        
        modalidades_tabs = list(modalidades_com_dados.keys())
        tabs = st.tabs([f"🏅 {mod}" for mod in modalidades_tabs])
        
        for i, (modalidade, candidatos) in enumerate(modalidades_com_dados.items()):
            with tabs[i]:
                # ============ ESTATÍSTICAS DA MODALIDADE ============
                total_candidatos = len(candidatos)
                aprovados = sum(1 for c in candidatos if c['aprovacao']['aprovado_geral'])
                media_pontos = sum(c['pontuacao']['total'] for c in candidatos) / total_candidatos if total_candidatos > 0 else 0
                maior_pontuacao = max(c['pontuacao']['total'] for c in candidatos) if candidatos else 0
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric(
                        "👥 Total de Candidatos", 
                        total_candidatos,
                        help="Número total de candidatos nesta modalidade"
                    )
                
                with col2:
                    st.metric(
                        "✅ Aprovados", 
                        aprovados,
                        delta=f"{(aprovados/total_candidatos)*100:.1f}%" if total_candidatos > 0 else "0%",
                        help="Candidatos que atingiram a nota mínima"
                    )
                
                with col3:
                    st.metric(
                        "📊 Média de Pontos", 
                        f"{media_pontos:.1f}",
                        help="Média aritmética das pontuações"
                    )
                
                with col4:
                    st.metric(
                        "🏆 Maior Pontuação", 
                        f"{maior_pontuacao:.1f}",
                        help="Maior pontuação alcançada nesta modalidade"
                    )
                
                st.markdown("---")
                
                # ============ PODIUM (TOP 3) ============
                if len(candidatos) >= 3:
                    st.subheader("🏆 Pódium")
                    
                    col1, col2, col3 = st.columns(3)
                    
                    # 2º Lugar
                    with col1:
                        candidato_2 = candidatos[1]
                        st.markdown(
                            f"""
                            <div style="text-align: center; padding: 20px; background: linear-gradient(135deg, #C0C0C0, #E8E8E8); border-radius: 15px; margin: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);">
                                <h3 style="margin: 0; color: #666;">🥈 2º Lugar</h3>
                                <h4 style="margin: 10px 0; color: #333;">{candidato_2['nome']}</h4>
                                <p style="margin: 5px 0; font-size: 18px; font-weight: bold; color: #555;">{candidato_2['pontuacao']['total']:.1f} pontos</p>
                                <p style="margin: 0; color: #777;">{candidato_2['cargo']}</p>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                    
                    # 1º Lugar
                    with col2:
                        candidato_1 = candidatos[0]
                        st.markdown(
                            f"""
                            <div style="text-align: center; padding: 25px; background: linear-gradient(135deg, #FFD700, #FFA500); border-radius: 15px; margin: 10px; transform: scale(1.05); box-shadow: 0 6px 12px rgba(0,0,0,0.2);">
                                <h2 style="margin: 0; color: #8B4513;">🥇 1º Lugar</h2>
                                <h3 style="margin: 10px 0; color: #8B4513;">{candidato_1['nome']}</h3>
                                <p style="margin: 5px 0; font-size: 20px; font-weight: bold; color: #8B4513;">{candidato_1['pontuacao']['total']:.1f} pontos</p>
                                <p style="margin: 0; color: #8B4513;">{candidato_1['cargo']}</p>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                    
                    # 3º Lugar
                    with col3:
                        candidato_3 = candidatos[2]
                        st.markdown(
                            f"""
                            <div style="text-align: center; padding: 20px; background: linear-gradient(135deg, #CD7F32, #D2B48C); border-radius: 15px; margin: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);">
                                <h3 style="margin: 0; color: #654321;">🥉 3º Lugar</h3>
                                <h4 style="margin: 10px 0; color: #654321;">{candidato_3['nome']}</h4>
                                <p style="margin: 5px 0; font-size: 18px; font-weight: bold; color: #654321;">{candidato_3['pontuacao']['total']:.1f} pontos</p>
                                <p style="margin: 0; color: #654321;">{candidato_3['cargo']}</p>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                    
                    st.markdown("---")
                
                # ============ TABELA COMPLETA DE CLASSIFICAÇÃO ============
                st.subheader("📊 Classificação Completa")
                
                # Preparar dados para a tabela
                dados_tabela = []
                for candidato in candidatos:
                    # Determinar ícone de posição
                    posicao = candidato['posicao']
                    if posicao == 1:
                        icone_posicao = "🥇 1º"
                    elif posicao == 2:
                        icone_posicao = "🥈 2º"
                    elif posicao == 3:
                        icone_posicao = "🥉 3º"
                    else:
                        icone_posicao = f"{posicao}º"
                    
                    # Status de aprovação com ícone
                    status = "✅ Aprovado" if candidato['aprovacao']['aprovado_geral'] else "❌ Reprovado"
                    
                    dados_tabela.append({
                        'Posição': icone_posicao,
                        'Nome': candidato['nome'],
                        'Cargo': candidato['cargo'],
                        'Básicos': f"{candidato['pontuacao']['conhecimentos_basicos']:.1f}",
                        'Específicos': f"{candidato['pontuacao']['conhecimentos_especificos']:.1f}",
                        'Total': f"{candidato['pontuacao']['total']:.1f}",
                        'Status': status,
                        'Data': candidato['data_analise']
                    })
                
                df_candidatos = pd.DataFrame(dados_tabela)
                
                # Exibir tabela com estilo
                st.dataframe(
                    df_candidatos,
                    use_container_width=True,
                    hide_index=True,
                    height=400,
                    column_config={
                        "Posição": st.column_config.TextColumn("Posição", width="small"),
                        "Nome": st.column_config.TextColumn("Nome", width="medium"),
                        "Cargo": st.column_config.TextColumn("Cargo", width="medium"),
                        "Básicos": st.column_config.NumberColumn("Básicos", format="%.1f"),
                        "Específicos": st.column_config.NumberColumn("Específicos", format="%.1f"),
                        "Total": st.column_config.NumberColumn("Total", format="%.1f"),
                        "Status": st.column_config.TextColumn("Status", width="small"),
                        "Data": st.column_config.DatetimeColumn("Data Análise", width="small")
                    }
                )
                
                # ============ OPÇÕES DE EXPORTAÇÃO ============
                st.markdown("---")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    # Download CSV
                    csv = df_candidatos.to_csv(index=False, encoding='utf-8-sig')
                    st.download_button(
                        label=f"📥 Baixar CSV",
                        data=csv,
                        file_name=f"classificacao_{modalidade.lower().replace(' ', '_')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                
                with col2:
                    # Botão para atualizar dados
                    if st.button(f"🔄 Atualizar", key=f"refresh_{modalidade}", use_container_width=True):
                        st.rerun()
                
                with col3:
                    # Estatísticas rápidas
                    if st.button(f"📈 Estatísticas", key=f"stats_{modalidade}", use_container_width=True):
                        st.info(f"📊 **Resumo {modalidade}:**\n\n" +
                               f"• Candidatos: {total_candidatos}\n" +
                               f"• Taxa de Aprovação: {(aprovados/total_candidatos)*100:.1f}%\n" +
                               f"• Média: {media_pontos:.1f} pontos\n" +
                               f"• Maior Nota: {maior_pontuacao:.1f} pontos")
    
    elif menu_opcao == "👤 Meu Resultado":
        st.header("👤 Consultar Meu Resultado")
        
        nome_busca = st.text_input("Digite seu nome para buscar:")
        
        if nome_busca.strip():
            resultados_todos = carregar_resultados_candidatos()
            meus_resultados = [r for r in resultados_todos if nome_busca.lower() in r['nome'].lower()]
            
            if meus_resultados:
                st.success(f"✅ Encontrados {len(meus_resultados)} resultado(s) para '{nome_busca}'")
                
                for i, resultado in enumerate(meus_resultados):
                    with st.expander(f"📋 {resultado['nome']} - {resultado['cargo']} ({resultado['modalidade']})"):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write("**📊 Pontuação:**")
                            st.write(f"• Conhecimentos Básicos: {resultado['pontuacao']['conhecimentos_basicos']} pts")
                            st.write(f"• Conhecimentos Específicos: {resultado['pontuacao']['conhecimentos_especificos']} pts")
                            st.write(f"• **Total: {resultado['pontuacao']['total']} pts**")
                            
                            st.write("**✅ Status de Aprovação:**")
                            st.write(f"• Básicos: {'✅' if resultado['aprovacao']['aprovado_basicos'] else '❌'}")
                            st.write(f"• Específicos: {'✅' if resultado['aprovacao']['aprovado_especificos'] else '❌'}")
                            st.write(f"• **Geral: {'✅ APROVADO' if resultado['aprovacao']['aprovado_geral'] else '❌ REPROVADO'}**")
                        
                        with col2:
                            st.write("**📈 Posição no Ranking:**")
                            # Calcular posição
                            classificacoes = gerar_classificacao_por_modalidade(resultado['cargo'])
                            modalidade = resultado['modalidade']
                            posicao = "N/A"
                            total_modalidade = 0
                            
                            if modalidade in classificacoes:
                                for pos, candidato in enumerate(classificacoes[modalidade]):
                                    if candidato['id'] == resultado['id']:
                                        posicao = pos + 1
                                        break
                                total_modalidade = len(classificacoes[modalidade])
                            
                            st.metric("Posição", f"{posicao}º de {total_modalidade}" if posicao != "N/A" else "N/A")
                            st.write(f"**Modalidade:** {resultado['modalidade']}")
                            st.write(f"**Data da Análise:** {resultado['data_analise']}")
                        
                        # Detalhes por matéria
                        st.write("**📚 Detalhamento por Matéria:**")
                        
                        # Conhecimentos Básicos
                        st.write("*Conhecimentos Básicos:*")
                        for materia, dados_materia in resultado['detalhes_materias']['conhecimentos_basicos'].items():
                            acertos = dados_materia['acertos']
                            total = dados_materia['total_questoes']
                            pontos = dados_materia['pontos']
                            st.write(f"• {materia}: {acertos}/{total} questões ({pontos} pts)")
                        
                        # Conhecimentos Específicos
                        st.write("*Conhecimentos Específicos:*")
                        for materia, dados_materia in resultado['detalhes_materias']['conhecimentos_especificos'].items():
                            acertos = dados_materia['acertos']
                            total = dados_materia['total_questoes']
                            pontos = dados_materia['pontos']
                            st.write(f"• {materia}: {acertos}/{total} questões ({pontos} pts)")
            else:
                st.warning(f"⚠️ Nenhum resultado encontrado para '{nome_busca}'. Verifique se você já analisou seu gabarito.")
    
    # Informações adicionais
    st.markdown("---")
    st.markdown("### ℹ️ Informações")
    
    
    st.markdown("""
        **Formato da Imagem:**
        - Dimensões recomendadas: 2338x1653 pixels
        - Formatos suportados: PNG, JPG, JPEG
        - Qualidade: Alta resolução preferível
        """)

if __name__ == "__main__":
    main()