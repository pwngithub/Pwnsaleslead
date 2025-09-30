import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import datetime
import csv
import os

from config import API_KEY, FORM_ID, FIELD_ID

st.set_page_config(page_title="Sales Lead Tracker v19.10.20", page_icon="📊", layout="wide")

BASE_URL = "https://api.jotform.com"

# Utility: fetch submissions
def fetch_submissions():
    url = f"{BASE_URL}/form/{FORM_ID}/submissions?apiKey={API_KEY}"
    r = requests.get(url)
    data = r.json()
    out = []
    for item in data.get("content", []):
        answers = item.get("answers", {})
        out.append({
            "SubmissionID": item.get("id"),
            "Name": f"{answers.get(str(FIELD_ID['name_first']), {}).get('answer', '')} {answers.get(str(FIELD_ID['name_last']), {}).get('answer', '')}",
            "Source": answers.get(str(FIELD_ID['source']), {}).get("answer"),
            "Status": answers.get(str(FIELD_ID['status']), {}).get("answer"),
            "ServiceType": answers.get(str(FIELD_ID['service_type']), {}).get("answer"),
            "Notes": answers.get(str(FIELD_ID['notes']), {}).get("answer"),
            "LostReason": answers.get(str(FIELD_ID['lost_reason']), {}).get("answer"),
            "Address": answers.get(str(FIELD_ID['address']), {}).get("answer", {}),
            "LastUpdated": datetime.fromtimestamp(int(item.get("updated_at", item.get("created_at")))),
        })
    return pd.DataFrame(out)

# Utility: log audit events
def log_action(action, ticket_id, name, details=""):
    log_file = "audit_log.csv"
    exists = os.path.exists(log_file)
    with open(log_file, "a", newline="") as f:
        writer = csv.writer(f)
        if not exists:
            writer.writerow(["Timestamp", "Action", "TicketID", "Name", "Details"])
        writer.writerow([datetime.now().isoformat(), action, ticket_id, name, details])

# UI
menu = st.sidebar.radio("Navigation", ["All Tickets", "Add Ticket"])
df = fetch_submissions()

if menu == "All Tickets":
    st.title("All Tickets")
    if df.empty:
        st.info("No tickets found.")
    else:
        st.dataframe(df, use_container_width=True)

        # KPIs
        by_status = df.groupby("Status").size().reset_index(name="Count")
        fig = px.bar(by_status, x="Status", y="Count")
        st.plotly_chart(fig, use_container_width=True, config={"responsive": True})

        # Actions per row
        for i, row in df.iterrows():
            cols = st.columns([6,1,1])
            with cols[0]:
                st.write(f"**{row['Name']}** — {row['Status']}")
            with cols[1]:
                if st.button("✏️ Edit", key=f"edit_{row['SubmissionID']}"):
                    st.session_state["edit_ticket"] = row["SubmissionID"]
                    st.experimental_rerun()
            with cols[2]:
                if st.button("🗑️ Delete", key=f"del_{row['SubmissionID']}"):
                    requests.delete(f"{BASE_URL}/submission/{row['SubmissionID']}?apiKey={API_KEY}")
                    log_action("Delete", row["SubmissionID"], row["Name"])
                    st.success(f"Deleted ticket {row['Name']}")
                    st.experimental_rerun()

    # Edit form
    if "edit_ticket" in st.session_state:
        sid = st.session_state["edit_ticket"]
        st.subheader(f"Edit Ticket — {sid}")
        ticket = df[df["SubmissionID"]==sid].iloc[0]
        new_status = st.selectbox("Status", ["Survey Scheduled","Survey Completed","Scheduled","Installed","Waiting on Customer"], index=0 if not ticket["Status"] else ["Survey Scheduled","Survey Completed","Scheduled","Installed","Waiting on Customer"].index(ticket["Status"]))
        notes = st.text_area("Notes", value=ticket["Notes"] or "")
        lost_reason = st.text_input("Lost Reason", value=ticket["LostReason"] or "")
        if st.button("Save Changes"):
            payload = { f"submission[{FIELD_ID['status']}]": new_status,
                        f"submission[{FIELD_ID['notes']}]": notes,
                        f"submission[{FIELD_ID['lost_reason']}]": lost_reason }
            requests.post(f"{BASE_URL}/submission/{sid}?apiKey={API_KEY}", data=payload)
            log_action("Edit", sid, ticket["Name"], f"Status={new_status}, Notes={notes}, LostReason={lost_reason}")
            st.success("Updated ticket")
            del st.session_state["edit_ticket"]
            st.experimental_rerun()

elif menu == "Add Ticket":
    st.title("Add Ticket")
    with st.form("add_ticket_form"):
        fname = st.text_input("First Name")
        lname = st.text_input("Last Name")
        source = st.selectbox("Source", ["Email","Phone","Social Media","Walk In","In Person"])
        status = st.selectbox("Status", ["Survey Scheduled","Survey Completed","Scheduled","Installed","Waiting on Customer"])
        service = st.selectbox("Service Type", ["Internet","Phone","TV","Cell Phone","Internet and Phone","Internet and TV","Internet and Cell Phone"])
        notes = st.text_area("Notes")
        lost_reason = st.text_input("Lost Reason")
        submitted = st.form_submit_button("Save Ticket")
        if submitted:
            payload = {
                f"submission[{FIELD_ID['name_first']}]": fname,
                f"submission[{FIELD_ID['name_last']}]": lname,
                f"submission[{FIELD_ID['source']}]": source,
                f"submission[{FIELD_ID['status']}]": status,
                f"submission[{FIELD_ID['service_type']}]": service,
                f"submission[{FIELD_ID['notes']}]": notes,
                f"submission[{FIELD_ID['lost_reason']}]": lost_reason
            }
            resp = requests.post(f"{BASE_URL}/form/{FORM_ID}/submissions?apiKey={API_KEY}", data=payload)
            if resp.status_code == 200:
                st.success("Ticket added")
                sid = resp.json().get("content", {}).get("submissionID")
                log_action("Add", sid, f"{fname} {lname}", f"Source={source}, Status={status}")
                st.experimental_rerun()
            else:
                st.error(f"Failed to add ticket: {resp.text}")
