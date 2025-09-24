
import streamlit as st
import pandas as pd
import requests
import os, json
from datetime import datetime
import plotly.express as px
from config import API_KEY, FORM_ID, FIELD_ID, BLOCKED_WORDS as DEFAULT_BLOCKED

JOTFORM_API = "https://api.jotform.com"
SETTINGS_FILE = "settings.json"

STATUS_LIST = ["Survey Scheduled","Survey Completed","Scheduled","Installed","Waiting on Customer","Lost"]
STATUS_TO_FIELD = {
    "Survey Scheduled": FIELD_ID["survey_scheduled"],
    "Survey Completed": FIELD_ID["survey_completed"],
    "Scheduled": FIELD_ID["scheduled"],
    "Installed": FIELD_ID["installed"],
    "Waiting on Customer": FIELD_ID["waiting_on_customer"]
}

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                return json.load(f)
        except:
            return {"blocked_words": DEFAULT_BLOCKED, "reminder_days": 3}
    return {"blocked_words": DEFAULT_BLOCKED, "reminder_days": 3}

def save_settings(settings: dict):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f)

def fetch_jotform_data():
    url = f"{JOTFORM_API}/form/{FORM_ID}/submissions?apikey={API_KEY}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    subs = r.json().get("content", [])
    records = []
    for sub in subs:
        ans = sub.get("answers") or {}
        if not isinstance(ans, dict):
            ans = {}
        name_raw = ans.get(str(FIELD_ID["name"]), {}).get("answer", {})
        if isinstance(name_raw, dict):
            first = name_raw.get("first", "").strip()
            last = name_raw.get("last", "").strip()
            name_val = f"{first} {last}".strip()
        elif isinstance(name_raw, str):
            name_val = name_raw.strip()
        else:
            name_val = None

        def get_ts(fid):
            val = ans.get(str(fid), {}).get("answer")
            return val if isinstance(val, str) else None

        records.append({
            "SubmissionID": sub.get("id"),
            "Name": name_val if name_val else f"Unnamed ({sub.get('id')})",
            "Source": ans.get(str(FIELD_ID["source"]), {}).get("answer"),
            "Status": ans.get(str(FIELD_ID["status"]), {}).get("answer"),
            "ServiceType": ans.get(str(FIELD_ID["service_type"]), {}).get("answer"),
            "LostReason": ans.get(str(FIELD_ID["lost_reason"]), {}).get("answer"),
            "ts_survey_scheduled": get_ts(FIELD_ID["survey_scheduled"]),
            "ts_survey_completed": get_ts(FIELD_ID["survey_completed"]),
            "ts_scheduled": get_ts(FIELD_ID["scheduled"]),
            "ts_installed": get_ts(FIELD_ID["installed"]),
            "ts_waiting": get_ts(FIELD_ID["waiting_on_customer"]),
            "RawAnswers": ans
        })
    df = pd.DataFrame(records)
    if not df.empty:
        df = df[~df["Name"].str.startswith("Unnamed (")]
    return df

def apply_blocklist(df, blocked_words):
    if df.empty:
        return df, 0
    mask = df["Name"].astype(str).str.lower().apply(
        lambda x: any(word.lower() in x for word in blocked_words)
    )
    hidden_count = mask.sum()
    df = df[~mask]
    return df, hidden_count

def update_submission(sub_id, payload: dict):
    url = f"{JOTFORM_API}/submission/{sub_id}?apiKey={API_KEY}"
    resp = requests.post(url, data=payload, timeout=30)
    return resp.status_code == 200, resp.text

def delete_submission(sub_id):
    url = f"{JOTFORM_API}/submission/{sub_id}?apiKey={API_KEY}"
    resp = requests.delete(url, timeout=30)
    return resp.status_code == 200, resp.text

def add_submission(payload: dict):
    url = f"{JOTFORM_API}/form/{FORM_ID}/submissions?apiKey={API_KEY}"
    resp = requests.post(url, data=payload, timeout=30)
    return resp.status_code == 200, resp.text

st.set_page_config(page_title="Sales Lead Tracker v19.10.4", page_icon="📊", layout="wide")
st.title("📊 Sales Lead Tracker v19.10.4 — Full CRUD + Analytics")

settings = load_settings()
blocked_words = settings.get("blocked_words", DEFAULT_BLOCKED)
reminder_days = int(settings.get("reminder_days", 3))

df = fetch_jotform_data()
df, hidden_count = apply_blocklist(df, blocked_words)

st.caption(f"Last synced from JotForm: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
if hidden_count > 0:
    st.info(f"ℹ️ {hidden_count} tickets hidden (blocked words: {', '.join(blocked_words)})")

# Tabs
tab_all, tab_edit, tab_add, tab_pipeline, tab_reminders, tab_kpi, tab_settings = st.tabs(
    ["📋 All Tickets", "📝 Edit Ticket", "➕ Add Ticket", "🗂 Pipeline", "⏰ Reminders", "📊 KPI Dashboard", "⚙️ Settings"]
)

if "edit_ticket" not in st.session_state:
    st.session_state["edit_ticket"] = None

with tab_all:
    st.subheader("All Tickets")
    if df.empty:
        st.info("No tickets available.")
    else:
        for _, row in df.iterrows():
            cols = st.columns([4,1])
            cols[0].write(f"**{row['Name']}** | {row['Source']} | {row['Status']} | {row['ServiceType']}")
            if cols[1].button("✏️ Edit", key=f"edit_{row['SubmissionID']}"):
                st.session_state["edit_ticket"] = row["SubmissionID"]
                st.experimental_rerun()

with tab_edit:
    st.subheader("📝 Edit Ticket")
    if not st.session_state["edit_ticket"]:
        st.info("Select a ticket from All Tickets to edit.")
    else:
        sub_id = st.session_state["edit_ticket"]
        ticket = df[df["SubmissionID"] == sub_id].iloc[0]
        with st.form("edit_ticket_form"):
            name = st.text_input("Name", value=ticket["Name"] or "")
            source = st.text_input("Source", value=ticket["Source"] or "")
            status = st.selectbox("Status", STATUS_LIST, index=STATUS_LIST.index(ticket["Status"]) if ticket["Status"] in STATUS_LIST else 0)
            service = st.text_input("Service Type", value=ticket["ServiceType"] or "")
            lost = st.text_input("Lost Reason", value=ticket["LostReason"] or "")
            submitted = st.form_submit_button("💾 Save Changes")
            if submitted:
                payload = {}
                if name != ticket["Name"]:
                    parts = name.split(" ",1)
                    payload[f"submission[{FIELD_ID['name']}][first]"] = parts[0]
                    payload[f"submission[{FIELD_ID['name']}][last]"] = parts[1] if len(parts)>1 else ""
                if source != ticket["Source"]:
                    payload[f"submission[{FIELD_ID['source']}]"] = source
                if status != ticket["Status"]:
                    payload[f"submission[{FIELD_ID['status']}]"] = status
                    payload[f"submission[{STATUS_TO_FIELD[status]}]"] = datetime.now().isoformat()
                if service != ticket["ServiceType"]:
                    payload[f"submission[{FIELD_ID['service_type']}]"] = service
                if lost != ticket["LostReason"]:
                    payload[f"submission[{FIELD_ID['lost_reason']}]"] = lost
                if payload:
                    ok,msg = update_submission(sub_id,payload)
                    if ok:
                        st.success("✅ Ticket updated")
                        st.session_state["edit_ticket"]=None
                        st.experimental_rerun()
                    else:
                        st.error(f"❌ Failed: {msg}")
        if st.button("🗑 Delete Ticket", type="primary"):
            ok,msg = delete_submission(sub_id)
            if ok:
                st.success("✅ Ticket deleted")
                st.session_state["edit_ticket"]=None
                st.experimental_rerun()
            else:
                st.error(f"❌ Failed to delete: {msg}")

with tab_add:
    st.subheader("➕ Add Ticket")
    with st.form("add_ticket_form"):
        first = st.text_input("First Name")
        last = st.text_input("Last Name")
        source = st.selectbox("Source", ["Email","Phone","Walk In","Social Media","In Person"])
        status = st.selectbox("Status", STATUS_LIST, index=0)
        service = st.selectbox("Service Type", ["Internet","Phone","TV","Internet and Phone","Internet and TV","Internet and Cell Phone"])
        lost = st.text_input("Lost Reason")
        submitted = st.form_submit_button("➕ Add")
        if submitted:
            payload = {
                f"submission[{FIELD_ID['name']}][first]": first,
                f"submission[{FIELD_ID['name']}][last]": last,
                f"submission[{FIELD_ID['source']}]": source,
                f"submission[{FIELD_ID['status']}]": status,
                f"submission[{FIELD_ID['service_type']}]": service,
                f"submission[{FIELD_ID['lost_reason']}]": lost
            }
            if status in STATUS_TO_FIELD:
                payload[f"submission[{STATUS_TO_FIELD[status]}]"] = datetime.now().isoformat()
            ok,msg = add_submission(payload)
            if ok:
                st.success("✅ Ticket added")
                st.experimental_rerun()
            else:
                st.error(f"❌ Failed: {msg}")

with tab_pipeline:
    st.subheader("🗂 Pipeline")
    if st.checkbox("⚡ Quick Add Lead"):
        with st.form("quick_add"):
            qname = st.text_input("Name")
            qsource = st.selectbox("Source", ["Email","Phone","Walk In","Social Media","In Person"], key="qsource")
            qstatus = st.selectbox("Status", STATUS_LIST, index=0, key="qstatus")
            qsub = st.form_submit_button("Add")
            if qsub:
                parts = qname.split(" ",1)
                payload = {
                    f"submission[{FIELD_ID['name']}][first]": parts[0] if parts else "",
                    f"submission[{FIELD_ID['name']}][last]": parts[1] if len(parts)>1 else "",
                    f"submission[{FIELD_ID['source']}]": qsource,
                    f"submission[{FIELD_ID['status']}]": qstatus
                }
                if qstatus in STATUS_TO_FIELD:
                    payload[f"submission[{STATUS_TO_FIELD[qstatus]}]"] = datetime.now().isoformat()
                ok,msg = add_submission(payload)
                if ok:
                    st.success("✅ Quick ticket added")
                    st.experimental_rerun()
                else:
                    st.error(f"❌ Failed: {msg}")
    if not df.empty:
        for status in STATUS_LIST:
            st.markdown(f"### {status}")
            subset = df[df["Status"]==status]
            for _, row in subset.iterrows():
                st.write(f"- {row['Name']} ({row['Source']})")

with tab_reminders:
    st.subheader("⏰ Reminders")
    if not df.empty:
        now = pd.to_datetime(datetime.now())
        df["LastUpdated"] = pd.to_datetime(df[["ts_survey_scheduled","ts_survey_completed","ts_scheduled","ts_installed","ts_waiting"]].max(axis=1), errors="coerce")
        df["DaysSince"] = (now - df["LastUpdated"]).dt.days
        reminders = df[df["DaysSince"]>=reminder_days]
        st.write(reminders[["Name","Status","DaysSince"]])
    else:
        st.info("No tickets available.")

with tab_kpi:
    st.subheader("📊 KPI Dashboard")
    if not df.empty:
        by_src = df.groupby("Source").size().reset_index(name="Leads")
        fig1 = px.bar(by_src, x="Source", y="Leads", title="Leads by Source")
        st.plotly_chart(fig1, use_container_width=True)
        lost = df[df["Status"]=="Lost"]
        if not lost.empty:
            by_reason = lost.groupby("LostReason").size().reset_index(name="LostLeads")
            fig2 = px.bar(by_reason, x="LostReason", y="LostLeads", title="Lost Leads by Reason")
            st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No data for KPI.")

with tab_settings:
    st.subheader("⚙️ Settings")
    bw = st.text_area("Blocked Words (comma separated)", value=",".join(blocked_words))
    rd = st.number_input("Reminder Threshold (days)", min_value=1, max_value=30, value=reminder_days)
    if st.button("💾 Save Settings"):
        settings["blocked_words"] = [b.strip() for b in bw.split(",") if b.strip()]
        settings["reminder_days"] = int(rd)
        save_settings(settings)
        st.success("✅ Settings saved")
