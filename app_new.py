
import streamlit as st
import numpy as np
from PIL import Image
from keras.models import load_model
import plotly.graph_objs as go
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import hashlib
import os
import io
import matplotlib.pyplot as plt
import seaborn as sns

# Configuração da página
st.set_page_config(page_title="MedVision AI - Análise Avançada de Raio-X", layout="wide")

# Carregar o modelo e os nomes das classes
@st.cache_resource
def load_ai_model():
    model = load_model("keras_Model.h5", compile=False)
    class_names = open("labels.txt", "r").readlines()
    return model, class_names

model, class_names = load_ai_model()

# Funções do banco de dados
def init_database():
    conn = sqlite3.connect('medvision_ai.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS patients
                 (id INTEGER PRIMARY KEY, name TEXT, date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS analyses
                 (id INTEGER PRIMARY KEY, patient_id INTEGER, 
                  image_path TEXT, prediction TEXT, confidence REAL, 
                  date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (username TEXT PRIMARY KEY, password_hash TEXT, role TEXT, 
                  trial_expiration TEXT)''')
    conn.commit()
    conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Autenticação
def login(username, password):
    conn = sqlite3.connect('medvision_ai.db')
    c = conn.cursor()
    c.execute("SELECT password_hash, role, trial_expiration FROM users WHERE username = ?", (username,))
    user = c.fetchone()
    conn.close()

    if user and user[0] == hash_password(password):
        if user[2] and datetime.now() > datetime.strptime(user[2], "%Y-%m-%d %H:%M:%S"):
            st.error("Período de teste expirado. Por favor, contate o administrador.")
            return False
        st.session_state['logged_in'] = True
        st.session_state['username'] = username
        st.session_state['role'] = user[1]
        return True
    return False

def logout():
    for key in ['logged_in', 'username', 'role']:
        if key in st.session_state:
            del st.session_state[key]

# Aplicação principal
def main():
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False

    if not st.session_state['logged_in']:
        login_page()
    else:
        if st.session_state['role'] == 'admin':
            admin_page()
        else:
            user_page()

def login_page():
    st.title("MedVision AI - Login")
    username = st.text_input("Usuário")
    password = st.text_input("Senha", type="password")
    if st.button("Login"):
        if login(username, password):
            st.experimental_rerun()
        else:
            st.error("Usuário ou senha inválidos")
    
    if st.button("Registrar"):
        register_page()

def register_page():
    st.title("MedVision AI - Registro")
    new_username = st.text_input("Novo Usuário")
    new_password = st.text_input("Nova Senha", type="password")
    confirm_password = st.text_input("Confirmar Senha", type="password")

    if st.button("Registrar"):
        if new_password != confirm_password:
            st.error("As senhas não coincidem.")
        else:
            conn = sqlite3.connect('medvision_ai.db')
            c = conn.cursor()
            expiration_date = datetime.now() + timedelta(days=7)
            c.execute("INSERT INTO users (username, password_hash, role, trial_expiration) VALUES (?, ?, ?, ?)",
                      (new_username, hash_password(new_password), "user", expiration_date.strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
            conn.close()
            st.success(f"Conta {new_username} criada com sucesso! Você tem um período de teste de 7 dias.")

def admin_page():
    st.title("MedVision AI - Painel de Administração")

    if st.button("Logout"):
        logout()
        st.experimental_rerun()

    if st.button("Mudar para Aplicação Principal"):
        st.session_state['role'] = 'user'
        st.experimental_rerun()

    st.header("Gerenciamento de Usuários")
    
    conn = sqlite3.connect('medvision_ai.db')
    c = conn.cursor()
    c.execute("SELECT username, role, trial_expiration FROM users")
    users = c.fetchall()
    conn.close()

    user_df = pd.DataFrame(users, columns=['Usuário', 'Função', 'Expiração do Teste'])
    st.dataframe(user_df)

    st.subheader("Adicionar Novo Usuário")
    new_username = st.text_input("Novo Usuário")
    new_password = st.text_input("Nova Senha", type="password")
    new_role = st.selectbox("Função", ["user", "admin"])

    if st.button("Adicionar Usuário"):
        if new_username and new_password:
            conn = sqlite3.connect('medvision_ai.db')
            c = conn.cursor()
            c.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                      (new_username, hash_password(new_password), new_role))
            conn.commit()
            conn.close()
            st.success(f"Usuário {new_username} adicionado com sucesso")
            st.experimental_rerun()
        else:
            st.error("Todos os campos são obrigatórios")

def user_page():
    st.title("MedVision AI - Análise Avançada de Raio-X")

    if st.button("Logout"):
        logout()
        st.experimental_rerun()

    col1, col2 = st.columns(2)

    with col1:
        st.header("Upload e Análise de Imagem")
        uploaded_file = st.file_uploader("Escolha uma imagem de raio-X", type=["jpg", "jpeg", "png"])
        if uploaded_file is not None:
            image = Image.open(uploaded_file)
            st.image(image, caption="Imagem de raio-X carregada", use_column_width=True)

            if st.button("Analisar Imagem"):
                with st.spinner("Analisando..."):
                    image_array = np.asarray(image.resize((224, 224)))
                    normalized_image_array = (image_array.astype(np.float32) / 127.5) - 1
                    data = np.expand_dims(normalized_image_array, axis=0)

                    prediction = model.predict(data)
                    index = np.argmax(prediction)
                    class_name = class_names[index].strip()
                    confidence_score = float(prediction[0][index])

                    st.success(f"Previsão: {class_name}")
                    st.info(f"Confiança: {confidence_score:.2f}")

                    # Salvar análise no banco de dados
                    save_analysis(st.session_state['username'], class_name, confidence_score)

    with col2:
        st.header("Histórico do Paciente")
        patient_name = st.text_input("Nome do Paciente")
        if st.button("Adicionar Paciente"):
            add_patient(patient_name)

        patients = get_patients()
        selected_patient = st.selectbox("Selecionar Paciente", patients)

        if selected_patient:
            patient_id = int(selected_patient.split(':')[0])
            analyses = get_patient_analyses(patient_id)
            if analyses:
                analyses_df = pd.DataFrame(analyses, columns=['Data', 'Previsão', 'Confiança'])
                st.dataframe(analyses_df)
            else:
                st.info("Nenhuma análise encontrada para este paciente.")

    st.header("Estatísticas")
    create_statistics()

def save_analysis(username, prediction, confidence):
    conn = sqlite3.connect('medvision_ai.db')
    c = conn.cursor()
    c.execute("INSERT INTO analyses (patient_id, prediction, confidence, date) VALUES (?, ?, ?, ?)",
              (1, prediction, confidence, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def add_patient(name):
    conn = sqlite3.connect('medvision_ai.db')
    c = conn.cursor()
    c.execute("INSERT INTO patients (name, date) VALUES (?, ?)",
              (name, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    st.success(f"Paciente {name} adicionado com sucesso")

def get_patients():
    conn = sqlite3.connect('medvision_ai.db')
    c = conn.cursor()
    c.execute("SELECT id, name FROM patients ORDER BY name")
    patients = c.fetchall()
    conn.close()
    return [f"{id}: {name}" for id, name in patients]

def get_patient_analyses(patient_id):
    conn = sqlite3.connect('medvision_ai.db')
    c = conn.cursor()
    c.execute("SELECT date, prediction, confidence FROM analyses WHERE patient_id = ? ORDER BY date DESC", (patient_id,))
    analyses = c.fetchall()
    conn.close()
    return analyses

def create_statistics():
    conn = sqlite3.connect('medvision_ai.db')
    df = pd.read_sql_query("SELECT prediction, COUNT(*) as count FROM analyses GROUP BY prediction", conn)
    conn.close()

    fig = go.Figure(data=[go.Pie(labels=df['prediction'], values=df['count'])])
    fig.update_layout(title='Distribuição de Diagnósticos')
    st.plotly_chart(fig)

    # Gráfico de barras para confiança média por diagnóstico
    conn = sqlite3.connect('medvision_ai.db')
    df_confidence = pd.read_sql_query("SELECT prediction, AVG(confidence) as avg_confidence FROM analyses GROUP BY prediction", conn)
    conn.close()

    fig_confidence = go.Figure(data=[go.Bar(x=df_confidence['prediction'], y=df_confidence['avg_confidence'])])
    fig_confidence.update_layout(title='Confiança Média por Diagnóstico', xaxis_title='Diagnóstico', yaxis_title='Confiança Média')
    st.plotly_chart(fig_confidence)

    # Gráfico de linha para tendência de diagnósticos ao longo do tempo
    conn = sqlite3.connect('medvision_ai.db')
    df_trend = pd.read_sql_query("SELECT date, prediction FROM analyses ORDER BY date", conn)
    conn.close()

    df_trend['date'] = pd.to_datetime(df_trend['date'])
    df_trend = df_trend.groupby([df_trend['date'].dt.to_period('D'), 'prediction']).size().unstack(fill_value=0)

    fig_trend = go.Figure()
    for col in df_trend.columns:
        fig_trend.add_trace(go.Scatter(x=df_trend.index.astype(str), y=df_trend[col], mode='lines', name=col))
    
    fig_trend.update_layout(title='Tendência de Diagnósticos ao Longo do Tempo', xaxis_title='Data', yaxis_title='Número de Diagnósticos')
    st.plotly_chart(fig_trend)

if __name__ == "__main__":
    init_database()
    main()
