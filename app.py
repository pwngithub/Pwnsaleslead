import streamlit as st
import pandas as pd
from datetime import datetime
import numpy as np

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
        'Last Updated': [datetime.now(), datetime.now(), datetime.now()],
        'Notes': ['Initial inquiry received.', 'Followed up via email.', 'Sent a demo link.']
    })

# --- Main Application UI ---
st.title("📈 Sales Lead Tracking System")

# --- Lead Status KPIs ---
st.markdown("### Key Performance Indicators")
status_list = [
    "New", "Contacted", "Proposal Sent", "Negotiation", "Closed Won", "Closed Lost",
    "Survey Added", "Survey Completed", "Prep Scheduled", "Prep Completed", "Install Scheduled"
]
kpi_cols = st.columns(len(status_list))

# Calculate time in status for each lead
now = datetime.now()
st.session_state.leads_df['Time In Status'] = (now - st.session_state.leads_df['Last Updated']).dt.total_seconds() / 86400  # Convert to days

for i, status in enumerate(status_list):
    leads_in_status = st.session_state.leads_df[st.session_state.leads_df['Status'] == status]
    
    if not leads_in_status.empty:
        avg_time = leads_in_status['Time In Status'].mean()
        avg_time_str = f"{avg_time:.1f} days"
        
        with kpi_cols[i]:
            st.metric(
                label=f"Avg. Time in '{status}'",
                value=avg_time_str
            )

# --- View and Manage Leads Section ---
st.markdown("---")
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
    filtered_df[['Lead ID', 'Name', 'Company', 'Status', 'Last Updated', 'Time In Status', 'Notes']],
    use_container_width=True,
    hide_index=True,
    column_config={
        "Last Updated": st.column_config.DatetimeColumn(format="YYYY-MM-DD HH:mm:ss"),
        "Time In Status": st.column_config.NumberColumn(format="%.2f days")
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
            options=status_list,
            index=0
        )
    with col2:
        new_notes = st.text_area("Notes", placeholder="e.g., Initial meeting scheduled for next week.", height=100)

    # Every form must have a submit button
    submitted = st.form_submit_button("Add Lead")

    if submitted:
        # Check if required fields are filled
        if new_name and new_company:
            # Generate a new Lead ID
            last_id = st.session_state.leads_df['Lead ID'].iloc[-1] if not st.session_state.leads_df.empty else 'L000'
            last_number = int(last_id[1:])
            new_id = f'L{last_number + 1:03d}'

            # Create a new DataFrame row
            new_row = pd.DataFrame([{
                'Lead ID': new_id,
                'Name': new_name,
                'Company': new_company,
                'Status': new_status,
                'Last Updated': datetime.now(),
                'Notes': new_notes
            }])

            # Append the new row to the main DataFrame in session state
            st.session_state.leads_df = pd.concat([st.session_state.leads_df, new_row], ignore_index=True)
            st.success("New lead added successfully!")
            st.rerun()
        else:
            st.error("Please fill out both Name and Company fields.")


# --- Update Lead Status Section ---
st.markdown("---")
st.markdown("### Update Existing Lead Status")
with st.form("update_lead_form", clear_on_submit=True):
    lead_ids = st.session_state.leads_df['Lead ID'].tolist()
    
    if lead_ids:
        col1, col2 = st.columns(2)
        with col1:
            lead_to_update = st.selectbox("Select Lead to Update", options=lead_ids)
            new_status_update = st.selectbox("New Status", options=status_list)
        
        with col2:
            update_notes = st.text_area("Update Notes (Optional)", height=100)

        update_submitted = st.form_submit_button("Update Status")

        if update_submitted:
            idx = st.session_state.leads_df[st.session_state.leads_df['Lead ID'] == lead_to_update].index[0]
            st.session_state.leads_df.loc[idx, 'Status'] = new_status_update
            st.session_state.leads_df.loc[idx, 'Last Updated'] = datetime.now()
            if update_notes:
                st.session_state.leads_df.loc[idx, 'Notes'] += f"\n\n--- Status updated to '{new_status_update}' on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n{update_notes}"
            st.success(f"Lead {lead_to_update} status updated to '{new_status_update}'!")
            st.rerun()
    else:
        st.warning("No leads to update. Please add a new lead first.")


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
            'Last Updated': [datetime.now(), datetime.now(), datetime.now()],
            'Notes': ['Initial inquiry received.', 'Followed up via email.', 'Sent a demo link.']
        })
        st.rerun()
