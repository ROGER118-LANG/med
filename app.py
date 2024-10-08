import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import pyrebase
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
                
                if processed_image is not None:
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
                        st.error("Ocorreu um erro durante a predição. Tente novamente.")
                else:
                    st.error("Falha ao pré-processar a imagem. Tente uma imagem diferente.")
            else:
                st.error("Falha ao carregar o modelo e labels. Verifique os arquivos e tente novamente.")
        except Exception as e:
            st.error(f"Ocorreu um erro durante a classificação: {str(e)}")
    else:
        st.error("Por favor, faça o upload de uma imagem primeiro.")
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
                # Verifica se a coluna de role existe e se o usuário é admin
                is_admin = len(row) > 4 and row[4] == 'admin'
                
                if not is_admin:
                    # Se não for admin, verifica a data de expiração (se existir)
                    if len(row) > 3 and row[3]:
                        expiry_date = row[3]
                        if isinstance(expiry_date, datetime) and datetime.now() > expiry_date:
                            return False, "Conta expirada"
                
                return True, "Sucesso"
        
        return False, "Credenciais inválidas"
    except Exception as e:
        st.error(f"Ocorreu um erro ao verificar o login: {str(e)}")
        return False, "Falha ao verificar o login"

def update_last_login(username):
    wb = load_workbook(LOGIN_FILE)
    ws = wb.active
    for row in ws.iter_rows(min_row=2):
        if row[0].value == username:
            row[2].value = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            break
    wb.save(LOGIN_FILE)

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

def view_patient_history(patient_id):
    if patient_id in st.session_state.patient_history:
        history = st.session_state.patient_history[patient_id]
        df = pd.DataFrame(history)
        st.dataframe(df)
        
        # Visualização do histórico do paciente
        st.subheader("Visualização do Histórico de Exames do Paciente")
        fig, ax = plt.subplots(figsize=(10, 6))
        sns.scatterplot(data=df, x='date', y='confidence', hue='model', size='confidence', ax=ax)
        ax.set_title(f"Confiança dos Exames ao Longo do Tempo para o Paciente {patient_id}")
        ax.set_xlabel("Data")
        ax.set_ylabel("Pontuação de Confiança")
        st.pyplot(fig)
    else:
        st.info("Nenhum histórico encontrado para este paciente.")

def compare_patients():
    st.subheader("Comparar Pacientes")
    patient_ids = list(st.session_state.patient_history.keys())
    if len(patient_ids) < 2:
        st.warning("É necessário pelo menos dois pacientes com histórico para comparar.")
        return
    
    patient1 = st.selectbox("Selecione o primeiro paciente", patient_ids)
    patient2 = st.selectbox("Selecione o segundo paciente", [id for id in patient_ids if id != patient1])
    
    if st.button("Comparar"):
        # Coletar dados dos pacientes
        history1 = st.session_state.patient_history[patient1]
        history2 = st.session_state.patient_history[patient2]
        
        df1 = pd.DataFrame(history1)
        df2 = pd.DataFrame(history2)
        
        # Visualização comparativa
        fig, ax = plt.subplots(figsize=(12, 8))
        sns.lineplot(data=df1, x='date', y='confidence', label=patient1, marker='o')
        sns.lineplot(data=df2, x='date', y='confidence', label=patient2, marker='o')
        ax.set_title(f"Comparação de Confiança dos Exames: {patient1} vs {patient2}")
        ax.set_xlabel("Data")
        ax.set_ylabel("Pontuação de Confiança")
        plt.xticks(rotation=45)
        st.pyplot(fig)

def main():
    # Inicializa o Firebase
    cred = credentials.Certificate('path_to_your_firebase_credentials.json')
    firebase_admin.initialize_app(cred)
    firebase_config = {
        'apiKey': "YOUR_API_KEY",
        'authDomain': "YOUR_AUTH_DOMAIN",
        'databaseURL': "YOUR_DATABASE_URL",
        'projectId': "YOUR_PROJECT_ID",
        'storageBucket': "YOUR_STORAGE_BUCKET",
        'messagingSenderId': "YOUR_MESSAGING_SENDER_ID",
        'appId': "YOUR_APP_ID",
        'measurementId': "YOUR_MEASUREMENT_ID"
    }
    
    pyrebase_app = pyrebase.initialize_app(firebase_config)
    db = pyrebase_app.database()

    st.title("Classificação de Exames de Raio-X")
    
    init_login_file()
    
    if not st.session_state.logged_in:
        login_page()
    else:
        st.sidebar.title("Menu")
        option = st.sidebar.selectbox("Escolha uma opção", ["Classificar Exame", "Histórico do Paciente", "Comparar Pacientes"])

        if option == "Classificar Exame":
            patient_id = st.text_input("ID do Paciente")
            model_option = st.selectbox("Selecione o modelo", list(model_paths.keys()))
            uploaded_file = st.file_uploader("Escolha uma imagem de raio-X", type=["jpg", "jpeg", "png"])
            
            if st.button("Classificar"):
                result = classify_exam(patient_id, model_option, uploaded_file)
                if result:
                    st.write(f"Classe: {result['class']}, Confiança: {result['confidence']:.2f}")
        
        elif option == "Histórico do Paciente":
            patient_id = st.text_input("ID do Paciente", value=list(st.session_state.patient_history.keys())[0] if st.session_state.patient_history else "")
            view_patient_history(patient_id)

        elif option == "Comparar Pacientes":
            compare_patients()

if __name__ == "__main__":
    main()
