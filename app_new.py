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
import base64
from io import BytesIO

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
PATIENT_DATA_FILE = 'patient_data.xlsx'

# Define the path for the fractured arm model and labels
MODEL_PATH = "fractured_arm_model.h5"
LABELS_PATH = "fractured_arm_labels.txt"

def custom_depthwise_conv2d(*args, **kwargs):
    kwargs.pop('groups', None)
    return DepthwiseConv2D(*args, **kwargs)

def load_model_and_labels():
    try:
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(f"Model file not found: {MODEL_PATH}")
        if not os.path.exists(LABELS_PATH):
            raise FileNotFoundError(f"Labels file not found: {LABELS_PATH}")
        
        with custom_object_scope({'DepthwiseConv2D': custom_depthwise_conv2d}):
            model = load_model(MODEL_PATH, compile=False)
        
        with open(LABELS_PATH, "r") as f:
            class_names = f.readlines()
        return model, class_names
    except Exception as e:
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
        st.error(f"Error during prediction: {str(e)}")
        return None, None

def classify_exam(patient_id, uploaded_file):
    if uploaded_file is not None:
        try:
            model, class_names = load_model_and_labels()
            
            if model is not None and class_names is not None:
                processed_image = preprocess_image(uploaded_file)
                class_name, confidence_score = predict(model, processed_image, class_names)
                
                if class_name is not None and confidence_score is not None:
                    result = {
                        'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'class': class_name,
                        'confidence': confidence_score
                    }
                    
                    if patient_id not in st.session_state.patient_history:
                        st.session_state.patient_history[patient_id] = []
                    st.session_state.patient_history[patient_id].append(result)
                    
                    save_patient_exam(patient_id, result)
                    
                    st.success("Exam classified successfully!")
                    return result
                else:
                    st.error("An error occurred during prediction. Please try again.")
            else:
                st.error("Failed to load the model and labels. Please check the files and try again.")
        except Exception as e:
            st.error(f"An error occurred during classification: {str(e)}")
    else:
        st.error("Please upload an image first")
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
                is_admin = len(row) > 4 and row[4] == 'admin'
                
                if not is_admin:
                    if len(row) > 3 and row[3]:
                        expiry_date = row[3]
                        if isinstance(expiry_date, datetime) and datetime.now() > expiry_date:
                            return False, "Account expired"
                
                return True, "Success"
        
        return False, "Invalid credentials"
    except Exception as e:
        st.error(f"An error occurred while checking login: {str(e)}")
        return False, "Login check failed"

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

def update_last_login(username):
    wb = load_workbook(LOGIN_FILE)
    ws = wb.active
    for row in ws.iter_rows(min_row=2):
        if row[0].value == username:
            row[2].value = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            break
    wb.save(LOGIN_FILE)

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
        st.error(f"Error preprocessing image: {str(e)}")
        return None

def view_patient_history(patient_id):
    if patient_id in st.session_state.patient_history:
        history = st.session_state.patient_history[patient_id]
        df = pd.DataFrame(history)
        st.dataframe(df)
        
        st.subheader("Patient Exam History Visualization")
        fig, ax = plt.subplots(figsize=(10, 6))
        sns.scatterplot(data=df, x='date', y='confidence', hue='class', size='confidence', ax=ax)
        ax.set_title(f"Exam Confidence Over Time for Patient {patient_id}")
        ax.set_xlabel("Date")
        ax.set_ylabel("Confidence Score")
        st.pyplot(fig)
    else:
        st.info("No history found for this patient.")

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
        st.error(f"An error occurred during user management: {str(e)}")

def save_patient_exam(patient_id, exam_data):
    try:
        if not os.path.exists(PATIENT_DATA_FILE):
            wb = Workbook()
            ws = wb.active
            ws.append(['Patient ID', 'Exam Date', 'Classification', 'Confidence'])
        else:
            wb = load_workbook(PATIENT_DATA_FILE)
            ws = wb.active
        
        ws.append([patient_id, exam_data['date'], exam_data['class'], exam_data['confidence']])
        wb.save(PATIENT_DATA_FILE)
    except Exception as e:
        st.error(f"Error saving patient exam data: {str(e)}")

def view_all_patient_data():
    st.header("All Patient Data")
    try:
        if os.path.exists(PATIENT_DATA_FILE):
            df = pd.read_excel(PATIENT_DATA_FILE)
            st.dataframe(df)
            
            st.subheader("Export Data")
            csv = df.to_csv(index=False)
            b64 = base64.b64encode(csv.encode()).decode()
            href = f'<a href="data:file/csv;base64,{b64}" download="patient_data.csv">Download CSV File</a>'
            st.markdown(href, unsafe_allow_html=True)
        else:
            st.info("No patient data available.")
    except Exception as e:
        st.error(f"Error viewing patient data: {str(e)}")

def generate_report(patient_id):
    st.header(f"Report for Patient {patient_id}")
    try:
        if os.path.exists(PATIENT_DATA_FILE):
            df = pd.read_excel(PATIENT_DATA_FILE)
            patient_data = df[df['Patient ID'] == patient_id]
            
            if not patient_data.empty:
                st.subheader("Exam History")
                st.dataframe(patient_data)
                
                st.subheader("Exam Trend")
                fig, ax = plt.subplots(figsize=(10, 6))
                sns.lineplot(data=patient_data, x='Exam Date', y='Confidence', ax=ax)
                ax.set_title(f"Exam Confidence Trend for Patient {patient_id}")
                ax.set_xlabel("Exam Date")
                ax.set_ylabel("Confidence Score")
                st.pyplot(fig)
                
                st.subheader("Classification Distribution")
                class_dist = patient_data['Classification'].value_counts()
                fig, ax = plt.subplots(figsize=(8, 8))
                ax.pie(class_dist.values, labels=class_dist.index, autopct='%1.1f%%')
                ax.set_title("Classification Distribution")
                st.pyplot(fig)
                
                st.subheader("Export Report")
                report = patient_data.to_csv(index=False)
                b64 = base64.b64encode(report.encode()).decode()
                href = f'<a href="data:file/csv;base64,{b64}" download="patient_{patient_id}_report.csv">Download Patient Report</a>'
                st.markdown(href, unsafe_allow_html=True)
            else:
                st.info(f"No data found for Patient {patient_id}")
        else:
            st.info("No patient data available.")
    except Exception as e:
        st.error(f"Error generating report: {str(e)}")

def main():
    init_login_file()
    if not st.session_state.get('logged_in', False):
        login_page()
    else:
        st.title("Fractured Arm Detection using AI")
        st.sidebar.title(f"Welcome, {st.session_state.username}")
        if st.sidebar.button("Logout"):
            st.session_state.logged_in = False
            st.session_state.username = None
            st.rerun()

        options = ["Classify Exam", "View Patient History", "View All Patient Data", "Generate Patient Report"]
        if st.session_state.username == 'admin':
            options.append("User Management")
        menu_option = st.sidebar.radio("Choose an option:", options)

        if menu_option == "Classify Exam":
            st.header("Classify Exam")
            patient_id = st.text_input("Enter Patient
