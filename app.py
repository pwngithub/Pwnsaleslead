import streamlit as st
import pandas as pd
import requests
from datetime import datetime

# JotForm credentials
API_KEY = "22179825a79dba61013e4fc3b9d30fa4"
FORM_ID = "252598168633065"

# Field IDs for timestamps
FIELD_IDS = {
    "survey_scheduled_date": 12,
    "survey_completed_date": 13,
    "scheduled_date": 14,
    "installed_date": 15,
    "waiting_on_customer_date": 16,
    "status": 4
}

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
            "CreatedAt": item.get("created_at", ""),
            "Name": answers.get("1", {}).get("answer", ""),
            "Contact": answers.get("2", {}).get("answer", ""),
            "Source": answers.get("3", {}).get("answer", ""),
            "Status": answers.get(str(FIELD_IDS["status"]), {}).get("answer", ""),
            "Notes": answers.get("5", {}).get("answer", ""),
            "SurveyScheduledDate": answers.get(str(FIELD_IDS["survey_scheduled_date"]), {}).get("answer", ""),
            "SurveyCompletedDate": answers.get(str(FIELD_IDS["survey_completed_date"]), {}).get("answer", ""),
            "ScheduledDate": answers.get(str(FIELD_IDS["scheduled_date"]), {}).get("answer", ""),
            "InstalledDate": answers.get(str(FIELD_IDS["installed_date"]), {}).get("answer", ""),
            "WaitingOnCustomerDate": answers.get(str(FIELD_IDS["waiting_on_customer_date"]), {}).get("answer", ""),
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
    """Update status and timestamp of an existing submission"""
    url = f"https://api.jotform.com/submission/{submission_id}?apiKey={API_KEY}"
    data = { f"submission[{FIELD_IDS['status']}]": new_status }
    now = datetime.utcnow().isoformat()

    if new_status == "Survey Scheduled":
        data[f"submission[{FIELD_IDS['survey_scheduled_date']}]"] = now
    elif new_status == "Survey Completed":
        data[f"submission[{FIELD_IDS['survey_completed_date']}]"] = now
    elif new_status == "Scheduled":
        data[f"submission[{FIELD_IDS['scheduled_date']}]"] = now
    elif new_status == "Installed":
        data[f"submission[{FIELD_IDS['installed_date']}]"] = now
    elif new_status == "Waiting on Customer":
        data[f"submission[{FIELD_IDS['waiting_on_customer_date']}]"] = now

    response = requests.post(url, data=data)
    return response.status_code == 200

def calculate_durations(df):
    """Calculate durations between stages and total time to install"""
    if df.empty:
        return df

    def parse_date(x):
        try:
            return pd.to_datetime(x)
        except Exception:
            return pd.NaT

    for col in ["CreatedAt", "SurveyScheduledDate", "SurveyCompletedDate",
                "ScheduledDate", "InstalledDate", "WaitingOnCustomerDate"]:
        df[col] = df[col].apply(parse_date)

    df["TotalDaysToInstall"] = (df["InstalledDate"] - df["CreatedAt"]).dt.days
    df["SurveyDuration"] = (df["SurveyCompletedDate"] - df["SurveyScheduledDate"]).dt.days
    df["SchedulingDuration"] = (df["ScheduledDate"] - df["SurveyCompletedDate"]).dt.days
    df["InstallWaitDuration"] = (df["InstalledDate"] - df["ScheduledDate"]).dt.days

    return df

# Streamlit App
st.set_page_config(page_title="Sales Lead Tracker", page_icon="📊", layout="wide")
st.title("📊 Sales Lead Tracker (JotForm Backend)")

# Fetch Data
df = fetch_jotform_data()
df = calculate_durations(df)

# Tabs
tab1, tab2, tab3 = st.tabs(["📋 Leads Dashboard", "➕ Add New Lead", "✏️ Edit Lead Status"])

with tab1:
    st.subheader("All Leads")
    if not df.empty:
        st.dataframe(df, use_container_width=True)

        # KPI Metrics
        installs = df.dropna(subset=["TotalDaysToInstall"])
        if not installs.empty:
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Average Days to Install", round(installs["TotalDaysToInstall"].mean(), 1))
            col2.metric("Median Days to Install", installs["TotalDaysToInstall"].median())
            col3.metric("Fastest Install", installs["TotalDaysToInstall"].min())
            col4.metric("Slowest Install", installs["TotalDaysToInstall"].max())

            # Stage averages
            stage_avg = {
                "Survey": installs["SurveyDuration"].mean(),
                "Scheduling": installs["SchedulingDuration"].mean(),
                "Install Wait": installs["InstallWaitDuration"].mean(),
            }
            st.subheader("⏱️ Average Time Spent per Stage (days)")
            st.bar_chart(pd.Series(stage_avg))

            # Export to CSV
            st.download_button(
                "📥 Download Leads with Durations (CSV)",
                installs.to_csv(index=False).encode("utf-8"),
                "leads_durations.csv",
                "text/csv",
            )
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
