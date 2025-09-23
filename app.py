import streamlit as st
import json
import os
from datetime import datetime, timedelta

# --- Configuration ---
DATA_FILE = 'leads.json'
STATUSES = [
    "Survey Scheduled",
    "Survey Complete",
    "Prep Scheduled",
    "Prep Complete",
    "Install Scheduled",
    "Install Completed"
]

# --- Helper Functions for Data Persistence ---
def load_leads():
    """Loads leads from the local JSON file."""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return []

def save_leads(leads):
    """Saves leads to the local JSON file."""
    with open(DATA_FILE, 'w') as f:
        json.dump(leads, f, indent=4)

# --- UI Layout and Logic ---

st.set_page_config(layout="centered", page_title="ISP Lead Tracker")
st.title("ISP Lead Tracker")
st.markdown("Track the status and time for each lead.")

# Initialize session state for the leads
if 'leads' not in st.session_state:
    st.session_state.leads = load_leads()

# --- Add New Lead Form ---
st.header("Add New Lead")
with st.form("add_lead_form", clear_on_submit=True):
    lead_name = st.text_input("Enter Lead Name")
    col1, col2 = st.columns([1, 4])
    with col1:
        submitted = st.form_submit_button("Add Lead")

    if submitted and lead_name:
        new_lead = {
            "name": lead_name,
            "status": STATUSES[0],
            "statusHistory": [{"status": STATUSES[0], "timestamp": datetime.now().isoformat()}],
        }
        st.session_state.leads.append(new_lead)
        save_leads(st.session_state.leads)
        st.success(f"Lead '{lead_name}' added successfully!")
        st.experimental_rerun()


# --- Display Leads and Actions ---
st.header("Current Leads")

if not st.session_state.leads:
    st.info("No leads yet. Add one above!")
else:
    for i, lead in enumerate(st.session_state.leads):
        st.subheader(lead['name'])
        
        # Calculate time in status and total time
        current_status_start = datetime.fromisoformat(lead['statusHistory'][-1]['timestamp'])
        time_in_status = datetime.now() - current_status_start
        
        total_time = datetime.now() - datetime.fromisoformat(lead['statusHistory'][0]['timestamp'])

        # Display details
        st.write(f"**Current Status:** {lead['status']}")
        st.write(f"**Time in Status:** {time_in_status}")
        st.write(f"**Total Time:** {total_time}")
        
        # Action buttons
        current_index = STATUSES.index(lead['status'])
        
        button_col1, button_col2, button_col3 = st.columns([1, 1, 1])

        # Move to next status button
        with button_col1:
            if current_index < len(STATUSES) - 1:
                if st.button(f"Move to {STATUSES[current_index + 1]}", key=f"move_{i}"):
                    lead['status'] = STATUSES[current_index + 1]
                    lead['statusHistory'].append({
                        "status": STATUSES[current_index + 1],
                        "timestamp": datetime.now().isoformat()
                    })
                    save_leads(st.session_state.leads)
                    st.success(f"Status for '{lead['name']}' updated.")
                    st.experimental_rerun()
        
        # Delete lead button
        with button_col2:
            if st.button("Delete", key=f"delete_{i}"):
                st.session_state.leads.pop(i)
                save_leads(st.session_state.leads)
                st.warning(f"Lead '{lead['name']}' deleted.")
                st.experimental_rerun()
        
        st.markdown("---")
