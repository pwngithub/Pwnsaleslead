import streamlit as st
import pandas as pd
import numpy as np
import uuid

# --- Page Configuration ---
# Use a wide layout and set a title for the page
st.set_page_config(layout="wide", page_title="Sales & Leads Dashboard", page_icon="📈")

# --- Session State Management ---
# Initialize session state variables if they don't exist
# This is crucial for persisting data across app reruns
if 'leads_df' not in st.session_state:
    # Create a sample DataFrame for demonstration
    sample_data = {
        'id': [str(uuid.uuid4()) for _ in range(10)],
        'Lead Name': ['Acme Corp', 'Globex Inc.', 'Initech', 'Hooli', 'Pied Piper', 'Cyberdyne', 'Tyrell Corp', 'Weyland-Yutani', 'Omni Consumer Products', 'Stark Industries'],
        'Status': ['New', 'Contacted', 'Qualified', 'New', 'Contacted', 'Qualified', 'New', 'Contacted', 'Qualified', 'New'],
        'Source': ['Website', 'Referral', 'Paid Ad', 'Referral', 'Website', 'Referral', 'Paid Ad', 'Website', 'Referral', 'Paid Ad'],
        'Value': [15000, 25000, 50000, 10000, 30000, 60000, 5000, 20000, 45000, 80000],
        'Assigned Rep': ['Sarah', 'John', 'Sarah', 'Alex', 'Alex', 'John', 'Alex', 'Sarah', 'John', 'Alex'],
        'Notes': ['Initial contact made.', 'Sent follow-up email.', 'Scheduled demo.', 'New lead from contact form.', 'Left a voicemail.', 'High potential lead.', 'Followed up via social media.', 'Responded to our newsletter.', 'Needs a custom quote.', 'Looking for enterprise solution.']
    }
    st.session_state['leads_df'] = pd.DataFrame(sample_data)

# --- Functions for Data Operations ---
def add_lead(name, status, source, value, rep, notes):
    """Adds a new lead to the DataFrame in session state."""
    new_lead = pd.DataFrame([{
        'id': str(uuid.uuid4()),
        'Lead Name': name,
        'Status': status,
        'Source': source,
        'Value': value,
        'Assigned Rep': rep,
        'Notes': notes
    }])
    st.session_state['leads_df'] = pd.concat([st.session_state['leads_df'], new_lead], ignore_index=True)
    st.success("Lead added successfully!")

def update_lead(updated_df):
    """Updates the entire DataFrame from the data editor and stores it in session state."""
    st.session_state['leads_df'] = updated_df
    st.success("Leads updated successfully!")

# --- Dashboard UI ---
st.title("Sales & Leads Dashboard 📈")
st.markdown("Track your sales performance and manage your leads in real-time.")

# --- Key Performance Indicators (KPIs) ---
st.header("Key Metrics")

# Calculate KPIs
total_leads = st.session_state['leads_df'].shape[0]
new_leads = st.session_state['leads_df'][st.session_state['leads_df']['Status'] == 'New'].shape[0]
total_value = st.session_state['leads_df']['Value'].sum()
avg_lead_value = st.session_state['leads_df']['Value'].mean()

# Display KPIs using columns
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(label="Total Leads", value=total_leads, delta=f"+{new_leads} new")

with col2:
    st.metric(label="Total Pipeline Value", value=f"${total_value:,.0f}")

with col3:
    st.metric(label="Average Lead Value", value=f"${avg_lead_value:,.0f}")

with col4:
    # Calculate conversion rate from 'Qualified' to a hypothetical 'Closed Won' status
    qualified_leads = st.session_state['leads_df'][st.session_state['leads_df']['Status'] == 'Qualified'].shape[0]
    conversion_rate = (qualified_leads / total_leads * 100) if total_leads > 0 else 0
    st.metric(label="Conversion Rate", value=f"{conversion_rate:.1f}%")

# --- Interactive Charts ---
st.header("Sales & Leads Funnel")

# Create a bar chart for leads by status
leads_by_status = st.session_state['leads_df'].groupby('Status').size().reset_index(name='count')
st.bar_chart(leads_by_status.set_index('Status'))

# Create a pie chart for leads by source
leads_by_source = st.session_state['leads_df'].groupby('Source').size()
st.subheader("Leads by Source")
st.bar_chart(leads_by_source)

# --- Leads Data Table ---
st.header("Leads Data")
st.markdown("Use the table below to view and edit your leads. Changes are saved automatically.")

# The data editor allows the user to directly modify the DataFrame
# The on_change callback is triggered when the user modifies data
st.data_editor(st.session_state['leads_df'], key="leads_table", on_change=lambda: update_lead(st.session_state.leads_table), use_container_width=True)


# --- Add New Lead Form (in a sidebar) ---
st.sidebar.header("Add New Lead")
with st.sidebar.form(key='add_lead_form'):
    lead_name = st.text_input("Lead Name", placeholder="e.g., Jane Doe")
    lead_status = st.selectbox("Status", ['New', 'Contacted', 'Qualified', 'Closed Won', 'Closed Lost'])
    lead_source = st.text_input("Source", placeholder="e.g., Website, Referral, etc.")
    lead_value = st.number_input("Value ($)", min_value=0, value=0)
    lead_rep = st.selectbox("Assigned Rep", ['Sarah', 'John', 'Alex'])
    lead_notes = st.text_area("Notes", placeholder="Add any relevant notes about the lead.")
    
    submit_button = st.form_submit_button(label='Add Lead')
    
    if submit_button:
        if lead_name and lead_status and lead_source and lead_value:
            add_lead(lead_name, lead_status, lead_source, lead_value, lead_rep, lead_notes)
        else:
            st.warning("Please fill in all required fields.")

# --- Explanation and How-to-run ---
st.markdown("""
---
### How to Use this Dashboard
1.  **Run the app:** Save this code as `app.py` and run it from your terminal using the command `streamlit run app.py`.
2.  **View and Edit Data:** The main table allows you to directly edit existing lead data. Any changes you make will be saved automatically.
3.  **Add New Leads:** Use the form in the sidebar to input information for new leads.
4.  **Analyze Metrics:** The key metrics and charts at the top will automatically update as you add or edit data, giving you a real-time view of your sales funnel.
""")
