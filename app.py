import streamlit as st
from PIL import Image, ImageOps
import numpy as np
from tensorflow.keras.models import load_model
import sqlite3
from datetime import datetime
import pandas as pd
import seaborn as sns
from sklearn.metrics import confusion_matrix
import io
import base64
import matplotlib.pyplot as plt

# Desabilitar notação científica para clareza
np.set_printoptions(suppress=True)

def load_image(image_path):
    image = Image.open(image_path).convert("RGB")
    size = (224, 224)
    image = ImageOps.fit(image, size, Image.Resampling.LANCZOS)
    image_array = np.asarray(image)
    normalized_image_array = (image_array.astype(np.float32) / 127.5) - 1
    return normalized_image_array

def predict(image_path, model, class_names):
    data = np.ndarray(shape=(1, 224, 224, 3), dtype=np.float32)
    data[0] = load_image(image_path)
    prediction = model.predict(data)
    index = np.argmax(prediction)
    class_name = class_names[index].strip()
    confidence_score = prediction[0][index]
    return class_name, confidence_score

def load_models(model_paths, labels_paths):
    models = []
    class_names_list = []
    
    for model_path, labels_path in zip(model_paths, labels_paths):
        model = load_model(model_path, compile=False)
        models.append(model)
        
        with open(labels_path, 'r') as f:
            class_names = f.read().splitlines()
            class_names_list.append(class_names)
    
    return models, class_names_list

model_paths = ["tuberculose_model.h5", "model_pneumonia.h5", "model_outro.h5"]
labels_paths = ["labels_tuberculose.txt", "labels_pneumonia.txt", "labels_outro.txt"]

models, class_names_list = load_models(model_paths, labels_paths)

# Função para preparar o banco de dados
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

def add_patient(name, age, gender):
    conn = sqlite3.connect('medvision_ai.db')
    c = conn.cursor()
    c.execute("INSERT INTO patients (name, date, age, gender) VALUES (?, ?, ?, ?)",
              (name, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), age, gender))
    conn.commit()
    patient_id = c.lastrowid
    conn.close()
    return patient_id

def get_patient_history(patient_id):
    conn = sqlite3.connect('medvision_ai.db')
    df = pd.read_sql_query("SELECT * FROM analyses WHERE patient_id = ? ORDER BY date DESC", conn, params=(patient_id,))
    conn.close()
    return df

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

def display_confusion_matrix(df):
    diseases = df['disease'].unique()
    for disease in diseases:
        disease_df = df[df['disease'] == disease]
        true_labels = disease_df['prediction']
        predicted_labels = disease_df['prediction']
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

# Inicializar o banco de dados
init_database()

# Interface principal
st.title("MedVision AI - Análise Avançada de Raio-X")
st.sidebar.header("Configurações")

# Carregar modelos
if not models:
    st.error("Nenhum modelo foi carregado. Por favor, verifique se os arquivos dos modelos estão presentes.")
else:
    st.success(f"{len(models)} modelos carregados com sucesso.")

# Gerenciamento de Pacientes
st.sidebar.header("Gerenciamento de Pacientes")
new_patient_name = st.sidebar.text_input("Nome do Novo Paciente")
new_patient_age = st.sidebar.number_input("Idade do Paciente", min_value=0, max_value=120)
new_patient_gender = st.sidebar.selectbox("Gênero do Paciente", ["Masculino", "Feminino", "Outro"])
if st.sidebar.button("Adicionar Paciente"):
    if new_patient_name:
        patient_id = add_patient(new_patient_name, new_patient_age, new_patient_gender)
        st.sidebar.success(f"Paciente adicionado com sucesso! ID: {patient_id}")
    else:
        st.sidebar.error("Por favor, insira o nome do paciente.")

# Análise de Imagem
st.header("Análise de Imagem")
uploaded_file = st.file_uploader("Escolha um arquivo de imagem...", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    image = Image.open(uploaded_file)
    st.image(image, caption='Imagem Carregada', use_column_width=True)
    st.write("")
    st.write("Classificando...")

    try:
        results = analyze_image(image, models)
        for disease, (prediction, confidence) in results.items():
            st.write(f"{disease.capitalize()}: {prediction} (Confiança: {confidence:.2f})")
        save_analysis(patient_id, prediction, disease, confidence, image)

    except Exception as e:
        st.error(f"Ocorreu um erro: {e}")

# Visualização de Histórico de Pacientes
st.sidebar.header("Histórico de Pacientes")
patient_id_input = st.sidebar.number_input("ID do Paciente", min_value=1)

if st.sidebar.button("Buscar Histórico"):
    history_df = get_patient_history(patient_id_input)
    if not history_df.empty:
        visualize_patient_history(history_df)
        st.sidebar.markdown(export_to_csv(history_df), unsafe_allow_html=True)
    else:
        st.sidebar.error("Nenhum histórico encontrado para este paciente.")

