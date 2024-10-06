import streamlit as st
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

# Function to load models and labels
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

# Function to initialize the database
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

# Function to hash password
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Function to register new user
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

# Function to verify user credentials
def verify_user(username, password):
    conn = sqlite3.connect('medvision_ai.db')
    c = conn.cursor()
    c.execute("SELECT password FROM users WHERE username = ?", (username,))
    result = c.fetchone()
    conn.close()
    if result:
        return result[0] == hash_password(password)
    return False

# Function to save analysis in the database
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
def analyze_image(image, model_index):
    results = {}
    disease = list(models.keys())[model_index]
    model_instance, class_names = models[disease]

    image_array = np.asarray(image.resize((224, 224)))
    normalized_image_array = (image_array.astype(np.float32) / 127.5) - 1
    data = np.expand_dims(normalized_image_array, axis=0)

    prediction = model_instance.predict(data)
    index = np.argmax(prediction)
    class_name = class_names[index].strip()  # Clean class name
    confidence_score = float(prediction[0][index])

    results[disease] = (class_name, confidence_score)
    return results

# Function to add patient
def add_patient(name, age, gender):
    try:
        conn = sqlite3.connect('medvision_ai.db')
        c = conn.cursor()
        c.execute("INSERT INTO patients (name, date, age, gender) VALUES (?, ?, ?, ?)",
                  (name, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), age, gender))
        conn.commit()
        patient_id = c.lastrowid
        conn.close()
        return patient_id
    except sqlite3.Error as e:
        st.error(f"Erro ao adicionar paciente: {e}")
        return None

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
    if 'disease' in df.columns and 'prediction' in df.columns:
        diseases = df['disease'].unique()
        for disease in diseases:
            disease_df = df[df['disease'] == disease]
            true_labels = disease_df['disease']
            predicted_labels = disease_df['prediction']
            cm = confusion_matrix(true_labels, predicted_labels)
            plt.figure(figsize=(8, 6))
            sns.heatmap(cm, annot=True, fmt='d', cmap='Blues')
            plt.title(f'Matriz de Confusão - {disease}')
            plt.xlabel('Previsão')
            plt.ylabel('Verdadeiro')
            st.pyplot(plt)
    else:
        st.error("Colunas 'disease' ou 'prediction' não encontradas.")

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
    st.error("Nenhum modelo foi carregado. Por favor, verifique se os arquivos dos modelos estão presentes no diretório.")
else:
    st.success(f"{len(models)} modelos carregados com sucesso.")

# Patient management
st.sidebar.header("Gerenciamento de Pacientes")
new_patient_name = st.sidebar.text_input("Nome do Novo Paciente")
new_patient_age = st.sidebar.number_input("Idade do Paciente", min_value=0, max_value=120)
new_patient_gender = st.sidebar.selectbox("Gênero do Paciente", ["Masculino", "Feminino", "Outro"])
patient_id = None

if st.sidebar.button("Adicionar Paciente"):
    if new_patient_name and new_patient_age:
        patient_id = add_patient
(new_patient_name, new_patient_age, new_patient_gender)
        st.sidebar.success(f"Paciente {new_patient_name} adicionado com ID {patient_id}")
    else:
        st.sidebar.error("Por favor, preencha todos os campos do paciente")

# Load image
uploaded_file = st.file_uploader("Carregar Imagem de Raio-X", type=["png", "jpg", "jpeg"])

if uploaded_file is not None:
    image = Image.open(uploaded_file)

    # Model selection
    model_options = list(models.keys())
    selected_model = st.selectbox("Escolha o Modelo de Análise", model_options)

    if st.button("Analisar Imagem"):
        model_index = model_options.index(selected_model)
        results = analyze_image(image, model_index)

        for disease, (prediction, confidence) in results.items():
            st.success(f"Diagnóstico para {disease}: {prediction} com {confidence:.2f}% de confiança")
            if patient_id:
                save_analysis(patient_id, disease, prediction, confidence, image)

        # Visualize patient analysis history
        if patient_id:
            patient_history = get_patient_history(patient_id)
            visualize_patient_history(patient_history)
            st.markdown(export_to_csv(patient_history), unsafe_allow_html=True)
            display_confusion_matrix(patient_history)

# Function to generate PDF report
def generate_pdf_report(patient_id, analyses_df):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
    from reportlab.lib.styles import getSampleStyleSheet

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []

    styles = getSampleStyleSheet()
    elements.append(Paragraph(f"Relatório do Paciente - ID: {patient_id}", styles['Heading1']))

    data = [analyses_df.columns.tolist()] + analyses_df.values.tolist()
    t = Table(data)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 12),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    elements.append(t)

    doc.build(elements)
    buffer.seek(0)
    return buffer

# Main interface function
def main():
    st.set_page_config(page_title="MedVision AI", layout="wide")

    # Initialize database and load models
    init_database()
    models = load_models()

    if not models:
        st.error("Nenhum modelo foi carregado. Verifique se os arquivos estão no diretório.")
        return

    st.success(f"{len(models)} modelos carregados com sucesso.")

    # Patient management and analysis
    new_patient_name = st.sidebar.text_input("Nome do Novo Paciente")
    new_patient_age = st.sidebar.number_input("Idade do Paciente", min_value=0, max_value=120)
    new_patient_gender = st.sidebar.selectbox("Gênero do Paciente", ["Masculino", "Feminino", "Outro"])
    patient_id = None

    if st.sidebar.button("Adicionar Paciente"):
        if new_patient_name and new_patient_age:
            patient_id = add_patient(new_patient_name, new_patient_age, new_patient_gender)
            st.sidebar.success(f"Paciente {new_patient_name} adicionado com ID {patient_id}")
        else:
            st.sidebar.error("Por favor, preencha todos os campos do paciente")

    uploaded_file = st.file_uploader("Carregar Imagem de Raio-X", type=["png", "jpg", "jpeg"])

    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        model_options = list(models.keys())
        selected_model = st.selectbox("Escolha o Modelo de Análise", model_options)

        if st.button("Analisar Imagem"):
            model_index = model_options.index(selected_model)
            results = analyze_image(image, model_index)

            for disease, (prediction, confidence) in results.items():
                st.success(f"Diagnóstico para {disease}: {prediction} com {confidence:.2f}% de confiança")
                if patient_id:
                    save_analysis(patient_id, disease, prediction, confidence, image)

            if patient_id:
                patient_history = get_patient_history(patient_id)
                visualize_patient_history(patient_history)
                st.markdown(export_to_csv(patient_history), unsafe_allow_html=True)
                display_confusion_matrix(patient_history)

                # Generate and offer PDF report download
                pdf_buffer = generate_pdf_report(patient_id, patient_history)
                st.download_button(
                    label="Download Relatório PDF",
                    data=pdf_buffer,
                    file_name=f"relatorio_paciente_{patient_id}.pdf",
                    mime="application/pdf"
                )

if __name__ == "__main__":
    main()
