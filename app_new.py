import streamlit as st
import streamlit_authenticator as stauth
from PIL import Image
import numpy as np
from keras.models import load_model
import sqlite3
from datetime import datetime
import matplotlib.pyplot as plt
import os
import pandas as pd
import seaborn as sns
from sklearn.metrics import confusion_matrix
import io
import base64
import hashlib
import yaml
from yaml.loader import SafeLoader

# Inicializar o banco de dados
def init_database():
    conn = sqlite3.connect('medvision_ai.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS patients
                 (id INTEGER PRIMARY KEY, name TEXT, date TEXT, age INTEGER, gender TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS analyses
                 (id INTEGER PRIMARY KEY, patient_id INTEGER, 
                  disease TEXT, prediction TEXT, confidence REAL, 
                  date TEXT, image BLOB)''')
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, email TEXT UNIQUE)''')
    conn.commit()
    conn.close()

# Função para carregar modelos e rótulos
def load_models():
    models = {}
    disease_configs = {
        "Tuberculose": {
            "model": "C:/Users/RORO_LINDO/PycharmProjects/Curso____/MedVision IA/tuberculose_model.h5",
            "labels": "C:/Users/RORO_LINDO/PycharmProjects/Curso____/MedVision IA/tuberculose_labels.txt"
        },
        "Câncer": {
            "model": "C:/Users/RORO_LINDO/PycharmProjects/Curso____/MedVision IA/cancer_model.h5",
            "labels": "C:/Users/RORO_LINDO/PycharmProjects/Curso____/MedVision IA/cancer_labels.txt"
        },
        "Pneumonia": {
            "model": "C:/Users/RORO_LINDO/PycharmProjects/Curso____/MedVision IA/pneumonia_model.h5",
            "labels": "C:/Users/RORO_LINDO/PycharmProjects/Curso____/MedVision IA/pneumonia_labels.txt"
        }
    }

    for disease, config in disease_configs.items():
        model_path = config["model"]
        label_path = config["labels"]

        if os.path.exists(model_path) and os.path.exists(label_path):
            try:
                model = load_model(model_path, compile=False)
                with open(label_path, "r") as f:
                    labels = [line.strip() for line in f.readlines()]
                models[disease] = (model, labels)
                st.sidebar.success(f"Modelo de {disease} carregado com sucesso.")
            except Exception as e:
                st.sidebar.error(f"Erro ao carregar o modelo de {disease}: {str(e)}")
        else:
            st.sidebar.warning(f"Arquivos do modelo de {disease} não encontrados.")
    return models

# Função para gerar hash da senha
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Função para registrar novo usuário
def register_user(username, password, email):
    conn = sqlite3.connect('medvision_ai.db')
    c = conn.cursor()
    try:
        hashed_password = hash_password(password)
        c.execute("INSERT INTO users (username, password, email) VALUES (?, ?, ?)",
                  (username, hashed_password, email))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

# Função para verificar credenciais do usuário
def verify_user(username, password):
    conn = sqlite3.connect('medvision_ai.db')
    c = conn.cursor()
    c.execute("SELECT password FROM users WHERE username = ?", (username,))
    result = c.fetchone()
    conn.close()
    if result:
        return result[0] == hash_password(password)
    return False

# Função para adicionar paciente
def add_patient(name, age, gender):
    try:
        conn = sqlite3.connect('medvision_ai.db')
        c = conn.cursor()
        c.execute("INSERT INTO patients (name, date, age, gender) VALUES (?, ?, ?, ?)",
                  (name, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), age, gender))
        conn.commit()
        patient_id = c.lastrowid
        return patient_id
    except sqlite3.Error as e:
        st.error(f"Erro ao adicionar paciente: {e}")
        return None
    finally:
        conn.close()

# Função para salvar análise no banco de dados
def save_analysis(patient_id, disease, prediction, confidence, image):
    conn = sqlite3.connect('medvision_ai.db')
    c = conn.cursor()
    image_bytes = io.BytesIO()
    image.save(image_bytes, format='PNG')
    image_blob = image_bytes.getvalue()
    c.execute(
        "INSERT INTO analyses (patient_id, disease, prediction, confidence, date, image) VALUES (?, ?, ?, ?, ?, ?)",
        (patient_id, disease, prediction, confidence, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), image_blob))
    conn.commit()
    conn.close()

# Função para analisar a imagem
def analyze_image(image, model_index, models):
    results = {}
    disease = list(models.keys())[model_index]
    model_instance, class_names = models[disease]

    image_array = np.asarray(image.resize((224, 224)))
    normalized_image_array = (image_array.astype(np.float32) / 127.5) - 1
    data = np.expand_dims(normalized_image_array, axis=0)

    prediction = model_instance.predict(data)
    index = np.argmax(prediction)
    class_name = class_names[index].strip()  # Limpar nome da classe
    confidence_score = float(prediction[0][index])

    results[disease] = (class_name, confidence_score)
    return results

# Função para exportar dados do paciente para CSV
def export_to_csv(df):
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="patient_data.csv">Download CSV File</a>'
    return href

# Função principal
def main():
    st.set_page_config(page_title="MedVision AI", layout="wide")
    st.title("MedVision AI - Análise Avançada de Raio-X")

    # Autenticação
    with open('config.yaml') as file:
        config = yaml.load(file, Loader=SafeLoader)

    authenticator = stauth.Authenticate(
        config['credentials'],
        config['cookie']['name'],
        config['cookie']['key'],
        config['cookie']['expiry_days'],
        config['preauthorized']
    )

    name, authentication_status, username = authenticator.login('Login', 'main')

    if authentication_status:
        authenticator.logout('Logout', 'main')
        st.write(f'Welcome *{name}*')

        # Carregar modelos
        models = load_models()

        if not models:
            st.error("Nenhum modelo foi carregado. Por favor, verifique se os arquivos dos modelos estão presentes no diretório.")
        else:
            st.success(f"{len(models)} modelos carregados com sucesso.")

        # Gerenciamento de Pacientes
        st.sidebar.header("Gerenciamento de Pacientes")
        new_patient_name = st.sidebar.text_input("Nome do Novo Paciente")
        new_patient_age = st.sidebar.number_input("Idade do Paciente", min_value=0, max_value=120)
        new_patient_gender = st.sidebar.selectbox("Gênero do Paciente", ["Masculino", "Feminino", "Outro"])
        patient_id = None  # Inicializa patient_id

        if st.sidebar.button("Adicionar Paciente"):
            if new_patient_name and new_patient_age:
                patient_id = add_patient(new_patient_name, new_patient_age, new_patient_gender)
                st.sidebar.success(f"Paciente {new_patient_name} adicionado com ID {patient_id}")
            else:
                st.sidebar.error("Por favor, preencha todos os campos do paciente")

        # Carregar imagem
        uploaded_file = st.file_uploader("Carregar Imagem de Raio-X", type=["png", "jpg", "jpeg"])

        if uploaded_file is not None:
            image = Image.open(uploaded_file)

            # Seleção do modelo
            model_options = list(models.keys())
            selected_model = st.selectbox("Escolha o Modelo de Análise", model_options)

            if st.button("Analisar Imagem"):
                model_index = model_options.index(selected_model)
                results = analyze_image(image, model_index, models)

                for disease, (prediction, confidence) in results.items():
                    st.success(f"Diagnóstico para {disease}: {prediction} com {confidence:.2f}% de confiança")
                    if patient_id:
                        save_analysis(patient_id, disease, prediction, confidence, image)

                # Visualizar histórico de análises do paciente
                if patient_id:
                    patient_history = get_patient_history(patient_id)
                    st.write("Histórico de Análises do Paciente")
                    st.dataframe(patient_history)

        # Exibir e exportar dados do paciente
        if st.button("Exportar Dados para CSV"):
            if patient_id:
                patient_data = get_patient_data(patient_id)
                if patient_data is not None:
                    df = pd.DataFrame(patient_data)
                    st.markdown(export_to_csv(df), unsafe_allow_html=True)
                else:
                    st.error("Não foi possível encontrar dados para exportar.")

    elif authentication_status == False:
        st.error('Usuário/senha incorretos.')
    elif authentication_status == None:
        st.warning('Por favor, insira seu nome de usuário e senha.')

        if st.button("Registrar Novo Usuário"):
            registration_form()

# Inicializar o banco de dados ao iniciar o aplicativo
init_database()

if __name__ == "__main__":
    main()
