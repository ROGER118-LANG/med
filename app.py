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
        st.write(f"Model option selected: {model_option}")
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

def manage_users():
    st.header("User Management")
    wb = load_workbook(LOGIN_FILE)
    ws = wb.active

    # Show existing users
    st.subheader("Existing Users")
    user_data = {row[0]: row for row in ws.iter_rows(min_row=2, values_only=True)}
    user_df = pd.DataFrame(user_data.values(), columns=["Username", "Password", "Last Login"])
    st.dataframe(user_df)

    # Add new user
    st.subheader("Add User")
    new_username = st.text_input("New Username")
    new_password = st.text_input("New Password", type="password")
    if st.button("Add User"):
        if new_username and new_password:
            hashed_password = hash_password(new_password)
            ws.append([new_username, hashed_password, ""])
            wb.save(LOGIN_FILE)
            st.success("User added successfully!")
        else:
            st.error("Please provide both username and password.")

    # Edit user
    st.subheader("Edit User")
    edit_username = st.selectbox("Select User to Edit", list(user_data.keys()))
    edited_password = st.text_input("New Password for Selected User", type="password")
    if st.button("Edit User"):
        if edited_password:
            hashed_password = hash_password(edited_password)
            for row in ws.iter_rows(min_row=2):
                if row[0].value == edit_username:
                    row[1].value = hashed_password
                    break
            wb.save(LOGIN_FILE)
            st.success("User edited successfully!")
        else:
            st.error("Please provide a new password.")

    # Remove user
    st.subheader("Remove User")
    remove_username = st.selectbox("Select User to Remove", list(user_data.keys()))
    if st.button("Remove User"):
        ws.delete_rows(list(user_data.keys()).index(remove_username) + 2)
        wb.save(LOGIN_FILE)
        st.success("User removed successfully!")

def main():
    init_login_file()
    if not st.session_state.get('logged_in', False):
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

        # Add "User Management" option for admin
        if st.session_state.username == 'admin':
            menu_option = st.sidebar.radio("Choose an option:", ("Classify Exam", "View Patient History", "User Management"))

        if menu_option == "Classify Exam":
            st.header("Classify Exam")
            patient_id = st.text_input("Enter Patient ID:")
            model_option = st.selectbox("Choose a model for analysis:", ("Pneumonia", "Tuberculosis", "Cancer"))
            uploaded_file = st.file_uploader("Upload X-ray or CT scan image", type=["jpg", "jpeg", "png"])
            if st.button("Classify"):
                classify_exam(patient_id, model_option, uploaded_file)
        elif menu_option == "View Patient History":
            st.header("Patient History")
            patient_id = st.text_input("Enter Patient ID:")
            if st.button("View History"):
                view_patient_history(patient_id)
        elif menu_option == "User Management":
            manage_users()


        # Sidebar menu
        menu_option = st.sidebar.radio("Choose an option:", ("Classify Exam", "View Patient History"))

        # Add "User Management" option for admin
        if st.session_state.username == 'admin':
            menu_option = st.sidebar.radio("Choose an option:", ("Classify Exam", "View Patient History", "User Management"))

        if menu_option == "Classify Exam":
            st.header("Classify Exam")
            patient_id = st.text_input("Enter Patient ID:")
            model_option = st.selectbox("Choose a model for analysis:", ("Pneumonia", "Tuberculosis", "Cancer"))
            uploaded_file = st.file_uploader("Upload X-ray or CT scan image", type=["jpg", "jpeg", "png"])

            if st.button("Classify"):
                classify_exam(patient_id, model_option, uploaded_file)

        elif menu_option == "View Patient History":
            st.header("Patient History")
            patient_id = st.text_input("Enter Patient ID:")
            if st.button("View History"):
                view_patient_history(patient_id)

        elif menu_option == "User Management":
            manage_users()

if __name__ == "__main__":
    main()
