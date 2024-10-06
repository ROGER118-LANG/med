import streamlit as st
from keras.models import load_model
from PIL import Image, ImageOps
import numpy as np

# Disable scientific notation for clarity
np.set_printoptions(suppress=True)

def load_model_and_labels(model_path, labels_path):
    model = load_model(model_path, compile=False)
    class_names = open(labels_path, "r").readlines()
    return model, class_names

def preprocess_image(image):
    size = (224, 224)
    image = ImageOps.fit(image, size, Image.Resampling.LANCZOS)
    image_array = np.asarray(image)
    normalized_image_array = (image_array.astype(np.float32) / 127.5) - 1
    data = np.ndarray(shape=(1, 224, 224, 3), dtype=np.float32)
    data[0] = normalized_image_array
    return data

def predict(model, data, class_names):
    prediction = model.predict(data)
    index = np.argmax(prediction)
    class_name = class_names[index]
    confidence_score = prediction[0][index]
    return class_name[2:], confidence_score

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
        processed_image = preprocess_image(image)
        class_name, confidence_score = predict(model, processed_image, class_names)

        st.write(f"Model: {model_option}")
        st.write(f"Class: {class_name}")
        st.write(f"Confidence Score: {confidence_score:.2f}")
