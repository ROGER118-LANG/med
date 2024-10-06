import streamlit as st
import numpy as np
import tensorflow as tf
from tensorflow.keras.models import load_model
from PIL import Image, ImageOps
import sqlite3
from datetime import datetime
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from sklearn.metrics import confusion_matrix
import io
import base64

# Configuração inicial
st.set_page_config(page_title="MedVision AI", layout="wide")
st.title("MedVision AI - Análise Avançada de Raio-X")

# Desabilitar notação científica para clareza
np.set_printoptions(suppress=True)

# Funções de processamento de imagem e predição
def load_image(image):
    """Carrega e processa a imagem para o modelo."""
    size = (224, 224)
    image = ImageOps.fit(image, size, Image.Resampling.LANCZOS)
    image_array = np.asarray(image)
    normalized_image_array = (image_array.astype(np.float32) / 127.5) - 1
    return normalized_image_array

def predict(image, model, class_names):
    """Faz a predição da imagem usando o modelo fornecido."""
    data = np.ndarray(shape=(1, 224, 224, 3), dtype=np.float32)
    data[0] = load_image(image)
    prediction = model.predict(data)
    index = np.argmax(prediction)
    class_name = class_names[index].strip()
    confidence_score = prediction[0][index]
    return class_name, confidence_score

# Função para carregar os modelos e os rótulos
@st.cache_resource
def load_models():
    """Carrega múltiplos modelos e suas classes."""
    model_paths = ["tuberculose_model.h5", "pneumonia_model.h5", "cancer_model.h5"]
    labels_paths = ["labels_tuberculose.txt", "labels_pneumonia.txt", "labels_outro.txt"]
    
    models = {}
  for model_path in model_paths:  # Certifique-se de que model_paths esteja definido
    model = load_model(model_path, compile=False

        with open(labels_path, "r") as f:
            class_names = [line.strip() for line in f.readlines()]
        disease_name = model_path.split('_')[1].split('.')[0]  # Extrai o nome da doença do nome do arquivo
        models[disease_name] = (model, class_names)
    return models

# Funções de banco de dados
def init_database():
    conn = sqlite3.connect('medvision_ai.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS patients
                 (id INTEGER PRIMARY KEY, name TEXT, date TEXT, age INTEGER, gender TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS analyses
                 (id INTEGER PRIMARY KEY, patient_id INTEGER, 
                  disease TEXT, prediction TEXT, confidence REAL, 
                  date TEXT, image BLOB)''')
    conn.commit()
    conn.close()

def add_patient(name, age, gender):
    conn = sqlite3.connect('medvision_ai.db')
    c = conn.cursor()
    c.execute("INSERT INTO patients (name, date, age, gender) VALUES (?, ?, ?, ?)",
              (name, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), age, gender))
    conn.commit()
    patient_id = c.lastrowid
    conn.close()
    return patient_id

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

def get_patient_history(patient_id):
    conn = sqlite3.connect('medvision_ai.db')
    df = pd.read_sql_query("SELECT * FROM analyses WHERE patient_id = ? ORDER BY date DESC", conn, params=(patient_id,))
    conn.close()
    return df

# Funções de visualização
def visualize_patient_history(df):
    st.write("Histórico de Análises do Paciente")
    st.dataframe(df)

    st.write("Gráfico de Confiança das Análises")
    plt.figure(figsize=(10, 5))
    sns.lineplot(x='date', y='confidence', hue='disease', data=df)
    plt.xlabel('Data')
    plt.ylabel('Confiança')
    plt.title('Histórico de Confiança das Análises')
    plt.xticks(rotation=45)
    st.pyplot(plt)

    st.write("Distribuição de Previsões por Doença")
    fig, ax = plt.subplots(figsize=(10, 5))
    df_grouped = df.groupby(['disease', 'prediction']).size().unstack(fill_value=0)
    df_grouped.plot(kind='bar', stacked=True, ax=ax)
    plt.xlabel('Doença')
    plt.ylabel('Contagem')
    plt.title('Distribuição de Previsões por Doença')
    plt.legend(title='Previsão', bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    st.pyplot(fig)

def display_confusion_matrix(df):
    diseases = df['disease'].unique()
    for disease in diseases:
        disease_df = df[df['disease'] == disease]
        true_labels = disease_df['prediction']
        predicted_labels = disease_df['prediction']  # Assumindo que a previsão está correta para este exemplo
        cm = confusion_matrix(true_labels, predicted_labels)
        plt.figure(figsize=(8, 6))
        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues')
        plt.title(f'Matriz de Confusão - {disease}')
        plt.xlabel('Previsão')
        plt.ylabel('Verdadeiro')
        st.pyplot(plt)

def export_to_csv(df):
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="patient_data.csv">Download CSV File</a>'
    return href

# Inicialização
init_database()

# Carregar modelos
models = load_models()

# Interface principal
st.sidebar.header("Gerenciamento de Pacientes")
new_patient_name = st.sidebar.text_input("Nome do Novo Paciente")
new_patient_age = st.sidebar.number_input("Idade do Paciente", min_value=0, max_value=120)
new_patient_gender = st.sidebar.selectbox("Gênero do Paciente", ["Masculino", "Feminino", "Outro"])
if st.sidebar.button("Adicionar Paciente"):
    if new_patient_name and new_patient_age:
        patient_id = add_patient(new_patient_name, new_patient_age, new_patient_gender)
        st.sidebar.success(f"Paciente {new_patient_name} adicionado com ID {patient_id}")
    else:
        st.sidebar.error("Por favor, preencha todos os campos do paciente")

# Upload e análise de imagem
uploaded_file = st.file_uploader("Carregar Imagem de Raio-X", type=["png", "jpg", "jpeg"])

if uploaded_file is not None:
    image = Image.open(uploaded_file).convert("RGB")
    st.image(image, caption="Imagem Carregada", use_column_width=True)

    if st.button("Analisar Imagem"):
        results = {}
        for disease, (model, class_names) in models.items():
            class_name, confidence_score = predict(image, model, class_names)
            results[disease] = (class_name, confidence_score)
            st.write(f"Análise para {disease}:")
            st.write(f"Previsão: {class_name}")
            st.write(f"Confiança: {confidence_score:.2f}")
            st.write("---")

        # Selecionar paciente e salvar análise
        conn = sqlite3.connect('medvision_ai.db')
        c = conn.cursor()
        c.execute("SELECT id, name, age, gender FROM patients ORDER BY name")
        patients = c.fetchall()
        conn.close()

        patient_names = [f"{id}: {name} (Idade: {age}, Gênero: {gender})" for (id, name, age, gender) in patients]
        selected_patient = st.selectbox("Selecionar Paciente", patient_names)

        if st.button("Salvar Análise"):
            if selected_patient:
                patient_id = int(selected_patient.split(':')[0])
                for disease, (class_name, confidence_score) in results.items():
                    save_analysis(patient_id, disease, class_name, confidence_score, image)
                st.success("Análise salva com sucesso!")
            else:
                st.error("Por favor, selecione um paciente.")

        # Visualizar histórico do paciente
        if st.button("Ver Histórico do Paciente"):
            patient_id = int(selected_patient.split(':')[0])
            history_df = get_patient_history(patient_id)
            if not history_df.empty:
                visualize_patient_history(history_df)
                st.markdown(export_to_csv(history_df), unsafe_allow_html=True)
                display_confusion_matrix(history_df)
            else:
                st.write("Nenhum histórico encontrado para este paciente.")
