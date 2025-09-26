import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Sales Lead Tracker v19.10.19", page_icon="📊", layout="wide")

# Top menu
menu = st.sidebar.radio("Navigation", ["All Tickets", "Add Ticket"])

# Placeholder demo data
df = pd.DataFrame({
    "Name": ["Brian Barton", "Jane Doe"],
    "Source": ["Email", "Phone"],
    "Status": ["Survey Scheduled", "Installed"],
    "ServiceType": ["Internet", "Internet + Phone"],
    "Notes": ["Follow-up needed", "Completed"],
    "LostReason": ["Price", None]
})

if menu == "All Tickets":
    st.title("All Tickets Preview")
    st.dataframe(df, use_container_width=True)

    # KPI example
    by_status = df.groupby("Status").size().reset_index(name="Count")
    fig = px.bar(by_status, x="Status", y="Count")
    st.plotly_chart(fig, use_container_width=True, config={"responsive": True})

elif menu == "Add Ticket":
    st.title("Add Ticket")
    with st.form("add_ticket_form"):
        name = st.text_input("Name")
        source = st.selectbox("Contact Source", ["Email", "Phone", "Social Media", "Walk In", "In Person"])
        status = st.selectbox("Status", ["Survey Scheduled", "Survey Completed", "Scheduled", "Installed", "Waiting on Customer"])
        service_type = st.selectbox("Service Type", ["Internet", "Phone", "TV", "Cell Phone", 
                                                     "Internet and Phone", "Internet and TV", "Internet and Cell Phone"])
        notes = st.text_area("Notes")
        lost_reason = st.text_input("Lost Reason")
        submitted = st.form_submit_button("Save Ticket")
        if submitted:
            st.success(f"Ticket added for {name}")
