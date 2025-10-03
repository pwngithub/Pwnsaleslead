# Pioneer Sales Lead App – v19.10.35
# Live JotForm integration, KPI, auto-dating, and history
import streamlit as st
import pandas as pd
from datetime import datetime, timezone
import requests
import config # Import the config file
import re

# --- CONSTANTS ---
st.set_page_config(page_title="Pioneer Sales Lead App", page_icon="📶", layout="wide")

LOGO = "https://images.squarespace-cdn.com/content/v1/651eb4433b13e72c1034f375/369c5df0-5363-4827-b041-1add0367f447/PBB+long+logo.png?format=1500w"

STATUS_LIST = config.STATUS_LIST
SERVICE_TYPES = config.SERVICE_TYPES
# Create a list of salesperson names from the USERS dict in config
SALES_TEAM = [details["name"] for details in config.USERS.values()]

COLORS = {
    "Survey Scheduled": "#3b82f6",
    "Survey Completed": "#fbbf24",
    "Scheduled": "#fb923c",
    "Installed": "#22c55e",
    "Waiting on Customer": "#a855f7",
    "Lost": "#ef4444"
}

STATUS_TO_DATE_FIELD = {
    "Survey Scheduled": "survey_scheduled_date",
    "Survey Completed": "survey_completed_date",
    "Scheduled": "scheduled_date",
    "Installed": "installed_date",
    "Waiting on Customer": "waiting_on_customer_date",
}
# -----------------

# --- JOTFORM API FUNCTIONS ---

@st.cache_data(ttl=300)
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
                
                def get_ans(qid):
                    ans_dict = answers.get(str(qid))
                    if ans_dict:
                        return ans_dict.get('answer', '')
                    return ''
                
                def get_date_ans(qid):
                    date_ans = get_ans(qid)
                    if isinstance(date_ans, dict):
                        date_str = f"{date_ans.get('year')}-{date_ans.get('month')}-{date_ans.get('day')}"
                        return pd.to_datetime(date_str, errors='coerce')
                    return pd.to_datetime(date_ans, errors='coerce')

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
                    "AssignedTo": get_ans(config.FIELD_ID['assigned_to']),
                    "ContactSource": get_ans(config.FIELD_ID['source']),
                    "Status": get_ans(config.FIELD_ID['status']),
                    "TypeOfService": get_ans(config.FIELD_ID['service_type']),
                    "LostReason": get_ans(config.FIELD_ID['lost_reason']),
                    "Notes": get_ans(config.FIELD_ID['notes']),
                    "CreatedAt": pd.to_datetime(sub.get('created_at'), utc=True),
                    "LastUpdated": pd.to_datetime(sub.get('updated_at'), utc=True) if sub.get('updated_at') else pd.to_datetime(sub.get('created_at'), utc=True),
                    "SurveyScheduledDate": get_date_ans(config.FIELD_ID['survey_scheduled_date']),
                    "InstalledDate": get_date_ans(config.FIELD_ID['installed_date']),
                })

        df = pd.DataFrame(records)
        # Ensure all necessary columns exist
        for col in ["SubmissionID", "Name", "Status", "CreatedAt", "AssignedTo"]:
            if col not in df.columns:
                df[col] = pd.Series(dtype='object' if col != "CreatedAt" else 'datetime64[ns, UTC]')
        return df

    except Exception as e:
        st.error(f"An error occurred while processing JotForm data: {e}")
        return pd.DataFrame()

# All other API functions (update, add, delete) remain the same

def update_jotform_submission(submission_id, payload):
    try:
        url = f"https://api.jotform.com/submission/{submission_id}?apiKey={config.API_KEY}"
        response = requests.post(url, data=payload)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        st.error(f"Error updating ticket {submission_id}: {e}")
        return False

def add_jotform_submission(payload):
    try:
        url = f"https://api.jotform.com/form/{config.FORM_ID}/submissions?apiKey={config.API_KEY}"
        response = requests.post(url, data=payload)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        st.error(f"Error creating new ticket: {e}")
        return False
        
def delete_jotform_submission(submission_id):
    try:
        url = f"https://api.jotform.com/submission/{submission_id}?apiKey={config.API_KEY}"
        response = requests.delete(url)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        st.error(f"Error deleting ticket {submission_id}: {e}")
        return False

# All other helper functions remain the same

def refresh_data():
    st.cache_data.clear()
    st.rerun()

def calculate_status_durations(df):
    duration_records = []
    now = datetime.now(timezone.utc)
    for _, row in df.iterrows():
        notes = row.get('Notes', '') or ''
        history = re.findall(r'\[(.*?)\] Status → (.*?)\n', notes)
        events = []
        for ts_str, status in history:
            events.append({'timestamp': pd.to_datetime(ts_str, utc=True), 'status': status})
        events.sort(key=lambda x: x['timestamp'])
        first_event_timestamp = row['CreatedAt']
        initial_status = events[0]['status'] if events else row['Status']
        events.insert(0, {'timestamp': first_event_timestamp, 'status': initial_status})
        for i in range(len(events)):
            start_time = events[i]['timestamp']
            end_time = events[i+1]['timestamp'] if i + 1 < len(events) else now
            duration = (end_time - start_time).total_seconds() / (3600 * 24)
            duration_records.append({
                'SubmissionID': row['SubmissionID'], 'Name': row['Name'],
                'Status': events[i]['status'], 'Duration (Days)': duration
            })
    return pd.DataFrame(duration_records)

def kpi_bar(vdf):
    parts = [f"**Total Leads:** {len(vdf)}"]
    for s in STATUS_LIST:
        parts.append(f"**{s}:** {int((vdf['Status']==s).sum())}")
    st.markdown(" | ".join(parts))

def update_ticket_status(submission_id, widget_key):
    new_status = st.session_state[widget_key]
    row = st.session_state.df[st.session_state.df["SubmissionID"] == submission_id].iloc[0]
    old_status = row['Status']
    if old_status != new_status:
        payload = {}
        payload[f'submission[{config.FIELD_ID["status"]}]'] = new_status
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        history_note = f"[{timestamp}] Status → {new_status}"
        current_notes = row.get('Notes', '')
        new_notes = f"{history_note}\n{current_notes}".strip()
        payload[f'submission[{config.FIELD_ID["notes"]}]'] = new_notes
        if new_status in STATUS_TO_DATE_FIELD:
            date_field_key = STATUS_TO_DATE_FIELD[new_status]
            date_field_id = config.FIELD_ID[date_field_key]
            now_local = datetime.now()
            payload[f'submission[{date_field_id}][month]'] = now_local.month
            payload[f'submission[{date_field_id}][day]'] = now_local.day
            payload[f'submission[{date_field_id}][year]'] = now_local.year
        if update_jotform_submission(submission_id, payload):
            st.success(f"Moved ticket {submission_id} to {new_status}")
            refresh_data()

def update_ticket_details(sid, new_status, new_service, new_lost, new_notes, new_assigned_to):
    row = st.session_state.df[st.session_state.df["SubmissionID"] == sid].iloc[0]
    old_status = row['Status']
    payload = {
        f'submission[{config.FIELD_ID["service_type"]}]': new_service,
        f'submission[{config.FIELD_ID["lost_reason"]}]': new_lost,
        f'submission[{config.FIELD_ID["assigned_to"]}]': new_assigned_to,
    }
    if old_status != new_status:
        payload[f'submission[{config.FIELD_ID["status"]}]'] = new_status
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        history_note = f"[{timestamp}] Status → {new_status}"
        new_notes_with_history = f"{history_note}\n{new_notes}".strip()
        payload[f'submission[{config.FIELD_ID["notes"]}]'] = new_notes_with_history
        if new_status in STATUS_TO_DATE_FIELD:
            date_field_key = STATUS_TO_DATE_FIELD[new_status]
            date_field_id = config.FIELD_ID[date_field_key]
            now_local = datetime.now()
            payload[f'submission[{date_field_id}][month]'] = now_local.month
            payload[f'submission[{date_field_id}][day]'] = now_local.day
            payload[f'submission[{date_field_id}][year]'] = now_local.year
    else:
        payload[f'submission[{config.FIELD_ID["notes"]}]'] = new_notes
    if update_jotform_submission(sid, payload):
        st.success(f"Ticket {sid} changes saved.")
        refresh_data()
        
# --- AUTHENTICATION LOGIC ---

def check_password():
    """Simple login form."""
    st.image(LOGO, width=300)
    st.title("Sales Lead Tracker Login")
    
    username = st.text_input("Username", key="login_user")
    password = st.text_input("Password", type="password", key="login_pass")

    if st.button("Login"):
        if username in config.USERS and config.USERS[username]["password"] == password:
            st.session_state["authentication_status"] = True
            st.session_state["name"] = config.USERS[username]["name"]
            st.rerun()
        else:
            st.error("😕 Username not found or password incorrect")
    
# --- MAIN APP LAYOUT ---

def main_app():
    # Authentication check
    if not st.session_state.get("authentication_status"):
        check_password()
        return

    # Header with logout button
    left, mid, right = st.columns([1, 4, 1])
    with left:
        st.image(LOGO, use_container_width=True)
    with mid:
        st.title("Sales Lead Tracker")
        st.caption(f"Welcome, {st.session_state['name']}")
    with right:
        st.button("🔄 Refresh Data", on_click=refresh_data, use_container_width=True)
        if st.button("Logout", use_container_width=True):
            st.session_state["authentication_status"] = False
            st.rerun()

    st.session_state.df = get_jotform_submissions()
    is_empty = st.session_state.df.empty
    
    # NEW: Filter for "My Tickets" vs "All Tickets"
    view_mode = st.radio("View Tickets", ["My Tickets", "All Tickets"], horizontal=True)
    
    view_df = st.session_state.df
    if view_mode == "My Tickets":
        view_df = st.session_state.df[st.session_state.df['AssignedTo'] == st.session_state['name']]
    
    tab_pipe, tab_all, tab_add, tab_edit, tab_kpi = st.tabs(["🧩 Pipeline View","📋 All Tickets","➕ Add Ticket","✏️ Edit Ticket","📈 KPI"])
    
    if is_empty:
        st.warning("No tickets found. You can create the first one in the 'Add Ticket' tab.")

    with tab_pipe:
        st.subheader("Pipeline")
        if view_df.empty:
            st.info(f"There are no tickets to display in this view.")
        else:
            kpi_bar(view_df)
            cols = st.columns(len(STATUS_LIST))
            for i, status in enumerate(STATUS_LIST):
                with cols[i]:
                    status_count = int((view_df['Status']==status).sum())
                    st.markdown(f"<div style='background:{COLORS[status]};padding:8px;border-radius:8px;color:#111;font-weight:700'>{status} ({status_count})</div>", unsafe_allow_html=True)
                    subset = view_df[view_df["Status"]==status]
                    if not subset.empty:
                        for _, row in subset.sort_values("LastUpdated", ascending=False).iterrows():
                            expander_title = f"{row['Name']} · {row.get('AssignedTo', 'Unassigned')}"
                            with st.expander(expander_title, expanded=False):
                                st.caption(f"Updated: {row['LastUpdated'].strftime('%Y-%m-%d %H:%M')}")
                                st.write(row.get("Notes",""))
                                widget_key = f"mv_{row['SubmissionID']}"
                                st.selectbox("Move to", STATUS_LIST, index=STATUS_LIST.index(status), key=widget_key, on_change=update_ticket_status, args=(row['SubmissionID'], widget_key))

    with tab_all:
        st.subheader("All Tickets")
        if view_df.empty:
            st.info("There are no tickets to display.")
        else:
            st.dataframe(view_df[["SubmissionID","Name","AssignedTo","ContactSource","Status","TypeOfService","LostReason","CreatedAt","LastUpdated"]], use_container_width=True)

    with tab_add:
        st.subheader("Add Ticket")
        with st.form("add"):
            c1, c2 = st.columns(2)
            first = c1.text_input("First Name *")
            last = c2.text_input("Last Name *")
            source = c1.selectbox("Contact Source *", ["", "Email", "Phone Call", "Walk In", "Social Media", "In Person"])
            service = c2.selectbox("Type of Service *", [""] + SERVICE_TYPES)
            status = c1.selectbox("Status *", [""] + STATUS_LIST)
            assigned_to = c2.selectbox("Assigned To *", [""] + SALES_TEAM, index=SALES_TEAM.index(st.session_state['name']) + 1 if st.session_state['name'] in SALES_TEAM else 0)
            notes = st.text_area("Notes")
            lost = st.text_input("Lost Reason")
            
            if st.form_submit_button("Create Ticket"):
                miss = [n for n,vv in [("First Name",first),("Last Name",last),("Source",source),("Status",status),("Service",service),("Assigned To", assigned_to)] if not vv]
                if miss:
                    st.error("Missing: " + ", ".join(miss))
                else:
                    name_field_str = config.FIELD_ID.get('name_first', '')
                    name_id_match = re.search(r'\d+', name_field_str)
                    if name_id_match:
                        name_id = name_id_match.group()
                        payload = {
                            f'submission[{name_id}][first]': first, f'submission[{name_id}][last]': last,
                            f'submission[{str(config.FIELD_ID["source"])}]': source, f'submission[{str(config.FIELD_ID["status"])}]': status,
                            f'submission[{str(config.FIELD_ID["service_type"])}]': service, f'submission[{str(config.FIELD_ID["notes"])}]': notes,
                            f'submission[{str(config.FIELD_ID["lost_reason"])}]': lost,
                            f'submission[{str(config.FIELD_ID["assigned_to"])}]': assigned_to,
                        }
                        if status in STATUS_TO_DATE_FIELD:
                            date_field_key = STATUS_TO_DATE_FIELD[status]
                            date_field_id = config.FIELD_ID[date_field_key]
                            now_local = datetime.now()
                            payload[f'submission[{date_field_id}][month]'] = now_local.month
                            payload[f'submission[{date_field_id}][day]'] = now_local.day
                            payload[f'submission[{date_field_id}][year]'] = now_local.year
                        if add_jotform_submission(payload):
                            st.success("Ticket created successfully.")
                            refresh_data()

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
                    current_assignee = row.get("AssignedTo")
                    assignee_index = SALES_TEAM.index(current_assignee) if current_assignee in SALES_TEAM else 0
                    new_assigned_to = st.selectbox("Assigned To", SALES_TEAM, index=assignee_index, key=f"edit_assign_{sid}")
                    new_status = st.selectbox("Status", STATUS_LIST, index=STATUS_LIST.index(row["Status"]) if row["Status"] in STATUS_LIST else 0, key=f"edit_status_{sid}")
                with c2:
                    new_service = st.selectbox("Type of Service", SERVICE_TYPES, index=SERVICE_TYPES.index(row["TypeOfService"]) if row["TypeOfService"] in SERVICE_TYPES else 0, key=f"edit_service_{sid}")
                    new_lost = st.text_input("Lost Reason", value=row.get("LostReason") or "", key=f"edit_lost_{sid}")
                new_notes = st.text_area("Notes", value=row.get("Notes") or "", key=f"edit_notes_{sid}", help="A history entry will be automatically added if you change the status.")
                
                col_save, col_delete = st.columns([1,1])
                with col_save:
                    if st.button("Save Changes", use_container_width=True):
                        update_ticket_details(sid, new_status, new_service, new_lost, new_notes, new_assigned_to)
                # ... delete logic remains the same

    # KPI tab remains the same but now operates on the filtered view_df
    with tab_kpi:
        st.subheader("KPI & Lifecycle Dashboard")
        if view_df.empty:
            st.info("There is no data for the KPI dashboard in this view.")
        else:
            v = view_df.copy() # Use the filtered dataframe
            kpi_bar(v)
            # ... all other KPI calculations remain the same

if __name__ == "__main__":
    main_app()
