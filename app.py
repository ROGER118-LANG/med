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
from openpyxl import Workbook, load_workbook
import hashlib
import json
import logging
import plotly.graph_objects as go

# Configure logging
logging.basicConfig(filename='medvision.log', level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

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
CONFIG_FILE = 'config.json'

# Load configuration
def load_config():
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

config = load_config()

# Model and label paths
model_paths = config.get('model_paths', {
    "Pneumonia": "pneumonia_model.h5",
    "Tuberculosis": "tuberculose_model.h5",
    "Cancer": "cancer_model.h5"
})

label_paths = config.get('label_paths', {
    "Pneumonia": "pneumonia_labels.txt",
    "Tuberculosis": "tuberculose_labels.txt",
    "Cancer": "cancer_labels.txt"
})

def custom_depthwise_conv2d(*args, **kwargs):
    kwargs.pop('groups', None)
    return DepthwiseConv2D(*args, **kwargs)

def load_model_and_labels(model_path, labels_path):
    try:
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found: {model_path}")
        if not os.path.exists(labels_path):
            raise FileNotFoundError(f"Labels file not found: {labels_path}")
        
        with custom_object_scope({'DepthwiseConv2D': custom_depthwise_conv2d}):
            model = load_model(model_path, compile=False)
        
        with open(labels_path, "r") as f:
            class_names = f.readlines()
        return model, class_names
    except Exception as e:
        logging.error(f"Error loading model and labels: {str(e)}")
        st.error(f"Error loading model and labels: {str(e)}")
        return None, None

def predict(model, data, class_names):
    try:
        prediction = model.predict(data)
        index = np.argmax(prediction)
        class_name = class_names[index]
        confidence_score = float(prediction[0][index])
        return class_name.strip(), confidence_score
    except Exception as e:
        logging.error(f"Error during prediction: {str(e)}")
        st.error(f"Error during prediction: {str(e)}")
        return None, None

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
                            return False, "Account expired"
                
                return True, "Success"
        
        return False, "Invalid credentials"
    except Exception as e:
        logging.error(f"An error occurred while checking login: {str(e)}")
        return False, "Login check failed"

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
            st.success("Logged in successfully!")
        else:
            st.error(message)

def preprocess_image(uploaded_file):
    try:
        image_bytes = uploaded_file.getvalue()
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        size = (224, 224)
        image = ImageOps.fit(image, size, Image.Resampling.LANCZOS)
        image_array = np.asarray(image)
        normalized_image_array = (image_array.astype(np.float32) / 127.5) - 1
        data = np.ndarray(shape=(1, 224, 224, 3), dtype=np.float32)
        data[0] = normalized_image_array
        return data
    except Exception as e:
        logging.error(f"Error preprocessing image: {str(e)}")
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
            logging.error(f"An error occurred during classification: {str(e)}")
            st.error(f"An error occurred during classification: {str(e)}")
    else:
        st.error("Please upload an image first.")
    return None

def view_patient_history(patient_id):
    if patient_id in st.session_state.patient_history:
        history = st.session_state.patient_history[patient_id]
        df = pd.DataFrame(history)
        st.dataframe(df)
        
        st.subheader("Patient Exam History Visualization")
        fig = go.Figure()
        for model in df['model'].unique():
            model_data = df[df['model'] == model]
            fig.add_trace(go.Scatter(x=model_data['date'], y=model_data['confidence'],
                                     mode='markers+lines', name=model))
        fig.update_layout(title=f"Exam Confidence Over Time for Patient {patient_id}",
                          xaxis_title="Date", yaxis_title="Confidence Score")
        st.plotly_chart(fig)
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
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df1['date'], y=df1['confidence'], mode='lines+markers', name=patient1))
        fig.add_trace(go.Scatter(x=df2['date'], y=df2['confidence'], mode='lines+markers', name=patient2))
        
        fig.update_layout(title=f"Comparison of Exam Confidence Between {patient1} and {patient2}",
                          xaxis_title="Date", yaxis_title="Confidence Score")
        st.plotly_chart(fig)

def generate_report(patient_id):
    report_file = f"{patient_id}_report.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.append(['Date', 'Model', 'Class', 'Confidence'])
    
    if patient_id in st.session_state.patient_history:
        for entry in st.session_state.patient_history[patient_id]:
            ws.append([entry['date'], entry['model'], entry['class'], entry['confidence']])
        
        wb.save(report_file)
        st.success(f"Report generated: {report_file}")
    else:
        st.error("No history found for this patient.")

# Main application logic
def main():
    st.title("MedVision: Image Classification for Medical Exams")
    init_login_file()
    
    if st.session_state.logged_in:
        st.sidebar.title("Menu")
        patient_id = st.sidebar.text_input("Patient ID")
        
        menu_option = st.sidebar.selectbox("Select action", ["Classify Exam", "View Patient History", "Compare Patients", "Generate Report"])
        
        if menu_option == "Classify Exam":
            model_option = st.sidebar.selectbox("Select Model", list(model_paths.keys()))
            uploaded_file = st.file_uploader("Upload Medical Image", type=["jpg", "jpeg", "png"])
            if st.button("Classify"):
                classify_exam(patient_id, model_option, uploaded_file)
        
        elif menu_option == "View Patient History":
            view_patient_history(patient_id)
        
        elif menu_option == "Compare Patients":
            compare_patients()
        
        elif menu_option == "Generate Report":
            if st.button("Generate Report"):
                generate_report(patient_id)
                
    else:
        login_page()

if __name__ == "__main__":
    main()
