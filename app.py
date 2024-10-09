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
import psycopg2
from psycopg2 import sql

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

# PostgreSQL connection parameters
DB_PARAMS = {
    'dbname': 'your_database_name',
    'user': 'your_username',
    'password': 'your_password',
    'host': 'your_host',
    'port': 'your_port'
}

# Definition of model and label paths
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
        "Braço Fraturado": "fractured_arm_model.h5"
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
        "Braço Fraturado": "fractured_arm_labels.txt"
    }
}

def get_db_connection():
    return psycopg2.connect(**DB_PARAMS)

def initialize_database():
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id SERIAL PRIMARY KEY,
        nome_usuario VARCHAR(50) UNIQUE NOT NULL,
        senha VARCHAR(64) NOT NULL,
        ultimo_login TIMESTAMP,
        data_expiracao TIMESTAMP,
        funcao VARCHAR(20) NOT NULL,
        setores TEXT
    )
    """)
    
    cur.execute("SELECT * FROM usuarios WHERE nome_usuario = 'admin'")
    if cur.fetchone() is None:
        senha_admin = hash_senha('123')
        cur.execute("""
        INSERT INTO usuarios (nome_usuario, senha, funcao, setores)
        VALUES ('admin', %s, 'admin', 'Pneumologia,Neurologia,Ortopedia')
        """, (senha_admin,))
    
    conn.commit()
    cur.close()
    conn.close()

def hash_senha(senha):
    return hashlib.sha256(senha.encode()).hexdigest()

def verificar_login(nome_usuario, senha):
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
    SELECT * FROM usuarios WHERE nome_usuario = %s
    """, (nome_usuario,))
    
    user = cur.fetchone()
    
    if user and user[2] == hash_senha(senha):
        eh_admin = user[5] == 'admin'
        
        if not eh_admin and user[4]:
            if datetime.now() > user[4]:
                cur.close()
                conn.close()
                return False, "Conta expirada", []
        
        setores = user[6].split(',') if user[6] else []
        
        cur.close()
        conn.close()
        return True, "Sucesso", setores
    
    cur.close()
    conn.close()
    return False, "Credenciais inválidas", []

def atualizar_ultimo_login(nome_usuario):
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
    UPDATE usuarios SET ultimo_login = %s WHERE nome_usuario = %s
    """, (datetime.now(), nome_usuario))
    
    conn.commit()
    cur.close()
    conn.close()

def adicionar_usuario(nome_usuario, senha, funcao, dias_validade, setores):
    conn = get_db_connection()
    cur = conn.cursor()
    
    senha_hash = hash_senha(senha)
    data_expiracao = datetime.now() + timedelta(days=dias_validade) if funcao != "admin" else None
    
    try:
        cur.execute("""
        INSERT INTO usuarios (nome_usuario, senha, data_expiracao, funcao, setores)
        VALUES (%s, %s, %s, %s, %s)
        """, (nome_usuario, senha_hash, data_expiracao, funcao, ",".join(setores)))
        
        conn.commit()
        cur.close()
        conn.close()
        return True, "Usuário adicionado com sucesso!"
    except psycopg2.IntegrityError:
        conn.rollback()
        cur.close()
        conn.close()
        return False, "Nome de usuário já existe."
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        return False, f"Erro ao adicionar usuário: {str(e)}"

def editar_usuario(nome_usuario, nova_senha, nova_funcao, nova_validade, novos_setores):
    conn = get_db_connection()
    cur = conn.cursor()
    
    senha_hash = hash_senha(nova_senha)
    nova_data_expiracao = datetime.now() + timedelta(days=nova_validade) if nova_funcao != "admin" else None
    
    try:
        cur.execute("""
        UPDATE usuarios 
        SET senha = %s, data_expiracao = %s, funcao = %s, setores = %s
        WHERE nome_usuario = %s
        """, (senha_hash, nova_data_expiracao, nova_funcao, ",".join(novos_setores), nome_usuario))
        
        conn.commit()
        cur.close()
        conn.close()
        return True, "Usuário editado com sucesso!"
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        return False, f"Erro ao editar usuário: {str(e)}"

def remover_usuario(nome_usuario):
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
        DELETE FROM usuarios WHERE nome_usuario = %s
        """, (nome_usuario,))
        
        conn.commit()
        cur.close()
        conn.close()
        return True, "Usuário removido com sucesso!"
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        return False, f"Erro ao remover usuário: {str(e)}"

def obter_todos_usuarios():
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT nome_usuario, ultimo_login, data_expiracao, funcao, setores FROM usuarios")
    usuarios = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return usuarios

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

def gerenciar_usuarios():
    st.header("Gerenciamento de Usuários")
    
    usuarios = obter_todos_usuarios()
    df_usuario = pd.DataFrame(usuarios, columns=["Nome de Usuário", "Último Login", "Data de Expiração", "Função", "Setores"])
    st.dataframe(df_usuario)
    
    st.subheader("Adicionar Usuário")
    novo_nome_usuario = st.text_input("Novo Nome de Usuário")
    nova_senha = st.text_input("Nova Senha", type="password")
    nova_funcao = st.selectbox("Função", ["usuário", "admin"])
    dias_validade = st.number_input("Validade da Conta (dias)", min_value=1, value=7, step=1)
    novos_setores = st.multiselect("Setores", ["Pneumologia", "Neurologia", "Ortopedia"])
    
    if st.button("Adicionar Usuário"):
        if novo_nome_usuario and nova_senha:
            sucesso, mensagem = adicionar_usuario(novo_nome_usuario, nova_senha, nova_funcao, dias_validade, novos_setores)
            if sucesso:
                st.success(mensagem)
            else:
                st.error(mensagem)
        else:
            st.error("Por favor, forneça nome de usuário e senha.")
    
    st.subheader("Editar Usuário")
    editar_nome_usuario = st.selectbox("Selecione o Usuário para Editar", [user[0] for user in usuarios])
    senha_editada = st.text_input("Nova Senha para o Usuário Selecionado", type="password")
    funcao_editada = st.selectbox("Nova Função", ["usuário", "admin"])
    validade_editada = st.number_input("Nova Validade da Conta (dias)", min_value=1, value=7, step=1)
    setores_editados = st.multiselect("Novos Setores", ["Pneumologia", "Neurologia", "Ortopedia"])
    
    if st.button("Editar Usuário"):
        if senha_editada:
            sucesso, mensagem = editar_usuario(editar_nome_usuario, senha_editada, funcao_editada, validade_editada, setores_editados)
            if sucesso:
                st.success(mensagem)
            else:
                st.error(mensagem)
        else:
            st.error("Por favor, forneça uma nova senha.")
    
    st.subheader("Remover Usuário")
    remover_nome_usuario = st.selectbox("Selecione o Usuário para Remover", [user[0] for user in usuarios])
    if st.button("Remover Usuário"):
        sucesso, mensagem = remover_usuario(remover_nome_usuario)
        if sucesso:
            st.success(mensagem)
        else:
            st.error(mensagem)

def main():
    initialize_database()
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
