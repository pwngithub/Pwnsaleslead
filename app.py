import streamlit as st
import pandas as pd
from datetime import datetime

# --- Page Configuration ---
st.set_page_config(
    page_title="Sales Lead System",
    page_icon="📈",
    layout="wide"
)

# --- Data Initialization (using st.session_state for persistence) ---
# Check if the DataFrame already exists in session state. If not, create it.
if 'leads_df' not in st.session_state:
    st.session_state.leads_df = pd.DataFrame({
        'Lead ID': ['L001', 'L002', 'L003'],
        'Name': ['John Doe', 'Jane Smith', 'Peter Jones'],
        'Company': ['Acme Corp', 'Beta Inc.', 'Gamma LLC'],
        'Status': ['New', 'Contacted', 'New'],
        'Last Contact': [datetime(2023, 10, 25).date(), datetime(2023, 10, 24).date(), datetime(2023, 10, 23).date()],
        'Notes': ['Initial inquiry received.', 'Followed up via email.', 'Sent a demo link.']
    })

# --- Main Application UI ---
st.title("📈 Sales Lead Tracking System")
st.markdown("### View and Manage Leads")

# Filter and search UI
st.sidebar.header("Filter and Search")

# Search by name or company
search_query = st.sidebar.text_input("Search by Name or Company")
filtered_df = st.session_state.leads_df[
    st.session_state.leads_df['Name'].str.contains(search_query, case=False) |
    st.session_state.leads_df['Company'].str.contains(search_query, case=False)
]

# Filter by status
selected_statuses = st.sidebar.multiselect(
    "Filter by Status",
    options=st.session_state.leads_df['Status'].unique(),
    default=st.session_state.leads_df['Status'].unique()
)
filtered_df = filtered_df[filtered_df['Status'].isin(selected_statuses)]

# Display the data table
st.dataframe(
    filtered_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Last Contact": st.column_config.DateColumn(format="YYYY-MM-DD")
    }
)

# --- Add New Lead Section ---
st.markdown("---")
st.markdown("### Add a New Lead")

# Use a form to group input widgets and make the submission atomic
with st.form("new_lead_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        new_name = st.text_input("Name", placeholder="e.g., Jane Doe", help="Enter the lead's full name.")
        new_company = st.text_input("Company", placeholder="e.g., Sample Corp", help="Enter the lead's company name.")
        new_status = st.selectbox(
            "Status",
            options=[
                "New",
                "Contacted",
                "Proposal Sent",
                "Negotiation",
                "Closed Won",
                "Closed Lost",
                "Survey Added",
                "Survey Completed",
                "Prep Scheduled",
                "Prep Completed",
                "Install Scheduled"
            ],
            index=0
        )
    with col2:
        new_last_contact = st.date_input("Last Contact Date", value=datetime.now().date(), help="Select the date of the last contact.")
        new_notes = st.text_area("Notes", placeholder="e.g., Initial meeting scheduled for next week.", height=100)

    # Every form must have a submit button
    submitted = st.form_submit_button("Add Lead")

    if submitted:
        # Check if required fields are filled
        if new_name and new_company:
            # Generate a new Lead ID
            last_id = st.session_state.leads_df['Lead ID'].iloc[-1]
            last_number = int(last_id[1:])
            new_id = f'L{last_number + 1:03d}'

            # Create a new DataFrame row
            new_row = pd.DataFrame([{
                'Lead ID': new_id,
                'Name': new_name,
                'Company': new_company,
                'Status': new_status,
                'Last Contact': new_last_contact,
                'Notes': new_notes
            }])

            # Append the new row to the main DataFrame in session state
            st.session_state.leads_df = pd.concat([st.session_state.leads_df, new_row], ignore_index=True)
            st.success("New lead added successfully!")
            st.rerun()
        else:
            st.error("Please fill out both Name and Company fields.")

# --- Lead Status Visualization ---
st.markdown("---")
st.markdown("### Lead Status Visualization")

# Count the number of leads for each status
status_counts = st.session_state.leads_df['Status'].value_counts().reset_index()
status_counts.columns = ['Status', 'Count']

# Display the data in a bar chart
st.bar_chart(status_counts.set_index('Status'))

# Display a table of the counts
st.write("Lead Counts by Status:")
st.dataframe(status_counts, hide_index=True)

# --- Action Buttons ---
st.markdown("---")
st.markdown("### Actions")
col1, col2 = st.columns([1, 4])
with col1:
    if st.button("Reset Data", help="This will delete all leads and reload the initial data."):
        st.session_state.leads_df = pd.DataFrame({
            'Lead ID': ['L001', 'L002', 'L003'],
            'Name': ['John Doe', 'Jane Smith', 'Peter Jones'],
            'Company': ['Acme Corp', 'Beta Inc.', 'Gamma LLC'],
            'Status': ['New', 'Contacted', 'New'],
            'Last Contact': [datetime(2023, 10, 25).date(), datetime(2023, 10, 24).date(), datetime(2023, 10, 23).date()],
            'Notes': ['Initial inquiry received.', 'Followed up via email.', 'Sent a demo link.']
        })
        st.rerun()
