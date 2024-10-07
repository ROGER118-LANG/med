import streamlit as st
from keras.models import load_model
from keras.layers import DepthwiseConv2D
from keras.utils import custom_object_scope
from PIL import Image, ImageOps
import numpy as np
import io
import os
import pandas as pd
from datetime import datetime
from openpyxl import Workbook, load_workbook
import hashlib

# Desativar notação científica para clareza
np.set_printoptions(suppress=True)

# Inicializar estado da sessão
if 'historico_paciente' not in st.session_state:
    st.session_state.historico_paciente = {}
if 'logado' not in st.session_state:
    st.session_state.logado = False
if 'nome_de_usuario' not in st.session_state:
    st.session_state.nome_de_usuario = None

# Arquivo para armazenar informações de login
ARQUIVO_LOGIN = 'informacoes_de_login.xlsx'

def gerar_hash_senha(senha):
    return hashlib.sha256(senha.encode()).hexdigest()

def inicializar_arquivo_login():
    if not os.path.exists(ARQUIVO_LOGIN):
        wb = Workbook()
        ws = wb.active
        ws.append(['Nome de Usuário', 'Senha', 'Último Login'])
        senha_admin = gerar_hash_senha('123')
        ws.append(['admin', senha_admin, ''])
        wb.save(ARQUIVO_LOGIN)

def verificar_login(nome_de_usuario, senha):
    wb = load_workbook(ARQUIVO_LOGIN)
    ws = wb.active
    for linha in ws.iter_rows(min_row=2, values_only=True):
        if linha[0] == nome_de_usuario and linha[1] == gerar_hash_senha(senha):
            return True
    return False

def atualizar_ultimo_login(nome_de_usuario):
    wb = load_workbook(ARQUIVO_LOGIN)
    ws = wb.active
    for linha in ws.iter_rows(min_row=2):
        if linha[0].value == nome_de_usuario:
            linha[2].value = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            break
    wb.save(ARQUIVO_LOGIN)

def pagina_de_login():
    st.title("Login")
    nome_de_usuario = st.text_input("Nome de Usuário")
    senha = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        if verificar_login(nome_de_usuario, senha):
            st.session_state.logado = True
            st.session_state.nome_de_usuario = nome_de_usuario
            atualizar_ultimo_login(nome_de_usuario)
            st.success("Login efetuado com sucesso!")
        else:
            st.error("Nome de usuário ou senha inválidos")

def custom_depthwise_conv2d(*args, **kwargs):
    kwargs.pop('groups', None)
    return DepthwiseConv2D(*args, **kwargs)

def carregar_modelo_e_etiquetas(caminho_do_modelo, caminho_das_etiquetas):
    try:
        if not os.path.exists(caminho_do_modelo):
            raise FileNotFoundError(f"Arquivo do modelo não encontrado: {caminho_do_modelo}")
        if not os.path.exists(caminho_das_etiquetas):
            raise FileNotFoundError(f"Arquivo de etiquetas não encontrado: {caminho_das_etiquetas}")

        with custom_object_scope({'DepthwiseConv2D': custom_depthwise_conv2d}):
            modelo = load_model(caminho_do_modelo, compile=False)

        with open(caminho_das_etiquetas, "r") as f:
            nomes_das_classes = f.readlines()
        return modelo, nomes_das_classes
    except Exception as e:
        st.error(f"Erro ao carregar modelo e etiquetas: {str(e)}")
        return None, None

def pre_processar_imagem(arquivo_enviado):
    # Corpo da funçãodef pre_processar_imagem(arquivo_enviado):  # Function definition on line 91
    bytes_da_imagem = arquivo_enviado.getvalue()  # Line 92 indented
    imagem = Image.open(io.BytesIO(bytes_da_imagem)).convert("RGB")  # Line 93 indented
    tamanho = (224, 224)  # Line 94 indented
    imagem = ImageOps.fit(imagem, tamanho, Image.Resampling.LANCZOS)  #
array_da_imagem = np.asarray(imagem)
array_da_imagem_normalizado = (array_da_imagem.astype(np.float32) / 127.5) - 1
dados = np.ndarray(shape=(1, 224, 224, 3), dtype=np.float32)
dados[0] = array_da_imagem_normalizado
return dados
def prever(modelo, dados, nomes_das_classes):  # Function definition on line 103
    try:
        previsao = modelo.predict(dados)  # Line 104 indented
        indice = np.argmax(previsao)  # Line 105 indented
        nome_da_classe = nomes_das_classes[indice]  # Line 106 indented
        pontuacao_de_confianca = previsao[0][indice] # Line 107 indented
        return nome_da_classe[2:], pontuacao_de_confianca  # Line 108 indented
    except Exception as e:
        st.error(f"Erro durante a previsão: {str(e)}")  # Line 109 indented (part of the try-except block)
        return None, None  # Line 110 indented (part of the try-except block)
def classificar_exame(id_do_paciente, opcao_do_modelo, arquivo_enviado):
if arquivo_enviado is not None:
st.write(f"Opção de modelo selecionada: {opcao_do_modelo}")
modelo, nomes_das_classes = carregar_modelo_e_etiquetas(caminhos_dos_modelos[opcao_do_modelo], caminhos_das_etiquetas[opcao_do_modelo])

    if modelo is not None and nomes_das_classes is not None:
        imagem_processada = pre processar_imagem(arquivo_enviado)
        nome_da_classe, pontuacao_de_confianca = prever(modelo, imagem_processada, nomes_das_classes)

        if nome_da_classe is not None and pontuacao_de_confianca is not None:
            resultado = {
                'data': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'modelo': opcao_do_modelo,
                'classe': nome_da_classe,
                'confianca': pontuacao_de_confianca
            }

            if id_do_paciente not in st.session_state.historico_paciente:
                st.session_state.historico_paciente[id_do_paciente] = []
            st.session_state.historico_paciente[id_do_paciente].append(resultado)

            st.success("Exame classificado com sucesso!")
            return resultado
        else:
            st.error("Ocorreu um erro durante a previsão. Tente novamente.")
    else:
        st.error("Falha ao carregar o modelo e as etiquetas. Verifique os arquivos e tente novamente.")
else:
    st.error("Por favor, faça o upload de uma imagem primeiro.")
return None
def visualizar_historico_do_paciente(id_do_paciente):
if id_do_paciente in st.session_state.historico_paciente:
historico = st.session_state.historico_paciente[id_do_paciente]
df = pd.DataFrame(historico)
st.dataframe(df)
else:
st.info("Nenhum histórico encontrado para este paciente.")

def gerenciar_usuarios():
st.header("Gerenciamento de Usuários")
wb = load_workbook(ARQUIVO_LOGIN)
ws = wb.active

# Mostrar usuários existentes
st.subheader("Usuários Existentes")
dados_do_usuario = {linha[0]: linha for linha in ws.iter_rows(min_row=2, values_only=True)}
df_do_usuario = pd.DataFrame(dados_do_usuario.values(), columns=["Nome de Usuário", "Senha", "Último Login"])
st.dataframe(df_do_usuario)

# Adicionar novo usuário
st.subheader("Adicionar Usuário")
novo_nome_de_usuario = st.text_input("Novo Nome de Usuário")
nova_senha = st.text_input("Nova Senha", type="password")
if st.button("Adicionar Usuário"):
    if novo_nome_de_usuario and nova_senha:
        senha_criptografada = gerar_hash_senha(nova_senha)
        ws.append([novo_nome_de_usuario, senha_criptografada, ""])
        wb.save(ARQUIVO_LOGIN)
        st.success("Usuário adicionado com sucesso!")
    else:
        st.error("Por favor, forneça nome de usuário e senha.")

# Editar usuário
st.subheader("Editar Usuário")
nome_de_usuario_a_editar = st.selectbox("Selecione o Usuário a Editar", list(dados_do_usuario.keys()))
senha_editada = st.text_input("Nova Senha para o Usuário Selecionado", type="password")
if st.button("Editar Usuário"):
    if senha_editada:
        senha_criptografada = gerar_hash_senha(senha_editada)
        for linha in ws.iter_rows(min_row=2):
            if linha[0].value == nome_de_usuario_a_editar:
                linha[1].value = senha_criptografada
                break
        wb.save(ARQUIVO_LOGIN)
        st.success("Usuário editado com sucesso!")
    else:
        st.error("Por favor, forneça uma nova senha.")

# Remover usuário
st.subheader("Remover Usuário")
nome_de_usuario_a_remover = st.selectbox("Selecione o Usuário a Remover", list(dados_do_usuario.keys()))
if st.button("Remover Usuário"):
    ws.delete_rows(list(dados_do_usuario.keys()).index(nome_de_usuario_a_remover) + 2)
    wb.save(ARQUIVO_LOGIN)
    st.success("Usuário removido com sucesso!")
def main():
inicializar_arquivo_login()
if not st.session_state.get('logado', False):
pagina_de_login()
else:
st.title("Análise de Imagens Médicas usando IA")
st.sidebar.title(f"Bem-vindo, {st.session_state.nome_de_usuario}")
if st.sidebar.button("Sair"):
st.session_state.logado = False
st.session_state.nome_de_usuario = None
st.rerun()

    # Menu lateral
    if 'opcao_do_menu' not in st.session_state:
        st.session_state.opcao_do_menu = "Classificar Exame"

    opcoes = ["Classificar Exame", "Visualizar Histórico do Paciente"]
    if st.session_state.nome_de_usuario == 'admin':
        opcoes.append("Gerenciamento de Usuários")

    st.session_state.opcao_do_menu = st.sidebar.radio("Escolha uma opção:", opcoes, key="menu_radio")

    if st.session_state.opcao_do_menu == "Classificar Exame":
        st.header("Classificar Exame")
        id_do_paciente = st.text_input("Digite o ID do Paciente:")
        opcao_do_modelo = st.selectbox("Escolha um modelo para análise:", ("Pneumonia", "Tuberculose", "Câncer"))
        arquivo_enviado = st.file_uploader("Faça o upload de uma imagem de raio-X ou tomografia computadorizada", type=["jpg", "jpeg", "png"])
        if st.button("Classificar"):
            classificar_exame(id_do_paciente, opcao_do_modelo, arquivo_enviado)
    elif st.session_state.opcao_do_menu == "Visualizar Histórico do Paciente":
        st.header("Histórico do Paciente")
        id_do_paciente = st.text_input("Digite o ID do Paciente:")
        if st.button("Visualizar Histórico"):
            visualizar_historico_do_paciente(id_do_paciente)
    elif st.session_state.opcao_do_menu == "Gerenciamento de Usuários":
        gerenciar_usuarios()
if name == "main":
main()
