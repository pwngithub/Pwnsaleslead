import streamlit as st
from datetime import datetime

st.set_page_config(page_title="Pioneer Sales Lead Manager v19.6")

st.title("Pioneer Sales Lead Manager v19.6")
st.image("https://images.squarespace-cdn.com/content/v1/651eb4433b13e72c1034f375/369c5df0-5363-4827-b041-1add0367f447/PBB+long+logo.png?format=1500w")

st.write("Version: v19.6 — Fixed Ticket Editing & Auto Status Dates")

# Placeholder demo UI for ticket editing fix
st.header("All Tickets")
tickets = [
    {"Name": "Brian Barton", "Status": "Survey Scheduled", "Notes": "", "LostReason": "", "Service": "Internet"},
    {"Name": "Jane Doe", "Status": "Installed", "Notes": "Follow-up needed", "LostReason": "", "Service": "Phone"}
]

selected = st.selectbox("Select Ticket to Edit", [t["Name"] for t in tickets])

ticket = next(t for t in tickets if t["Name"] == selected)

st.subheader(f"Editing Ticket: {ticket['Name']}")
new_status = st.selectbox("Status",
                          ["Survey Scheduled","Survey Completed","Scheduled","Installed","Waiting on Customer"],
                          index=["Survey Scheduled","Survey Completed","Scheduled","Installed","Waiting on Customer"].index(ticket["Status"]))

ticket["Status"] = new_status

# Auto fill date fields when status changes
today = datetime.today().strftime('%Y-%m-%d')
date_fields = {
    "Survey Scheduled": "survey_scheduled_date",
    "Survey Completed": "survey_completed_date",
    "Scheduled": "scheduled_date",
    "Installed": "installed_date",
    "Waiting on Customer": "waiting_on_customer_date"
}
auto_date_field = date_fields.get(new_status)
if auto_date_field:
    ticket[auto_date_field] = today

ticket["Notes"] = st.text_area("Notes", ticket["Notes"])
ticket["LostReason"] = st.text_input("Lost Reason", ticket["LostReason"])
ticket["Service"] = st.selectbox("Type of Service", ["Internet","Phone","TV","Cell Phone",
                                                   "Internet and Phone","Internet and TV","Internet and Cell Phone"],
                                 index=0 if not ticket["Service"] else ["Internet","Phone","TV","Cell Phone",
                                                                         "Internet and Phone","Internet and TV","Internet and Cell Phone"].index(ticket["Service"]))

if st.button("Save Changes"):
    st.success("✅ Ticket updated successfully!")
    st.json(ticket)
