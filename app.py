import streamlit as st
from keras.models import load_model
from PIL import Image, ImageOps
import numpy as np
import os

# Disable scientific notation for clarity
np.set_printoptions(suppress=True)

from keras.layers import DepthwiseConv2D
from keras.utils import custom_object_scope

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

uploaded_file = st.file_uploader("Choose an image...", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    image = Image.open(uploaded_file).convert("RGB")
    st.image(image, caption="Uploaded Image", use_column_width=True)

    if st.button("Analyze"):
        model, class_names = load_model_and_labels(model_paths[model_option], label_paths[model_option])
        
        if model is not None and class_names is not None:
            processed_image = preprocess_image(image)
            class_name, confidence_score = predict(model, processed_image, class_names)
            
            if class_name is not None and confidence_score is not None:
                st.write(f"Model: {model_option}")
                st.write(f"Class: {class_name}")
                st.write(f"Confidence Score: {confidence_score:.2f}")
            else:
                st.error("An error occurred during prediction. Please try again.")
        else:
            st.error("Failed to load the model and labels. Please check the files and try again.")

