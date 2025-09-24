
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

        notes_val = ans.get(str(FIELD_ID["notes"]), {}).get("answer")
        if isinstance(notes_val, dict):
            notes_val = notes_val.get("text") if "text" in notes_val else str(notes_val)
        if isinstance(notes_val, list):
            notes_val = " ".join(str(x) for x in notes_val)

        records.append({
            "SubmissionID": sub.get("id"),
            "Name": name_val if name_val else f"Unnamed ({sub.get('id')})",
            "Source": ans.get(str(FIELD_ID["source"]), {}).get("answer"),
            "Status": ans.get(str(FIELD_ID["status"]), {}).get("answer"),
            "ServiceType": ans.get(str(FIELD_ID["service_type"]), {}).get("answer"),
            "LostReason": ans.get(str(FIELD_ID["lost_reason"]), {}).get("answer"),
            "Notes": notes_val,
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

st.set_page_config(page_title="Sales Lead Tracker v19.10.6", page_icon="📊", layout="wide")
st.title("📊 Sales Lead Tracker v19.10.6 — Full CRUD + Notes + Address")

settings = load_settings()
blocked_words = settings.get("blocked_words", DEFAULT_BLOCKED)
reminder_days = int(settings.get("reminder_days", 3))

df = fetch_jotform_data()
st.session_state["all_data"] = df.copy()
df, hidden_count = apply_blocklist(df, blocked_words)

st.caption(f"Last synced from JotForm: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
if hidden_count > 0:
    st.info(f"ℹ️ {hidden_count} tickets hidden (blocked words: {', '.join(blocked_words)})")

# Tabs
tab_all, tab_edit, tab_add = st.tabs(["📋 All Tickets", "📝 Edit Ticket", "➕ Add Ticket"])

if "edit_ticket" not in st.session_state:
    st.session_state["edit_ticket"] = None

with tab_all:
    st.subheader("All Tickets")
    search = st.text_input("🔍 Search tickets")
    if df.empty:
        st.info("No tickets available.")
    else:
        if search:
            mask = (
                df["Name"].astype(str).str.contains(search, case=False, na=False) |
                df["Source"].astype(str).str.contains(search, case=False, na=False) |
                df["Status"].astype(str).str.contains(search, case=False, na=False)
            )
            df = df[mask]
        for _, row in df.iterrows():
            cols = st.columns([5,1])
            cols[0].write(f"**{row['Name']}** | {row['Source']} | {row['Status']} | {row['ServiceType']} | {row['Notes']}")
            if cols[1].button("✏️ Edit", key=f"edit_{row['SubmissionID']}"):
                st.session_state["edit_ticket"] = row["SubmissionID"]
                st.rerun()

with tab_edit:
    st.subheader("📝 Edit Ticket")
    if not st.session_state["edit_ticket"]:
        st.info("Select a ticket from All Tickets to edit.")
    else:
        sub_id = st.session_state["edit_ticket"]
        ticket = st.session_state["all_data"][st.session_state["all_data"]["SubmissionID"] == sub_id].iloc[0]
        with st.form("edit_ticket_form"):
            name = st.text_input("Name", value=ticket["Name"] or "")
            source = st.text_input("Source", value=ticket["Source"] or "")
            status = st.selectbox("Status", STATUS_LIST, index=STATUS_LIST.index(ticket["Status"]) if ticket["Status"] in STATUS_LIST else 0)
            service = st.text_input("Service Type", value=ticket["ServiceType"] or "")
            lost = st.text_input("Lost Reason", value=ticket["LostReason"] or "")
            notes = st.text_area("Notes", value=ticket["Notes"] or "")
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
                if notes != ticket["Notes"]:
                    payload[f"submission[{FIELD_ID['notes']}]"] = notes
                if payload:
                    ok,msg = update_submission(sub_id,payload)
                    if ok:
                        st.success("✅ Ticket updated")
                        st.session_state["edit_ticket"]=None
                        st.rerun()
                    else:
                        st.error(f"❌ Failed: {msg}")
        if st.button("🗑 Delete Ticket", type="primary"):
            ok,msg = delete_submission(sub_id)
            if ok:
                st.success("✅ Ticket deleted")
                st.session_state["edit_ticket"]=None
                st.rerun()
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
        notes = st.text_area("Notes")
        street1 = st.text_input("Street 1")
        street2 = st.text_input("Street 2")
        city = st.text_input("City")
        state = st.text_input("State")
        postal = st.text_input("Postal Code")
        submitted = st.form_submit_button("➕ Add")
        if submitted:
            payload = {
                f"submission[{FIELD_ID['name']}][first]": first,
                f"submission[{FIELD_ID['name']}][last]": last,
                f"submission[{FIELD_ID['source']}]": source,
                f"submission[{FIELD_ID['status']}]": status,
                f"submission[{FIELD_ID['service_type']}]": service,
                f"submission[{FIELD_ID['lost_reason']}]": lost,
                f"submission[{FIELD_ID['notes']}]": notes,
                f"submission[{FIELD_ID['address']}][addr_line1]": street1,
                f"submission[{FIELD_ID['address']}][addr_line2]": street2,
                f"submission[{FIELD_ID['address']}][city]": city,
                f"submission[{FIELD_ID['address']}][state]": state,
                f"submission[{FIELD_ID['address']}][postal]": postal
            }
            if status in STATUS_TO_FIELD:
                payload[f"submission[{STATUS_TO_FIELD[status]}]"] = datetime.now().isoformat()
            ok,msg = add_submission(payload)
            if ok:
                st.success("✅ Ticket added")
                st.rerun()
            else:
                st.error(f"❌ Failed: {msg}")
