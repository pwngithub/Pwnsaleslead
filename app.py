
import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from datetime import date
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
        ans = sub.get("answers", {})
        records.append({
            "SubmissionID": sub.get("id"),
            "Name": ans.get(str(FIELD_ID["name"]), {}).get("answer"),
            "Source": ans.get(str(FIELD_ID["source"]), {}).get("answer"),
            "Status": ans.get(str(FIELD_ID["status"]), {}).get("answer"),
            "ServiceType": ans.get(str(FIELD_ID["service_type"]), {}).get("answer"),
            "LostReason": ans.get(str(FIELD_ID["lost_reason"]), {}).get("answer")
        })
    return pd.DataFrame(records)

def update_submission(submission_id: str, payload: dict):
    form = {f"submission[{qid}]": val for qid,val in payload.items() if val is not None}
    url = f"{JOTFORM_API}/submission/{submission_id}?apiKey={API_KEY}"
    resp = requests.post(url, data=form, timeout=30)
    ok = resp.status_code == 200
    return ok, (resp.json() if ok else {"status_code": resp.status_code, "text": resp.text})

def add_submission(payload: dict):
    form = {f"submission[{qid}]": val for qid,val in payload.items() if val is not None}
    url = f"{JOTFORM_API}/form/{FORM_ID}/submissions?apiKey={API_KEY}"
    resp = requests.post(url, data=form, timeout=30)
    ok = resp.status_code == 200
    return ok, (resp.json() if ok else {"status_code": resp.status_code, "text": resp.text})

st.set_page_config(page_title="Sales Lead Tracker v19.7", page_icon="📊", layout="wide")
st.title("📊 Sales Lead Tracker v19.7 — Service Type Integration")

df = fetch_jotform_data()
if df.empty:
    st.warning("⚠️ No data pulled from JotForm yet.")
    st.stop()

# Tabs
tab_add, tab_edit, tab_kpi = st.tabs(["➕ Add Ticket", "✏️ Edit Ticket", "📊 KPI Dashboard"])

# Add Ticket
with tab_add:
    st.subheader("Add Ticket")
    name = st.text_input("Name")
    source = st.selectbox("Source", SOURCE_LIST)
    status = st.selectbox("Status", STATUS_LIST)
    service_type = st.selectbox("Service Type", SERVICE_TYPES)

    if st.button("💾 Save New Ticket"):
        payload = {
            str(FIELD_ID["name"]): name,
            str(FIELD_ID["source"]): source,
            str(FIELD_ID["status"]): status,
            str(FIELD_ID["service_type"]): service_type
        }
        ok, resp = add_submission(payload)
        if ok:
            st.success("✅ Ticket added."); st.json(resp); st.experimental_rerun()
        else:
            st.error("❌ Failed to add ticket."); st.write(resp)

# Edit Ticket
with tab_edit:
    st.subheader("Edit Ticket")
    if not df.empty:
        df["label"] = df.apply(lambda r: f"{r['Name']} — {r['Status']} — {r['SubmissionID']}", axis=1)
        sel = st.selectbox("Select Ticket", df["label"].tolist())
        if sel:
            curr = df[df["label"]==sel].iloc[0]
            new_status = st.selectbox("Status", STATUS_LIST, index=STATUS_LIST.index(curr["Status"]) if curr["Status"] in STATUS_LIST else 0)
            new_service = st.selectbox("Service Type", SERVICE_TYPES, index=SERVICE_TYPES.index(curr["ServiceType"]) if curr["ServiceType"] in SERVICE_TYPES else 0)
            if st.button("💾 Save Changes"):
                payload = {
                    str(FIELD_ID["status"]): new_status,
                    str(FIELD_ID["service_type"]): new_service
                }
                ok, resp = update_submission(curr["SubmissionID"], payload)
                if ok:
                    st.success("✅ Ticket updated."); st.json(resp); st.experimental_rerun()
                else:
                    st.error("❌ Failed to update."); st.write(resp)

# KPI Dashboard
with tab_kpi:
    st.subheader("📊 KPI Dashboard")
    if not df.empty:
        st.markdown("### Tickets by Service Type")
        st.bar_chart(df["ServiceType"].value_counts())
