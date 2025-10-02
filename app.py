# Pioneer Sales Lead App – v19.10.35
# Live JotForm integration, KPI, auto-dating, and history
import streamlit as st
import pandas as pd
from datetime import datetime
import requests
import config # Import the config file
import re

# --- CONSTANTS ---
st.set_page_config(page_title="Pioneer Sales Lead App", page_icon="📶", layout="wide")

LOGO = "https://images.squarespace-cdn.com/content/v1/651eb4433b13e72c1034f375/369c5df0-5363-4827-b041-1add0367f447/PBB+long+logo.png?format=1500w"

STATUS_LIST = config.STATUS_LIST
SERVICE_TYPES = config.SERVICE_TYPES
COLORS = {
    "Survey Scheduled": "#3b82f6",
    "Survey Completed": "#fbbf24",
    "Scheduled": "#fb923c",
    "Installed": "#22c55e",
    "Waiting on Customer": "#a855f7",
    "Lost": "#ef4444"
}

# Map statuses to their corresponding date fields from config.py
STATUS_TO_DATE_FIELD = {
    "Survey Scheduled": "survey_scheduled_date",
    "Survey Completed": "survey_completed_date",
    "Scheduled": "scheduled_date",
    "Installed": "installed_date",
    "Waiting on Customer": "waiting_on_customer_date",
}
# -----------------

# --- JOTFORM API FUNCTIONS ---

@st.cache_data(ttl=300) # Cache data for 5 minutes
def get_jotform_submissions():
    """Fetches all submissions from the JotForm form and returns a DataFrame."""
    try:
        url = f"https://api.jotform.com/form/{config.FORM_ID}/submissions?apiKey={config.API_KEY}&limit=1000"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json().get('content', [])
        
        records = []
        for sub in data:
            if sub.get('status') == 'ACTIVE':
                answers = sub.get('answers', {})
                
                # Helper to get answer value by question ID
                def get_ans(qid):
                    ans_dict = answers.get(str(qid))
                    if ans_dict:
                        return ans_dict.get('answer', '')
                    return ''

                # --- NEW, ROBUST NAME PARSING LOGIC ---
                # It extracts the numeric ID (e.g., '3') from "first_3"
                name_field_str = config.FIELD_ID.get('name_first', '')
                name_id_match = re.search(r'\d+', name_field_str)
                first_name, last_name = '', ''
                if name_id_match:
                    name_id = name_id_match.group()
                    name_ans = get_ans(name_id)
                    first_name = name_ans.get('first', '') if isinstance(name_ans, dict) else ''
                    last_name = name_ans.get('last', '') if isinstance(name_ans, dict) else ''

                records.append({
                    "SubmissionID": sub.get('id'),
                    "Name": f"{first_name} {last_name}".strip(),
                    "ContactSource": get_ans(config.FIELD_ID['source']),
                    "Status": get_ans(config.FIELD_ID['status']),
                    "TypeOfService": get_ans(config.FIELD_ID['service_type']),
                    "LostReason": get_ans(config.FIELD_ID['lost_reason']),
                    "Notes": get_ans(config.FIELD_ID['notes']),
                    "CreatedAt": pd.to_datetime(sub.get('created_at')),
                    "LastUpdated": pd.to_datetime(sub.get('updated_at')) if sub.get('updated_at') else pd.to_datetime(sub.get('created_at')),
                })

        df = pd.DataFrame(records)
        # Ensure critical columns exist even if no data
        for col in ["SubmissionID", "Name", "Status"]:
            if col not in df.columns:
                df[col] = pd.Series(dtype='object')
        return df

    except requests.exceptions.RequestException as e:
        st.error(f"Failed to connect to JotForm API: {e}")
        return pd.DataFrame() # Return empty dataframe on error
    except Exception as e:
        st.error(f"An error occurred while processing JotForm data: {e}")
        return pd.DataFrame()

def update_jotform_submission(submission_id, payload):
    """Posts an update to a specific JotForm submission."""
    try:
        url = f"https://api.jotform.com/submission/{submission_id}?apiKey={config.API_KEY}"
        response = requests.post(url, data=payload)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        st.error(f"Error updating ticket {submission_id}: {e}")
        return False

def add_jotform_submission(payload):
    """Adds a new submission to the JotForm form."""
    try:
        url = f"https://api.jotform.com/form/{config.FORM_ID}/submissions?apiKey={config.API_KEY}"
        response = requests.post(url, data=payload)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        st.error(f"Error creating new ticket: {e}")
        return False
        
def delete_jotform_submission(submission_id):
    """Deletes a submission from JotForm."""
    try:
        url = f"https://api.jotform.com/submission/{submission_id}?apiKey={config.API_KEY}"
        response = requests.delete(url)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        st.error(f"Error deleting ticket {submission_id}: {e}")
        return False

# --- CALLBACK & HELPER FUNCTIONS ---

def refresh_data():
    """Clear cache and rerun to fetch fresh data."""
    st.cache_data.clear()
    st.rerun()

def update_ticket_status(submission_id, widget_key):
    """Updates status, adds history note, and auto-stamps date."""
    new_status = st.session_state[widget_key]
    row = st.session_state.df[st.session_state.df["SubmissionID"] == submission_id].iloc[0]
    old_status = row['Status']
    
    if old_status != new_status:
        payload = {}
        # 1. Update Status
        payload[f'submission[{config.FIELD_ID["status"]}]'] = new_status
        
        # 2. Append history to notes
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        history_note = f"[{timestamp}] Status → {new_status}"
        current_notes = row.get('Notes', '')
        new_notes = f"{history_note}\n{current_notes}".strip()
        payload[f'submission[{config.FIELD_ID["notes"]}]'] = new_notes
        
        # 3. Auto-stamp date if applicable
        if new_status in STATUS_TO_DATE_FIELD:
            date_field_key = STATUS_TO_DATE_FIELD[new_status]
            date_field_id = config.FIELD_ID[date_field_key]
            payload[f'submission[{date_field_id}][month]'] = datetime.now().month
            payload[f'submission[{date_field_id}][day]'] = datetime.now().day
            payload[f'submission[{date_field_id}][year]'] = datetime.now().year

        if update_jotform_submission(submission_id, payload):
            st.success(f"Moved ticket {submission_id} to {new_status}")
            refresh_data()

def update_ticket_details(sid, new_status, new_service, new_lost, new_notes):
    """Updates all details, including status history and auto-dating."""
    row = st.session_state.df[st.session_state.df["SubmissionID"] == sid].iloc[0]
    old_status = row['Status']

    payload = {
        f'submission[{config.FIELD_ID["service_type"]}]': new_service,
        f'submission[{config.FIELD_ID["lost_reason"]}]': new_lost,
    }

    # Check if status has changed to add history and auto-date
    if old_status != new_status:
        payload[f'submission[{config.FIELD_ID["status"]}]'] = new_status
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        history_note = f"[{timestamp}] Status → {new_status}"
        # Prepend history to the user's latest notes
        new_notes_with_history = f"{history_note}\n{new_notes}".strip()
        payload[f'submission[{config.FIELD_ID["notes"]}]'] = new_notes_with_history
        
        if new_status in STATUS_TO_DATE_FIELD:
            date_field_key = STATUS_TO_DATE_FIELD[new_status]
            date_field_id = config.FIELD_ID[date_field_key]
            payload[f'submission[{date_field_id}][month]'] = datetime.now().month
            payload[f'submission[{date_field_id}][day]'] = datetime.now().day
            payload[f'submission[{date_field_id}][year]'] = datetime.now().year
    else:
        # If status didn't change, just save the notes as is
        payload[f'submission[{config.FIELD_ID["notes"]}]'] = new_notes
        
    if update_jotform_submission(sid, payload):
        st.success(f"Ticket {sid} changes saved.")
        refresh_data()
        
def kpi_bar(vdf):
    parts = [f"**Total Leads:** {len(vdf)}"]
    for s in STATUS_LIST:
        parts.append(f"**{s}:** {int((vdf['Status']==s).sum())}")
    st.markdown(" | ".join(parts))

# --- MAIN APP LAYOUT ---

def main_app():
    # Header
    left, mid, right = st.columns([1, 4, 1])
    with left:
        st.image(LOGO, use_container_width=True)
    with mid:
        st.title("Sales Lead Tracker — Pipeline")
    with right:
        st.button("🔄 Refresh Data", on_click=refresh_data, use_container_width=True)

    # Load data from JotForm
    st.session_state.df = get_jotform_submissions()
    is_empty = st.session_state.df.empty
    
    # Define tabs
    tab_pipe, tab_all, tab_add, tab_edit, tab_kpi = st.tabs(["🧩 Pipeline View","📋 All Tickets","➕ Add Ticket","✏️ Edit Ticket","📈 KPI"])

    # Display a warning if the dataframe is empty, but still render the tabs
    if is_empty:
        st.warning("No tickets found. You can create the first one in the 'Add Ticket' tab.")

    with tab_pipe:
        st.subheader("Pipeline")
        if is_empty:
            st.info("There are no tickets to display in the pipeline.")
        else:
            kpi_bar(st.session_state.df)
            cols = st.columns(6)
            for i, status in enumerate(STATUS_LIST):
                with cols[i]:
                    status_count = int((st.session_state.df['Status']==status).sum())
                    st.markdown(f"<div style='background:{COLORS[status]};padding:8px;border-radius:8px;color:#111;font-weight:700'>{status} ({status_count})</div>", unsafe_allow_html=True)
                    
                    subset = st.session_state.df[st.session_state.df["Status"]==status]
                    
                    if subset.empty:
                        st.write("—")
                    else:
                        for _, row in subset.sort_values("LastUpdated", ascending=False).iterrows():
                            with st.expander(f"{row['Name']} · {row.get('TypeOfService','')}", expanded=False):
                                st.caption(f"Updated: {row['LastUpdated'].strftime('%Y-%m-%d %H:%M')}")
                                st.write(row.get("Notes",""))
                                widget_key = f"mv_{row['SubmissionID']}"
                                st.selectbox(
                                    "Move to", STATUS_LIST, 
                                    index=STATUS_LIST.index(status), 
                                    key=widget_key,
                                    on_change=update_ticket_status,
                                    args=(row['SubmissionID'], widget_key) 
                                )

    with tab_all:
        st.subheader("All Tickets")
        if is_empty:
            st.info("There are no tickets to display.")
        else:
            c0,c1,c2,c3,c4 = st.columns([2,1,1,1,1])
            q = c0.text_input("🔍 Search name")
            src = c1.selectbox("Source", ["All"] + ["Email","Phone Call","Walk In","Social Media","In Person"])
            stt = c2.selectbox("Status", ["All"]+STATUS_LIST)
            svc = c3.selectbox("Service", ["All"]+SERVICE_TYPES)
            lost_opts = ["All"] + sorted([x for x in st.session_state.df["LostReason"].dropna().unique()])
            los = c4.selectbox("Lost Reason", lost_opts)
            
            v = st.session_state.df.copy()
            if q: v = v[v["Name"].str.contains(q, case=False, na=False)]
            if src!="All": v = v[v["ContactSource"]==src]
            if stt!="All": v = v[v["Status"]==stt]
            if svc!="All": v = v[v["TypeOfService"]==svc]
            if los!="All": v = v[v["LostReason"]==los]
            st.dataframe(v[["SubmissionID","Name","ContactSource","Status","TypeOfService","LostReason","CreatedAt","LastUpdated"]], use_container_width=True)

    with tab_add:
        st.subheader("Add Ticket")
        with st.form("add"):
            c1,c2 = st.columns(2)
            with c1:
                first = st.text_input("First Name *")
                source = st.selectbox("Contact Source *", [""]+ ["Email","Phone Call","Walk In","Social Media","In Person"])
                status = st.selectbox("Status *", [""]+STATUS_LIST)
            with c2:
                last = st.text_input("Last Name *")
                service = st.selectbox("Type of Service *", [""]+SERVICE_TYPES)
                notes = st.text_area("Notes")
            lost = st.text_input("Lost Reason")
            
            if st.form_submit_button("Create Ticket"):
                miss = [n for n,vv in [("First Name",first),("Last Name",last),("Source",source),("Status",status),("Service",service)] if not vv]
                if miss:
                    st.error("Missing: " + ", ".join(miss))
                else:
                    # --- NEW, ROBUST PAYLOAD CREATION FOR NAME ---
                    name_field_str = config.FIELD_ID.get('name_first', '')
                    name_id_match = re.search(r'\d+', name_field_str)
                    if name_id_match:
                        name_id = name_id_match.group()
                        payload = {
                            f'submission[{name_id}][first]': first,
                            f'submission[{name_id}][last]': last,
                            f'submission[{str(config.FIELD_ID["source"])}]': source,
                            f'submission[{str(config.FIELD_ID["status"])}]': status,
                            f'submission[{str(config.FIELD_ID["service_type"])}]': service,
                            f'submission[{str(config.FIELD_ID["notes"])}]': notes,
                            f'submission[{str(config.FIELD_ID["lost_reason"])}]': lost,
                        }
                        
                        # Auto-stamp date if applicable on creation
                        if status in STATUS_TO_DATE_FIELD:
                            date_field_key = STATUS_TO_DATE_FIELD[status]
                            date_field_id = config.FIELD_ID[date_field_key]
                            payload[f'submission[{date_field_id}][month]'] = datetime.now().month
                            payload[f'submission[{date_field_id}][day]'] = datetime.now().day
                            payload[f'submission[{date_field_id}][year]'] = datetime.now().year
                        
                        if add_jotform_submission(payload):
                            st.success("Ticket created successfully.")
                            refresh_data()
                    else:
                        st.error("Could not determine Name Field ID from config.py.")

    with tab_edit:
        st.subheader("Edit Ticket")
        if is_empty:
            st.info("There are no tickets to edit.")
        else:
            opts = {f"{r['Name']} ({r['SubmissionID']})": r["SubmissionID"] for _, r in st.session_state.df.sort_values("Name").iterrows()}
            
            sel_key = st.selectbox("Select by Name", list(opts.keys()), key="edit_sel")
            if sel_key:
                sid = opts[sel_key]
                row = st.session_state.df[st.session_state.df["SubmissionID"]==sid].iloc[0]
                
                c1,c2 = st.columns(2)
                with c1:
                    new_status = st.selectbox("Status", STATUS_LIST, 
                                            index=STATUS_LIST.index(row["Status"]) if row["Status"] in STATUS_LIST else 0,
                                            key=f"edit_status_{sid}")
                    new_service = st.selectbox("Type of Service", SERVICE_TYPES, 
                                                index=SERVICE_TYPES.index(row["TypeOfService"]) if row["TypeOfService"] in SERVICE_TYPES else 0,
                                                key=f"edit_service_{sid}")
                with c2:
                    new_lost = st.text_input("Lost Reason", value=row.get("LostReason") or "", key=f"edit_lost_{sid}")
                    new_notes = st.text_area("Notes", value=row.get("Notes") or "", key=f"edit_notes_{sid}", help="A history entry will be automatically added if you change the status.")
                    
                col_save, col_delete = st.columns([1,1])
                with col_save:
                    if st.button("Save Changes", use_container_width=True):
                        update_ticket_details(sid, new_status, new_service, new_lost, new_notes)
                with col_delete:
                    if st.button("❌ Delete Ticket", type="primary", use_container_width=True):
                        st.session_state['confirm_delete'] = sid
                
                if st.session_state.get('confirm_delete') == sid:
                    st.warning(f"Are you sure you want to delete ticket for {row['Name']} ({sid})?")
                    c_yes, c_no = st.columns(2)
                    with c_yes:
                        if st.button("Yes, Delete Permanently", type="primary", use_container_width=True):
                            if delete_jotform_submission(sid):
                                st.success(f"Ticket {sid} has been permanently deleted.")
                                st.session_state['confirm_delete'] = None
                                refresh_data()
                    with c_no:
                        if st.button("No, Keep It", use_container_width=True):
                            st.session_state['confirm_delete'] = None

    with tab_kpi:
        st.subheader("KPI Dashboard")
        if is_empty:
            st.info("There is no data for the KPI dashboard.")
        else:
            v = st.session_state.df.copy()
            kpi_bar(v)
            st.write("---")
            st.write("**By Status**")
            st.dataframe(v.groupby("Status").size().reset_index(name="Count"), use_container_width=True)
            st.write("**By Source**")
            st.dataframe(v.groupby("ContactSource").size().reset_index(name="Count"), use_container_width=True)
            st.write("**By Service**")
            st.dataframe(v.groupby("TypeOfService").size().reset_index(name="Count"), use_container_width=True)
            if "LostReason" in v.columns and not v["LostReason"].dropna().empty:
                st.write("**Lost Reasons**")
                st.dataframe(v.groupby("LostReason").size().reset_index(name="Count"), use_container_width=True)

    st.markdown("<hr/>", unsafe_allow_html=True)
    st.caption("Powered by Pioneer Broadband | Internal Use Only")

# --- APP INITIALIZATION ---
if __name__ == "__main__":
    if 'confirm_delete' not in st.session_state:
        st.session_state['confirm_delete'] = None
    main_app()
