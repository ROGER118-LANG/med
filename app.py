import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from ttkthemes import ThemedTk
from PIL import Image, ImageTk, ImageOps, ImageEnhance
import numpy as np
from keras.models import load_model
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import sqlite3
from datetime import datetime
import os
import cv2
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import pydicom
import threading
import queue
import tempfile
from tensorflow.keras.models import Model

class MedVisionAIPro:
    def __init__(self, root):
        self.root = root
        self.root.title("MedVision AI Pro - Advanced Medical Imaging Analysis")
        self.root.geometry("1600x900")
        self.root.configure(bg="#1E1E1E")

        # Load the model and class names
        self.model = load_model("pneumonia_model.h5", compile=False)
        self.class_names = open("pnuemonia_labels.txt", "r").readlines()

        # Create a model for generating heatmaps
        self.heatmap_model = Model(inputs=self.model.inputs, outputs=self.model.layers[-1].output)

        # Initialize database
        self.init_database()

        # Create main layout
        self.create_main_layout()

        # Initialize variables
        self.current_image = None
        self.current_patient_id = None
        self.original_image = None
        self.enhanced_image = None
        self.heatmap_image = None

        # Threading
        self.queue = queue.Queue()
        self.thread = None

    # ... (previous methods remain the same)

    def create_main_layout(self):
        # Main frame
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Left panel (Image upload and analysis)
        left_panel = ttk.Frame(main_frame)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Image upload area
        self.image_label = ttk.Label(left_panel, text="No image selected")
        self.image_label.pack(pady=10)

        upload_button = ttk.Button(left_panel, text="Load Image", command=self.load_image)
        upload_button.pack(pady=5)

        analyze_button = ttk.Button(left_panel, text="Analyze Image", command=self.start_analysis_thread)
        analyze_button.pack(pady=5)

        enhance_button = ttk.Button(left_panel, text="Enhance Image", command=self.enhance_image)
        enhance_button.pack(pady=5)

        heatmap_button = ttk.Button(left_panel, text="Generate Heatmap", command=self.generate_heatmap)
        heatmap_button.pack(pady=5)

        self.progress_bar = ttk.Progressbar(left_panel, orient=tk.HORIZONTAL, length=200, mode='indeterminate')

        # Analysis result area
        self.result_label = ttk.Label(left_panel, text="Analysis Result:")
        self.result_label.pack(pady=10)

        # Notes area
        self.notes_text = tk.Text(left_panel, height=5, width=40)
        self.notes_text.pack(pady=10)
        
        save_notes_button = ttk.Button(left_panel, text="Save Notes", command=self.save_notes)
        save_notes_button.pack(pady=5)

        # Right panel (Patient info, history, and statistics)
        right_panel = ttk.Frame(main_frame)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # ... (rest of the layout remains the same)

    def generate_heatmap(self):
        if self.current_image is None:
            messagebox.showwarning("Warning", "Please load and analyze an image first.")
            return

        # Prepare the image for the model
        image_array = np.asarray(self.current_image.resize((224, 224)))
        normalized_image_array = (image_array.astype(np.float32) / 127.5) - 1
        data = np.expand_dims(normalized_image_array, axis=0)

        # Get the model's prediction
        predictions = self.heatmap_model.predict(data)
        class_idx = np.argmax(predictions[0])

        # Generate class activation heatmap
        cam = np.zeros(dtype=np.float32, shape=predictions.shape[1:3])
        for i, w in enumerate(self.model.layers[-1].get_weights()[0][:, class_idx]):
            cam += w * predictions[0, :, :, i]
        cam = cv2.resize(cam, (224, 224))
        cam = np.maximum(cam, 0)
        heatmap = (cam - cam.min()) / (cam.max() - cam.min())

        # Apply the heatmap to the original image
        heatmap = cv2.applyColorMap(np.uint8(255 * heatmap), cv2.COLORMAP_JET)
        heatmap = cv2.cvtColor(heatmap, cv2.COLOR_BGR2RGB)
        superimposed_img = heatmap * 0.4 + image_array * 0.6

        # Convert back to PIL Image
        self.heatmap_image = Image.fromarray(np.uint8(superimposed_img))
        self.display_image(self.heatmap_image)

    def display_image(self, image):
        display_image = ImageOps.fit(image, (400, 400), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(display_image)
        self.image_label.config(image=photo)
        self.image_label.image = photo

    def analyze_image_thread(self):
        # Prepare the image for the model
        image_array = np.asarray(self.current_image.resize((224, 224)))
        normalized_image_array = (image_array.astype(np.float32) / 127.5) - 1
        data = np.expand_dims(normalized_image_array, axis=0)

        # Predict
        prediction = self.model.predict(data)
        index = np.argmax(prediction)
        class_name = self.class_names[index].strip()
        confidence_score = float(prediction[0][index])

        self.queue.put((class_name, confidence_score))

        # Generate heatmap
        self.generate_heatmap()

    def process_analysis_result(self):
        class_name, confidence_score = self.queue.get()

        # Update result label
        result_text = f"Prediction: {class_name}\nConfidence: {confidence_score:.2f}"
        self.result_label.config(text=result_text)

        # Save analysis to database
        self.save_analysis(class_name, confidence_score)

        # Update patient history and statistics
        self.load_patient_history()

        # Display heatmap
        if self.heatmap_image:
            self.display_image(self.heatmap_image)

    def generate_report(self):
        if not self.current_patient_id:
            messagebox.showwarning("Warning", "Please select a patient first.")
            return

        conn = sqlite3.connect('medvision_ai_pro.db')
        c = conn.cursor()
        c.execute("SELECT name, age, gender FROM patients WHERE id = ?", (self.current_patient_id,))
        patient_info = c.fetchone()
        
        c.execute("SELECT date, prediction, confidence, notes FROM analyses WHERE patient_id = ? ORDER BY date DESC LIMIT 5",
                  (self.current_patient_id,))
        analyses = c.fetchall()
        conn.close()

        if not patient_info or not analyses:
            messagebox.showwarning("Warning", "No data available for report generation.")
            return

        # Create PDF
        file_path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")])
        if not file_path:
            return

        c = canvas.Canvas(file_path, pagesize=letter)
        width, height = letter

        # Title
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, height - 50, "MedVision AI Pro - Patient Report")

        # Patient Info
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, height - 80, "Patient Information:")
        c.setFont("Helvetica", 12)
        c.drawString(50, height - 100, f"Name: {patient_info[0]}")
        c.drawString(50, height - 120, f"Age: {patient_info[1]}")
        c.drawString(50, height - 140, f"Gender: {patient_info[2]}")

        # Recent Analyses
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, height - 180, "Recent Analyses:")
        c.setFont("Helvetica", 10)
        for i, analysis in enumerate(analyses):
            y_position = height - 200 - (i * 60)
            c.drawString(50, y_position, f"Date: {analysis[0]}")
            c.drawString(50, y_position - 15, f"Prediction: {analysis[1]}")
            c.drawString(50, y_position - 30, f"Confidence: {analysis[2]:.2f}")
            c.drawString(50, y_position - 45, f"Notes: {analysis[3][:50]}...")  # Truncate long notes

        # Add images if available
        if self.current_image:
            img_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            img_temp_filename = img_temp.name
            self.current_image.save(img_temp_filename, format="PNG")
            c.drawImage(img_temp_filename, 300, height - 300, width=250, height=250)
            os.unlink(img_temp_filename)

        if self.heatmap_image:
            heatmap_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            heatmap_temp_filename = heatmap_temp.name
            self.heatmap_image.save(heatmap_temp_filename, format="PNG")
            c.drawImage(heatmap_temp_filename, 300, height - 600, width=250, height=250)
            os.unlink(heatmap_temp_filename)

        c.save()
        messagebox.showinfo("Success", f"Report saved as {file_path}")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    root = ThemedTk(theme="equilux")
    app = MedVisionAIPro(root)
    app.run()
