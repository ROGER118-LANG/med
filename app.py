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
if 'is_admin' not in st.session_state:
    st.session_state.is_admin = False

# File to store login information
LOGIN_FILE = 'login_info.xlsx'

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def init_login_file():
    if not os.path.exists(LOGIN_FILE):
        wb = Workbook()
        ws = wb.active
        ws.append(['Username', 'Password', 'Last Login', 'Expiration Date', 'Is Admin'])
        admin_password = hash_password('123')
        ws.append(['admin', admin_password, '', '', True])
        wb.save(LOGIN_FILE)

def check_login(username, password):
    wb = load_workbook(LOGIN_FILE)
    ws = wb.active
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[0] == username and row[1] == hash_password(password):
            expiration_date = row[3]
            if expiration_date and datetime.now() > expiration_date:
                return False, "Account expired"
            return True, row[4]  # Return login success and admin status
    return False, "Invalid credentials"

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
        login_success, result = check_login(username, password)
        if login_success:
            st.session_state.logged_in = True
            st.session_state.username = username
            st.session_state.is_admin = result
            update_last_login(username)
            st.success("Logged in successfully!")
        else:
            st.error(result)

def manage_users():
    st.header("Manage Users")
    
    # Add new user
    st.subheader("Add New User")
    new_username = st.text_input("New Username")
    new_password = st.text_input("New Password", type="password")
    expiration_days = st.number_input("Account active for (days)", min_value=1, value=30)
    is_admin = st.checkbox("Is Admin")
    if st.button("Add User"):
        add_user(new_username, new_password, expiration_days, is_admin)

    # Edit/Delete existing users
    st.subheader("Existing Users")
    wb = load_workbook(LOGIN_FILE)
    ws = wb.active
    users = [row[0].value for row in ws.iter_rows(min_row=2, max_col=1)]
    selected_user = st.selectbox("Select User", users)
    
    if selected_user:
        user_data = get_user_data(selected_user)
        new_password = st.text_input("New Password (leave blank to keep current)", type="password")
        new_expiration_days = st.number_input("New Account active for (days)", min_value=1, value=user_data['expiration_days'])
        new_is_admin = st.checkbox("Is Admin", value=user_data['is_admin'])
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Update User"):
                update_user(selected_user, new_password, new_expiration_days, new_is_admin)
        with col2:
            if st.button("Delete User"):
                delete_user(selected_user)

def add_user(username, password, expiration_days, is_admin):
    wb = load_workbook(LOGIN_FILE)
    ws = wb.active
    hashed_password = hash_password(password)
    expiration_date = datetime.now() + timedelta(days=expiration_days)
    ws.append([username, hashed_password, '', expiration_date.strftime("%Y-%m-%d %H:%M:%S"), is_admin])
    wb.save(LOGIN_FILE)
    st.success(f"User {username} added successfully!")

def get_user_data(username):
    wb = load_workbook(LOGIN_FILE)
    ws = wb.active
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[0] == username:
            expiration_date = datetime.strptime(row[3], "%Y-%m-%d %H:%M:%S") if row[3] else None
            expiration_days = (expiration_date - datetime.now()).days if expiration_date else 30
            return {
                'username': row[0],
                'expiration_days': expiration_days,
                'is_admin': row[4]
            }
    return None

def update_user(username, new_password, new_expiration_days, new_is_admin):
    wb = load_workbook(LOGIN_FILE)
    ws = wb.active
    for row in ws.iter_rows(min_row=2):
        if row[0].value == username:
            if new_password:
                row[1].value = hash_password(new_password)
            row[3].value = (datetime.now() + timedelta(days=new_expiration_days)).strftime("%Y-%m-%d %H:%M:%S")
            row[4].value = new_is_admin
            break
    wb.save(LOGIN_FILE)
    st.success(f"User {username} updated successfully!")

def delete_user(username):
    wb = load_workbook(LOGIN_FILE)
    ws = wb.active
    for row in ws.iter_rows(min_row=2):
        if row[0].value == username:
            ws.delete_rows(row[0].row)
            break
    wb.save(LOGIN_FILE)
    st.success(f"User {username} deleted successfully!")

# ... (keep all the previous functions for image classification)
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
        st.write(f"Model option selected: {model_option}")  # Depuração
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
            st.session_state.is_admin = False
            st.experimental_rerun()

        # Sidebar menu
        menu_options = ["Classify Exam", "View Patient History"]
        if st.session_state.is_admin:
            menu_options.append("Manage Users")
        
        menu_option = st.sidebar.radio("Choose an option:", menu_options)

        if menu_option == "Classify Exam":
            # ... (keep the existing classify exam code)
            pass
        elif menu_option == "View Patient History":
            # ... (keep the existing view patient history code)
            pass
        elif menu_option == "Manage Users" and st.session_state.is_admin:
            manage_users()

if __name__ == "__main__":
    main()

