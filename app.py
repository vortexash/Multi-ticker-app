import streamlit as st
import requests
import pandas as pd
import boto3
import json
import numpy as np
from datetime import datetime
import io
from dotenv import load_dotenv
import os
import re

# Load environment variables
load_dotenv()



# Configure the page
st.set_page_config(
    page_title="Ticker Analysis Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📈 Ticker Analysis Dashboard")

# Debug start
# st.info("App reached initialization")

# AWS Config
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
BUCKET_NAME = os.getenv("S3_BUCKET")


def init_aws_client():
    try:
        return boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION
        )
    except Exception as e:
        st.error(f"AWS Configuration Error: {str(e)}")
        return None

# Sidebar Setup
st.sidebar.header("🔧 Configuration")

# Removed S3 Bucket Name input from sidebar
# bucket_name = st.sidebar.text_input("S3 Bucket Name", value=BUCKET_NAME)
bucket_name = BUCKET_NAME  # Use environment variable or default
email = st.sidebar.text_input("Email", value="user@example.com")

# Ticker Input
st.subheader("Enter Available Tickers")
ticker_input = st.text_area("Enter ticker symbols (comma or newline separated):", height=120)
if st.button("Submit", type="primary"):
    st.session_state['available_tickers'] = list({
        ticker.strip().upper()
        for ticker in re.split(r'[,\n]+', ticker_input)
        if ticker.strip()
    })

available_tickers = st.session_state.get('available_tickers', [])

if available_tickers:
    st.success(f"Loaded {len(available_tickers)} tickers: {', '.join(available_tickers)}")
    if st.button("🚀 Process All Tickers"):
        st.toast("Processing tickers...", icon="🚀")
        api_url = "http://139.59.25.242:5000/submit-job"
        filter_data = {"Country of incorporation": "United States", "Industry (US)": "Software"}  # Example only
        payload = {
            "ticker_names": available_tickers,
            "email": email,
            "filter_data": filter_data
        }

        print("Payload:", payload)
        try:
            with st.spinner("Sending job to API..."):
                res = requests.post(api_url, json=payload, timeout=60)
                if res.status_code == 200:
                    st.success("✅ Job submitted successfully!")
                    st.json(res.json())
                else:
                    st.error(f"API Error {res.status_code}: {res.text}")
        except Exception as e:
            st.error(f"API Request failed: {str(e)}")

# Minimal viewer section (simplified)
st.subheader("📂 Ticker Viewer")
selected = st.selectbox("Select ticker:", options=[""] + available_tickers)

if selected:
    s3 = init_aws_client()
    if s3:
        print(f"Selected ticker: {selected}")
        prefix = f"{email}/{selected}/"
        try:
            response = s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
            all_files = [obj['Key'] for obj in response.get('Contents', [])]
            files = all_files  # Show all files
            print(f"Files found for {selected}: {files}")
            if files:
                file = st.selectbox("Select file to load:", files)
                obj = s3.get_object(Bucket=bucket_name, Key=file)
                file_ext = file.split('.')[-1].lower()
                if file_ext == 'csv':
                    df = pd.read_csv(io.BytesIO(obj['Body'].read()))
                    st.dataframe(df)
                elif file_ext in ['txt', 'json']:
                    content = obj['Body'].read().decode('utf-8')
                    st.text(content)
                elif file_ext in ['png', 'jpg', 'jpeg']:
                    st.image(obj['Body'].read())
                else:
                    st.info(f"File type .{file_ext} not directly supported for preview.")
            else:
                st.warning("Still Processing Please wait...")
        except Exception as e:
            st.error(f"S3 error: {str(e)}")
