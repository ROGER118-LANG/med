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

# Inicializar o estado da sessão
if 'historico_pacientes' not in st.session_state:
    st.session_state.historico_pacientes = {}
if 'logado' not in st.session_state:
    st.session_state.logado = False
if 'nome_usuario' not in st.session_state:
    st.session_state.nome_usuario = None

# Arquivo para armazenar informações de login
ARQUIVO_LOGIN = 'login_info.xlsx'

def hash_senha(senha):
    return hashlib.sha256(senha.encode()).hexdigest()

def inicializar_arquivo_login():
    if not os.path.exists(ARQUIVO_LOGIN):
        wb = Workbook()
        ws = wb.active
        ws.append(['Usuário', 'Senha', 'Último Login'])
        senha_admin = hash_senha('123')
        ws.append(['admin', senha_admin, ''])
        wb.save(ARQUIVO_LOGIN)

def verificar_login(usuario, senha):
    wb = load_workbook(ARQUIVO_LOGIN)
    ws = wb.active
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[0] == usuario and row[1] == hash_senha(senha):
            return True
    return False

def atualizar_ultimo_login(usuario):
    wb = load_workbook(ARQUIVO_LOGIN)
    ws = wb.active
    for row in ws.iter_rows(min_row=2):
        if row[0].value == usuario:
            row[2].value = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            break
    wb.save(ARQUIVO_LOGIN)

def pagina_login():
    st.title("Login")
    usuario = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        if verificar_login(usuario, senha):
            st.session_state.logado = True
            st.session_state.nome_usuario = usuario
            atualizar_ultimo_login(usuario)
            st.success("Login realizado com sucesso!")
        else:
            st.error("Usuário ou senha inválidos")

def custom_depthwise_conv2d(*args, **kwargs):
    kwargs.pop('groups', None)
    return DepthwiseConv2D(*args, **kwargs)

def carregar_modelo_e_labels(caminho_modelo, caminho_labels):
    try:
        if not os.path.exists(caminho_modelo):
            raise FileNotFoundError(f"Arquivo do modelo não encontrado: {caminho_modelo}")
        if not os.path.exists(caminho_labels):
            raise FileNotFoundError(f"Arquivo de labels não encontrado: {caminho_labels}")
        
        with custom_object_scope({'DepthwiseConv2D': custom_depthwise_conv2d}):
            modelo = load_model(caminho_modelo, compile=False)
        
        with open(caminho_labels, "r") as f:
            nomes_classes = f.readlines()
        return modelo, nomes_classes
    except Exception as e:
        st.error(f"Erro ao carregar modelo e labels: {str(e)}")
        return None, None

def preprocessar_imagem(arquivo_enviado):
    imagem_bytes = arquivo_enviado.getvalue()
    imagem = Image.open(io.BytesIO(imagem_bytes)).convert("RGB")
    tamanho = (224, 224)
    imagem = ImageOps.fit(imagem, tamanho, Image.Resampling.LANCZOS)
    imagem_array = np.asarray(imagem)
    imagem_normalizada = (imagem_array.astype(np.float32) / 127.5) - 1
    dados = np.ndarray(shape=(1, 224, 224, 3), dtype=np.float32)
    dados[0] = imagem_normalizada
    return dados

def prever(modelo, dados, nomes_classes):
    try:
        previsao = modelo.predict(dados)
        indice = np.argmax(previsao)
        nome_classe = nomes_classes[indice]
        confianca = previsao[0][indice]
        return nome_classe[2:], confianca
    except Exception as e:
        st.error(f"Erro durante a previsão: {str(e)}")
        return None, None

def classificar_exame(id_paciente, opcao_modelo, arquivo_enviado):
    if arquivo_enviado is not None:
        st.write(f"Modelo selecionado: {opcao_modelo}")
        modelo, nomes_classes = carregar_modelo_e_labels(caminho_modelos[opcao_modelo], caminho_labels[opcao_modelo])
        
    if modelo is None or nomes_classes is None:
    st.error("Falha ao carregar o modelo e labels. Verifique os arquivos e tente novamente.")

            imagem_processada = preprocessar_imagem(arquivo_enviado)
            nome_classe, confianca = prever(modelo, imagem_processada, nomes_classes)
            
            if nome_classe é não None e confianca é não None:
                resultado = {
                    'data': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'modelo': opcao_modelo,
                    'classe': nome_classe,
                    'confianca': confianca
                }
                
                if id_paciente not in st.session_state.historico_pacientes:
                    st.session_state.historico_pacientes[id_paciente] = []
                st.session_state.historico_pacientes[id_paciente].append(resultado)
                
                st.success("Exame classificado com sucesso!")
                return resultado
            else:
                st.error("Ocorreu um erro durante a previsão. Tente novamente.")
    else:
        st.error("Por favor, envie uma imagem primeiro.")
    return None

def visualizar_historico_paciente(id_paciente):
    if id_paciente in st.session_state.historico_pacientes:
        historico = st.session_state.historico_pacientes[id_paciente]
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
    dados_usuarios = {row[0]: row for row in ws.iter_rows(min_row=2, values_only=True)}
    usuarios_df = pd.DataFrame(dados_usuarios.values(), columns=["Usuário", "Senha", "Último Login"])
    st.dataframe(usuarios_df)

    # Adicionar novo usuário
    st.subheader("Adicionar Usuário")
    novo_usuario = st.text_input("Novo Usuário")
    nova_senha = st.text_input("Nova Senha", type="password")
    if st.button("Adicionar Usuário"):
        if novo_usuario and nova_senha:
            senha_hash = hash_senha(nova_senha)
            ws.append([novo_usuario, senha_hash, ""])
            wb.save(ARQUIVO_LOGIN)
            st.success("Usuário adicionado com sucesso!")
        else:
            st.error("Por favor, insira tanto o nome de usuário quanto a senha.")

    # Editar usuário
    st.subheader("Editar Usuário")
    usuario_para_editar = st.selectbox("Selecione o usuário para editar", list(dados_usuarios.keys()))
    nova_senha_editar = st.text_input("Nova Senha para o Usuário Selecionado", type="password")
    if st.button("Editar Usuário"):
        if nova_senha_editar:
            senha_hash_editar = hash_senha(nova_senha_editar)
            for row in ws.iter_rows(min_row=2):
                if row[0].value == usuario_para_editar:
                    row[1].value = senha_hash_editar
                    break
            wb.save(ARQUIVO_LOGIN)
            st.success("Usuário editado com sucesso!")
        else:
            st.error("Por favor, insira uma nova senha.")

    # Remover usuário
    st.subheader("Remover Usuário")
    usuario_para_remover = st.selectbox("Selecione o usuário para remover", list(dados_usuarios.keys()))
    if st.button("Remover Usuário"):
        ws.delete_rows(list(dados_usuarios.keys()).index(usuario_para_remover) + 2)
        wb.save(ARQUIVO_LOGIN)
        st.success("Usuário removido com sucesso!")

def main():
    inicializar_arquivo_login()

    if not st.session_state.logado:
        pagina_login()
    else:
        st.title("Análise de Imagem Médica usando IA")
        st.sidebar.title(f"Bem-vindo, {st.session_state.nome_usuario}")

        if st.sidebar.button("Sair"):
            st.session_state.logado = False
            st.session_state.nome_usuario = None
            st.experimental_rerun()

        # Menu lateral
        opcao_menu = st.sidebar.radio("Escolha uma opção:", ("Classificar Exame", "Visualizar Histórico de Paciente"))

        # Adicionar a opção "Gerenciamento de Usuários" para o admin
        if st.session_state.nome_usuario == 'admin':
            opcao_menu = st.sidebar.radio("Escolha uma opção:", ("Classificar Exame", "Visualizar Histórico de Paciente", "Gerenciamento de Usuários"))

        if opcao_menu == "Classificar Exame":
            st.header("Classificação de Imagem Médica")

            id_paciente = st.text_input("ID do Paciente")
            opcao_modelo = st.selectbox("Escolha o Modelo", ["Modelo 1", "Modelo 2"])
            arquivo_enviado = st.file_uploader("Envie a Imagem do Exame", type=["jpg", "png", "jpeg"])

            if st.button("Classificar Exame"):
                resultado = classificar_exame(id_paciente, opcao_modelo, arquivo_enviado)
                if resultado:
                    st.write("Resultado da Classificação:")
                    st.write(f"Classe: {resultado['classe']}")
                    st.write(f"Confiança: {resultado['confianca'] * 100:.2f}%")

        elif opcao_menu == "Visualizar Histórico de Paciente":
            st.header("Histórico de Paciente")
            id_paciente = st.text_input("ID do Paciente")
            if st.button("Visualizar Histórico"):
                visualizar_historico_paciente(id_paciente)

        elif opcao_menu == "Gerenciamento de Usuários" and st.session_state.nome_usuario == 'admin':
            gerenciar_usuarios()

# Caminhos para os arquivos do modelo e labels
caminho_modelos = {
    "Modelo 1": "modelo_cancer.h5",
    "Modelo 2": "outro_modelo.h5"
}

caminho_labels = {
    "Modelo 1": "labels_cancer.txt",
    "Modelo 2": "labels_cancer.txt"
}

if __name__ == "__main__":
    main()
