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
import sqlite3


# Disable scientific notation for clarity
np.set_printoptions(suppress=True)

# Initialize session state
if 'patient_history' not in st.session_state:
    st.session_state.patient_history = {}
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'username' not in st.session_state:
    st.session_state.username = None

# Database file
DB_FILE = 'users.db'

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


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def init_database():
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (username TEXT PRIMARY KEY, password TEXT, last_login TEXT, expiry_date TEXT, role TEXT)''')
        
        c.execute("SELECT * FROM users WHERE username='admin'")
        if c.fetchone() is None:
            admin_password = hash_password('123')
            c.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?)", 
                      ('admin', admin_password, '', '', 'admin'))
        
        conn.commit()
        print("Database initialized successfully")
    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
    finally:
        if conn:
            conn.close()

def check_login(username, password):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=?", (username,))
    user = c.fetchone()
    conn.close()

    if user and user[1] == hash_password(password):
        is_admin = user[4] == 'admin'
        if not is_admin and user[3]:
            expiry_date = datetime.strptime(user[3], "%Y-%m-%d %H:%M:%S")
            if datetime.now() > expiry_date:
                return False, "Account expired"
        return True, "Success"
    return False, "Invalid credentials"

def update_last_login(username):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE users SET last_login=? WHERE username=?", 
              (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), username))
    conn.commit()
    conn.close()

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
            st.success("Logged in successfully!")
        else:
            st.error(message)

def custom_depthwise_conv2d(*args, **kwargs):
    kwargs.pop('groups', None)
    return DepthwiseConv2D(*args, **kwargs)

def load_model_and_labels(model_path, labels_path):
    try:
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Arquivo de modelo não funciona: {model_path}")
        if not os.path.exists(labels_path):
            raise FileNotFoundError(f"Labels não funciona: {labels_path}")
        
        with custom_object_scope({'DepthwiseConv2D': custom_depthwise_conv2d}):
            model = load_model(model_path, compile=False)
        
        with open(labels_path, "r") as f:
            class_names = f.readlines()
        return model, class_names
    except Exception as e:
        st.error(f"Error loading model and labels: {str(e)}")
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
        st.error(f"Error during prediction: {str(e)}")
        return None, None

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
                    st.error("An error occurred during prediction. Please try again.")
            else:
                st.error("Failed to load the model and labels. Please check the files and try again.")
        except Exception as e:
            st.error(f"An error occurred during classification: {str(e)}")
    else:
        st.error("Por favor faça upload primeiro")
    return None


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
        st.error(f"Error preprocessing image: {str(e)}")
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
                        
                        st.success("Exam classified successfully!")
                        return result
                    else:
                        st.error("An error occurred during prediction. Please try again.")
                else:
                    st.error("Failed to preprocess the image. Please try a different image.")
            else:
                st.error("Failed to load the model and labels. Please check the files and try again.")
        except Exception as e:
            st.error(f"An error occurred during classification: {str(e)}")
    else:
        st.error("Please upload an image first.")
    return None

def view_patient_history(patient_id):
    if patient_id in st.session_state.patient_history:
        history = st.session_state.patient_history[patient_id]
        df = pd.DataFrame(history)
        st.dataframe(df)
        
        # Visualization of patient history
        st.subheader("Patient Exam History Visualization")
        fig, ax = plt.subplots(figsize=(10, 6))
        sns.scatterplot(data=df, x='date', y='confidence', hue='model', size='confidence', ax=ax)
        ax.set_title(f"Exam Confidence Over Time for Patient {patient_id}")
        ax.set_xlabel("Date")
        ax.set_ylabel("Confidence Score")
        st.pyplot(fig)
    else:
        st.info("No history found for this patient.")

def compare_patients():
    st.subheader("Compare Patients")
    patient_ids = list(st.session_state.patient_history.keys())
    if len(patient_ids) < 2:
        st.warning("Need at least two patients with history to compare.")
        return
    
    patient1 = st.selectbox("Select first patient", patient_ids)
    patient2 = st.selectbox("Select second patient", [id for id in patient_ids if id != patient1])
    
    if st.button("Compare"):
        df1 = pd.DataFrame(st.session_state.patient_history[patient1])
        df2 = pd.DataFrame(st.session_state.patient_history[patient2])
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
        
        sns.boxplot(data=df1, x='model', y='confidence', ax=ax1)
        ax1.set_title(f"Patient {patient1}")
        ax1.set_ylim(0, 1)
        
        sns.boxplot(data=df2, x='model', y='confidence', ax=ax2)
        ax2.set_title(f"Patient {patient2}")
        ax2.set_ylim(0, 1)
        
        st.pyplot(fig)
def manage_users():
    st.header("User Management")
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Fetch all users
    c.execute("SELECT username, last_login, expiry_date, role FROM users")
    users = c.fetchall()
    user_df = pd.DataFrame(users, columns=["Username", "Last Login", "Expiry Date", "Role"])
    st.dataframe(user_df)

    # Add new user form
    st.subheader("Add User")
    new_username = st.text_input("New Username")
    new_password = st.text_input("New Password", type="password")
    new_role = st.selectbox("Role", ["user", "admin"])
    validity_days = st.number_input("Account Validity (days)", min_value=1, value=7, step=1)
    if st.button("Add User"):
        if new_username and new_password:
            hashed_password = hash_password(new_password)
            expiry_date = (datetime.now() + timedelta(days=validity_days)).strftime("%Y-%m-%d %H:%M:%S") if new_role != "admin" else None
            c.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?)", 
                      (new_username, hashed_password, '', expiry_date, new_role))
            conn.commit()
            st.success("User added successfully!")
        else:
            st.error("Please provide both username and password.")

    # Edit user form
    st.subheader("Edit User")
    edit_username = st.selectbox("Select User to Edit", [user[0] for user in users])
    edited_password = st.text_input("New Password for Selected User", type="password")
    edited_role = st.selectbox("New Role", ["user", "admin"])
    edited_validity = st.number_input("New Account Validity (days)", min_value=1, value=7, step=1)
    if st.button("Edit User"):
        if edited_password:
            hashed_password = hash_password(edited_password)
            expiry_date = (datetime.now() + timedelta(days=edited_validity)).strftime("%Y-%m-%d %H:%M:%S") if edited_role != "admin" else None
            c.execute("UPDATE users SET password=?, expiry_date=?, role=? WHERE username=?", 
                      (hashed_password, expiry_date, edited_role, edit_username))
            conn.commit()
            st.success("User edited successfully!")
        else:
            st.error("Please provide a new password.")

    # Remove user form
    st.subheader("Remove User")
    remove_username = st.selectbox("Select User to Remove", [user[0] for user in users if user[0] != 'admin'])
    if st.button("Remove User"):
        c.execute("DELETE FROM users WHERE username=?", (remove_username,))
        conn.commit()
        st.success("User removed successfully!")

    conn.close()

def main():
    init_database()
    if not st.session_state.get('logged_in', False):
        login_page()
    else:
        st.title("MedVision")
        st.sidebar.title(f"Bem Vindo, {st.session_state.username}")
        if st.sidebar.button("Sair"):
            st.session_state.logged_in = False
            st.session_state.username = None
            st.rerun()

        # Sidebar menu
        if 'menu_option' not in st.session_state:
            st.session_state.menu_option = "Classify Exam"
        options = ["Classify Exam", "View Patient History", "Compare Patients"]
        if st.session_state.username == 'admin':
            options.append("User Management")
        st.session_state.menu_option = st.sidebar.radio("Choose an option:", options, key="menu_radio")

        if st.session_state.menu_option == "Classify Exam":
            st.header("Classify Exam")
            patient_id = st.text_input("Enter Patient ID:")
            model_option = st.selectbox("Choose a model for analysis:", ("Pneumonia", "Tuberculosis", "Cancer"))
            uploaded_file = st.file_uploader("Upload X-ray or CT scan image", type=["jpg", "jpeg", "png"])
            if st.button("Classify"):
                classify_exam(patient_id, model_option, uploaded_file)
        elif st.session_state.menu_option == "View Patient History":
            st.header("Patient History")
            patient_id = st.text_input("Enter Patient ID:")
            if st.button("View History"):
                view_patient_history(patient_id)
        elif st.session_state.menu_option == "Compare Patients":
            compare_patients()
        elif st.session_state.menu_option == "User Management":
            manage_users()

if __name__ == "__main__":
    main()

