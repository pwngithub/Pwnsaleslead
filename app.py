# Pioneer Sales Lead App – v19.10.35
# Live JotForm integration, KPI, auto-dating, and history
import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta, date
import requests
import config # Import the config file
import re
import plotly.express as px # NEW: Import Plotly

# --- CONSTANTS ---
st.set_page_config(page_title="Pioneer Sales Lead App", page_icon="📶", layout="wide")

LOGO = "https://images.squarespace-cdn.com/content/v1/651eb4433b13e72c1034f375/369c5df0-5363-4827-b041-1add0367f447/PBB+long+logo.png?format=1500w"

STATUS_LIST = config.STATUS_LIST
SERVICE_TYPES = config.SERVICE_TYPES
SALES_TEAM = [details["name"] for details in config.USERS.values()]

COLORS = {
    "Survey Scheduled": "#3b82f6", "Survey Completed": "#fbbf24", "Scheduled": "#fb923c",
    "Installed": "#22c55e", "Waiting on Customer": "#a855f7", "Lost": "#ef4444"
}

STATUS_TO_DATE_FIELD = {
    "Survey Scheduled": "survey_scheduled_date", "Survey Completed": "survey_completed_date",
    "Scheduled": "scheduled_date", "Installed": "installed_date",
    "Waiting on Customer": "waiting_on_customer_date",
}
# -----------------

# --- JOTFORM API FUNCTIONS and HELPERS (No changes in this section) ---
@st.cache_data(ttl=300)
def get_jotform_submissions():
    try:
        url = f"https://api.jotform.com/form/{config.FORM_ID}/submissions?apiKey={config.API_KEY}&limit=1000"
        response = requests.get(url); response.raise_for_status()
        data = response.json().get('content', [])
        records = []
        for sub in data:
            if sub.get('status') == 'ACTIVE':
                answers = sub.get('answers', {})
                def get_ans(qid):
                    ans_dict = answers.get(str(qid)); return ans_dict.get('answer', '') if ans_dict else ''
                def get_date_ans(qid):
                    date_ans = get_ans(qid)
                    if isinstance(date_ans, dict):
                        date_str = f"{date_ans.get('year')}-{date_ans.get('month')}-{date_ans.get('day')}"
                        return pd.to_datetime(date_str, errors='coerce')
                    return pd.to_datetime(date_ans, errors='coerce')
                name_field_str = config.FIELD_ID.get('name_first', ''); name_id_match = re.search(r'\d+', name_field_str)
                first_name, last_name = '', ''
                if name_id_match:
                    name_id = name_id_match.group(); name_ans = get_ans(name_id)
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
                    "NextActionDate": get_date_ans(config.FIELD_ID['next_action_date']),
                    "NextAction": get_ans(config.FIELD_ID['next_action']),
                })
        df = pd.DataFrame(records)
        for col in ["SubmissionID", "Name", "Status", "CreatedAt", "AssignedTo", "NextActionDate"]:
            if col not in df.columns:
                df[col] = pd.Series(dtype='object' if 'Date' not in col else 'datetime64[ns]')
        return df
    except Exception as e:
        st.error(f"An error occurred while processing JotForm data: {e}"); return pd.DataFrame()
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
def update_ticket_details(sid, new_status, new_service, new_lost, new_notes, new_assigned_to, next_action_date, next_action):
    row = st.session_state.df[st.session_state.df["SubmissionID"] == sid].iloc[0]
    payload = {
        f'submission[{config.FIELD_ID["service_type"]}]': new_service,
        f'submission[{config.FIELD_ID["lost_reason"]}]': new_lost,
        f'submission[{config.FIELD_ID["assigned_to"]}]': new_assigned_to,
        f'submission[{config.FIELD_ID["next_action"]}]': next_action,
    }
    if next_action_date:
        payload[f'submission[{config.FIELD_ID["next_action_date"]}][month]'] = next_action_date.month
        payload[f'submission[{config.FIELD_ID["next_action_date"]}][day]'] = next_action_date.day
        payload[f'submission[{config.FIELD_ID["next_action_date"]}][year]'] = next_action_date.year
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
def check_password():
    st.image(LOGO, width=300); st.title("Sales Lead Tracker Login")
    username = st.text_input("Username", key="login_user"); password = st.text_input("Password", type="password", key="login_pass")
    if st.button("Login"):
        if username in config.USERS and config.USERS[username]["password"] == password:
            st.session_state.update({"authentication_status": True, "name": config.USERS[username]["name"], "role": config.USERS[username]["role"]}); st.rerun()
        else:
            st.error("😕 Username not found or password incorrect")
    
# --- MAIN APP LAYOUT ---
def main_app():
    if not st.session_state.get("authentication_status"):
        check_password(); return

    left, mid, right = st.columns([1, 4, 1]);
    with left: st.image(LOGO, use_container_width=True)
    with mid: st.title("Sales Lead Tracker"); st.caption(f"Welcome, {st.session_state['name']} (Role: {st.session_state['role']})")
    with right:
        st.button("🔄 Refresh Data", on_click=refresh_data, use_container_width=True)
        if st.button("Logout", use_container_width=True):
            st.session_state["authentication_status"] = False; st.rerun()

    st.session_state.df = get_jotform_submissions()
    is_empty = st.session_state.df.empty
    view_mode = st.radio("View Tickets", ["My Tickets", "All Tickets"], index=1, horizontal=True)
    view_df = st.session_state.df
    if view_mode == "My Tickets":
        view_df = st.session_state.df[st.session_state.df['AssignedTo'] == st.session_state['name']]
    
    tab_tasks, tab_pipe, tab_all, tab_add, tab_edit, tab_kpi = st.tabs(["✅ Tasks", "🧩 Pipeline View","📋 All Tickets","➕ Add Ticket","✏️ Edit Ticket","📈 KPI"])
    
    if is_empty and view_mode == "All Tickets":
        st.warning("No tickets found. You can create the first one in the 'Add Ticket' tab.")

    with tab_tasks:
        st.subheader(f"Tasks for {view_mode}")
        tasks_df = view_df[view_df['NextActionDate'].notna()].copy()
        if tasks_df.empty:
            st.info("No tickets with a 'Next Action Date' found in this view.")
        else:
            today = pd.to_datetime(date.today())
            tasks_df['DaysUntil'] = (tasks_df['NextActionDate'] - today).dt.days
            overdue = tasks_df[tasks_df['DaysUntil'] < 0]
            due_today = tasks_df[tasks_df['DaysUntil'] == 0]
            upcoming = tasks_df[tasks_df['DaysUntil'] > 0]
            st.error(f"Overdue Tasks ({len(overdue)})", icon="🔥")
            if not overdue.empty: st.dataframe(overdue[['Name', 'AssignedTo', 'NextActionDate', 'NextAction']].sort_values('NextActionDate'), use_container_width=True)
            st.warning(f"Tasks Due Today ({len(due_today)})", icon="❗")
            if not due_today.empty: st.dataframe(due_today[['Name', 'AssignedTo', 'NextActionDate', 'NextAction']], use_container_width=True)
            st.success(f"Upcoming Tasks ({len(upcoming)})", icon="🗓️")
            if not upcoming.empty: st.dataframe(upcoming[['Name', 'AssignedTo', 'NextActionDate', 'NextAction']].sort_values('NextActionDate'), use_container_width=True)

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
                            can_edit = (st.session_state['role'] == 'admin') or (row['AssignedTo'] == st.session_state['name'])
                            lock_icon = "" if can_edit else "🔒"
                            expander_title = f"{row['Name']} · {row.get('AssignedTo', 'Unassigned')} {lock_icon}"
                            with st.expander(expander_title, expanded=False):
                                st.caption(f"Updated: {row['LastUpdated'].strftime('%Y-%m-%d %H:%M')}")
                                st.write(row.get("Notes",""))
                                widget_key = f"mv_{row['SubmissionID']}"
                                st.selectbox("Move to", STATUS_LIST, index=STATUS_LIST.index(status), key=widget_key, on_change=update_ticket_status, args=(row['SubmissionID'], widget_key), disabled=not can_edit)

    with tab_all:
        st.subheader("All Tickets")
        if view_df.empty:
            st.info("There are no tickets to display.")
        else:
            st.dataframe(view_df[["SubmissionID","Name","AssignedTo","ContactSource","Status","TypeOfService","NextActionDate", "LostReason","CreatedAt"]], use_container_width=True)
            csv = view_df.to_csv(index=False).encode('utf-8')
            st.download_button(label="📥 Download as CSV", data=csv, file_name=f"sales_leads_{datetime.now().strftime('%Y-%m-%d')}.csv", mime="text/csv")

    with tab_add:
        st.subheader("Add Ticket")
        with st.form("add"):
            c1, c2 = st.columns(2);
            first = c1.text_input("First Name *"); last = c2.text_input("Last Name *")
            source = c1.selectbox("Contact Source *", ["", "Email", "Phone Call", "Walk In", "Social Media", "In Person"])
            service = c2.selectbox("Type of Service *", [""] + SERVICE_TYPES)
            status = c1.selectbox("Status *", [""] + STATUS_LIST)
            assigned_to = c2.selectbox("Assigned To *", [""] + SALES_TEAM, index=SALES_TEAM.index(st.session_state['name']) + 1 if st.session_state['name'] in SALES_TEAM else 0)
            notes = st.text_area("Notes", height=100)
            st.markdown("##### Task / Follow-up")
            c3, c4 = st.columns(2)
            next_action_date = c3.date_input("Next Action Date", value=None)
            next_action = c4.text_area("Next Action", height=100)
            lost = st.text_input("Lost Reason")
            if st.form_submit_button("Create Ticket"):
                miss = [n for n,vv in [("First Name",first),("Last Name",last),("Source",source),("Status",status),("Service",service),("Assigned To", assigned_to)] if not vv]
                if miss: st.error("Missing: " + ", ".join(miss))
                else:
                    name_field_str = config.FIELD_ID.get('name_first', ''); name_id_match = re.search(r'\d+', name_field_str)
                    if name_id_match:
                        name_id = name_id_match.group()
                        payload = {
                            f'submission[{name_id}][first]': first, f'submission[{name_id}][last]': last,
                            f'submission[{str(config.FIELD_ID["source"])}]': source, f'submission[{str(config.FIELD_ID["status"])}]': status,
                            f'submission[{str(config.FIELD_ID["service_type"])}]': service, f'submission[{str(config.FIELD_ID["notes"])}]': notes,
                            f'submission[{str(config.FIELD_ID["lost_reason"])}]': lost, f'submission[{str(config.FIELD_ID["assigned_to"])}]': assigned_to,
                            f'submission[{str(config.FIELD_ID["next_action"])}]': next_action,
                        }
                        if next_action_date:
                            payload.update({
                                f'submission[{config.FIELD_ID["next_action_date"]}][month]': next_action_date.month,
                                f'submission[{config.FIELD_ID["next_action_date"]}][day]': next_action_date.day,
                                f'submission[{config.FIELD_ID["next_action_date"]}][year]': next_action_date.year,
                            })
                        if status in STATUS_TO_DATE_FIELD:
                            date_field_key = STATUS_TO_DATE_FIELD[status]; date_field_id = config.FIELD_ID[date_field_key]; now_local = datetime.now()
                            payload.update({f'submission[{date_field_id}][month]': now_local.month, f'submission[{date_field_id}][day]': now_local.day, f'submission[{date_field_id}][year]': now_local.year})
                        if add_jotform_submission(payload):
                            st.success("Ticket created successfully."); refresh_data()
    
    with tab_edit:
        st.subheader("Edit Ticket")
        if is_empty: st.info("There are no tickets to edit.")
        else:
            opts = {f"{r['Name']} · {r.get('AssignedTo', 'Unassigned')} ({r['SubmissionID']})": r["SubmissionID"] for _, r in st.session_state.df.sort_values("Name").iterrows()}
            sel_key = st.selectbox("Select a Ticket to Edit", list(opts.keys()), key="edit_sel")
            if sel_key:
                sid = opts[sel_key]
                row = st.session_state.df[st.session_state.df["SubmissionID"]==sid].iloc[0]
                can_edit = (st.session_state['role'] == 'admin') or (row['AssignedTo'] == st.session_state['name'])
                if not can_edit: st.warning("🔒 You do not have permission to edit this ticket because it is not assigned to you.", icon="⚠️")
                c1,c2 = st.columns(2)
                with c1:
                    current_assignee = row.get("AssignedTo"); assignee_index = SALES_TEAM.index(current_assignee) if current_assignee in SALES_TEAM else 0
                    new_assigned_to = st.selectbox("Assigned To", SALES_TEAM, index=assignee_index, key=f"edit_assign_{sid}", disabled=not can_edit)
                    new_status = st.selectbox("Status", STATUS_LIST, index=STATUS_LIST.index(row["Status"]) if row["Status"] in STATUS_LIST else 0, key=f"edit_status_{sid}", disabled=not can_edit)
                with c2:
                    new_service = st.selectbox("Type of Service", SERVICE_TYPES, index=SERVICE_TYPES.index(row["TypeOfService"]) if row["TypeOfService"] in SERVICE_TYPES else 0, key=f"edit_service_{sid}", disabled=not can_edit)
                    new_lost = st.text_input("Lost Reason", value=row.get("LostReason") or "", key=f"edit_lost_{sid}", disabled=not can_edit)
                st.markdown("##### Task / Follow-up")
                c3, c4 = st.columns(2)
                next_action_date_val = row['NextActionDate'].to_pydatetime().date() if pd.notna(row['NextActionDate']) else None
                new_next_action_date = c3.date_input("Next Action Date", value=next_action_date_val, key=f"edit_nad_{sid}", disabled=not can_edit)
                new_next_action = c4.text_area("Next Action", value=row.get("NextAction") or "", key=f"edit_na_{sid}", disabled=not can_edit, height=100)
                new_notes = st.text_area("Notes", value=row.get("Notes") or "", key=f"edit_notes_{sid}", help="A history entry will be automatically added if you change the status.", disabled=not can_edit, height=100)
                col_save, col_delete = st.columns([1,1])
                with col_save:
                    if st.button("Save Changes", use_container_width=True, disabled=not can_edit):
                        update_ticket_details(sid, new_status, new_service, new_lost, new_notes, new_assigned_to, new_next_action_date, new_next_action)
                with col_delete:
                    if st.button("❌ Delete Ticket", type="primary", use_container_width=True, disabled=not can_edit):
                        st.session_state['confirm_delete'] = sid
                if st.session_state.get('confirm_delete') == sid:
                    st.warning(f"Are you sure you want to delete ticket for {row['Name']} ({sid})?")
                    c_yes, c_no = st.columns(2)
                    with c_yes:
                        if st.button("Yes, Delete Permanently", type="primary", use_container_width=True):
                            if delete_jotform_submission(sid):
                                st.success(f"Ticket {sid} has been permanently deleted."); st.session_state['confirm_delete'] = None; refresh_data()
                    with c_no:
                        if st.button("No, Keep It", use_container_width=True):
                            st.session_state['confirm_delete'] = None

    with tab_kpi:
        st.subheader("KPI & Lifecycle Dashboard (All Tickets)")
        if is_empty: st.info("There is no data for the KPI dashboard.")
        else:
            st.markdown("#### Filter by Date Created")
            c1, c2 = st.columns(2)
            start_date = c1.date_input("Start Date", value=datetime.now() - timedelta(days=90)); end_date = c2.date_input("End Date", value=datetime.now())
            start_datetime = pd.to_datetime(start_date).tz_localize('UTC'); end_datetime = (pd.to_datetime(end_date) + timedelta(days=1)).tz_localize('UTC')
            v = st.session_state.df[(st.session_state.df['CreatedAt'] >= start_datetime) & (st.session_state.df['CreatedAt'] < end_datetime)].copy()
            st.markdown("---")
            if v.empty: st.warning("No tickets found in the selected date range.")
            else:
                kpi_bar(v); st.markdown("---")
                
                # --- KPI Metrics ---
                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("📈 Conversion Rate")
                    installed_count = (v['Status'] == 'Installed').sum(); lost_count = (v['Status'] == 'Lost').sum()
                    total_resolved = installed_count + lost_count
                    if total_resolved > 0:
                        conversion_rate = (installed_count / total_resolved) * 100
                        st.metric("Lead Conversion Rate", f"{conversion_rate:.1f}%", help=f"Based on {total_resolved} resolved tickets.")
                    else: st.info("No tickets were resolved in this period.")
                with col2:
                    st.subheader("⏱️ Process Duration")
                    installed_tickets = v[v['InstalledDate'].notna() & v['SurveyScheduledDate'].notna()].copy()
                    if not installed_tickets.empty:
                        installed_tickets['Duration'] = (installed_tickets['InstalledDate'] - installed_tickets['SurveyScheduledDate']).dt.days
                        avg_duration = installed_tickets['Duration'].mean()
                        st.metric("Avg. Survey to Install", f"{avg_duration:.1f} Days")
                    else: st.info("No tickets completed the full process in this period.")
                st.markdown("---")

                # --- NEW: Interactive Charts ---
                st.subheader("📊 Visual Analytics")
                c1, c2 = st.columns(2)
                with c1:
                    status_counts = v['Status'].value_counts().reset_index()
                    status_counts.columns = ['Status', 'Count']
                    fig_status = px.bar(status_counts, x='Count', y='Status', orientation='h', title='Leads by Current Status', color_discrete_sequence=px.colors.qualitative.Pastel)
                    st.plotly_chart(fig_status, use_container_width=True)
                with c2:
                    source_counts = v['ContactSource'].value_counts().reset_index()
                    source_counts.columns = ['ContactSource', 'Count']
                    fig_source = px.pie(source_counts, names='ContactSource', values='Count', title='Leads by Contact Source', color_discrete_sequence=px.colors.qualitative.Pastel)
                    st.plotly_chart(fig_source, use_container_width=True)

                st.markdown("---")
                st.subheader("⏳ Leads Created Over Time")
                leads_over_time = v.set_index('CreatedAt').resample('D').size().reset_index(name='Count')
                fig_time = px.line(leads_over_time, x='CreatedAt', y='Count', title='Daily Lead Creation')
                st.plotly_chart(fig_time, use_container_width=True)


    st.markdown("<hr/>", unsafe_allow_html=True)
    st.caption("Powered by Pioneer Broadband | Internal Use Only")

if __name__ == "__main__":
    main_app()
