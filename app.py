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
                # Verifica se a coluna 'Is Admin' existe
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
        
        # Ensure all rows have the same number of columns
        max_columns = max(len(row) for row in user_data) if user_data else 5
        user_data = [row + (None,) * (max_columns - len(row)) for row in user_data]
        
        columns = ["Username", "Password", "Last Login", "Valid Until", "Is Admin"]
        columns = columns[:max_columns]  # Adjust columns based on actual data
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
                ws.append(new_row[:max_columns])  # Ensure we only add existing columns
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
            edit_valid_days = st.number_input("Extend validity (days)", min_value=0, value=0)
            if st.button("Edit User"):
                for row in ws.iter_rows(min_row=2):
                    if row[0].value == edit_username:
                        if edited_password:
                            row[1].value = hash_password(edited_password)
                        if len(row) > 4:
                            row[4].value = str(edit_is_admin)
                        if edit_valid_days > 0 and len(row) > 3:
                            current_valid_until = datetime.strptime(row[3].value, "%Y-%m-%d %H:%M:%S") if row[3].value else datetime.now()
                            new_valid_until = (current_valid_until + timedelta(days=edit_valid_days)).strftime("%Y-%m-%d %H:%M:%S")
                            row[3].value = new_valid_until
                        break
                wb.save(LOGIN_FILE)
                st.success("User edited successfully!")

        # Remove user
        st.subheader("Remove User")
        if usernames:
            remove_username = st.selectbox("Select User to Remove", usernames)
            if st.button("Remove User"):
                for idx, row in enumerate(ws.iter_rows(min_row=2), start=2):
                    if row[0].value == remove_username:
                        ws.delete_rows(idx)
                        break
                wb.save(LOGIN_FILE)
                st.success("User removed successfully!")
        else:
            st.info("No users to remove.")
    except Exception as e:
        st.error(f"Error managing users: {str(e)}")

def display_image(uploaded_file):
    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        st.image(image, caption='Uploaded Image', use_column_width=True)

def export_patient_history(patient_id):
    if patient_id in st.session_state.patient_history:
        df = pd.DataFrame(st.session_state.patient_history[patient_id])
        csv = df.to_csv(index=False)
        st.download_button(
            label="Download Patient History",
            data=csv,
            file_name=f"{patient_id}_history.csv",
            mime="text/csv",
        )

def compare_models(uploaded_file):
    results = {}
    for model_option in model_paths.keys():
        result = classify_exam("", model_option, uploaded_file)
        if result:
            results[model_option] = result
    
    comparison_df = pd.DataFrame(results).T
    st.dataframe(comparison_df)

def display_usage_stats():
    total_exams = sum(len(history) for history in st.session_state.patient_history.values())
    model_usage = {}
    for history in st.session_state.patient_history.values():
        for exam in history:
            model = exam['model']
            model_usage[model] = model_usage.get(model, 0) + 1
    
    st.write(f"Total exams classified: {total_exams}")
    st.bar_chart(model_usage)

def collect_feedback(prediction_result):
    st.write("Was this prediction helpful?")
    if st.button("Yes"):
        # Store positive feedback
        st.success("Thank you for your feedback!")
    if st.button("No"):
        reason = st.text_input("Please tell us why:")
        if st.button("Submit"):
            # Store negative feedback with reason
            st.success("Thank you for your feedback!")

def add_doctor_notes(patient_id, exam_index):
    notes = st.text_area("Doctor's Notes:")
    if st.button("Save Notes"):
        st.session_state.patient_history[patient_id][exam_index]['doctor_notes'] = notes
        st.success("Notes saved successfully!")
        def filter_patient_history(patient_id):
    if patient_id in st.session_state.patient_history:
        df = pd.DataFrame(st.session_state.patient_history[patient_id])
        start_date = st.date_input("Start Date")
        end_date = st.date_input("End Date")
        filtered_df = df[(df['date'] >= str(start_date)) & (df['date'] <= str(end_date))]
        st.dataframe(filtered_df)

def print_login_file_contents():
    try:
        wb = load_workbook(LOGIN_FILE)
        ws = wb.active
        for row in ws.iter_rows(values_only=True):
            print(row)
    except Exception as e:
        print(f"Error reading LOGIN_FILE: {str(e)}")

def main():
    init_login_file()
    print_login_file_contents()  # Para debug

    if not st.session_state.get('logged_in', False):
        login_page()
    else:
        st.title("Medical Image Analysis using AI")
        st.sidebar.title(f"Welcome, {st.session_state.username}")
        if st.sidebar.button("Logout"):
            st.session_state.logged_in = False
            st.session_state.username = None
            st.rerun()

        # Sidebar menu
        if 'menu_option' not in st.session_state:
            st.session_state.menu_option = "Classify Exam"
        options = ["Classify Exam", "View Patient History", "Compare Models", "Usage Statistics"]
        if is_admin(st.session_state.username):
            options.append("User Management")
        st.session_state.menu_option = st.sidebar.radio("Choose an option:", options, key="menu_radio")

        if st.session_state.menu_option == "Classify Exam":
            st.header("Classify Exam")
            patient_id = st.text_input("Enter Patient ID:")
            model_option = st.selectbox("Choose a model for analysis:", ("Pneumonia", "Tuberculosis", "Cancer"))
            uploaded_file = st.file_uploader("Upload X-ray or CT scan image", type=["jpg", "jpeg", "png"])
            if uploaded_file:
                display_image(uploaded_file)
            if st.button("Classify"):
                result = classify_exam(patient_id, model_option, uploaded_file)
                if result:
                    st.write(result)
                    collect_feedback(result)
                    add_doctor_notes(patient_id, -1)  # Add notes to the last exam

        elif st.session_state.menu_option == "View Patient History":
            st.header("Patient History")
            patient_id = st.text_input("Enter Patient ID:")
            if st.button("View History"):
                view_patient_history(patient_id)
                export_patient_history(patient_id)
            if st.button("Filter History"):
                filter_patient_history(patient_id)

        elif st.session_state.menu_option == "Compare Models":
            st.header("Compare Models")
            uploaded_file = st.file_uploader("Upload X-ray or CT scan image", type=["jpg", "jpeg", "png"])
            if uploaded_file:
                display_image(uploaded_file)
                if st.button("Compare Models"):
                    compare_models(uploaded_file)

        elif st.session_state.menu_option == "Usage Statistics":
            st.header("Usage Statistics")
            display_usage_stats()

        elif st.session_state.menu_option == "User Management":
            if is_admin(st.session_state.username):
                manage_users()
            else:
                st.error("You don't have permission to access this page.")

if __name__ == "__main__":
    main()
