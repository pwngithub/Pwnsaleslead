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
                    "ContactSource": get_ans(config.FIELD_ID['source']),
                    "Status": get_ans(config.FIELD_ID['status']),
                    "TypeOfService": get_ans(config.FIELD_ID['service_type']),
                    "LostReason": get_ans(config.FIELD_ID['lost_reason']),
                    "Notes": get_ans(config.FIELD_ID['notes']),
                    # FIX: Ensure all datetimes are timezone-aware (UTC) upon creation
                    "CreatedAt": pd.to_datetime(sub.get('created_at'), utc=True),
                    "LastUpdated": pd.to_datetime(sub.get('updated_at'), utc=True) if sub.get('updated_at') else pd.to_datetime(sub.get('created_at'), utc=True),
                    "SurveyScheduledDate": get_date_ans(config.FIELD_ID['survey_scheduled_date']),
                    "InstalledDate": get_date_ans(config.FIELD_ID['installed_date']),
                })

        df = pd.DataFrame(records)
        for col in ["SubmissionID", "Name", "Status", "CreatedAt"]:
            if col not in df.columns:
                df[col] = pd.Series(dtype='object' if col != "CreatedAt" else 'datetime64[ns, UTC]')
        return df

    except requests.exceptions.RequestException as e:
        st.error(f"Failed to connect to JotForm API: {e}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"An error occurred while processing JotForm data: {e}")
        return pd.DataFrame()

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

# --- CALLBACK & HELPER FUNCTIONS ---

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
            # FIX: Ensure timestamps parsed from notes are treated as UTC
            events.append({'timestamp': pd.to_datetime(ts_str, utc=True), 'status': status})
        
        events.sort(key=lambda x: x['timestamp'])

        # The 'CreatedAt' timestamp is now guaranteed to be UTC from get_jotform_submissions
        first_event_timestamp = row['CreatedAt']
        
        # Determine the status at the time of creation
        initial_status = events[0]['status'] if events else row['Status']
        events.insert(0, {'timestamp': first_event_timestamp, 'status': initial_status})
        
        # Calculate duration between events
        for i in range(len(events)):
            start_time = events[i]['timestamp']
            end_time = events[i+1]['timestamp'] if i + 1 < len(events) else now
            
            # This calculation is now safe because all datetimes are timezone-aware
            duration = (end_time - start_time).total_seconds() / (3600 * 24)
            
            duration_records.append({
                'SubmissionID': row['SubmissionID'],
                'Name': row['Name'],
                'Status': events[i]['status'],
                'Duration (Days)': duration
            })
            
    return pd.DataFrame(duration_records)

def update_ticket_status(submission_id, widget_key):
    new_status = st.session_state[widget_key]
    row = st.session_state.df[st.session_state.df["SubmissionID"] == submission_id].iloc[0]
    old_status = row['Status']
    
    if old_status != new_status:
        payload = {}
        payload[f'submission[{config.FIELD_ID["status"]}]'] = new_status
        # FIX: Generate new timestamps in UTC
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        history_note = f"[{timestamp}] Status → {new_status}"
        current_notes = row.get('Notes', '')
        new_notes = f"{history_note}\n{current_notes}".strip()
        payload[f'submission[{config.FIELD_ID["notes"]}]'] = new_notes
        if new_status in STATUS_TO_DATE_FIELD:
            date_field_key = STATUS_TO_DATE_FIELD[new_status]
            date_field_id = config.FIELD_ID[date_field_key]
            # Jotform date fields don't have timezones, so local time is fine here
            now_local = datetime.now()
            payload[f'submission[{date_field_id}][month]'] = now_local.month
            payload[f'submission[{date_field_id}][day]'] = now_local.day
            payload[f'submission[{date_field_id}][year]'] = now_local.year
        if update_jotform_submission(submission_id, payload):
            st.success(f"Moved ticket {submission_id} to {new_status}")
            refresh_data()

def update_ticket_details(sid, new_status, new_service, new_lost, new_notes):
    row = st.session_state.df[st.session_state.df["SubmissionID"] == sid].iloc[0]
    old_status = row['Status']
    payload = {
        f'submission[{config.FIELD_ID["service_type"]}]': new_service,
        f'submission[{config.FIELD_ID["lost_reason"]}]': new_lost,
    }
    if old_status != new_status:
        payload[f'submission[{config.FIELD_ID["status"]}]'] = new_status
        # FIX: Generate new timestamps in UTC
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
        
def kpi_bar(vdf):
    parts = [f"**Total Leads:** {len(vdf)}"]
    for s in STATUS_LIST:
        parts.append(f"**{s}:** {int((vdf['Status']==s).sum())}")
    st.markdown(" | ".join(parts))

# --- MAIN APP LAYOUT ---

def main_app():
    left, mid, right = st.columns([1, 4, 1])
    with left:
        st.image(LOGO, use_container_width=True)
    with mid:
        st.title("Sales Lead Tracker — Pipeline")
    with right:
        st.button("🔄 Refresh Data", on_click=refresh_data, use_container_width=True)
    st.session_state.df = get_jotform_submissions()
    is_empty = st.session_state.df.empty
    tab_pipe, tab_all, tab_add, tab_edit, tab_kpi = st.tabs(["🧩 Pipeline View","📋 All Tickets","➕ Add Ticket","✏️ Edit Ticket","📈 KPI"])
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
                                st.selectbox("Move to", STATUS_LIST, index=STATUS_LIST.index(status), key=widget_key, on_change=update_ticket_status, args=(row['SubmissionID'], widget_key))
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
                    name_field_str = config.FIELD_ID.get('name_first', '')
                    name_id_match = re.search(r'\d+', name_field_str)
                    if name_id_match:
                        name_id = name_id_match.group()
                        payload = {
                            f'submission[{name_id}][first]': first, f'submission[{name_id}][last]': last,
                            f'submission[{str(config.FIELD_ID["source"])}]': source, f'submission[{str(config.FIELD_ID["status"])}]': status,
                            f'submission[{str(config.FIELD_ID["service_type"])}]': service, f'submission[{str(config.FIELD_ID["notes"])}]': notes,
                            f'submission[{str(config.FIELD_ID["lost_reason"])}]': lost,
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
                    new_status = st.selectbox("Status", STATUS_LIST, index=STATUS_LIST.index(row["Status"]) if row["Status"] in STATUS_LIST else 0, key=f"edit_status_{sid}")
                    new_service = st.selectbox("Type of Service", SERVICE_TYPES, index=SERVICE_TYPES.index(row["TypeOfService"]) if row["TypeOfService"] in SERVICE_TYPES else 0, key=f"edit_service_{sid}")
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
        st.subheader("KPI & Lifecycle Dashboard")
        if is_empty:
            st.info("There is no data for the KPI dashboard.")
        else:
            v = st.session_state.df.copy()
            kpi_bar(v)
            st.markdown("---")

            st.subheader("⏱️ Process Duration")
            installed_tickets = v[v['InstalledDate'].notna() & v['SurveyScheduledDate'].notna()].copy()
            if not installed_tickets.empty:
                installed_tickets['Duration'] = (installed_tickets['InstalledDate'] - installed_tickets['SurveyScheduledDate']).dt.days
                avg_duration = installed_tickets['Duration'].mean()
                st.metric("Average Time from Survey Scheduled to Installed", f"{avg_duration:.1f} Days")
                with st.expander("Show Details"):
                    st.dataframe(installed_tickets[['Name', 'SurveyScheduledDate', 'InstalledDate', 'Duration']], use_container_width=True)
            else:
                st.info("No tickets have completed the full 'Survey Scheduled' to 'Installed' process yet.")

            st.markdown("---")
            
            st.subheader("📊 Average Time in Each Status")
            duration_df = calculate_status_durations(v)
            if not duration_df.empty:
                avg_status_duration = duration_df.groupby('Status')['Duration (Days)'].mean().reset_index()
                avg_status_duration['Duration (Days)'] = avg_status_duration['Duration (Days)'].round(1)
                st.dataframe(avg_status_duration.sort_values("Duration (Days)", ascending=False), use_container_width=True)
            else:
                st.info("Not enough status change history to calculate durations.")

            st.markdown("---")

            st.subheader("⏳ Age of Open Tickets")
            open_tickets = v[~v['Status'].isin(['Installed', 'Lost'])].copy()
            if not open_tickets.empty:
                now_utc = datetime.now(timezone.utc)
                open_tickets['Age (Days)'] = (now_utc - open_tickets['CreatedAt']).dt.days
                st.dataframe(open_tickets[['Name', 'Status', 'Age (Days)']].sort_values('Age (Days)', ascending=False), use_container_width=True)
            else:
                st.info("There are no open tickets.")

    st.markdown("<hr/>", unsafe_allow_html=True)
    st.caption("Powered by Pioneer Broadband | Internal Use Only")

if __name__ == "__main__":
    if 'confirm_delete' not in st.session_state:
        st.session_state['confirm_delete'] = None
    main_app()
