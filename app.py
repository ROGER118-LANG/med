import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from PIL import Image, ImageOps
from keras.models import load_model
from keras.layers import DepthwiseConv2D
from keras.utils import custom_object_scope
import io
import os
from datetime import datetime, timedelta
from openpyxl import Workbook, load_workbook
import hashlib
import plotly.graph_objects as go
import plotly.express as px

# Disable scientific notation for clarity
np.set_printoptions(suppress=True)

# Initialize session state
if 'patient_history' not in st.session_state:
    st.session_state.patient_history = {}
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'username' not in st.session_state:
    st.session_state.username = None
if 'user_departments' not in st.session_state:
    st.session_state.user_departments = []

# File to store login information
LOGIN_FILE = 'login_info.xlsx'

# Define paths for models and labels
model_paths = {
    "Pneumology": {
        "Pneumonia": "pneumonia_model.h5",
        "Tuberculosis": "tuberculosis_model.h5",
        "Lung Cancer": "lung_cancer_model.h5"
    },
    "Neurology": {
        "Brain Tumor": "brain_tumor_model.h5"
    },
    "Orthopedics": {
        "Fractured Arm": "fractured_arm_model.h5",
        "Achilles Tendon Rupture": "achilles_tendon_rupture_model.h5",
        "ACL": "acl_model.h5",
        "Ankle Sprain": "ankle_sprain_model.h5",
        "Calcaneus Fracture": "calcaneus_fracture_model.h5"
    }
}

label_paths = {
    "Pneumology": {
        "Pneumonia": "pneumonia_labels.txt",
        "Tuberculosis": "tuberculosis_labels.txt",
        "Lung Cancer": "lung_cancer_labels.txt"
    },
    "Neurology": {
        "Brain Tumor": "brain_tumor_labels.txt"
    },
    "Orthopedics": {
        "Fractured Arm": "fractured_arm_labels.txt",
        "Achilles Tendon Rupture": "achilles_tendon_rupture_labels.txt",
        "ACL": "acl_labels.txt",
        "Ankle Sprain": "ankle_sprain_labels.txt",
        "Calcaneus Fracture": "calcaneus_fracture_labels.txt"
    }
}

def custom_depthwise_conv2d(*args, **kwargs):
    if 'groups' in kwargs:
        kwargs.pop('groups')
    return DepthwiseConv2D(*args, **kwargs)

def load_model_and_labels(model_path, label_path):
    try:
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found: {model_path}")
        if not os.path.exists(label_path):
            raise FileNotFoundError(f"Label file not found: {label_path}")
        
        with custom_object_scope({'DepthwiseConv2D': custom_depthwise_conv2d}):
            model = load_model(model_path, compile=False)
        
        with open(label_path, "r") as f:
            class_names = f.readlines()
        return model, class_names
    except Exception as e:
        st.error(f"Error loading model and labels: {str(e)}")
        return None, None

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

# ... (rest of the functions remain the same)

def analyze_department_performance():
    st.subheader("Department Performance Analysis")
    
    all_exams = []
    for patient_history in st.session_state.patient_history.values():
        all_exams.extend(patient_history)
    
    if not all_exams:
        st.warning("No exam data available for analysis.")
        return
    
    df = pd.DataFrame(all_exams)
    df['department'] = df['model'].apply(lambda x: x.split('_')[0])
    
    # Overall department performance
    st.write("Overall Department Performance")
    dept_performance = df.groupby('department')['confidence'].mean().sort_values(ascending=False)
    fig_dept = px.bar(dept_performance, x=dept_performance.index, y='confidence',
                      title="Average Confidence Score by Department")
    st.plotly_chart(fig_dept)
    
    # Department performance over time
    st.write("Department Performance Over Time")
    df['date'] = pd.to_datetime(df['date'])
    df_time = df.set_index('date').groupby([pd.Grouper(freq='M'), 'department'])['confidence'].mean().reset_index()
    fig_time = px.line(df_time, x='date', y='confidence', color='department',
                       title="Average Confidence Score Over Time by Department")
    st.plotly_chart(fig_time)
    
    # Top models by confidence
    st.write("Top Models by Confidence Score")
    top_models = df.groupby('model')['confidence'].mean().sort_values(ascending=False).head(5)
    fig_models = px.bar(top_models, x=top_models.index, y='confidence',
                        title="Top 5 Models by Average Confidence Score")
    st.plotly_chart(fig_models)

def main():
    initialize_login_file()
    if not st.session_state.get('logged_in', False):
        login_page()
    else:
        st.title("MedVision")
        st.sidebar.title(f"Welcome, {st.session_state.username}")
        if st.sidebar.button("Logout"):
            st.session_state.logged_in = False
            st.session_state.username = None
            st.session_state.user_departments = []
            st.rerun()

        # Sidebar menu
        if 'menu_option' not in st.session_state:
            st.session_state.menu_option = "Classify Exam"

        options = ["Classify Exam", "View Patient History", "Compare Patients", "Generate Report", "Department Analysis"]
        if st.session_state.username == 'admin':
            options.append("User Management")

        st.session_state.menu_option = st.sidebar.radio("Choose an option:", options, key="radio_menu")

        if st.session_state.menu_option == "Classify Exam":
            st.header("Classify Exam")
            
            department = st.selectbox("Choose a department:", st.session_state.user_departments)
            
            if department:
                patient_id = st.text_input("Enter Patient ID:")
                model_option = st.selectbox("Choose a model for analysis:", list(model_paths[department].keys()))
                uploaded_file = st.file_uploader("Upload an image", type=["jpg", "jpeg", "png"])
                
                if st.button("Classify"):
                    result = classify_exam(patient_id, f"{department}_{model_option}", uploaded_file)
                    if result:
                        st.write("Classification Result:")
                        st.json(result)
            else:
                st.warning("You don't have access to any department.")

        elif st.session_state.menu_option == "View Patient History":
            st.header("Patient History")
            patient_id = st.text_input("Enter Patient ID:")
            if st.button("View History"):
                view_patient_history(patient_id)

        elif st.session_state.menu_option == "Compare Patients":
            compare_patients()

        elif st.session_state.menu_option == "Generate Report":
            st.header("Generate Medical Report")
            patient_id = st.text_input("Enter Patient ID:")
            if st.button("Generate Report"):
                generate_report(patient_id)
                download_report(patient_id)

        elif st.session_state.menu_option == "Department Analysis":
            analyze_department_performance()

        elif st.session_state.menu_option == "User Management":
            manage_users()

if __name__ == "__main__":
    main()
