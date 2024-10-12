import streamlit as st
from keras.models import load_model
from keras.layers import DepthwiseConv2D
from keras.utils import custom_object_scope
from PIL import Image, ImageOps
import numpy as np
import io
import os
import pandas as pd
from datetime import datetime, timedelta
import hashlib
import matplotlib.pyplot as plt
import seaborn as sns
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# Disable scientific notation for clarity
np.set_printoptions(suppress=True)

# Initialize session state
if 'historico_paciente' not in st.session_state:
    st.session_state.historico_paciente = {}
if 'logado' not in st.session_state:
    st.session_state.logado = False
if 'nome_usuario' not in st.session_state:
    st.session_state.nome_usuario = None
if 'setores_usuario' not in st.session_state:
    st.session_state.setores_usuario = []

# Google Sheets setup
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SERVICE_ACCOUNT_FILE = 'path/to/your/service_account.json'
SAMPLE_SPREADSHEET_ID = 'your-spreadsheet-id'
SAMPLE_RANGE_NAME = 'Sheet1!A2:F'

creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
service = build('sheets', 'v4', credentials=creds)
sheet = service.spreadsheets()

# Define model and label paths
caminhos_modelos = {
    "Pneumologia": {
        "Pneumonia": "pneumonia_model.h5",
        "Tuberculose": "tuberculose_model.h5",
        "Câncer de Pulmão": "cancer_pulmao_model.h5"
    },
    "Neurologia": {
        "Tumor Cerebral": "tumor_cerebral_model.h5"
    },
    "Ortopedia": {
        "Braço Fraturado": "fractured_arm_model.h5",
        "Ruptura do Tendão de Aquiles": "achilles_tendon_rupture_model.h5",
        "ACL": "acl_model.h5",
        "Entorse de Tornozelo": "ankle_sprain_model.h5",
        "Fratura de Calcâneo": "calcaneus_fracture_model.h5"
    }
}

caminhos_rotulos = {
    "Pneumologia": {
        "Pneumonia": "pneumonia_labels.txt",
        "Tuberculose": "tuberculose_labels.txt",
        "Câncer de Pulmão": "cancer_pulmao_labels.txt"
    },
    "Neurologia": {
        "Tumor Cerebral": "tumor_cerebral_labels.txt"
    },
    "Ortopedia": {
        "Braço Fraturado": "fractured_arm_labels.txt",
        "Ruptura do Tendão de Aquiles": "achilles_tendon_rupture_labels.txt",
        "ACL": "acl_labels.txt",
        "Entorse de Tornozelo": "ankle_sprain_labels.txt",
        "Fratura de Calcâneo": "calcaneus_fracture_labels.txt"
    }
}

def custom_depthwise_conv2d(*args, **kwargs):
    kwargs.pop('groups', None)
    return DepthwiseConv2D(*args, **kwargs)

def carregar_modelo_e_rotulos(caminho_modelo, caminho_rotulos):
    try:
        if not os.path.exists(caminho_modelo):
            raise FileNotFoundError(f"Arquivo de modelo não encontrado: {caminho_modelo}")
        if not os.path.exists(caminho_rotulos):
            raise FileNotFoundError(f"Arquivo de rótulos não encontrado: {caminho_rotulos}")
        
        with custom_object_scope({'DepthwiseConv2D': custom_depthwise_conv2d}):
            modelo = load_model(caminho_modelo, compile=False)
        
        with open(caminho_rotulos, "r") as f:
            nomes_classes = f.readlines()
        return modelo, nomes_classes
    except Exception as e:
        st.error(f"Erro ao carregar modelo e rótulos: {str(e)}")
        return None, None

def prever(modelo, dados, nomes_classes):
    try:
        previsao = modelo.predict(dados)
        indice = np.argmax(previsao)
        nome_classe = nomes_classes[indice]
        pontuacao_confianca = float(previsao[0][indice])
        return nome_classe.strip(), pontuacao_confianca
    except Exception as e:
        st.error(f"Erro durante a previsão: {str(e)}")
        return None, None

def preprocessar_imagem(arquivo_carregado):
    try:
        bytes_imagem = arquivo_carregado.getvalue()
        imagem = Image.open(io.BytesIO(bytes_imagem)).convert("RGB")
        tamanho = (224, 224)
        imagem = ImageOps.fit(imagem, tamanho, Image.Resampling.LANCZOS)
        array_imagem = np.asarray(imagem)
        array_imagem_normalizado = (array_imagem.astype(np.float32) / 127.5) - 1
        dados = np.ndarray(shape=(1, 224, 224, 3), dtype=np.float32)
        dados[0] = array_imagem_normalizado
        return dados
    except Exception as e:
        st.error(f"Erro ao pré-processar imagem: {str(e)}")
        return None

def classificar_exame(id_paciente, opcao_modelo, arquivo_carregado):
    if arquivo_carregado is not None:
        st.write(f"Opção de modelo selecionada: {opcao_modelo}")
        
        setor, modelo = opcao_modelo.split('_', 1)
        if setor not in caminhos_modelos or modelo not in caminhos_modelos[setor]:
            st.error(f"Opção de modelo '{opcao_modelo}' não encontrada nos modelos disponíveis.")
            return None
        
        try:
            modelo, nomes_classes = carregar_modelo_e_rotulos(caminhos_modelos[setor][modelo], caminhos_rotulos[setor][modelo])
            
            if modelo is not None and nomes_classes is not None:
                imagem_processada = preprocessar_imagem(arquivo_carregado)
                
                if imagem_processada is not None:
                    nome_classe, pontuacao_confianca = prever(modelo, imagem_processada, nomes_classes)
                    
                    if nome_classe is not None and pontuacao_confianca is not None:
                        resultado = {
                            'data': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            'modelo': opcao_modelo,
                            'classe': nome_classe,
                            'confianca': pontuacao_confianca
                        }
                        
                        if id_paciente not in st.session_state.historico_paciente:
                            st.session_state.historico_paciente[id_paciente] = []
                        st.session_state.historico_paciente[id_paciente].append(resultado)
                        
                        st.success("Exame classificado com sucesso!")
                        return resultado
                    else:
                        st.error("Ocorreu um erro durante a previsão. Por favor, tente novamente.")
                else:
                    st.error("Falha ao pré-processar a imagem. Por favor, tente uma imagem diferente.")
            else:
                st.error("Falha ao carregar o modelo e rótulos. Por favor, verifique os arquivos e tente novamente.")
        except Exception as e:
            st.error(f"Ocorreu um erro durante a classificação: {str(e)}")
    else:
        st.error("Por favor, faça o upload de uma imagem primeiro.")
    return None

def hash_senha(senha):
    return hashlib.sha256(senha.encode()).hexdigest()

def ler_usuarios():
    result = sheet.values().get(spreadsheetId=SAMPLE_SPREADSHEET_ID, range=SAMPLE_RANGE_NAME).execute()
    valores = result.get('values', [])
    return pd.DataFrame(valores, columns=['Nome de Usuário', 'Senha', 'Último Login', 'Data de Expiração', 'Função', 'Setores'])

def atualizar_usuario(nome_usuario, dados):
    df = ler_usuarios()
    idx = df.index[df['Nome de Usuário'] == nome_usuario].tolist()[0]
    range_name = f'Sheet1!A{idx+2}:F{idx+2}'
    body = {'values': [dados]}
    sheet.values().update(spreadsheetId=SAMPLE_SPREADSHEET_ID, range=range_name, valueInputOption='USER_ENTERED', body=body).execute()

def adicionar_usuario(dados):
    range_name = 'Sheet1!A:F'
    body = {'values': [dados]}
    sheet.values().append(spreadsheetId=SAMPLE_SPREADSHEET_ID, range=range_name, valueInputOption='USER_ENTERED', body=body).execute()

def remover_usuario(nome_usuario):
    df = ler_usuarios()
    df = df[df['Nome de Usuário'] != nome_usuario]
    range_name = 'Sheet1!A2:F'
    body = {'values': df.values.tolist()}
    sheet.values().update(spreadsheetId=SAMPLE_SPREADSHEET_ID, range=range_name, valueInputOption='USER_ENTERED', body=body).execute()

def verificar_login(nome_usuario, senha):
    df = ler_usuarios()
    usuario = df[df['Nome de Usuário'] == nome_usuario]
    if not usuario.empty and usuario['Senha'].iloc[0] == hash_senha(senha):
        eh_admin = usuario['Função'].iloc[0] == 'admin'
        if not eh_admin and usuario['Data de Expiração'].iloc[0]:
            data_expiracao = datetime.strptime(usuario['Data de Expiração'].iloc[0], '%Y-%m-%d %H:%M:%S')
            if datetime.now() > data_expiracao:
                return False, "Conta expirada", []
        setores = usuario['Setores'].iloc[0].split(',') if usuario['Setores'].iloc[0] else []
        return True, "Sucesso", setores
    return False, "Credenciais inválidas", []

def atualizar_ultimo_login(nome_usuario):
    df = ler_usuarios()
    df.loc[df['Nome de Usuário'] == nome_usuario, 'Último Login'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    range_name = 'Sheet1!A2:F'
    body = {'values': df.values.tolist()}
    sheet.values().update(spreadsheetId=SAMPLE_SPREADSHEET_ID, range=range_name, valueInputOption='USER_ENTERED', body=body).execute()

def pagina_login():
    st.title("Login")
    nome_usuario = st.text_input("Nome de Usuário")
    senha = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        sucesso_login, mensagem, setores = verificar_login(nome_usuario, senha)
        if sucesso_login:
            st.session_state.logado = True
            st.session_state.nome_usuario = nome_usuario
            st.session_state.setores_usuario = setores
            atualizar_ultimo_login(nome_usuario)
            st.success("Login realizado com sucesso!")
        else:
            st.error(mensagem)

def visualizar_historico_paciente(id_paciente):
    if id_paciente in st.session_state.historico_paciente:
        historico = st.session_state.historico_paciente[id_paciente]
        df = pd.DataFrame(historico)
        st.dataframe(df)
        
        st.subheader("Visualização do Histórico de Exames do Paciente")
        fig, ax = plt.subplots(figsize=(10, 6))
        sns.scatterplot(data=df, x='data', y='confianca', hue='modelo', size='confianca', ax=ax)
        ax.set_title(f"Confiança dos Exames ao Longo do Tempo para o Paciente {id_paciente}")
        ax.set_xlabel("Data")
        ax.set_ylabel("Pontuação de Confiança")
        st.pyplot(fig)
    else:
        st.info("Nenhum histórico encontrado para este paciente.")

def comparar_pacientes():
    st.subheader("Comparar Pacientes")
    ids_pacientes = list(st.session_state.historico_paciente.keys())
    if len(ids_pacientes) < 2:
        st.warning("É necessário pelo menos dois pacientes com histórico para comparar.")
        return
    
    paciente1 = st.selectbox("Selecione o primeiro paciente", ids_pacientes)
    paciente2 = st.selectbox("Selecione o segundo paciente", [id for id in ids_pacientes if id != paciente1])
    
    if st.button("Comparar"):
        df1 = pd.DataFrame(st.session_state.historico_paciente[paciente1])
        df2 = pd.DataFrame(st.session_state.historico_paciente[paciente2])
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
        
        sns.boxplot(data=df1, x='modelo', y='confianca', ax=ax1)
        ax1.set_title(f"Paciente {paciente1}")
        ax1.set_ylim(0, 1)
        
        sns.boxplot(data=df2, x='modelo', y='confianca', ax=ax2)
        ax2.set_title(f"Paciente {paciente2}")
        ax2.set_ylim(0, 1)
        
        st.pyplot(fig)

# ... [Previous code remains the same]

def gerenciar_usuarios():
    st.header("Gerenciamento de Usuários")
    
    try:
        df_usuario = ler_usuarios()
        st.dataframe(df_usuario)

        st.subheader("Adicionar Usuário")
        novo_nome_usuario = st.text_input("Novo Nome de Usuário")
        nova_senha = st.text_input("Nova Senha", type="password")
        nova_funcao = st.selectbox("Função", ["usuário", "admin"])
        dias_validade = st.number_input("Validade da Conta (dias)", min_value=1, value=7, step=1)
        novos_setores = st.multiselect("Setores", ["Pneumologia", "Neurologia", "Ortopedia"])
        
        if st.button("Adicionar Usuário"):
            if novo_nome_usuario and nova_senha:
                senha_hash = hash_senha(nova_senha)
                data_expiracao = (datetime.now() + timedelta(days=dias_validade)).strftime("%Y-%m-%d %H:%M:%S") if nova_funcao != "admin" else ""
                adicionar_usuario([novo_nome_usuario, senha_hash, "", data_expiracao, nova_funcao, ",".join(novos_setores)])
                st.success("Usuário adicionado com sucesso!")
            else:
                st.error("Por favor, forneça nome de usuário e senha.")

        st.subheader("Editar Usuário")
        editar_nome_usuario = st.selectbox("Selecione o Usuário para Editar", df_usuario['Nome de Usuário'].tolist())
        senha_editada = st.text_input("Nova Senha para o Usuário Selecionado", type="password")
        funcao_editada = st.selectbox("Nova Função", ["usuário", "admin"])
        validade_editada = st.number_input("Nova Validade da Conta (dias)", min_value=1, value=7, step=1)
        setores_editados = st.multiselect("Novos Setores", ["Pneumologia", "Neurologia", "Ortopedia"])
        
        if st.button("Editar Usuário"):
            if senha_editada:
                senha_hash = hash_senha(senha_editada)
                data_expiracao = (datetime.now() + timedelta(days=validade_editada)).strftime("%Y-%m-%d %H:%M:%S") if funcao_editada != "admin" else ""
                atualizar_usuario(editar_nome_usuario, [editar_nome_usuario, senha_hash, "", data_expiracao, funcao_editada, ",".join(setores_editados)])
                st.success("Usuário editado com sucesso!")
            else:
                st.error("Por favor, forneça uma nova senha.")

        st.subheader("Remover Usuário")
        remover_nome_usuario = st.selectbox("Selecione o Usuário para Remover", df_usuario['Nome de Usuário'].tolist())
        if st.button("Remover Usuário"):
            remover_usuario(remover_nome_usuario)
            st.success("Usuário removido com sucesso!")
    
    except Exception as e:
        st.error(f"Ocorreu um erro durante o gerenciamento de usuários: {str(e)}")

def main():
    if not st.session_state.get('logado', False):
        pagina_login()
    else:
        st.title("MedVision")
        st.sidebar.title(f"Bem-vindo, {st.session_state.nome_usuario}")
        if st.sidebar.button("Sair"):
            st.session_state.logado = False
            st.session_state.nome_usuario = None
            st.session_state.setores_usuario = []
            st.rerun()

        # Menu lateral
        if 'opcao_menu' not in st.session_state:
            st.session_state.opcao_menu = "Classificar Exame"

        opcoes = ["Classificar Exame", "Visualizar Histórico do Paciente", "Comparar Pacientes"]
        if st.session_state.nome_usuario == 'admin':
            opcoes.append("Gerenciamento de Usuários")

        st.session_state.opcao_menu = st.sidebar.radio("Escolha uma opção:", opcoes, key="radio_menu")

        if st.session_state.opcao_menu == "Classificar Exame":
            st.header("Classificar Exame")
            
            setor = st.selectbox("Escolha um setor:", st.session_state.setores_usuario)
            
            if setor:
                id_paciente = st.text_input("Digite o ID do Paciente:")
                opcao_modelo = st.selectbox("Escolha um modelo para análise:", list(caminhos_modelos[setor].keys()))
                arquivo_carregado = st.file_uploader("Faça upload da imagem", type=["jpg", "jpeg", "png"])
                
                if st.button("Classificar"):
                    classificar_exame(id_paciente, f"{setor}_{opcao_modelo}", arquivo_carregado)
            else:
                st.warning("Você não tem acesso a nenhum setor.")

        elif st.session_state.opcao_menu == "Visualizar Histórico do Paciente":
            st.header("Histórico do Paciente")
            id_paciente = st.text_input("Digite o ID do Paciente:")
            if st.button("Visualizar Histórico"):
                visualizar_historico_paciente(id_paciente)

        elif st.session_state.opcao_menu == "Comparar Pacientes":
            comparar_pacientes()

        elif st.session_state.opcao_menu == "Gerenciamento de Usuários":
            gerenciar_usuarios()

if __name__ == "__main__":
    main()
