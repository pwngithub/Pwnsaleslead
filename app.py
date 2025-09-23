
import streamlit as st
import pandas as pd
import requests
import datetime
import csv, os
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
            first = name_raw.get("first", "").strip()
            last = name_raw.get("last", "").strip()
            name_val = f"{first} {last}".strip()
        elif isinstance(name_raw, str):
            name_val = name_raw.strip()
        else:
            name_val = None
        display_name = name_val if name_val else f"Unnamed ({sub.get('id')})"
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

def erase_all_submissions():
    deleted = 0
    errors = []
    while True:
        url = f"{JOTFORM_API}/form/{FORM_ID}/submissions?apikey={API_KEY}"
        r = requests.get(url, timeout=30)
        if r.status_code != 200:
            return deleted, [{"id": "fetch", "status": r.status_code, "text": r.text}]
        subs = r.json().get("content", [])
        if not subs:
            break
        for sub in subs:
            sid = sub.get("id")
            if sid:
                del_url = f"{JOTFORM_API}/submission/{sid}?apiKey={API_KEY}"
                d = requests.delete(del_url, timeout=30)
                if d.status_code == 200:
                    deleted += 1
                else:
                    errors.append({"id": sid, "status": d.status_code, "text": d.text})
    # Save errors to CSV if any
    if errors:
        log_file = "erase_log.csv"
        with open(log_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["id","status","text"])
            writer.writeheader()
            for e in errors:
                writer.writerow(e)
        return deleted, log_file
    return deleted, None

st.set_page_config(page_title="Sales Lead Tracker v19.9.14", page_icon="📊", layout="wide")
st.title("📊 Sales Lead Tracker v19.9.14 — Strong Erase with Log")

df = fetch_jotform_data()
if "edit_ticket_id" not in st.session_state:
    st.session_state.edit_ticket_id = None

tab_all, tab_kpi = st.tabs(["📋 All Tickets", "📊 KPI Dashboard"])

with tab_all:
    st.subheader("All Tickets Preview")
    if df.empty:
        st.info("No tickets available.")
    else:
        st.dataframe(df[["DisplayName","Source","Status","ServiceType","City","State","LostReason"]])

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
        deleted, log_file = erase_all_submissions()
        if log_file:
            st.error(f"Deleted {deleted} tickets, but some errors occurred. Download the log below.")
            with open(log_file, "r") as f:
                st.download_button("📥 Download Erase Log", f, file_name="erase_log.csv")
        else:
            st.success(f"✅ Successfully erased {deleted} tickets.")
        st.rerun()
