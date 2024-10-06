import streamlit as st
from keras.models import load_model
from keras.layers import DepthwiseConv2D
from keras.utils import custom_object_scope
from PIL import Image, ImageOps
import numpy as np
import io

# Disable scientific notation for clarity
np.set_printoptions(suppress=True)

def preprocess_image(uploaded_file):
    # Read the file into bytes
    image_bytes = uploaded_file.getvalue()
    
    # Open the image using PIL
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    
    # Resize and preprocess the image
    size = (224, 224)
    image = ImageOps.fit(image, size, Image.Resampling.LANCZOS)
    image_array = np.asarray(image)
    normalized_image_array = (image_array.astype(np.float32) / 127.5) - 1
    data = np.ndarray(shape=(1, 224, 224, 3), dtype=np.float32)
    data[0] = normalized_image_array
    return data

def load_model_and_labels(model_path, label_path):
    model = None
    class_names = []
    try:
        with custom_object_scope({'DepthwiseConv2D': DepthwiseConv2D}):
            model = load_model(model_path)
        with open(label_path, 'r') as file:
            class_names = file.read().strip().split('\n')
    except Exception as e:
        st.error(f"Error loading model or labels: {str(e)}")
    return model, class_names

def predict(model, data, class_names):
    try:
        prediction = model.predict(data)
        index = np.argmax(prediction)
        class_name = class_names[index]
        confidence_score = prediction[0][index]
        return class_name, confidence_score
    except Exception as e:
        st.error(f"Error during prediction: {str(e)}")
        return None, None

st.title("Medical Image Analysis using AI")

model_option = st.selectbox(
    "Choose a model for analysis:",
    ("Pneumonia", "Tuberculosis", "Cancer")
)

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

uploaded_file = st.file_uploader("Escolha uma imagem...", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    # Display the uploaded image
    st.image(uploaded_file, caption="Uploaded Image", use_column_width=True)

    if st.button("Analyze"):
        model, class_names = load_model_and_labels(model_paths[model_option], label_paths[model_option])
        
        if model is not None and class_names is not None:
            processed_image = preprocess_image(uploaded_file)
            class_name, confidence_score = predict(model, processed_image, class_names)
            
            if class_name is not None and confidence_score is not None:
                st.write(f"Model: {model_option}")
                st.write(f"Class: {class_name}")
                st.write(f"Confidence Score: {confidence_score:.2f}")
            else:
                st.error("An error occurred during prediction. Please try again.")
        else:
            st.error("Failed to load the model and labels. Please check the files.")
