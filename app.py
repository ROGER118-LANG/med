import streamlit as st
import tensorflow as tf
import cv2
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
# Definição dos caminhos dos modelos e rótulos
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

def custom_depthwise_conv2d(*args, **kwargs):
    kwargs.pop('groups', None)
    return DepthwiseConv2D(*args, **kwargs)

def load_model_and_labels(model_path, labels_path):
    try:
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Arquivo de modelo não funciona: {model_path}")
        if not os.path.exists(labels_path):
            raise FileNotFoundError(f"Labels não funciona: {labels_path}")
        
        with custom_object_scope({'DepthwiseConv2D': custom_depthwise_conv2d}):
            model = load_model(model_path, compile=False)
        
        with open(labels_path, "r") as f:
            class_names = f.readlines()
        return model, class_names
    except Exception as e:
        st.error(f"Error loading model and labels: {str(e)}")
        return None, None
def predict(model, data, class_names):
    try:
        # Faz a predição
        prediction = model.predict(data)
        
        # Obtém o índice da classe com maior probabilidade
        index = np.argmax(prediction)
        
        # Obtém o nome da classe
        class_name = class_names[index]
        
        # Obtém a pontuação de confiança
        confidence_score = float(prediction[0][index])
        
        return class_name.strip(), confidence_score
    except Exception as e:
        st.error(f"Error during prediction: {str(e)}")
        return None, None

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
                    
                    st.success("Exame classificado com sucesso!")
                    return result
                else:
                    st.error("An error occurred during prediction. Please try again.")
            else:
                st.error("Failed to load the model and labels. Please check the files and try again.")
        except Exception as e:
            st.error(f"An error occurred during classification: {str(e)}")
    else:
        st.error("Por favor faça upload primeiro")
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
                # Verifica se a coluna de role existe e se o usuário é admin
                is_admin = len(row) > 4 and row[4] == 'admin'
                
                if not is_admin:
                    # Se não for admin, verifica a data de expiração (se existir)
                    if len(row) > 3 and row[3]:
                        expiry_date = row[3]
                        if isinstance(expiry_date, datetime) and datetime.now() > expiry_date:
                            return False, "Account expired"
                
                return True, "Successo"
        
        return False, "Credenciais Invalidas"
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
        # Lê o arquivo carregado como bytes
        image_bytes = uploaded_file.getvalue()
        
        # Abre a imagem usando PIL
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        
        # Redimensiona a imagem para 224x224 pixels
        size = (224, 224)
        image = ImageOps.fit(image, size, Image.Resampling.LANCZOS)
        
        # Converte a imagem para um array numpy
        image_array = np.asarray(image)
        
        # Normaliza os valores dos pixels
        normalized_image_array = (image_array.astype(np.float32) / 127.5) - 1
        
        # Cria um array 4D para entrada no modelo
        data = np.ndarray(shape=(1, 224, 224, 3), dtype=np.float32)
        data[0] = normalized_image_array
        
        return data
    except Exception as e:
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
            st.error(f"An error occurred during classification: {str(e)}")
    else:
        st.error("Please upload an image first.")
    return None

def view_patient_history(patient_id):
    if patient_id in st.session_state.patient_history:
        history = st.session_state.patient_history[patient_id]
        df = pd.DataFrame(history)
        st.dataframe(df)
        
        # Visualization of patient history
        st.subheader("Patient Exam History Visualization")
        fig, ax = plt.subplots(figsize=(10, 6))
        sns.scatterplot(data=df, x='date', y='confidence', hue='model', size='confidence', ax=ax)
        ax.set_title(f"Exam Confidence Over Time for Patient {patient_id}")
        ax.set_xlabel("Date")
        ax.set_ylabel("Confidence Score")
        st.pyplot(fig)
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
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
        
        sns.boxplot(data=df1, x='model', y='confidence', ax=ax1)
        ax1.set_title(f"Patient {patient1}")
        ax1.set_ylim(0, 1)
        
        sns.boxplot(data=df2, x='model', y='confidence', ax=ax2)
        ax2.set_title(f"Patient {patient2}")
        ax2.set_ylim(0, 1)
        
        st.pyplot(fig)
def generate_heatmap(model, preprocessed_image, last_conv_layer_name, pred_index=None):
    # Create a model that maps the input image to the activations
    # of the last conv layer as well as the output predictions
    grad_model = Model(
        [model.inputs], 
        [model.get_layer(last_conv_layer_name).output, model.output]
    )

    # Then, we compute the gradient of the top predicted class for our input image
    # with respect to the activations of the last conv layer
    with tf.GradientTape() as tape:
        last_conv_layer_output, preds = grad_model(preprocessed_image)
        if pred_index is None:
            pred_index = tf.argmax(preds[0])
        class_channel = preds[:, pred_index]

    # This is the gradient of the output neuron (top predicted or chosen)
    # with regard to the output feature map of the last conv layer
    grads = tape.gradient(class_channel, last_conv_layer_output)

    # This is a vector where each entry is the mean intensity of the gradient
    # over a specific feature map channel
    pooled_grads = tf.reduce_mean(grads, axis=(0, 1, 2))

    # We multiply each channel in the feature map array
    # by "how important this channel is" with regard to the top predicted class
    # then sum all the channels to obtain the heatmap class activation
    last_conv_layer_output = last_conv_layer_output[0]
    heatmap = last_conv_layer_output @ pooled_grads[..., tf.newaxis]
    heatmap = tf.squeeze(heatmap)

    # For visualization purpose, we will also normalize the heatmap between 0 & 1
    heatmap = tf.maximum(heatmap, 0) / tf.math.reduce_max(heatmap)
    return heatmap.numpy()

def apply_heatmap(image, heatmap):
    # Resize the heatmap to match the image size
    heatmap = cv2.resize(heatmap, (image.shape[1], image.shape[0]))
    
    # Convert heatmap to RGB
    heatmap = np.uint8(255 * heatmap)
    heatmap = cv2.applyColorMap(heatmap, cv2.COLORMAP_JET)
    
    # Superimpose the heatmap on original image
    superimposed_img = heatmap * 0.4 + image
    superimposed_img = np.clip(superimposed_img, 0, 255).astype('uint8')
    
    return superimposed_img

def classify_exam_with_heatmap(patient_id, model_option, uploaded_file):
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
                        
                        # Generate heatmap
                        last_conv_layer_name = "Conv_1" # You might need to adjust this based on your model architecture
                        heatmap = generate_heatmap(model, processed_image, last_conv_layer_name)
                        
                        # Load the original image
                        original_image = Image.open(uploaded_file).convert("RGB")
                        original_image = np.array(original_image)
                        
                        # Apply heatmap to the original image
                        heatmap_image = apply_heatmap(original_image, heatmap)
                        
                        # Display the original and heatmap images side by side
                        col1, col2 = st.columns(2)
                        with col1:
                            st.image(original_image, caption="Original Image", use_column_width=True)
                        with col2:
                            st.image(heatmap_image, caption="Anomaly Heatmap", use_column_width=True)
                        
                        return result
                    else:
                        st.error("An error occurred during prediction. Please try again.")
                else:
                    st.error("Failed to preprocess the image. Please try a different image.")
            else:
                st.error("Failed to load the model and labels. Please check the files and try again.")
        except Exception as e:
            st.error(f"An error occurred during classification: {str(e)}")
    else:
        st.error("Please upload an image first.")
    return None


def manage_users():
    st.header("User Management")
    
    try:
        # Load the Excel workbook and active sheet
        wb = load_workbook(LOGIN_FILE)
        ws = wb.active

        # Prepare the data from Excel
        user_data = {row[0]: row for row in ws.iter_rows(min_row=2, values_only=True)}

        # Debugging: Check the content of user_data to identify any inconsistencies
        st.write("Loaded User Data:", user_data)

        # Ensure each row has exactly 5 elements, padding missing values with None
        cleaned_user_data = [
            (row if len(row) == 5 else row + (None,) * (5 - len(row))) 
            for row in user_data.values()
        ]

        # Debugging: Show cleaned data
        st.write("Cleaned User Data:", cleaned_user_data)

        # Create DataFrame with the cleaned data
        user_df = pd.DataFrame(cleaned_user_data, columns=["Username", "Password", "Last Login", "Expiry Date", "Role"])
        
        # Display the DataFrame
        st.dataframe(user_df)

        # Add new user form
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

        # Edit user form
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

        # Remove user form
        st.subheader("Remove User")
        remove_username = st.selectbox("Select User to Remove", list(user_data.keys()))
        if st.button("Remove User"):
            ws.delete_rows(list(user_data.keys()).index(remove_username) + 2)
            wb.save(LOGIN_FILE)
            st.success("User removed successfully!")
    
    except Exception as e:
        st.error(f"An error occurred during user management: {str(e)}")

def main():
    init_login_file()
    if not st.session_state.get('logged_in', False):
        login_page()
    else:
        st.title("MedVision")
        st.sidebar.title(f"Bem Vindo username, {st.session_state.username}")
        if st.sidebar.button("Sair"):
            st.session_state.logged_in = False
            st.session_state.username = None
            st.rerun()

        # Sidebar menu
        if 'menu_option' not in st.session_state:
            st.session_state.menu_option = "Classify Exam"
        options = ["Classify Exam", "View Patient History", "Compare Patients"]
        if st.session_state.username == 'admin':
            options.append("User Management")
        st.session_state.menu_option = st.sidebar.radio("Choose an option:", options, key="menu_radio")

        if st.session_state.menu_option == "Classify Exam":
            st.header("Classify Exam")
            patient_id = st.text_input("Enter Patient ID:")
            model_option = st.selectbox("Choose a model for analysis:", ("Pneumonia", "Tuberculosis", "Cancer"))
            uploaded_file = st.file_uploader("Upload X-ray or CT scan image", type=["jpg", "jpeg", "png"])
            if st.button("Classify"):
                classify_exam_with_heatmap(patient_id, model_option, uploaded_file)
        elif st.session_state.menu_option == "View Patient History":
            st.header("Patient History")
            patient_id = st.text_input("Enter Patient ID:")
            if st.button("View History"):
                view_patient_history(patient_id)
        elif st.session_state.menu_option == "Compare Patients":
            compare_patients()
        elif st.session_state.menu_option == "User Management":
            manage_users()

if __name__ == "__main__":
    main()

