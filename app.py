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
                    return ans_dict.get('answer', '') if ans_dict else ''
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
                    "SubmissionID": sub.get('id'), "Name": f"{first_name} {last_name}".strip(),
                    "AssignedTo": get_ans(config.FIELD_ID['assigned_to']), "ContactSource": get_ans(config.FIELD_ID['source']),
                    "Status": get_ans(config.FIELD_ID['status']), "TypeOfService": get_ans(config.FIELD_ID['service_type']),
                    "LostReason": get_ans(config.FIELD_ID['lost_reason']), "Notes": get_ans(config.FIELD_ID['notes']),
                    "CreatedAt": pd.to_datetime(sub.get('created_at'), utc=True),
                    "LastUpdated": pd.to_datetime(sub.get('updated_at'), utc=True) if sub.get('updated_at') else pd.to_datetime(sub.get('created_at'), utc=True),
                    "SurveyScheduledDate": get_date_ans(config.FIELD_ID['survey_scheduled_date']),
                    "InstalledDate": get_date_ans(config.FIELD_ID['installed_date']),
                })
        df = pd.DataFrame(records)
        for col in ["SubmissionID", "Name", "Status", "CreatedAt", "AssignedTo"]:
            if col not in df.columns:
                df[col] = pd.Series(dtype='object' if col != "CreatedAt" else 'datetime64[ns, UTC]')
        return df
    except Exception as e:
        st.error(f"An error occurred while processing JotForm data: {e}")
        return pd.DataFrame()
def update_jotform_submission(submission_id, payload):
    try:
        url = f"https://api.jotform.com/submission/{submission_id}?apiKey={config.API_KEY}"
        response = requests.post(url, data=payload); response.raise_for_status(); return True
    except requests.exceptions.RequestException as e:
        st.error(f"Error updating ticket {submission_id}: {e}"); return False
def add_jotform_submission(payload):
    try:
        url = f"https://api.jotform.com/form/{config.FORM_ID}/submissions?apiKey={config.API_KEY}"
        response = requests.post(url, data=payload); response.raise_for_status(); return True
    except requests.exceptions.RequestException as e:
        st.error(f"Error creating new ticket: {e}"); return False
def delete_jotform_submission(submission_id):
    try:
        url = f"https://api.jotform.com/submission/{submission_id}?apiKey={config.API_KEY}"
        response = requests.delete(url); response.raise_for_status(); return True
    except requests.exceptions.RequestException as e:
        st.error(f"Error deleting ticket {submission_id}: {e}"); return False

# --- CALLBACK & HELPER FUNCTIONS ---
def refresh_data():
    st.cache_data.clear(); st.rerun()
def calculate_status_durations(df):
    duration_records = []; now = datetime.now(timezone.utc)
    for _, row in df.iterrows():
        notes = row.get('Notes', '') or ''; history = re.findall(r'\[(.*?)\] Status → (.*?)\n', notes)
        events = [{'timestamp': pd.to_datetime(ts_str, utc=True), 'status': status} for ts_str, status in history]
        events.sort(key=lambda x: x['timestamp'])
        first_event_timestamp = row['CreatedAt']
        initial_status = events[0]['status'] if events else row['Status']
        events.insert(0, {'timestamp': first_event_timestamp, 'status': initial_status})
        for i in range(len(events)):
            start_time = events[i]['timestamp']; end_time = events[i+1]['timestamp'] if i + 1 < len(events) else now
            duration = (end_time - start_time).total_seconds() / (3600 * 24)
            duration_records.append({'SubmissionID': row['SubmissionID'], 'Name': row['Name'], 'Status': events[i]['status'], 'Duration (Days)': duration})
    return pd.DataFrame(duration_records)
def kpi_bar(vdf):
    parts = [f"**Total Leads:** {len(vdf)}"]
    for s in STATUS_LIST: parts.append(f"**{s}:** {int((vdf['Status']==s).sum())}")
    st.markdown(" | ".join(parts))
def update_ticket_status(submission_id, widget_key):
    new_status = st.session_state[widget_key]
    row = st.session_state.df[st.session_state.df["SubmissionID"] == submission_id].iloc[0]
    if row['Status'] != new_status:
        payload = {f'submission[{config.FIELD_ID["status"]}]': new_status}
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        history_note = f"[{timestamp}] Status → {new_status}"
        new_notes = f"{history_note}\n{row.get('Notes', '')}".strip()
        payload[f'submission[{config.FIELD_ID["notes"]}]'] = new_notes
        if new_status in STATUS_TO_DATE_FIELD:
            date_field_key = STATUS_TO_DATE_FIELD[new_status]; date_field_id = config.FIELD_ID[date_field_key]; now_local = datetime.now()
            payload.update({f'submission[{date_field_id}][month]': now_local.month, f'submission[{date_field_id}][day]': now_local.day, f'submission[{date_field_id}][year]': now_local.year})
        if update_jotform_submission(submission_id, payload):
            st.success(f"Moved ticket {submission_id} to {new_status}"); refresh_data()
def update_ticket_details(sid, new_status, new_service, new_lost, new_notes, new_assigned_to):
    row = st.session_state.df[st.session_state.df["SubmissionID"] == sid].iloc[0]
    payload = {
        f'submission[{config.FIELD_ID["service_type"]}]': new_service,
        f'submission[{config.FIELD_ID["lost_reason"]}]': new_lost,
        f'submission[{config.FIELD_ID["assigned_to"]}]': new_assigned_to,
    }
    if row['Status'] != new_status:
        payload[f'submission[{config.FIELD_ID["status"]}]'] = new_status
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        history_note = f"[{timestamp}] Status → {new_status}"
        payload[f'submission[{config.FIELD_ID["notes"]}]'] = f"{history_note}\n{new_notes}".strip()
        if new_status in STATUS_TO_DATE_FIELD:
            date_field_key = STATUS_TO_DATE_FIELD[new_status]; date_field_id = config.FIELD_ID[date_field_key]; now_local = datetime.now()
            payload.update({f'submission[{date_field_id}][month]': now_local.month, f'submission[{date_field_id}][day]': now_local.day, f'submission[{date_field_id}][year]': now_local.year})
    else:
        payload[f'submission[{config.FIELD_ID["notes"]}]'] = new_notes
    if update_jotform_submission(sid, payload):
        st.success(f"Ticket {sid} changes saved."); refresh_data()

# --- AUTHENTICATION LOGIC ---
def check_password():
    st.image(LOGO, width=300)
    st.title("Sales Lead Tracker Login")
    username = st.text_input("Username", key="login_user")
    password = st.text_input("Password", type="password", key="login_pass")
    if st.button("Login"):
        if username in config.USERS and config.USERS[username]["password"] == password:
            st.session_state["authentication_status"] = True
            st.session_state["name"] = config.USERS[username]["name"]
            st.session_state["role"] = config.USERS[username]["role"]
            st.rerun()
        else:
            st.error("😕 Username not found or password incorrect")
    
# --- MAIN APP LAYOUT ---
def main_app():
    if not st.session_state.get("authentication_status"):
        check_password(); return

    left, mid, right = st.columns([1, 4, 1])
    with left:
        st.image(LOGO, use_container_width=True)
    with mid:
        st.title("Sales Lead Tracker")
        st.caption(f"Welcome, {st.session_state['name']} (Role: {st.session_state['role']})")
    with right:
        st.button("🔄 Refresh Data", on_click=refresh_data, use_container_width=True)
        if st.button("Logout", use_container_width=True):
            st.session_state["authentication_status"] = False
            st.rerun()

    st.session_state.df = get_jotform_submissions()
    is_empty = st.session_state.df.empty
    
    view_mode = st.radio("View Tickets", ["My Tickets", "All Tickets"], index=1, horizontal=True)
    
    view_df = st.session_state.df
    if view_mode == "My Tickets":
        view_df = st.session_state.df[st.session_state.df['AssignedTo'] == st.session_state['name']]
    
    tab_pipe, tab_all, tab_add, tab_edit, tab_kpi = st.tabs(["🧩 Pipeline View","📋 All Tickets","➕ Add Ticket","✏️ Edit Ticket","📈 KPI"])
    
    if is_empty and view_mode == "All Tickets":
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
                            can_edit = (st.session_state['role'] == 'admin') or (row['AssignedTo'] == st.session_state['
