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
import matplotlib.pyplot as plt
import seaborn as sns
import json
import requests

# URL do webhook do Zapier
zapier_webhook_url = "https://zapier.com/editor/261273371/draft/_GEN_1728345153400/fields"

# Função para carregar logins do arquivo JSON
def load_logins():
    if not os.path.exists('logins.json'):
        with open('logins.json', 'w') as file:
            json.dump({"logins": []}, file)

    with open('logins.json', 'r') as file:
        data = json.load(file)
    return data['logins']

# Função para enviar dados para o Zapier
def send_data_to_zapier(data):
    response = requests.post(zapier_webhook_url, json=data)
    return response.status_code

# Lógica do seu aplicativo Streamlit
st.title("Meu Aplicativo de Saúde")

# Carregar e exibir logins
logins = load_logins()
if logins:
    st.write("Logins recebidos:")
    for login in logins:
        st.write(f"Usuário: {login['username']}, Senha: {login['password']}")
else:
    st.write("Nenhum login recebido ainda.")

# Formulário para adicionar novo login
username = st.text_input("Usuário")
password = st.text_input("Senha", type='password')
if st.button("Adicionar Login"):
    new_login = {"username": username, "password": password}
    
    # Adiciona novo login ao arquivo
    logins.append(new_login)
    with open('logins.json', 'w') as file:
        json.dump({"logins": logins}, file)

    # Envia dados para o Zapier
    response_code = send_data_to_zapier(new_login)
    if response_code == 200:
        st.success("Login enviado com sucesso para o Zapier!")
    else:
        st.error("Erro ao enviar o login para o Zapier.")

# Disable scientific notation for clarity
np.set_printoptions(suppress=True)

# Initialize session state
if 'patient_history' not in st.session_state:
    st.session_state.patient_history = {}
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'username' not in st.session_state:
    st.session_state.username = None

# File to store login information
LOGIN_FILE = 'login_info.xlsx'

# Definição dos caminhos dos modelos e rótulos
model_paths = {
    "Pneumonia": "pneumonia_model.h5",
    "Tuberculosis": "tuberculose_model.h5",
    "Cancer": "cancer_model.h5"
}

label_paths = {
    "Pneumonia": "pneumonia_labels.txt",
    "Tuberculosis": "tuberculose_labels.txt",
    "Cancer": "cancer_labels.txt"
}

def custom_depthwise_conv2d(*args, **kwargs):
    kwargs.pop('groups', None)
    return DepthwiseConv2D(*args, **kwargs)

def load_model_and_labels(model_path, labels_path):
    try:
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Arquivo de modelo não encontrado: {model_path}")
        if not os.path.exists(labels_path):
            raise FileNotFoundError(f"Labels não encontrados: {labels_path}")
        
        with custom_object_scope({'DepthwiseConv2D': custom_depthwise_conv2d}):
            model = load_model(model_path, compile=False)
        
        with open(labels_path, "r") as f:
            class_names = f.readlines()
        return model, class_names
    except Exception as e:
        st.error(f"Erro ao carregar modelo e labels: {str(e)}")
        return None, None

def predict(model, data, class_names):
    try:
        # Faz a predição
        prediction = model.predict(data)
        
        # Obtém o índice da classe com maior probabilidade
        index = np.argmax(prediction)
        
        # Obtém o nome da classe
        class_name = class_names[index]
        
        # Obtém a pontuação de confiança
        confidence_score = float(prediction[0][index])
        
        return class_name.strip(), confidence_score
    except Exception as e:
        st.error(f"Erro durante a predição: {str(e)}")
        return None, None

def preprocess_image(uploaded_file):
    try:
        # Lê o arquivo carregado como bytes
        image_bytes = uploaded_file.getvalue()
        
        # Abre a imagem usando PIL
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        
        # Redimensiona a imagem para 224x224 pixels
        size = (224, 224)
        image = ImageOps.fit(image, size, Image.Resampling.LANCZOS)
        
        # Converte a imagem para um array numpy
        image_array = np.asarray(image)
        
        # Normaliza os valores dos pixels
        normalized_image_array = (image_array.astype(np.float32) / 127.5) - 1
        
        # Cria um array 4D para entrada no modelo
        data = np.ndarray(shape=(1, 224, 224, 3), dtype=np.float32)
        data[0] = normalized_image_array
        
        return data
    except Exception as e:
        st.error(f"Erro ao pré-processar a imagem: {str(e)}")
        return None

def classify_exam(patient_id, model_option, uploaded_file):
    if uploaded_file is not None:
        st.write(f"Model option selected: {model_option}")
        
        if model_option not in model_paths or model_option not in label_paths:
            st.error(f"Model option '{model_option}' not found in available models.")
            return None
        
        try:
            model, class_names = load_model_and_labels(model_paths[model_option], label_paths[model_option])
            
            if model is not None and class_names is not None:
                processed_image = preprocess_image(uploaded_file)
                class_name, confidence_score = predict(model, processed_image, class_names)
                
                if class_name is not None and confidence_score is not None:
                    result = {
                        'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'model': model_option,
                        'class': class_name,
                        'confidence': confidence_score
                    }
                    
                    if patient_id not in st.session_state.patient_history:
                        st.session_state.patient_history[patient_id] = []
                    st.session_state.patient_history[patient_id].append(result)
                    
                    st.success("Exame classificado com sucesso!")
                    return result
                else:
                    st.error("Ocorreu um erro durante a predição. Por favor, tente novamente.")
            else:
                st.error("Falha ao carregar o modelo e os rótulos. Verifique os arquivos e tente novamente.")
        except Exception as e:
            st.error(f"Ocorreu um erro durante a classificação: {str(e)}")
    else:
        st.error("Por favor, faça o upload primeiro.")
    return None

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def init_login_file():
    if not os.path.exists(LOGIN_FILE):
        wb = Workbook()
        ws = wb.active
        ws.append(['Username', 'Password', 'Last Login', 'Expiry Date', 'Role'])
        admin_password = hash_password('123')
        ws.append(['admin', admin_password, '', '', 'admin'])
        wb.save(LOGIN_FILE)

def check_login(username, password):
    try:
        wb = load_workbook(LOGIN_FILE)
        ws = wb.active
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row[0] == username and row[1] == hash_password(password):
                is_admin = len(row) > 4 and row[4] == 'admin'
                
                if not is_admin:
                    if len(row) > 3 and row[3]:
                        expiry_date = row[3]
                        if isinstance(expiry_date, datetime) and datetime.now() > expiry_date:
                            return False, "Conta expirada"
                
                return True, "Sucesso"
        
        return False, "Credenciais inválidas"
    except Exception as e:
        st.error(f"Ocorreu um erro ao verificar o login: {str(e)}")
        return False, "Falha na verificação do login"

def login_page():
    st.title("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        login_success, message = check_login(username, password)
        if login_success:
            st.session_state.logged_in = True
            st.session_state.username = username
            update_last_login(username)
            st.success("Login realizado com sucesso!")
        else:
            st.error(message)

def update_last_login(username):
    wb = load_workbook(LOGIN_FILE)
    ws = wb.active
    for row in ws.iter_rows(min_row=2):
        if row[0] == username:
            row[2] = datetime.now()
            wb.save(LOGIN_FILE)
            break

# Função para exibir histórico de pacientes
def display_patient_history(patient_id):
    st.write(f"Histórico do Paciente: {patient_id}")
    
    if patient_id in st.session_state.patient_history:
        history = st.session_state.patient_history[patient_id]
        df_history = pd.DataFrame(history)
        
        if not df_history.empty:
            st.dataframe(df_history)
        else:
            st.write("Nenhum registro encontrado para este paciente.")
    else:
        st.write("Nenhum registro encontrado para este paciente.")

# Lógica de login
if st.session_state.logged_in:
    st.sidebar.title("Menu")
    menu_option = st.sidebar.selectbox("Escolha uma opção", ("Classificar Exame", "Histórico de Pacientes"))

    if menu_option == "Classificar Exame":
        st.header("Classificar Exame")
        
        # Formulário de upload de exames
        patient_id = st.text_input("ID do Paciente")
        model_option = st.selectbox("Modelo", list(model_paths.keys()))
        uploaded_file = st.file_uploader("Carregar Imagem do Exame", type=["jpg", "jpeg", "png"])
        
        if st.button("Classificar"):
            result = classify_exam(patient_id, model_option, uploaded_file)
            if result:
                st.write(f"Classe: {result['class']}, Confiança: {result['confidence']:.2f}")

    elif menu_option == "Histórico de Pacientes":
        st.header("Histórico de Pacientes")
        patient_id = st.text_input("ID do Paciente", "")
        
        if st.button("Buscar Histórico"):
            display_patient_history(patient_id)

else:
    init_login_file()
    login_page()
