import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import numpy as np

# --- Page Configuration ---
st.set_page_config(
    page_title="Sales Lead System",
    page_icon="📈",
    layout="wide"
)

# --- Data Initialization (using st.session_state for persistence) ---
@st.cache_data
def get_initial_data():
    """Initializes the dataframe with some sample data."""
    now = datetime.now()
    initial_data = {
        'Lead ID': ['L001', 'L002', 'L003'],
        'Name': ['John Doe', 'Jane Smith', 'Peter Jones'],
        'Company': ['Acme Corp', 'Beta Inc.', 'Gamma LLC'],
        'Sales Rep': ['Alice', 'Bob', 'Alice'],
        'Status': ['New', 'Contacted', 'New'],
        # Store a history of status changes
        'status_history': [
            [{'status': 'New', 'timestamp': now - timedelta(days=7)}],
            [{'status': 'New', 'timestamp': now - timedelta(days=10)}, {'status': 'Contacted', 'timestamp': now - timedelta(days=5)}],
            [{'status': 'New', 'timestamp': now - timedelta(days=12)}]
        ],
        'Notes': ['Initial inquiry received.', 'Followed up via email.', 'Sent a demo link.']
    }
    return pd.DataFrame(initial_data)

if 'leads_df' not in st.session_state:
    st.session_state.leads_df = get_initial_data()

if 'sales_reps' not in st.session_state:
    st.session_state.sales_reps = ['Alice', 'Bob', 'Charlie', 'Dana']

# --- Helper Functions ---
def calculate_time_in_status(history):
    """Calculates time spent in the most recent status."""
    if not history:
        return np.nan
    
    last_update_time = history[-1]['timestamp']
    return (datetime.now() - last_update_time).total_seconds() / 86400

def get_total_duration(history, start_status, end_status):
    """Calculates the duration from one status to another."""
    start_time = None
    end_time = None
    for item in history:
        if item['status'] == start_status and start_time is None:
            start_time = item['timestamp']
        if item['status'] == end_status and end_time is None:
            end_time = item['timestamp']
            break
    
    if start_time and end_time:
        return (end_time - start_time).total_seconds() / 86400
    return np.nan

# --- Main Application UI ---
st.title("📈 Sales Lead Tracking System")

# --- KPI Section ---
st.markdown("---")
st.markdown("### Key Performance Indicators")

# Recalculate 'Time In Status' for display
st.session_state.leads_df['Time In Status'] = st.session_state.leads_df['status_history'].apply(calculate_time_in_status)

col1, col2, col3, col4 = st.columns(4)

# KPI 1: Total Leads
col1.metric("Total Leads", st.session_state.leads_df.shape[0])

# KPI 2: Average time from New to Contacted
new_to_contacted_times = st.session_state.leads_df[
    st.session_state.leads_df['Status'].isin(['Contacted', 'Proposal Sent', 'Negotiation', 'Closed Won', 'Closed Lost'])
].apply(lambda row: get_total_duration(row['status_history'], 'New', 'Contacted'), axis=1).dropna()
avg_time_to_contacted = new_to_contacted_times.mean() if not new_to_contacted_times.empty else 0
col2.metric("Avg. Time to Contact", f"{avg_time_to_contacted:.1f} days")

# KPI 3: Average time to close (from New to Closed Won)
new_to_closed_times = st.session_state.leads_df[
    st.session_state.leads_df['Status'] == 'Closed Won'
].apply(lambda row: get_total_duration(row['status_history'], 'New', 'Closed Won'), axis=1).dropna()
avg_time_to_close = new_to_closed_times.mean() if not new_to_closed_times.empty else 0
col3.metric("Avg. Time to Close", f"{avg_time_to_close:.1f} days")

# KPI 4: Total Closed Won
closed_won_count = st.session_state.leads_df[st.session_state.leads_df['Status'] == 'Closed Won'].shape[0]
col4.metric("Total Closed Won", closed_won_count)

# --- View and Manage Leads Section ---
st.markdown("---")
with st.expander("View and Manage Leads", expanded=True):
    # Filter and search UI
    st.sidebar.header("Filter and Search")

    # Search by name or company
    search_query = st.sidebar.text_input("Search by Name or Company")
    
    # Filter by status
    status_list = [
        "New", "Contacted", "Proposal Sent", "Negotiation", "Closed Won", "Closed Lost",
        "Survey Added", "Survey Completed", "Prep Scheduled", "Prep Completed", "Install Scheduled"
    ]
    selected_statuses = st.sidebar.multiselect(
        "Filter by Status",
        options=status_list,
        default=status_list
    )
    
    # Filter by sales rep
    selected_reps = st.sidebar.multiselect(
        "Filter by Sales Rep",
        options=st.session_state.sales_reps,
        default=st.session_state.sales_reps
    )
    
    # Apply filters
    filtered_df = st.session_state.leads_df[
        (st.session_state.leads_df['Name'].str.contains(search_query, case=False)) |
        (st.session_state.leads_df['Company'].str.contains(search_query, case=False))
    ]
    filtered_df = filtered_df[filtered_df['Status'].isin(selected_statuses)]
    filtered_df = filtered_df[filtered_df['Sales Rep'].isin(selected_reps)]

    # Display the data table with st.data_editor for direct editing
    st.markdown("### All Leads (Click on a cell to edit)")
    
    # Create a copy for editing to avoid modifying session state directly during filtering
    edited_df = st.data_editor(
        filtered_df[['Lead ID', 'Name', 'Company', 'Sales Rep', 'Status', 'Time In Status', 'Notes']],
        use_container_width=True,
        hide_index=True,
        key="lead_editor",
        column_config={
            "Status": st.column_config.SelectboxColumn(
                "Status",
                options=status_list,
                required=True,
            ),
            "Sales Rep": st.column_config.SelectboxColumn(
                "Sales Rep",
                options=st.session_state.sales_reps,
                required=True
            ),
            "Time In Status": st.column_config.NumberColumn(
                "Time In Status (Days)",
                format="%.2f days",
                help="Time since the lead's last status change.",
                disabled=True
            )
        }
    )

    # Update session state with the edited DataFrame
    # Note: This is a simplified update logic. A more robust app would handle merges.
    if not edited_df.equals(filtered_df):
        for _, row in edited_df.iterrows():
            lead_id = row['Lead ID']
            original_status = st.session_state.leads_df.loc[st.session_state.leads_df['Lead ID'] == lead_id, 'Status'].iloc[0]
            new_status = row['Status']
            
            # Update the main DataFrame
            st.session_state.leads_df.loc[st.session_state.leads_df['Lead ID'] == lead_id, ['Name', 'Company', 'Sales Rep', 'Status', 'Notes']] = \
                [row['Name'], row['Company'], row['Sales Rep'], row['Status'], row['Notes']]

            # If the status changed, update the history
            if original_status != new_status:
                history_list = st.session_state.leads_df.loc[st.session_state.leads_df['Lead ID'] == lead_id, 'status_history'].iloc[0]
                history_list.append({'status': new_status, 'timestamp': datetime.now()})
                st.session_state.leads_df.loc[st.session_state.leads_df['Lead ID'] == lead_id, 'status_history'] = [history_list]

        st.success("Leads updated successfully!")
        st.experimental_rerun()

# --- Lead Status Visualization ---
st.markdown("---")
with st.expander("Lead Status Visualization", expanded=True):
    col1, col2 = st.columns([1, 2])
    
    # Count the number of leads for each status
    status_counts = st.session_state.leads_df['Status'].value_counts().reset_index()
    status_counts.columns = ['Status', 'Count']
    
    with col1:
        st.markdown("### Lead Distribution by Status")
        st.dataframe(status_counts, hide_index=True, use_container_width=True)

    with col2:
        st.markdown("### Lead Distribution Chart")
        # Use a pie chart for better visualization of proportions
        st.bar_chart(status_counts.set_index('Status'))

# --- Add New Lead Section ---
st.markdown("---")
with st.expander("Add a New Lead", expanded=False):
    with st.form("new_lead_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            new_name = st.text_input("Name", placeholder="e.g., Jane Doe")
            new_company = st.text_input("Company", placeholder="e.g., Sample Corp")
            new_rep = st.selectbox("Sales Rep", options=st.session_state.sales_reps)
        with col2:
            new_status = st.selectbox("Status", options=status_list, index=0)
            new_notes = st.text_area("Notes", placeholder="e.g., Initial meeting scheduled for next week.", height=100)

        submitted = st.form_submit_button("Add Lead")

        if submitted:
            if new_name and new_company:
                last_id = st.session_state.leads_df['Lead ID'].iloc[-1] if not st.session_state.leads_df.empty else 'L000'
                last_number = int(last_id[1:])
                new_id = f'L{last_number + 1:03d}'
                new_row = pd.DataFrame([{
                    'Lead ID': new_id,
                    'Name': new_name,
                    'Company': new_company,
                    'Sales Rep': new_rep,
                    'Status': new_status,
                    'status_history': [{'status': new_status, 'timestamp': datetime.now()}],
                    'Notes': new_notes
                }])
                st.session_state.leads_df = pd.concat([st.session_state.leads_df, new_row], ignore_index=True)
                st.success("New lead added successfully!")
                st.experimental_rerun()
            else:
                st.error("Please fill out both Name and Company fields.")

# --- Action Buttons ---
st.markdown("---")
with st.expander("App Actions", expanded=False):
    if st.button("Reset All Data", help="This will delete all leads and reset to the initial sample data."):
        st.session_state.leads_df = get_initial_data()
        st.experimental_rerun()
