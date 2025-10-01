import streamlit as st
import pandas as pd
import requests
from datetime import datetime

st.set_page_config(page_title="Pioneer Sales Lead", layout="wide")

# --- Version ---
VERSION = "v19.10.36"

# --- Config ---
API_KEY = st.secrets.get("jotform_api_key", "22179825a79dba61013e4fc3b9d30fa4")
FORM_ID = st.secrets.get("jotform_form_id", "252598168633065")

FIELD_ID = {
    "name": 3,
    "contact_source": 4,
    "status": 6,
    "notes": 10,
    "lost_reason": 17,
    "service_type": 18,
    "address": 19,
    "survey_scheduled_date": 12,
    "survey_completed_date": 13,
    "scheduled_date": 14,
    "installed_date": 15,
    "waiting_on_customer_date": 16
}

STATUS_LIST = [
    "Survey Scheduled",
    "Survey Completed",
    "Scheduled",
    "Installed",
    "Waiting on Customer",
    "Lost"
]

SERVICE_LIST = [
    "Internet",
    "Phone",
    "TV",
    "Cell Phone",
    "Internet and Phone",
    "Internet and TV",
    "Internet and Cell Phone"
]

# --- Helper functions ---
def fetch_submissions():
    url = f"https://api.jotform.com/form/{FORM_ID}/submissions?apiKey={API_KEY}"
    resp = requests.get(url).json()
    submissions = []
    for item in resp.get("content", []):
        answers = item.get("answers", {})
        addr_ans = answers.get(str(FIELD_ID["address"]), {}).get("answer", {})
        name_ans = answers.get(str(FIELD_ID["name"]), {}).get("answer", {})
        submissions.append({
            "SubmissionID": item.get("id"),
            "Name": f"{name_ans.get('first','')} {name_ans.get('last','')}".strip(),
            "Source": answers.get(str(FIELD_ID["contact_source"]), {}).get("answer"),
            "Status": answers.get(str(FIELD_ID["status"]), {}).get("answer"),
            "Notes": answers.get(str(FIELD_ID["notes"]), {}).get("answer"),
            "LostReason": answers.get(str(FIELD_ID["lost_reason"]), {}).get("answer"),
            "Service": answers.get(str(FIELD_ID["service_type"]), {}).get("answer"),
            "Street": addr_ans.get("addr_line1"),
            "City": addr_ans.get("city"),
            "State": addr_ans.get("state"),
            "Zip": addr_ans.get("postal"),
            "LastUpdated": datetime.fromtimestamp(int(item.get("updated_at", item.get("created_at"))))
        })
    return pd.DataFrame(submissions)

def export_csv(df):
    return df.to_csv(index=False).encode("utf-8")

# --- UI ---
st.image("https://images.squarespace-cdn.com/content/v1/651eb4433b13e72c1034f375/369c5df0-5363-4827-b041-1add0367f447/PBB+long+logo.png?format=1500w", use_container_width=True)
st.title("📋 Pioneer Sales Lead Management - " + VERSION)

menu = st.sidebar.radio("Menu", ["All Tickets", "Add Ticket", "Edit Ticket", "KPI"])

if "edited_ticket" not in st.session_state:
    st.session_state["edited_ticket"] = None

# --- All Tickets ---
if menu == "All Tickets":
    st.header("All Tickets Preview")
    if st.button("🔄 Refresh Tickets"):
        st.cache_data.clear()
    df = fetch_submissions()
    if not df.empty:
        st.dataframe(df, use_container_width=True)
        st.download_button("⬇️ Export CSV", data=export_csv(df), file_name="tickets.csv")
        for _, row in df.iterrows():
            if st.button(f"✏️ Edit {row['Name']}", key=f"edit_{row['SubmissionID']}"):
                st.session_state["edited_ticket"] = row.to_dict()
                st.session_state["menu"] = "Edit Ticket"
                st.rerun()
    else:
        st.info("No tickets found.")

# --- Add Ticket ---
elif menu == "Add Ticket":
    st.header("Add Ticket")
    with st.form("add_ticket_form"):
        first = st.text_input("First Name")
        last = st.text_input("Last Name")
        source = st.text_input("Contact Source")
        status = st.selectbox("Status", STATUS_LIST)
        notes = st.text_area("Notes")
        lost_reason = st.text_input("Lost Reason")
        service = st.selectbox("Service Type", SERVICE_LIST)
        street = st.text_input("Street")
        city = st.text_input("City")
        state = st.text_input("State")
        postal = st.text_input("Postal")
        submitted = st.form_submit_button("➕ Add Ticket")
        if submitted:
            st.success("Ticket added (simulation for demo).")

# --- Edit Ticket ---
elif menu == "Edit Ticket":
    ticket = st.session_state.get("edited_ticket")
    if not ticket:
        st.warning("No ticket selected for editing.")
    else:
        st.header(f"Edit Ticket: {ticket['Name']}")
        with st.form("edit_ticket_form"):
            status = st.selectbox("Status", STATUS_LIST, index=STATUS_LIST.index(ticket["Status"]) if ticket["Status"] in STATUS_LIST else 0)
            notes = st.text_area("Notes", value=ticket.get("Notes",""))
            lost_reason = st.text_input("Lost Reason", value=ticket.get("LostReason",""))
            service = st.selectbox("Service Type", SERVICE_LIST, index=SERVICE_LIST.index(ticket["Service"]) if ticket["Service"] in SERVICE_LIST else 0)
            save = st.form_submit_button("💾 Save")
            if save:
                st.success("Ticket updated (simulation for demo).")

# --- KPI Dashboard ---
elif menu == "KPI":
    st.header("KPI Dashboard")
    df = fetch_submissions()
    if df.empty:
        st.info("No data to calculate KPIs.")
    else:
        total = len(df)
        installed = len(df[df["Status"] == "Installed"])
        conv = round(installed/total*100,1) if total > 0 else 0
        st.metric("Total Leads", total)
        st.metric("Installed", installed)
        st.metric("Conversion %", conv)
