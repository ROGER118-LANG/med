import streamlit as st
import datadog
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
import hashlib
from ddtrace import patch_all
from keras.models import load_model
from keras.layers import DepthwiseConv2D
from keras.utils import custom_object_scope
from PIL import Image, ImageOps
import numpy as np
import io
import pandas as pd

# Initialize Datadog
datadog.initialize(api_key='YOUR_DATADOG_API_KEY', app_key='YOUR_DATADOG_APP_KEY')

# Patch all for Datadog APM
patch_all()

# Database setup
DATABASE_URL = "postgresql://username:password@host:port/database"
engine = create_engine(DATABASE_URL)
Base = declarative_base()
Session = sessionmaker(bind=engine)

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    last_login = Column(DateTime)
    expiration_date = Column(DateTime)
    is_admin = Column(Boolean, default=False)

Base.metadata.create_all(engine)

def get_db_session():
    return Session()

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

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def check_login(username, password):
    session = get_db_session()
    user = session.query(User).filter_by(username=username).first()
    session.close()

    if user and user.password == hash_password(password):
        if user.is_admin:
            return True, True
        if user.expiration_date and datetime.now() > user.expiration_date:
            return False, "Account expired"
        return True, False
    return False, "Invalid credentials"

def update_last_login(username):
    session = get_db_session()
    user = session.query(User).filter_by(username=username).first()
    if user:
        user.last_login = datetime.now()
        session.commit()
    session.close()

def login_page():
    st.title("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        login_success, result = check_login(username, password)
        if login_success:
            st.session_state.logged_in = True
            st.session_state.username = username
            st.session_state.is_admin = result if isinstance(result, bool) else False
            update_last_login(username)
            st.success("Logged in successfully!")
            datadog.statsd.increment('app.logins')
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
    session = get_db_session()
    users = session.query(User.username).all()
    session.close()
    selected_user = st.selectbox("Select User", [user[0] for user in users])
    
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
    session = get_db_session()
    hashed_password = hash_password(password)
    expiration_date = datetime.now() + timedelta(days=expiration_days)
    new_user = User(username=username, password=hashed_password, expiration_date=expiration_date, is_admin=is_admin)
    session.add(new_user)
    session.commit()
    session.close()
    st.success(f"User {username} added successfully!")
    datadog.statsd.increment('app.users.added')

def get_user_data(username):
    session = get_db_session()
    user = session.query(User).filter_by(username=username).first()
    session.close()
    if user:
        expiration_days = (user.expiration_date - datetime.now()).days if user.expiration_date else 30
        return {
            'username': user.username,
            'expiration_days': expiration_days,
            'is_admin': user.is_admin
        }
    return None

def update_user(username, new_password, new_expiration_days, new_is_admin):
    session = get_db_session()
    user = session.query(User).filter_by(username=username).first()
    if user:
        if new_password:
            user.password = hash_password(new_password)
        user.expiration_date = datetime.now() + timedelta(days=new_expiration_days)
        user.is_admin = new_is_admin
        session.commit()
    session.close()
    st.success(f"User {username} updated successfully!")
    datadog.statsd.increment('app.users.updated')

def delete_user(username):
    session = get_db_session()
    user = session.query(User).filter_by(username=username).first()
    if user:
        session.delete(user)
        session.commit()
    session.close()
    st.success(f"User {username} deleted successfully!")
    datadog.statsd.increment('app.users.deleted')

# Image classification functions (you'll need to implement these based on your specific model)
def load_model():
    # Load your model here
    pass

def preprocess_image(image):
    # Preprocess the image for your model
    pass

def classify_image(image, model):
    # Classify the image using your model
    pass

def main():
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
            st.header("Classify Medical Exam")
            uploaded_file = st.file_uploader("Choose an image...", type=["jpg", "jpeg", "png"])
            if uploaded_file is not None:
                image = Image.open(uploaded_file)
                st.image(image, caption='Uploaded Image.', use_column_width=True)
                st.write("")
                st.write("Classifying...")
                model = load_model()
                preprocessed_image = preprocess_image(image)
                prediction = classify_image(preprocessed_image, model)
                st.write(f"Prediction: {prediction}")
                
                # Save to patient history
                if 'patient_id' not in st.session_state:
                    st.session_state.patient_id = st.text_input("Enter patient ID:")
                if st.session_state.patient_id:
                    if st.session_state.patient_id not in st.session_state.patient_history:
                        st.session_state.patient_history[st.session_state.patient_id] = []
                    st.session_state.patient_history[st.session_state.patient_id].append({
                        'date': datetime.now(),
                        'prediction': prediction
                    })
                    st.success("Exam result saved to patient history.")
                    datadog.statsd.increment('app.exams.classified')

        elif menu_option == "View Patient History":
            st.header("Patient History")
            patient_id = st.text_input("Enter patient ID to view history:")
            if patient_id in st.session_state.patient_history:
                history = st.session_state.patient_history[patient_id]
                df = pd.DataFrame(history)
                st.table(df)
                datadog.statsd.increment('app.patient_history.viewed')
            else:
                st.write("No history found for this patient ID.")

        elif menu_option == "Manage Users" and st.session_state.is_admin:
            manage_users()

    # Send metrics to Datadog
    datadog.statsd.gauge('app.active_users', 1)
    session = get_db_session()
    user_count = session.query(User).count()
    session.close()
    datadog.statsd.gauge('app.total_users', user_count)

if __name__ == "__main__":
    main()
