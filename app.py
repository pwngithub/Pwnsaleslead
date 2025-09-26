
import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from config import API_KEY, FORM_ID, FIELD_ID

JOTFORM_API = "https://api.jotform.com"

STATUS_LIST = [
    "Survey Scheduled",
    "Survey Completed",
    "Scheduled",
    "Installed",
    "Waiting on Customer",
    "Lost",
]

SERVICE_TYPES = [
    "Internet",
    "Phone",
    "TV",
    "Cell Phone",
    "Internet and Phone",
    "Internet and TV",
    "Internet and Cell Phone",
]

st.set_page_config(page_title="Sales Lead Tracker v19.10.11", page_icon="📊", layout="wide")
st.title("📊 Sales Lead Tracker v19.10.11 — Minimal (Read + Add)")

# ---------- Data fetch (read-only) ----------
@st.cache_data(ttl=60)
def fetch_data():
    url = f"{JOTFORM_API}/form/{FORM_ID}/submissions?apikey={API_KEY}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    subs = r.json().get("content", [])
    rows = []
    for sub in subs:
        ans = sub.get("answers", {}) or {}
        name_raw = ans.get(str(FIELD_ID["name"]), {}).get("answer", {})
        if isinstance(name_raw, dict):
            name = f"{name_raw.get('first','').strip()} {name_raw.get('last','').strip()}".strip()
        else:
            name = str(name_raw) if name_raw else ""
        rows.append({
            "SubmissionID": sub.get("id"),
            "Name": name or f"Unnamed ({sub.get('id')})",
            "Source": ans.get(str(FIELD_ID["source"]), {}).get("answer"),
            "Status": ans.get(str(FIELD_ID["status"]), {}).get("answer"),
            "ServiceType": ans.get(str(FIELD_ID["service_type"]), {}).get("answer"),
            "Notes": ans.get(str(FIELD_ID["notes"]), {}).get("answer"),
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        # hide placeholder "Unnamed" entries if desired
        df = df[~df["Name"].str.startswith("Unnamed (")]
    return df

df = fetch_data()

tab_all, tab_add = st.tabs(["📋 All Tickets", "➕ Add Ticket"])

with tab_all:
    st.subheader("All Tickets")
    if df.empty:
        st.info("No tickets found.")
    else:
        search = st.text_input("🔍 Search by name / source / status")
        view = df.copy()
        if search:
            m = (
                view["Name"].astype(str).str.contains(search, case=False, na=False) |
                view["Source"].astype(str).str.contains(search, case=False, na=False) |
                view["Status"].astype(str).str.contains(search, case=False, na=False)
            )
            view = view[m]
        st.dataframe(view, use_container_width=True)

with tab_add:
    st.subheader("➕ Add Ticket")
    with st.form("add_ticket_form", clear_on_submit=False):
        c1, c2 = st.columns(2)
        with c1:
            first = st.text_input("First Name *", placeholder="Jane")
            source = st.selectbox("Contact Source *", ["", "Email", "Phone", "Walk In", "Social Media", "In Person"])
            status = st.selectbox("Status *", [""] + STATUS_LIST, index=0)
        with c2:
            last = st.text_input("Last Name *", placeholder="Doe")
            service = st.selectbox("Service Type *", [""] + SERVICE_TYPES, index=0)
            notes = st.text_area("Notes", placeholder="Optional details...")

        submitted = st.form_submit_button("Create Ticket")
    if submitted:
        # ---------- Validation ----------
        missing = []
        if not first.strip(): missing.append("First Name")
        if not last.strip(): missing.append("Last Name")
        if not source.strip(): missing.append("Contact Source")
        if not service.strip(): missing.append("Service Type")
        if not status.strip(): missing.append("Status")
        if missing:
            st.error("Please fill the required fields: " + ", ".join(missing))
        else:
            payload = {
                f"submission[{FIELD_ID['name']}][first]": first.strip(),
                f"submission[{FIELD_ID['name']}][last]": last.strip(),
                f"submission[{FIELD_ID['source']}]": source,
                f"submission[{FIELD_ID['status']}]": status,
                f"submission[{FIELD_ID['service_type']}]": service,
                f"submission[{FIELD_ID['notes']}]": notes or "",
            }
            # Auto-fill Survey Scheduled date if chosen
            if status == "Survey Scheduled":
                payload[f"submission[{FIELD_ID['survey_scheduled']}]"] = datetime.now().isoformat()

            url = f"{JOTFORM_API}/form/{FORM_ID}/submissions?apiKey={API_KEY}"
            resp = requests.post(url, data=payload, timeout=30)

            if resp.status_code == 200:
                st.success("✅ Ticket created successfully")
                fetch_data.clear()  # invalidate cache
                st.rerun()
            else:
                st.error(f"❌ Create failed ({resp.status_code}): {resp.text}")
