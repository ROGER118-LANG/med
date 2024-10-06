import streamlit as st
from keras.models import load_model
from keras.layers import DepthwiseConv2D
from keras.utils import custom_object_scope
from PIL import Image, ImageOps
import numpy as np
import io
import os
import pandas as pd
from datetime import datetime
from openpyxl import Workbook, load_workbook
import hashlib

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

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def init_login_file():
    if not os.path.exists(LOGIN_FILE):
        wb = Workbook()
        ws = wb.active
        ws.append(['Username', 'Password', 'Last Login'])
        admin_password = hash_password('123')
        ws.append(['admin', admin_password, ''])
        wb.save(LOGIN_FILE)

def check_login(username, password):
    wb = load_workbook(LOGIN_FILE)
    ws = wb.active
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[0] == username and row[1] == hash_password(password):
            return True
    return False

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
        if check_login(username, password):
            st.session_state.logged_in = True
            st.session_state.username = username
            update_last_login(username)
            st.success("Logged in successfully!")
        else:
            st.error("Invalid username or password")

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
        st.error(f"Error loading model and labels: {str(e)}")
        return None, None

def preprocess_image(uploaded_file):
    image_bytes = uploaded_file.getvalue()
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    size = (224, 224)
    image = ImageOps.fit(image, size, Image.Resampling.LANCZOS)
    image_array = np.asarray(image)
    normalized_image_array = (image_array.astype(np.float32) / 127.5) - 1
    data = np.ndarray(shape=(1, 224, 224, 3), dtype=np.float32)
    data[0] = normalized_image_array
    return data

def predict(model, data, class_names):
    try:
        prediction = model.predict(data)
        index = np.argmax(prediction)
        class_name = class_names[index]
        confidence_score = prediction[0][index]
        return class_name[2:], confidence_score
    except Exception as e:
        st.error(f"Error during prediction: {str(e)}")
        return None, None

def classify_exam(patient_id, model_option, uploaded_file):
    if uploaded_file is not None:
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
                
                st.success("Exam classified successfully!")
                return result
            else:
                st.error("An error occurred during prediction. Please try again.")
        else:
            st.error("Failed to load the model and labels. Please check the files and try again.")
    else:
        st.error("Please upload an image first.")
    return None

def view_patient_history(patient_id):
    if patient_id in st.session_state.patient_history:
        history = st.session_state.patient_history[patient_id]
        df = pd.DataFrame(history)
        st.dataframe(df)
    else:
        st.info("No history found for this patient.")

def main():
    init_login_file()

    if not st.session_state.logged_in:
        login_page()
    else:
        st.title("Medical Image Analysis using AI")
        st.sidebar.title(f"Welcome, {st.session_state.username}")

        if st.sidebar.button("Logout"):
            st.session_state.logged_in = False
            st.session_state.username = None
            st.experimental_rerun()

        # Sidebar menu
        menu_option = st.sidebar.radio("Choose an option:", ("Classify Exam", "View Patient History"))

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

        if menu_option == "Classify Exam":
            st.header("Classify Exam")
            patient_id = st.text_input("Enter Patient ID:")
            model_option = st.selectbox("Choose a model for analysis:", ("Pneumonia", "Tuberculosis", "Cancer"))
            uploaded_file = st.file_uploader("Choose an image...", type=["jpg", "jpeg", "png"])

            if uploaded_file is not None:
                st.image(uploaded_file, caption="Uploaded Image", use_column_width=True)

            if st.button("Analyze"):
                if patient_id:
                    result = classify_exam(patient_id, model_option, uploaded_file)
                    if result:
                        st.write(f"Model: {result['model']}")
                        st.write(f"Class: {result['class']}")
                        st.write(f"Confidence Score: {result['confidence']:.2f}")
                else:
                    st.error("Please enter a Patient ID.")

        elif menu_option == "View Patient History":
            st.header("View Patient History")
            patient_id = st.text_input("Enter Patient ID to view history:")
            if st.button("View History"):
                if patient_id:
                    view_patient_history(patient_id)
                else:
                    st.error("Please enter a Patient ID.")

if __name__ == "__main__":
    main()
