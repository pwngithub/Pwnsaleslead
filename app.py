
import streamlit as st
import pandas as pd
import requests
import csv
import os
from config import API_KEY, FORM_ID, FIELD_ID

JOTFORM_API = "https://api.jotform.com"
STATUS_LIST = ["Survey Scheduled","Survey Completed","Scheduled","Installed","Waiting on Customer","Lost"]
SOURCE_LIST = ["Email","Social Media","Phone Call","Walk-in","In Person"]
SERVICE_TYPES = [
    "Internet","Phone","TV","Cell Phone",
    "Internet and Phone","Internet and TV","Internet and Cell Phone"
]

LOG_FILE = "erase_log.csv"

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
    df = pd.DataFrame(records)
    if not df.empty:
        df = df[~df["DisplayName"].str.startswith("Unnamed (")]
    return df

def delete_submission(sub_id):
    del_url = f"{JOTFORM_API}/submission/{sub_id}?apiKey={API_KEY}"
    d = requests.delete(del_url, timeout=30)
    status, text = d.status_code, d.text
    # Log the attempt
    write_header = not os.path.exists(LOG_FILE)
    with open(LOG_FILE, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["id","status","text"])
        if write_header:
            writer.writeheader()
        writer.writerow({"id": sub_id, "status": status, "text": text})
    return status == 200, text

st.set_page_config(page_title="Sales Lead Tracker v19.9.17", page_icon="📊", layout="wide")
st.title("📊 Sales Lead Tracker v19.9.17 — Delete Selected Ticket")

df = fetch_jotform_data()

tab_all, tab_kpi = st.tabs(["📋 All Tickets", "📊 KPI Dashboard"])

with tab_all:
    st.subheader("All Tickets Preview")
    if df.empty:
        st.info("No tickets available.")
    else:
        for idx, row in df.iterrows():
            cols = st.columns([3,2,2,2,2,2,2,1,1])
            cols[0].write(row["DisplayName"])
            cols[1].write(row["Source"])
            cols[2].write(row["Status"])
            cols[3].write(row["ServiceType"])
            cols[4].write(row["City"])
            cols[5].write(row["State"])
            cols[6].write(row["LostReason"])
            sid = row["SubmissionID"]
            if cols[7].button("✏️ Edit", key=f"editbtn_{idx}_{sid}"):
                st.session_state.edit_ticket_id = sid
                st.rerun()
            # Delete button with confirmation
            with cols[8]:
                if st.button("🗑 Delete", key=f"delbtn_{idx}_{sid}"):
                    confirm_key = f"confirmdel_{sid}"
                    st.session_state[confirm_key] = True
            confirm_key = f"confirmdel_{sid}"
            if st.session_state.get(confirm_key, False):
                st.warning("⚠️ Confirm deletion of this ticket")
                if st.checkbox("Yes, delete this ticket permanently", key=f"chk_{sid}"):
                    ok, msg = delete_submission(sid)
                    if ok:
                        st.success(f"✅ Ticket {sid} deleted.")
                        del st.session_state[confirm_key]
                        st.rerun()
                    else:
                        st.error(f"❌ Failed to delete {sid}: {msg}")

with tab_kpi:
    st.subheader("📊 KPI Dashboard")
    if not df.empty:
        st.markdown("### Tickets by Service Type")
        st.bar_chart(df["ServiceType"].value_counts())
        st.markdown("### Tickets by State")
        st.bar_chart(df["State"].value_counts())
