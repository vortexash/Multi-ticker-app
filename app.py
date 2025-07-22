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
import time

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

# AWS Config
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
BUCKET_NAME = os.getenv("S3_BUCKET")


def init_aws_client():
    """Initialize S3 client with credentials from environment variables."""
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


# Initialize session state
if 'available_tickers' not in st.session_state:
    st.session_state['available_tickers'] = []
if 'last_refresh' not in st.session_state:
    st.session_state['last_refresh'] = time.time()

# Sidebar
st.sidebar.header("🔧 Configuration")
bucket_name = BUCKET_NAME
email = st.sidebar.text_input("Email", value="pronay@pavakicapital.com")

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

# Display tickers
if available_tickers:
    st.success(f"Loaded {len(available_tickers)} tickers: {', '.join(available_tickers)}")

    if st.button("🚀 Process All Tickers"):
        st.info("Processing tickers...")
        api_url = "http://139.59.25.242:5000/submit-job"

        # Full payload based on your example
        payload = {
            "ticker_names": available_tickers,
            "email": email,
            "economic_indicator_data": [
                4.28, 4.58, 1.31, 4.27, 5.86, 3.3, 3.89, 3.11, 7.62, 0.33
            ],
            "filter_data": {
                "Country of incorporation": "United States",
                "Industry (US)": "Software (System & Application)",
                "Industry (Global)": "Software (System & Application)",
                "Do you have R&D expenses to capitalize": "Yes",
                "Do you have operating lease commitments": "Yes",
                "Cross holdings and other non-operating assets": 12345,
                "Pre tax value": 8.67,
                "Compound revenue": -3.91,
                "Year of convergence": 3,
                "Do you have employee options outstanding": "Yes",
                "Number of options outstanding (in millions)": 0,
                "Average strike price": 0,
                "Average maturity": 0,
                "Standard deviation on stock price": 44.54,
                "Do you want to override cost of capital assumption": "Yes",
                "If yes, enter the cost of capital after year 10": 8,
                "Do you want to override return on capital assumption": "Yes",
                "If yes, enter the return on capital you expect after year 10": 10,
                "Do you want to override probability of failure assumption": "Yes",
                "If yes, enter the probability of failure": 12,
                "What do you want to tie your proceeds in failure to": "V",
                "Enter the distress proceeds as percentage of book or fair value": 50,
                "Do you want to override effective tax rate assumption": "Yes",
                "Do you want to override NOL assumption": "No",
                "If yes, enter the NOL that you are carrying over into year 1": 250,
                "Do you want to override growth rate assumption": "Yes",
                "If yes, enter the growth rate in perpetuity": 1,
                "Do you want to override trapped cash assumption": "Yes",
                "If yes, enter trapped cash (if taxes) or entire balance (if mistrust)": 140000,
                "& Average tax rate of the foreign markets where the cash is trapped": 15,
                "Comments": ""
            }
        }

        st.write("Payload being sent:", payload)

        try:
            with st.spinner("Sending job to API..."):
                res = requests.post(api_url, json=payload, timeout=300)
                if res.status_code == 200:
                    st.success("✅ Job submitted successfully!")
                    st.json(res.json())
                else:
                    st.error(f"API Error {res.status_code}: {res.text}")
        except Exception as e:
            st.error(f"API Request failed: {str(e)}")

# Viewer Section
st.subheader("📂 Ticker Viewer")
selected = st.selectbox("Select ticker:", options=[""] + available_tickers)


def fetch_s3_files(s3, bucket_name, prefix):
    try:
        response = s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
        return [obj['Key'] for obj in response.get('Contents', [])]
    except Exception as e:
        st.error(f"S3 error: {str(e)}")
        return []


if selected:
    s3 = init_aws_client()
    if s3:
        prefix = f"{email}/{selected}/"
        all_files = fetch_s3_files(s3, bucket_name, prefix)

        # Auto-refresh every 30s if no files yet
        if not all_files:
            st.warning("Still Processing.")
            if time.time() - st.session_state['last_refresh'] > 30:
                st.session_state['last_refresh'] = time.time()
                st.experimental_rerun()
            st.button("Refresh Now", on_click=lambda: st.experimental_rerun())
            st.stop()

        # Exclude JSON files and any JSON-like text files (e.g., valuation_output_lfy.json.txt)
        file_name_map = {
            key.split('/')[-1]: key for key in all_files
            if not key.lower().endswith('.json')          # Hide raw JSON
            and '.json.' not in key.lower()               # Hide JSON-like files
        }

        # Stop if no remaining files
        if not file_name_map:
            st.warning("No viewable files (CSV, TXT, images) found for this ticker yet.")
            st.stop()

        # Sort alphabetically (can be changed to last modified later)
        sorted_files = sorted(file_name_map.keys())
        selected_file_name = st.selectbox("Select file to load:", sorted_files)
        selected_full_key = file_name_map[selected_file_name]

        # Fetch and display the selected file
        obj = s3.get_object(Bucket=bucket_name, Key=selected_full_key)
        file_ext = selected_file_name.split(".")[-1].lower()

        if file_ext == 'csv':
            df = pd.read_csv(io.BytesIO(obj['Body'].read()))
            st.dataframe(df)
        elif file_ext == 'txt':
            st.text(obj['Body'].read().decode('utf-8'))
        elif file_ext in ['png', 'jpg', 'jpeg']:
            st.image(obj['Body'].read())
        else:
            st.info(f"File type .{file_ext} not directly supported for preview.")
