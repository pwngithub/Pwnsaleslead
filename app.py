
import streamlit as st
import pandas as pd
import requests
import datetime
from config import API_KEY, FORM_ID, FIELD_ID

JOTFORM_API = "https://api.jotform.com"
STATUS_LIST = ["Survey Scheduled","Survey Completed","Scheduled","Installed","Waiting on Customer","Lost"]
SOURCE_LIST = ["Email","Social Media","Phone Call","Walk-in","In Person"]
SERVICE_TYPES = [
    "Internet","Phone","TV","Cell Phone",
    "Internet and Phone","Internet and TV","Internet and Cell Phone"
]

def fetch_jotform_data():
    url = f"{JOTFORM_API}/form/{FORM_ID}/submissions?apikey={API_KEY}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    data = r.json()
    subs = data.get("content", [])
    records = []
    for sub in subs:
        ans = sub.get("answers") or {}
        if not isinstance(ans, dict):
            ans = {}
        addr_raw = ans.get(str(FIELD_ID["address"]), {}).get("answer", {})
        if not isinstance(addr_raw, dict):
            addr_raw = {}
        name_raw = ans.get(str(FIELD_ID["name"]), {}).get("answer", {})
        if isinstance(name_raw, dict):
            name_val = f"{name_raw.get('first','')} {name_raw.get('last','')}".strip()
        else:
            name_val = name_raw if isinstance(name_raw, str) else None
        display_name = name_val if name_val else "Unnamed"
        if addr_raw.get("city") or addr_raw.get("state"):
            display_name += f" – {addr_raw.get('city','')}, {addr_raw.get('state','')}"
        records.append({
            "SubmissionID": sub.get("id"),
            "DisplayName": display_name,
            "Name": name_val,
            "Source": ans.get(str(FIELD_ID["source"]), {}).get("answer"),
            "Status": ans.get(str(FIELD_ID["status"]), {}).get("answer"),
            "ServiceType": ans.get(str(FIELD_ID["service_type"]), {}).get("answer"),
            "LostReason": ans.get(str(FIELD_ID["lost_reason"]), {}).get("answer"),
            "Street": addr_raw.get("addr_line1"),
            "Street2": addr_raw.get("addr_line2"),
            "City": addr_raw.get("city"),
            "State": addr_raw.get("state"),
            "Postal": addr_raw.get("postal")
        })
    return pd.DataFrame(records)

def add_submission(payload: dict):
    form = {}
    for qid, val in payload.items():
        if qid == FIELD_ID["name"] and isinstance(val, str):
            parts = val.split(" ", 1)
            form[f"submission[{qid}][first]"] = parts[0]
            form[f"submission[{qid}][last]"] = parts[1] if len(parts) > 1 else ""
        elif qid == FIELD_ID["address"] and isinstance(val, dict):
            for subfield, subval in val.items():
                form[f"submission[{qid}][{subfield}]"] = subval
        else:
            if val is not None:
                form[f"submission[{qid}]"] = val
    url = f"{JOTFORM_API}/form/{FORM_ID}/submissions?apiKey={API_KEY}"
    resp = requests.post(url, data=form, timeout=30)
    ok = resp.status_code == 200
    return ok, (resp.json() if ok else {"status_code": resp.status_code, "text": resp.text, "sent_form": form})

def replace_submission(sub_id, payload: dict):
    del_url = f"{JOTFORM_API}/submission/{sub_id}?apiKey={API_KEY}"
    requests.delete(del_url, timeout=30)
    return add_submission(payload)

def erase_all_submissions():
    url = f"{JOTFORM_API}/form/{FORM_ID}/submissions?apikey={API_KEY}"
    r = requests.get(url, timeout=30)
    if r.status_code != 200:
        return False, f"Failed to fetch submissions: {r.text}"
    subs = r.json().get("content", [])
    count = 0
    for sub in subs:
        sid = sub.get("id")
        if sid:
            del_url = f"{JOTFORM_API}/submission/{sid}?apiKey={API_KEY}"
            d = requests.delete(del_url, timeout=30)
            if d.status_code == 200:
                count += 1
    return True, count

st.set_page_config(page_title="Sales Lead Tracker v19.9.11", page_icon="📊", layout="wide")
st.title("📊 Sales Lead Tracker v19.9.11 — Erase All Tickets")

df = fetch_jotform_data()
if "edit_ticket_id" not in st.session_state:
    st.session_state.edit_ticket_id = None

tab_all, tab_add, tab_edit, tab_kpi = st.tabs(["📋 All Tickets", "➕ Add Ticket", "✏️ Edit Ticket", "📊 KPI Dashboard"])

with tab_all:
    st.subheader("All Tickets Preview")
    for idx, row in df.iterrows():
        cols = st.columns([3,2,2,2,2,2,2,1])
        cols[0].write(row["DisplayName"])
        cols[1].write(row["Source"])
        cols[2].write(row["Status"])
        cols[3].write(row["ServiceType"])
        cols[4].write(row["City"])
        cols[5].write(row["State"])
        cols[6].write(row["LostReason"])
        sid = row["SubmissionID"] if pd.notna(row["SubmissionID"]) else "noid"
        if cols[7].button("✏️ Edit", key=f"editbtn_{idx}_{sid}"):
            st.session_state.edit_ticket_id = row["SubmissionID"]
            st.rerun()

with tab_kpi:
    st.subheader("📊 KPI Dashboard")
    if not df.empty:
        st.markdown("### Tickets by Service Type")
        st.bar_chart(df["ServiceType"].value_counts())
        st.markdown("### Tickets by State")
        st.bar_chart(df["State"].value_counts())

    st.markdown("---")
    st.error("⚠️ Danger Zone: This will erase ALL tickets from JotForm permanently!")
    confirm = st.checkbox("I understand this will erase all tickets permanently")
    if confirm and st.button("🚨 Erase All Tickets"):
        ok, result = erase_all_submissions()
        if ok:
            st.success(f"✅ Successfully erased {result} tickets.")
            st.rerun()
        else:
            st.error(f"❌ Failed: {result}")
