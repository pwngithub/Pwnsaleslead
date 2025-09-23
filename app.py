
import streamlit as st
import pandas as pd
import plotly.express as px
import requests
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
        records.append({
            "SubmissionID": sub.get("id"),
            "Name": ans.get(str(FIELD_ID["name"]), {}).get("answer"),
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

def update_submission(submission_id: str, payload: dict):
    # ⚠️ JotForm does not allow editing answers directly, only meta
    # Placeholder if needed for deletion/recreate approach
    url = f"{JOTFORM_API}/submission/{submission_id}?apiKey={API_KEY}"
    form = {f"q{qid}": val for qid, val in payload.items() if val is not None}
    resp = requests.post(url, data=form, timeout=30)
    ok = resp.status_code == 200
    return ok, (resp.json() if ok else {"status_code": resp.status_code, "text": resp.text})

def add_submission(payload: dict):
    # FIX: JotForm requires q{field_id} keys instead of submission[{id}]
    form = {f"q{qid}": val for qid, val in payload.items() if val is not None}
    url = f"{JOTFORM_API}/form/{FORM_ID}/submissions?apiKey={API_KEY}"
    resp = requests.post(url, data=form, timeout=30)
    ok = resp.status_code == 200
    return ok, (resp.json() if ok else {"status_code": resp.status_code, "text": resp.text})

st.set_page_config(page_title="Sales Lead Tracker v19.9.2", page_icon="📊", layout="wide")
st.title("📊 Sales Lead Tracker v19.9.2 — Add Ticket Fix")

df = fetch_jotform_data()
if df.empty:
    st.warning("⚠️ No data pulled from JotForm yet.")
    st.stop()

# Tabs (All Tickets first)
tab_all, tab_add, tab_edit, tab_kpi = st.tabs(["📋 All Tickets", "➕ Add Ticket", "✏️ Edit Ticket", "📊 KPI Dashboard"])

# All Tickets Preview
with tab_all:
    st.subheader("All Tickets Preview")

    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        f_status = st.multiselect("Filter by Status", options=STATUS_LIST, default=STATUS_LIST, key="all_status")
    with col2:
        f_service = st.multiselect("Filter by Service Type", options=SERVICE_TYPES, default=SERVICE_TYPES, key="all_service")
    with col3:
        search_name = st.text_input("Search by Name", key="all_search")

    filtered = df[df["Status"].isin(f_status) & df["ServiceType"].isin(f_service)]
    if search_name:
        filtered = filtered[filtered["Name"].str.contains(search_name, case=False, na=False)]

    show_cols = ["SubmissionID","Name","Source","Status","ServiceType","City","State","LostReason"]
    st.dataframe(filtered[show_cols], use_container_width=True)

# Add Ticket
with tab_add:
    st.subheader("Add Ticket")
    name = st.text_input("Name", key="add_name")
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
        ok, resp = add_submission(payload)
        if ok:
            st.success("✅ Ticket added.")
            st.json(resp)
            st.rerun()
        else:
            st.error("❌ Failed to add ticket."); st.write(resp)

# Edit Ticket
with tab_edit:
    st.subheader("Edit Ticket")
    if not df.empty:
        df["label"] = df.apply(lambda r: f"{r['Name']} — {r['Status']} — {r['SubmissionID']}", axis=1)
        sel = st.selectbox("Select Ticket", df["label"].tolist(), key="edit_select")
        if sel:
            curr = df[df["label"]==sel].iloc[0]
            new_status = st.selectbox("Status", STATUS_LIST, 
                                      index=STATUS_LIST.index(curr["Status"]) if curr["Status"] in STATUS_LIST else 0,
                                      key="edit_status")
            new_service = st.selectbox("Service Type", SERVICE_TYPES, 
                                       index=SERVICE_TYPES.index(curr["ServiceType"]) if curr["ServiceType"] in SERVICE_TYPES else 0,
                                       key="edit_service_type")
            st.markdown("**Address**")
            new_street = st.text_input("Street", value=curr["Street"] or "", key="edit_addr1")
            new_street2 = st.text_input("Street 2", value=curr["Street2"] or "", key="edit_addr2")
            new_city = st.text_input("City", value=curr["City"] or "", key="edit_city")
            new_state = st.text_input("State", value=curr["State"] or "", key="edit_state")
            new_postal = st.text_input("Postal Code", value=curr["Postal"] or "", key="edit_postal")

            if st.button("💾 Save Changes", key="edit_save_btn"):
                payload = {
                    FIELD_ID["status"]: new_status,
                    FIELD_ID["service_type"]: new_service,
                    FIELD_ID["address"]: {
                        "addr_line1": new_street,
                        "addr_line2": new_street2,
                        "city": new_city,
                        "state": new_state,
                        "postal": new_postal
                    }
                }
                ok, resp = update_submission(curr["SubmissionID"], payload)
                if ok:
                    st.success("✅ Ticket updated.")
                    st.json(resp)
                    st.rerun()
                else:
                    st.error("❌ Failed to update."); st.write(resp)

# KPI Dashboard
with tab_kpi:
    st.subheader("📊 KPI Dashboard")
    if not df.empty:
        st.markdown("### Tickets by Service Type")
        st.bar_chart(df["ServiceType"].value_counts())

        st.markdown("### Tickets by State")
        st.bar_chart(df["State"].value_counts())
