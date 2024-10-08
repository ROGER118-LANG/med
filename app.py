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
import matplotlib.pyplot as plt
import seaborn as sns
import logging
import json
from sklearn.metrics import confusion_matrix
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
        fig.add_trace(go.Box(y=df1['confidence'], name=f"Patient {patient1}"))
        fig.add_trace(go.Box(y=df2['confidence'], name=f"Patient {patient2}"))
        fig.update_layout(title="Comparison of Exam Confidences",
                          yaxis_title="Confidence Score")
        st.plotly_chart(fig)

def manage_users():
    st.header("User Management")
    
    try:
        wb = load_workbook(LOGIN_FILE)
        ws = wb.active

        user_data = {row[0]: row for row in ws.iter_rows(min_row=2, values_only=True)}

        cleaned_user_data = [
            (row if len(row) == 5 else row + (None,) * (5 - len(row))) 
            for row in user_data.values()
        ]

        user_df = pd.DataFrame(cleaned_user_data, columns=["Username", "Password", "Last Login", "Expiry Date", "Role"])
        
        st.dataframe(user_df)

        st.subheader("Add User")
        new_username = st.text_input("New Username")
        new_password = st.text_input("New Password", type="password")
        new_role = st.selectbox("Role", ["user", "admin"])
        validity_days = st.number_input("Account Validity (days)", min_value=1, value=7, step=1)
        if st.button("Add User"):
            if new_username and new_password:
                hashed_password = hash_password(new_password)
                expiry_date = datetime.now() + timedelta(days=validity_days) if new_role != "admin" else None
                ws.append([new_username, hashed_password, "", expiry_date, new_role])
                wb.save(LOGIN_FILE)
                st.success("User added successfully!")
            else:
                st.error("Please provide both username and password.")

        st.subheader("Edit User")
        edit_username = st.selectbox("Select User to Edit", list(user_data.keys()))
        edited_password = st.text_input("New Password for Selected User", type="password")
        edited_role = st.selectbox("New Role", ["user", "admin"])
        edited_validity = st.number_input("New Account Validity (days)", min_value=1, value=7, step=1)
        if st.button("Edit User"):
            if edited_password:
                hashed_password = hash_password(edited_password)
                for row in ws.iter_rows(min_row=2):
                    if row[0].value == edit_username:
                        row[1].value = hashed_password
                        row[3].value = datetime.now() + timedelta(days=edited_validity) if edited_role != "admin" else None
                        row[4].value = edited_role
                        break
                wb.save(LOGIN_FILE)
                st.success("User edited successfully!")
            else:
                st.error("Please provide a new password.")

        st.subheader("Remove User")
        remove_username = st.selectbox("Select User to Remove", list(user_data.keys()))
        if st.button("Remove User"):
            ws.delete_rows(list(user_data.keys()).index(remove_username) + 2)
            wb.save(LOGIN_FILE)
            st.success("User removed successfully!")
    
    except Exception as e:
        logging.error(f"An error occurred during user management: {str(e)}")
        st.error(f"An error occurred during user management: {str(e)}")


   def generate_report(patient_id):
    if patient_id in st.session_state.patient_history:
        history = st.session_state.patient_history[patient_id]
        df = pd.DataFrame(history)
        
        if patient_id:
        print("Gerando relatório para o paciente:", patient_id)
        
        # Summary statistics
        st.write("Summary Statistics:")
        st.write(df.describe())
        
        # Most recent exam
        st.write("Most Recent Exam:")
        st.write(df.iloc[-1])
        
        # Visualization
        st.subheader("Exam History Visualization")
        fig = go.Figure()
        for model in df['model'].unique():
            model_data = df[df['model'] == model]
            fig.add_trace(go.Scatter(x=model_data['date'], y=model_data['confidence'],
                                     mode='markers+lines', name=model))
        fig.update_layout(title=f"Exam Confidence Over Time for Patient {patient_id}",
                          xaxis_title="Date", yaxis_title="Confidence Score")
        st.plotly_chart(fig)
        
        # Class distribution
        st.subheader("Class Distribution")
        class_dist = df['class'].value_counts()
        fig = go.Figure(data=[go.Pie(labels=class_dist.index, values=class_dist.values)])
        fig.update_layout(title="Distribution of Exam Classifications")
        st.plotly_chart(fig)
        
    else:
        st.info("No history found for this patient.")

def analyze_model_performance():
    st.subheader("Model Performance Analysis")
    
    all_exams = []
    for patient_exams in st.session_state.patient_history.values():
        all_exams.extend(patient_exams)
    
    df = pd.DataFrame(all_exams)
    
    if df.empty:
        st.warning("No exam data available for analysis.")
        return
    
    # Model-wise performance
    st.write("Model-wise Performance:")
    model_performance = df.groupby('model')['confidence'].mean().sort_values(ascending=False)
    st.bar_chart(model_performance)
    
    # Confusion Matrix
    st.write("Confusion Matrix:")
    confusion_mat = confusion_matrix(df['class'], df['model'])
    fig = go.Figure(data=go.Heatmap(z=confusion_mat, x=df['model'].unique(), y=df['class'].unique()))
    fig.update_layout(title="Confusion Matrix", xaxis_title="Predicted", yaxis_title="Actual")
    st.plotly_chart(fig)
    
    # Time-based analysis
    st.write("Performance Over Time:")
    df['date'] = pd.to_datetime(df['date'])
    df.set_index('date', inplace=True)
    monthly_performance = df.resample('M')['confidence'].mean()
    st.line_chart(monthly_performance)

def main():
    init_login_file()
    if not st.session_state.get('logged_in', False):
        login_page()
    else:
        st.title("MedVision Dashboard")
        st.sidebar.title(f"Welcome, {st.session_state.username}")
        if st.sidebar.button("Logout"):
            st.session_state.logged_in = False
            st.session_state.username = None
            st.experimental_rerun()

        # Sidebar menu
        menu_options = ["Classify Exam", "View Patient History", "Compare Patients", "Generate Report", "Model Performance Analysis"]
        if st.session_state.username == 'admin':
            menu_options.append("User Management")

        menu_choice = st.sidebar.selectbox("Choose an option:", menu_options)

        if menu_choice == "Classify Exam":
            st.header("Classify Exam")
            patient_id = st.text_input("Enter Patient ID:")
            model_option = st.selectbox("Choose a model for analysis:", list(model_paths.keys()))
            uploaded_file = st.file_uploader("Upload X-ray or CT scan image", type=["jpg", "jpeg", "png"])
            if st.button("Classify"):
                result = classify_exam(patient_id, model_option, uploaded_file)
                if result:
                    st.write("Classification Result:")
                    st.json(result)
        
        elif menu_choice == "View Patient History":
            st.header("Patient History")
            patient_id = st.text_input("Enter Patient ID:")
            if st.button("View History"):
                view_patient_history(patient_id)
        
        elif menu_choice == "Compare Patients":
            compare_patients()
        
        elif menu_choice == "Generate Report":
            st.header("Generate Patient Report")
            patient_id = st.text_input("Enter Patient ID:")
            if st.button("Generate Report"):
                generate_report(patient_id)
        
        elif menu_choice == "Model Performance Analysis":
            analyze_model_performance()
        
        elif menu_choice == "User Management" and st.session_state.username == 'admin':
            manage_users()

if __name__ == "__main__":
    main()
