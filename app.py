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

# Define model and label paths
model_paths = {
    "Pneumonia": "keras_model.h5",
    "Tuberculosis": "tuberculose_model.h5",
    "Cancer": "cancer_model.h5"
}

label_paths = {
    "Pneumonia": "labels.txt",
    "Tuberculosis": "tuberculose_labels.txt",
    "Cancer": "cancer_labels.txt"
}

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def init_login_file():
    if not os.path.exists(LOGIN_FILE):
        wb = Workbook()
        ws = wb.active
        ws.append(['Username', 'Password', 'Last Login', 'Valid Until', 'Is Admin'])
        admin_password = hash_password('123')
        ws.append(['admin', admin_password, '', '', 'True'])
        wb.save(LOGIN_FILE)

def check_login(username, password):
    wb = load_workbook(LOGIN_FILE)
    ws = wb.active
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[0] == username and row[1] == hash_password(password):
            valid_until = row[3]
            if valid_until:
                if datetime.now() > datetime.strptime(valid_until, "%Y-%m-%d %H:%M:%S"):
                    return False, "Your account has expired. Please contact the admin."
            return True, ""
    return False, "Invalid username or password"

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
        success, message = check_login(username, password)
        if success:
            st.session_state.logged_in = True
            st.session_state.username = username
            update_last_login(username)
            st.success("Logged in successfully!")
        else:
            st.error(message)

def custom_depthwise_conv2d(*args, **kwargs):
    if kwargs is None:
        kwargs = {}
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
        if model is None:
            raise ValueError("Model is not loaded properly")
        if data is None:
            raise ValueError("Input data is None")
        if class_names is None or len(class_names) == 0:
            raise ValueError("Class names are not loaded properly")
        
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
        st.write(f"Model option selected: {model_option}")
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
                st.error("Error processing the image. Please try again with a different image.")
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

def is_admin(username):
    if not username:
        return False
    try:
        wb = load_workbook(LOGIN_FILE)
        ws = wb.active
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row and len(row) > 0 and row[0] == username:
                is_admin_value = row[4] if len(row) > 4 else False
                return str(is_admin_value).lower() == 'true'
    except Exception as e:
        st.error(f"Error checking admin status: {str(e)}")
    return False

def manage_users():
    st.header("User Management")
    try:
        wb = load_workbook(LOGIN_FILE)
        ws = wb.active
        # Show existing users
        st.subheader("Existing Users")
        user_data = list(ws.iter_rows(min_row=2, values_only=True))
        
        max_columns = max(len(row) for row in user_data) if user_data else 5
        user_data = [row + (None,) * (max_columns - len(row)) for row in user_data]
        
        columns = ["Username", "Password", "Last Login", "Valid Until", "Is Admin"]
        columns = columns[:max_columns]
        user_df = pd.DataFrame(user_data, columns=columns)
        st.dataframe(user_df)

        # Add new user
        st.subheader("Add User")
        new_username = st.text_input("New Username")
        new_password = st.text_input("New Password", type="password")
        is_admin = st.checkbox("Is Admin")
        valid_days = st.number_input("Valid for (days)", min_value=1, value=7)
        if st.button("Add User"):
            if new_username and new_password:
                hashed_password = hash_password(new_password)
                valid_until = (datetime.now() + timedelta(days=valid_days)).strftime("%Y-%m-%d %H:%M:%S")
                new_row = [new_username, hashed_password, "", valid_until, str(is_admin)]
                ws.append(new_row[:max_columns])
                wb.save(LOGIN_FILE)
                st.success("User added successfully!")
            else:
                st.error("Please provide both username and password.")

        # Edit user
        st.subheader("Edit User")
        usernames = [row[0] for row in user_data if row and len(row) > 0]
        if usernames:
            edit_username = st.selectbox("Select User to Edit", usernames)
            edited_password = st.text_input("New Password for Selected User", type="password")
            edit_is_admin = st.checkbox("Is Admin", value=False)
            edit_valid_days = st.number_input("Extend validity             by (days)", min_value=1, value=7)
            if st.button("Update User"):
                if edited_password:
                    hashed_password = hash_password(edited_password)
                    new_valid_until = (datetime.now() + timedelta(days=edit_valid_days)).strftime("%Y-%m-%d %H:%M:%S")
                    for row in ws.iter_rows(min_row=2):
                        if row[0].value == edit_username:
                            row[1].value = hashed_password
                            row[3].value = new_valid_until
                            row[4].value = str(edit_is_admin)
                            break
                    wb.save(LOGIN_FILE)
                    st.success("User updated successfully!")
                else:
                    st.error("Please provide a new password.")

    except Exception as e:
        st.error(f"Error managing users: {str(e)}")

# Main App Layout
def app_layout():
    st.title("Medical Exam Classifier")
    patient_id = st.text_input("Patient ID", placeholder="Enter Patient ID")
    model_option = st.selectbox("Select Exam Type", ["Pneumonia", "Tuberculosis", "Cancer"])
    
    uploaded_file = st.file_uploader("Choose an X-ray image...", type=["jpg", "jpeg", "png"])

    if st.button("Classify Exam"):
        result = classify_exam(patient_id, model_option, uploaded_file)
        if result:
            st.write(f"**Prediction:** {result['class']} with **confidence score** of {result['confidence']:.2f}")
    
    if st.button("View Patient History"):
        view_patient_history(patient_id)

# Main entry point of the app
if __name__ == '__main__':
    init_login_file()
    
    if not st.session_state.logged_in:
        login_page()
    else:
        if is_admin(st.session_state.username):
            if st.sidebar.checkbox("Manage Users"):
                manage_users()
        
        st.sidebar.title("Menu")
        if st.sidebar.button("Log Out"):
            st.session_state.logged_in = False
            st.session_state.username = None
            st.success("Logged out successfully!")
        else:
            app_layout()

