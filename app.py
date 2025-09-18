import streamlit as st
import pandas as pd
import requests

# JotForm credentials
API_KEY = "22179825a79dba61013e4fc3b9d30fa4"
FORM_ID = "252598168633065"

BASE_URL = f"https://api.jotform.com/form/{FORM_ID}/submissions?apiKey={API_KEY}"

def fetch_jotform_data():
    """Fetch submissions from JotForm API"""
    response = requests.get(BASE_URL)
    if response.status_code != 200:
        st.error("❌ Failed to fetch data from JotForm API.")
        return pd.DataFrame()
    
    data = response.json()
    submissions = []

    for item in data.get("content", []):
        answers = item.get("answers", {})
        submissions.append({
            "Name": answers.get("1", {}).get("answer", ""),
            "Contact": answers.get("2", {}).get("answer", ""),
            "Source": answers.get("3", {}).get("answer", ""),
            "Status": answers.get("4", {}).get("answer", ""),
            "Notes": answers.get("5", {}).get("answer", ""),
        })

    return pd.DataFrame(submissions)

def submit_lead(name, contact, source, status, notes):
    """Submit new lead to JotForm"""
    submission_data = {
        "submission[1]": name,
        "submission[2]": contact,
        "submission[3]": source,
        "submission[4]": status,
        "submission[5]": notes,
    }
    response = requests.post(
        f"https://api.jotform.com/form/{FORM_ID}/submissions?apiKey={API_KEY}",
        data=submission_data,
    )
    return response.status_code == 200


# Streamlit App
st.set_page_config(page_title="Sales Lead Tracker", page_icon="📊", layout="wide")

st.title("📊 Sales Lead Tracker (JotForm Backend)")

# Tabs
tab1, tab2 = st.tabs(["📋 Leads Dashboard", "➕ Add New Lead"])

with tab1:
    st.subheader("All Leads")
    df = fetch_jotform_data()

    if not df.empty:
        st.dataframe(df, use_container_width=True)

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Leads by Status")
            st.bar_chart(df["Status"].value_counts())

        with col2:
            st.subheader("Leads by Source")
            st.bar_chart(df["Source"].value_counts())
    else:
        st.info("No leads found yet.")

with tab2:
    st.subheader("Add New Lead")
    with st.form("add_lead"):
        name = st.text_input("Customer Name")
        contact = st.text_input("Contact Info")
        source = st.selectbox(
            "How they contacted us",
            ["Email", "Social Media", "Phone Call", "Walk In", "In Person"],
        )
        status = st.selectbox(
            "Lead Status",
            ["Survey Scheduled", "Survey Completed", "Scheduled", "Installed", "Waiting on Customer"],
        )
        notes = st.text_area("Notes")
        submitted = st.form_submit_button("Submit Lead")

        if submitted:
            if submit_lead(name, contact, source, status, notes):
                st.success("✅ Lead submitted successfully!")
            else:
                st.error("❌ Failed to submit lead.")
