
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

st.set_page_config(page_title="Sales Lead Tracker v19.9.8", page_icon="📊", layout="wide")
st.title("📊 Sales Lead Tracker v19.9.8 — Name-only Edit & Click-to-Edit")

df = fetch_jotform_data()
if df.empty:
    st.warning("⚠️ No data pulled from JotForm yet.")
    st.stop()

if "edit_ticket_id" not in st.session_state:
    st.session_state.edit_ticket_id = None

tab_all, tab_add, tab_edit, tab_kpi = st.tabs(["📋 All Tickets", "➕ Add Ticket", "✏️ Edit Ticket", "📊 KPI Dashboard"])

# All Tickets
with tab_all:
    st.subheader("All Tickets Preview")
    show_cols = ["DisplayName","Source","Status","ServiceType","City","State","LostReason"]
    for idx, row in df.iterrows():
        cols = st.columns([3,2,2,2,2,2,2,1])
        cols[0].write(row["DisplayName"])
        cols[1].write(row["Source"])
        cols[2].write(row["Status"])
        cols[3].write(row["ServiceType"])
        cols[4].write(row["City"])
        cols[5].write(row["State"])
        cols[6].write(row["LostReason"])
        if cols[7].button("✏️ Edit", key=f"editbtn_{row['SubmissionID']}"):
            st.session_state.edit_ticket_id = row["SubmissionID"]
            st.experimental_rerun()

# Add Ticket (same as before)
with tab_add:
    st.subheader("Add Ticket")
    name = st.text_input("Name (First Last)", key="add_name")
    source = st.selectbox("Source", SOURCE_LIST, key="add_source")
    status = st.selectbox("Status", STATUS_LIST, key="add_status")
    service_type = st.selectbox("Service Type", SERVICE_TYPES, key="add_service_type")
    st.markdown("**Address**")
    street = st.text_input("Street", key="add_addr1")
    street2 = st.text_input("Street 2", key="add_addr2")
    city = st.text_input("City", key="add_city")
    state = st.text_input("State", key="add_state")
    postal = st.text_input("Postal Code", key="add_postal")
    if st.button("💾 Save New Ticket", key="add_save_btn"):
        now = datetime.datetime.now().isoformat()
        payload = {
            FIELD_ID["name"]: name,
            FIELD_ID["source"]: source,
            FIELD_ID["status"]: status,
            FIELD_ID["service_type"]: service_type,
            FIELD_ID["address"]: {
                "addr_line1": street,
                "addr_line2": street2,
                "city": city,
                "state": state,
                "postal": postal
            }
        }
        if status == "Survey Scheduled":
            payload[FIELD_ID["survey_scheduled"]] = now
        elif status == "Survey Completed":
            payload[FIELD_ID["survey_completed"]] = now
        elif status == "Scheduled":
            payload[FIELD_ID["scheduled"]] = now
        elif status == "Installed":
            payload[FIELD_ID["installed"]] = now
        elif status == "Waiting on Customer":
            payload[FIELD_ID["waiting_on_customer"]] = now
        ok, resp = add_submission(payload)
        if ok:
            st.success("✅ Ticket added.")
            st.json(resp)
            st.rerun()
        else:
            st.error("❌ Failed to add ticket."); st.write(resp)

# Edit Ticket
with tab_edit:
    st.subheader("Edit Ticket (Change Status Only)")
    st.warning("⚠️ Editing will delete the old submission and create a new one. Submission ID will change.")
    options = dict(zip(df["DisplayName"], df["SubmissionID"]))
    default_idx = 0
    if st.session_state.edit_ticket_id:
        for i, sid in enumerate(options.values()):
            if sid == st.session_state.edit_ticket_id:
                default_idx = i
                break
    selected_name = st.selectbox("Select Ticket", options=list(options.keys()), index=default_idx)
    ticket_id = options[selected_name]
    if ticket_id:
        row = df[df["SubmissionID"] == ticket_id].iloc[0]
        st.write("**Name:**", row["Name"])
        st.write("**Source:**", row["Source"])
        st.write("**Service Type:**", row["ServiceType"])
        st.write("**Address:**", f"{row['Street']} {row['Street2']} {row['City']} {row['State']} {row['Postal']}")
        new_status = st.selectbox("New Status", STATUS_LIST, index=STATUS_LIST.index(row["Status"]) if row["Status"] in STATUS_LIST else 0, key="edit_status")
        if st.button("💾 Save Status Update", key="edit_save_btn"):
            now = datetime.datetime.now().isoformat()
            payload = {
                FIELD_ID["name"]: row["Name"],
                FIELD_ID["source"]: row["Source"],
                FIELD_ID["status"]: new_status,
                FIELD_ID["service_type"]: row["ServiceType"],
                FIELD_ID["address"]: {
                    "addr_line1": row["Street"],
                    "addr_line2": row["Street2"],
                    "city": row["City"],
                    "state": row["State"],
                    "postal": row["Postal"]
                }
            }
            if new_status == "Survey Scheduled":
                payload[FIELD_ID["survey_scheduled"]] = now
            elif new_status == "Survey Completed":
                payload[FIELD_ID["survey_completed"]] = now
            elif new_status == "Scheduled":
                payload[FIELD_ID["scheduled"]] = now
            elif new_status == "Installed":
                payload[FIELD_ID["installed"]] = now
            elif new_status == "Waiting on Customer":
                payload[FIELD_ID["waiting_on_customer"]] = now
            ok, resp = replace_submission(ticket_id, payload)
            if ok:
                st.success("✅ Ticket updated (recreated).")
                st.json(resp)
                st.session_state.edit_ticket_id = None
                st.rerun()
            else:
                st.error("❌ Failed to update ticket."); st.write(resp)

# KPI Dashboard (unchanged)
with tab_kpi:
    st.subheader("📊 KPI Dashboard")
    if not df.empty:
        st.markdown("### Tickets by Service Type")
        st.bar_chart(df["ServiceType"].value_counts())
        st.markdown("### Tickets by State")
        st.bar_chart(df["State"].value_counts())
