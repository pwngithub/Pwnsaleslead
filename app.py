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
            "SubmissionID": item.get("id", ""),
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

def update_lead(submission_id, new_status):
    """Update status of an existing submission"""
    url = f"https://api.jotform.com/submission/{submission_id}?apiKey={API_KEY}"
    data = { "submission[4]": new_status }  # "4" is the Status field
    response = requests.post(url, data=data)
    return response.status_code == 200


# Streamlit App
st.set_page_config(page_title="Sales Lead Tracker", page_icon="📊", layout="wide")
st.title("📊 Sales Lead Tracker (JotForm Backend)")

# Fetch Data
df = fetch_jotform_data()

# --- Filters ---
st.sidebar.header("🔍 Filter Leads")
if not df.empty:
    name_filter = st.sidebar.text_input("Search by Name")
    contact_filter = st.sidebar.text_input("Search by Contact")
    source_filter = st.sidebar.multiselect("Filter by Source", df["Source"].unique())
    status_filter = st.sidebar.multiselect("Filter by Status", df["Status"].unique())
    notes_filter = st.sidebar.text_input("Search Notes")

    filtered_df = df.copy()
    if name_filter:
        filtered_df = filtered_df[filtered_df["Name"].str.contains(name_filter, case=False, na=False)]
    if contact_filter:
        filtered_df = filtered_df[filtered_df["Contact"].str.contains(contact_filter, case=False, na=False)]
    if source_filter:
        filtered_df = filtered_df[filtered_df["Source"].isin(source_filter)]
    if status_filter:
        filtered_df = filtered_df[filtered_df["Status"].isin(status_filter)]
    if notes_filter:
        filtered_df = filtered_df[filtered_df["Notes"].str.contains(notes_filter, case=False, na=False)]
else:
    filtered_df = pd.DataFrame()

# Tabs
tab1, tab2, tab3 = st.tabs(["📋 Leads Dashboard", "➕ Add New Lead", "✏️ Edit Lead Status"])

with tab1:
    st.subheader("All Leads")
    if not filtered_df.empty:
        st.dataframe(filtered_df, use_container_width=True)
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Leads by Status")
            st.bar_chart(filtered_df["Status"].value_counts())

        with col2:
            st.subheader("Leads by Source")
            st.bar_chart(filtered_df["Source"].value_counts())
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

with tab3:
    st.subheader("Update Lead Status")
    if not df.empty:
        df["LeadDisplay"] = df["Name"] + " (" + df["Contact"] + ")"
        selected_lead = st.selectbox("Select a Lead", df["LeadDisplay"])
        lead_id = df.loc[df["LeadDisplay"] == selected_lead, "SubmissionID"].values[0]
        new_status = st.selectbox(
            "New Status",
            ["Survey Scheduled", "Survey Completed", "Scheduled", "Installed", "Waiting on Customer"]
        )
        if st.button("Update Status"):
            if update_lead(lead_id, new_status):
                st.success("✅ Lead status updated! Refresh to see changes.")
            else:
                st.error("❌ Failed to update lead.")
    else:
        st.info("No leads available to edit.")
