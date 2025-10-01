import streamlit as st
import pandas as pd
import os
from datetime import datetime

st.set_page_config(page_title="Pioneer Sales Lead App", layout="wide")

SEED_FILE = "saleslead_seed.csv"

# Load data
if os.path.exists(SEED_FILE):
    df = pd.read_csv(SEED_FILE)
    st.success("✅ Loaded tickets from local seed file")
else:
    # placeholder for JotForm fetch
    df = pd.DataFrame(columns=["SubmissionID","Name","ContactSource","Status","TypeOfService","LostReason",
                               "Notes","Street","City","State","Postal","CreatedAt","LastUpdated"])
    st.info("ℹ️ Loaded tickets from JotForm API (no local seed found)")

st.title("📊 All Tickets Preview")
st.dataframe(df)
