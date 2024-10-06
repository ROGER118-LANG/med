import streamlit as st
from PIL import Image, ImageOps
import numpy as np
from tensorflow.keras.models import load_model  
import tensorflow as tf
from PIL import Image, ImageOps
# Alterado para TensorFlow Keras
import sqlite3
from datetime import datetime
import matplotlib.pyplot as plt
import os
import pandas as pd
import seaborn as sns
from sklearn.metrics import confusion_matrix
import tempfile 
import base64
import os
import requests



import requests
import tensorflow as tf
from tensorflow.keras.models import load_model
import streamlit as st
import os
import tempfile

# Desabilitar notação científica para clareza
np.set_printoptions(suppress=True)

def load_image(image_path):
    """Carrega e processa a imagem para o modelo."""
    # Carregar a imagem e converter para RGB
    image = Image.open(image_path).convert("RGB")
    
    # Redimensionar a imagem para 224x224
    size = (224, 224)
    image = ImageOps.fit(image, size, Image.Resampling.LANCZOS)
    
    # Converter a imagem em um array numpy
    image_array = np.asarray(image)
    
    # Normalizar a imagem
    normalized_image_array = (image_array.astype(np.float32) / 127.5) - 1
    
    return normalized_image_array

def predict(image_path, model, class_names):
    """Faz a predição da imagem usando o modelo fornecido."""
    # Criar a array com a forma correta para alimentar o modelo
    data = np.ndarray(shape=(1, 224, 224, 3), dtype=np.float32)
    
    # Carregar e processar a imagem
    data[0] = load_image(image_path)

    # Fazer a predição
    prediction = model.predict(data)
    index = np.argmax(prediction)
    class_name = class_names[index].strip()  # Remover quebra de linha
    confidence_score = prediction[0][index]

    # Retornar resultados
    return class_name, confidence_score

# Função para carregar os modelos e os rótulos
def load_models(model_paths, labels_paths):
    """Carrega múltiplos modelos e suas classes."""
    models = []
    class_names_list = []
    
    for model_path, labels_path in zip(model_paths, labels_paths):
        model = load_model(model_path, compile=False)
        with open(labels_path, "r") as f:
            class_names = f.readlines()
        models.append(model)
        class_names_list.append(class_names)
    
    return models, class_names_list

# Definir caminhos para os modelos e rótulos
model_paths = ["tuberculose_model.h5", "model_pneumonia.h5", "model_outro.h5"]
labels_paths = ["labels_tuberculose.txt", "labels_pneumonia.txt", "labels_outro.txt"]

# Carregar modelos e rótulos
models, class_names_list = load_models(model_paths, labels_paths)

# Exibir opções para o usuário escolher
print("Escolha um modelo:")
for i, model_path in enumerate(model_paths):
    print(f"{i + 1}. {model_path}")

# Obter escolha do usuário
model_choice = int(input("Digite o número do modelo que deseja usar: ")) - 1

# Verificar se a escolha é válida
if model_choice < 0 or model_choice >= len(models):
    print("Escolha inválida.")
else:
    # Definir o modelo escolhido e suas classes
    selected_model = models[model_choice]
    selected_class_names = class_names_list[model_choice]

    # Defina o caminho para sua imagem
    image_path = input("Digite o caminho da imagem: ")  # Solicitar o caminho da imagem

    # Fazer a predição
    class_name, confidence_score = predict(image_path, selected_model, selected_class_names)

    # Exibir os resultados
    print("Class:", class_name)
    print("Confidence Score:", confidence_score)

# Function to prepare the database
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

# Function to save analysis to the database
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

# Function to analyze the image
def analyze_image(image, models):
    results = {}
    for disease, (model, class_names) in models.items():
        image_array = np.asarray(image.resize((224, 224)))
        normalized_image_array = (image_array.astype(np.float32) / 127.5) - 1
        data = np.expand_dims(normalized_image_array, axis=0)

        prediction = model.predict(data)
        index = np.argmax(prediction)
        class_name = class_names[index]
        confidence_score = float(prediction[0][index])

        results[disease] = (class_name, confidence_score)
    return results

# Function to add a new patient
def add_patient(name, age, gender):
    conn = sqlite3.connect('medvision_ai.db')
    c = conn.cursor()
    c.execute("INSERT INTO patients (name, date, age, gender) VALUES (?, ?, ?, ?)",
              (name, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), age, gender))
    conn.commit()
    patient_id = c.lastrowid
    conn.close()
    return patient_id

# Function to get patient history
def get_patient_history(patient_id):
    conn = sqlite3.connect('medvision_ai.db')
    df = pd.read_sql_query("SELECT * FROM analyses WHERE patient_id = ? ORDER BY date DESC", conn, params=(patient_id,))
    conn.close()
    return df

# Function to visualize patient history
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

# Function to generate and display confusion matrix
def display_confusion_matrix(df):
    diseases = df['disease'].unique()
    for disease in diseases:
        disease_df = df[df['disease'] == disease]
        true_labels = disease_df['prediction']
        predicted_labels = disease_df['prediction']  # Assuming the prediction is correct for this example
        cm = confusion_matrix(true_labels, predicted_labels)
        plt.figure(figsize=(8, 6))
        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues')
        plt.title(f'Matriz de Confusão - {disease}')
        plt.xlabel('Previsão')
        plt.ylabel('Verdadeiro')
        st.pyplot(plt)

# Function to export patient data to CSV
def export_to_csv(df):
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="patient_data.csv">Download CSV File</a>'
    return href

# Initialize the database
init_database()

# Main interface
st.title("MedVision AI - Análise Avançada de Raio-X")
st.sidebar.header("Configurações")

# Load models
models = load_models()

if not models:
    st.error("Nenhum modelo foi carregado. Por favor, verifique se os arquivos dos modelos estão presentes.")
else:
    st.success(f"{len(models)} modelos carregados com sucesso.")

# Patient management
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

# Load image
uploaded_file = st.file_uploader("Carregar Imagem de Raio-X", type=["png", "jpg", "jpeg"])

if uploaded_file is not None:
    image = Image.open(uploaded_file)
    image = ImageOps.fit(image, (300, 300), Image.Resampling.LANCZOS)
    st.image(image, caption="Imagem Carregada", use_column_width=True)

    if st.button("Analisar Imagem"):
        try:
            results = analyze_image(image, models)

            for disease, (class_name, confidence_score) in results.items():
                st.write(f"Análise para {disease}:")
                st.write(f"Previsão: {class_name}")
                st.write(f"Confiança: {confidence_score:.2f}")
                st.write("---")

            # Select patient
            conn = sqlite3.connect('medvision_ai.db')
            c = conn.cursor()
            c.execute("SELECT id, name, age, gender FROM patients ORDER BY name")
            patients = c.fetchall()
            conn.close()

            patient_names = [f"{id}: {name} (Idade: {age}, Gênero: {gender})" for (id, name, age, gender) in patients]
            selected_patient = st.selectbox("Selecionar Paciente", patient_names)

            # Save analysis to database
            if st.button("Salvar Análise"):
                if selected_patient:
                    patient_id = int(selected_patient.split(':')[0])
                    for disease, (class_name, confidence_score) in results.items():
                        save_analysis(patient_id, disease, class_name, confidence_score, image)
                    st.success("Análise salva com sucesso!")
                else:
                    st.error("Por favor, selecione um paciente para salvar a análise.")
        except Exception as e:
            st.error(f"Erro ao analisar a imagem: {str(e)}")

# Patient history
st.sidebar.header("Histórico de Pacientes")
patient_history_id = st.sidebar.number_input("ID do Paciente para Histórico", min_value=1)
if st.sidebar.button("Visualizar Histórico"):
    df_history = get_patient_history(patient_history_id)
    if not df_history.empty:
        visualize_patient_history(df_history)
        if st.button("Gerar Matriz de Confusão"):
            display_confusion_matrix(df_history)
        st.sidebar.markdown(export_to_csv(df_history), unsafe_allow_html=True)
    else:
        st.sidebar.warning("Nenhum histórico encontrado para este paciente.")
