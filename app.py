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
from sklearn.metrics import confusion_matrix
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

def classify_exam(patient_id, model_option, uploaded_file):
    if uploaded_file is not None:
        st.write(f"Selected model option: {model_option}")
        
        department, model = model_option.split('_', 1)
        if department not in model_paths or model not in model_paths[department]:
            st.error(f"Model option '{model_option}' not found in available models.")
            return None
        
        try:
            model, class_names = load_model_and_labels(model_paths[department][model], label_paths[department][model])
            
            if model is None or class_names is None:
                st.error("Failed to load model or labels. Please check the files and try again.")
                return None
            
            processed_image = preprocess_image(uploaded_file)
            
            if processed_image is None:
                st.error("Failed to preprocess the image. Please try a different image.")
                return None
            
            class_name, confidence_score = predict(model, processed_image, class_names)
            
            if class_name is None or confidence_score is None:
                st.error("An error occurred during prediction. Please try again.")
                return None
            
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
        except Exception as e:
            st.error(f"An error occurred during classification: {str(e)}")
    else:
        st.error("Please upload an image first.")
    return None

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def initialize_login_file():
    if not os.path.exists(LOGIN_FILE):
        wb = Workbook()
        ws = wb.active
        ws.append(['Username', 'Password', 'Last Login', 'Expiration Date', 'Role', 'Departments'])
        admin_password = hash_password('admin123')
        ws.append(['admin', admin_password, '', '', 'admin', 'Pneumology,Neurology,Orthopedics'])
        wb.save(LOGIN_FILE)

def verify_login(username, password):
    try:
        wb = load_workbook(LOGIN_FILE)
        ws = wb.active
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row[0] == username and row[1] == hash_password(password):
                is_admin = len(row) > 4 and row[4] == 'admin'
                
                if not is_admin:
                    if len(row) > 3 and row[3]:
                        expiration_date = row[3]
                        if isinstance(expiration_date, datetime) and datetime.now() > expiration_date:
                            return False, "Account expired", []
                
                departments = row[5].split(',') if len(row) > 5 and row[5] else []
                return True, "Success", departments
        
        return False, "Invalid credentials", []
    except Exception as e:
        st.error(f"An error occurred while verifying login: {str(e)}")
        return False, "Login verification failed", []

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
        login_success, message, departments = verify_login(username, password)
        if login_success:
            st.session_state.logged_in = True
            st.session_state.username = username
            st.session_state.user_departments = departments
            update_last_login(username)
            st.success("Login successful!")
        else:
            st.error(message)

def view_patient_history(patient_id):
    if patient_id in st.session_state.patient_history:
        history = st.session_state.patient_history[patient_id]
        df = pd.DataFrame(history)
        st.dataframe(df)
        
        st.subheader("Patient Exam History Visualization")
        fig = px.scatter(df, x='date', y='confidence', color='model', size='confidence',
                         title=f"Exam Confidence Over Time for Patient {patient_id}")
        fig.update_layout(xaxis_title="Date", yaxis_title="Confidence Score")
        st.plotly_chart(fig)
    else:
        st.info("No history found for this patient.")

def compare_patients():
    st.subheader("Compare Patients")
    patient_ids = list(st.session_state.patient_history.keys())
    if len(patient_ids) < 2:
        st.warning("At least two patients with history are needed for comparison.")
        return
    
    patient1 = st.selectbox("Select the first patient", patient_ids)
    patient2 = st.selectbox("Select the second patient", [id for id in patient_ids if id != patient1])
    
    if st.button("Compare"):
        df1 = pd.DataFrame(st.session_state.patient_history[patient1])
        df2 = pd.DataFrame(st.session_state.patient_history[patient2])
        
        fig = go.Figure()
        fig.add_trace(go.Box(y=df1['confidence'], name=f"Patient {patient1}", boxpoints="all"))
        fig.add_trace(go.Box(y=df2['confidence'], name=f"Patient {patient2}", boxpoints="all"))
        
        fig.update_layout(title="Comparison of Exam Confidence Scores",
                          yaxis_title="Confidence Score",
                          boxmode="group")
        st.plotly_chart(fig)

def manage_users():
    st.header("User Management")
    
    try:
        wb = load_workbook(LOGIN_FILE)
        ws = wb.active
        user_data = {row[0]: row for row in ws.iter_rows(min_row=2, values_only=True)}
        
        clean_user_data = [
            (row if len(row) == 6 else row + (None,) * (6 - len(row))) 
            for row in user_data.values()
        ]
        
        df_user = pd.DataFrame(clean_user_data, columns=["Username", "Password", "Last Login", "Expiration Date", "Role", "Departments"])
        
        st.dataframe(df_user)

        st.subheader("Add User")
        new_username = st.text_input("New Username")
        new_password = st.text_input("New Password", type="password")
        new_role = st.selectbox("Role", ["user", "admin"])
        validity_days = st.number_input("Account Validity (days)", min_value=1, value=7, step=1)
        new_departments = st.multiselect("Departments", ["Pneumology", "Neurology", "Orthopedics"])
        
        if st.button("Add User"):
            if new_username and new_password:
                password_hash = hash_password(new_password)
                expiration_date = datetime.now() + timedelta(days=validity_days) if new_role != "admin" else None
                ws.append([new_username, password_hash, "", expiration_date, new_role, ",".join(new_departments)])
                wb.save(LOGIN_FILE)
                st.success("User added successfully!")
            else:
                st.error("Please provide both username and password.")

        st.subheader("Edit User")
        edit_username = st.selectbox("Select User to Edit", list(user_data.keys()))
        edited_password = st.text_input("New Password for Selected User", type="password")
        edited_role = st.selectbox("New Role", ["user", "admin"])
        edited_validity = st.number_input("New Account Validity (days)", min_value=1, value=7, step=1)
        edited_departments = st.multiselect("New Departments", ["Pneumology", "Neurology", "Orthopedics"])
        
        if st.button("Edit User"):
            if edited_password:
                password_hash = hash_password(edited_password)
                for row in ws.iter_rows(min_row=2):
                    if row[0].value == edit_username:
                        row[1].value = password_hash
                        row[3].value = datetime.now() + timedelta(days=edited_validity) if edited_role != "admin" else None
                        row[4].value = edited_role
                        row[5].value = ",".join(edited_departments)
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

def generate_report(patient_id):
    if patient_id in st.session_state.patient_history:
        history = st.session_state.patient_history[patient_id]
        df = pd.DataFrame(history)
        
        st.subheader(f"Medical Report for Patient {patient_id}")
        
        # Summary statistics
        st.write("Summary Statistics:")
        st.write(f"Total exams: {len(df)}")
st.write(f"Average confidence score: {df['confidence'].mean():.2f}")
        st.write(f"Most recent exam: {df['date'].max()}")
        
        # Exam history table
        st.write("Exam History:")
        st.dataframe(df)
        
        # Visualizations
        st.subheader("Visualizations")
        
        # Confidence score over time
        fig_confidence = px.line(df, x='date', y='confidence', color='model',
                                 title="Confidence Score Over Time")
        st.plotly_chart(fig_confidence)
        
        # Exam distribution by model
        fig_distribution = px.pie(df, names='model', title="Exam Distribution by Model")
        st.plotly_chart(fig_distribution)
        
        # Generate PDF report
        generate_pdf_report(patient_id, df)

def generate_pdf_report(patient_id, df):
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        from io import BytesIO
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        elements = []
        
        # Title
        styles = getSampleStyleSheet()
        elements.append(Paragraph(f"Medical Report for Patient {patient_id}", styles['Title']))
        elements.append(Spacer(1, 12))
        
        # Summary statistics
        elements.append(Paragraph("Summary Statistics", styles['Heading2']))
        summary_data = [
            ["Total exams", str(len(df))],
            ["Average confidence score", f"{df['confidence'].mean():.2f}"],
            ["Most recent exam", str(df['date'].max())]
        ]
        summary_table = Table(summary_data)
        summary_table.setStyle(TableStyle([
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
        elements.append(summary_table)
        elements.append(Spacer(1, 12))
        
        # Exam history table
        elements.append(Paragraph("Exam History", styles['Heading2']))
        exam_data = [df.columns.tolist()] + df.values.tolist()
        exam_table = Table(exam_data)
        exam_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(exam_table)
        
        doc.build(elements)
        pdf = buffer.getvalue()
        buffer.close()
        
        return pdf
    except Exception as e:
        st.error(f"Error generating PDF report: {str(e)}")
        return None

def download_report(patient_id):
    if patient_id in st.session_state.patient_history:
        history = st.session_state.patient_history[patient_id]
        df = pd.DataFrame(history)
        pdf = generate_pdf_report(patient_id, df)
        
        if pdf:
            st.download_button(
                label="Download PDF Report",
                data=pdf,
                file_name=f"medical_report_patient_{patient_id}.pdf",
                mime="application/pdf"
            )
        else:
            st.error("Failed to generate PDF report.")
    else:
        st.error("No history found for this patient.")

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
