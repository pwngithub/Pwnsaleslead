
import streamlit as st
import pandas as pd
import requests
from io import BytesIO
import os, json
from datetime import datetime
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
        status_val = ans.get(str(FIELD_ID["status"]), {}).get("answer")
        records.append({
            "SubmissionID": sub.get("id"),
            "Name": name_val if name_val else f"Unnamed ({sub.get('id')})",
            "Source": ans.get(str(FIELD_ID["source"]), {}).get("answer"),
            "Status": status_val,
            "ServiceType": ans.get(str(FIELD_ID["service_type"]), {}).get("answer"),
            "LostReason": ans.get(str(FIELD_ID["lost_reason"]), {}).get("answer"),
            "Notes": ans.get(str(FIELD_ID["notes"]), {}).get("answer"),
            "LastUpdated": sub.get("created_at")
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

def colored_status(s):
    if s == "Installed":
        return "🟢 Installed"
    if s == "Waiting on Customer":
        return "🟡 Waiting on Customer"
    if s in ["Survey Scheduled","Survey Completed","Scheduled"]:
        return "🔵 " + s
    if s == "Lost":
        return "🔴 Lost"
    return s

st.set_page_config(page_title="Sales Lead Tracker v19.10.9", page_icon="📊", layout="wide")
st.title("📊 Sales Lead Tracker v19.10.9")

settings = load_settings()
blocked_words = settings.get("blocked_words", DEFAULT_BLOCKED)
reminder_days = int(settings.get("reminder_days", 3))

df = fetch_jotform_data()
st.session_state["all_data"] = df.copy()
df, hidden_count = apply_blocklist(df, blocked_words)

tab_all, tab_edit, tab_add, tab_kpi, tab_settings = st.tabs(
    ["📋 All Tickets", "📝 Edit Ticket", "➕ Add Ticket", "📊 KPI Dashboard", "⚙️ Settings"]
)

with tab_all:
    st.subheader("All Tickets")
    if df.empty:
        st.info("No tickets available.")
    else:
        search = st.text_input("🔍 Search tickets")
        status_filter = st.multiselect("Filter by Status", STATUS_LIST)
        service_filter = st.multiselect("Filter by Service Type", sorted(df["ServiceType"].dropna().unique()))
        df_view = df.copy()
        if search:
            mask = (
                df_view["Name"].astype(str).str.contains(search, case=False, na=False) |
                df_view["Source"].astype(str).str.contains(search, case=False, na=False) |
                df_view["Status"].astype(str).str.contains(search, case=False, na=False)
            )
            df_view = df_view[mask]
        if status_filter:
            df_view = df_view[df_view["Status"].isin(status_filter)]
        if service_filter:
            df_view = df_view[df_view["ServiceType"].isin(service_filter)]

        # summary counts
        total = len(df_view)
        installed = (df_view["Status"]=="Installed").sum()
        waiting = (df_view["Status"]=="Waiting on Customer").sum()
        inprog = df_view["Status"].isin(["Survey Scheduled","Survey Completed","Scheduled"]).sum()
        lost = (df_view["Status"]=="Lost").sum()
        overdue = 0  # placeholder logic
        st.markdown(f"**Summary:** {total} Total | 🟢 {installed} Installed | 🟡 {waiting} Waiting | 🔵 {inprog} In Progress | 🔴 {lost+overdue} Lost/Overdue")

        df_view = df_view.copy()
        df_view["Status"] = df_view["Status"].apply(lambda x: colored_status(x))
        st.dataframe(df_view[["Name","Source","Status","ServiceType","Notes"]], use_container_width=True)

        buf = BytesIO(); df_view.to_excel(buf, index=False)
        st.download_button("📥 Export All Tickets", buf.getvalue(), "all_tickets.xlsx")

with tab_kpi:
    st.subheader("📊 KPI Dashboard")
    if df.empty:
        st.info("No data available")
    else:
        by_src = df.groupby("Source").size().reset_index(name="Leads")
        st.bar_chart(by_src.set_index("Source"))

        # KPI metrics placeholders
        st.metric("Avg Days Survey → Install", "5")
        st.metric("Avg Days Waiting", "3")
        st.metric("Overall Lead → Install", "12")

        buf2 = BytesIO(); df.to_excel(buf2, index=False)
        st.download_button("📥 Export KPI Data", buf2.getvalue(), "kpi_data.xlsx")

with tab_settings:
    st.subheader("⚙️ Settings")
    blocked = st.text_area("Blocked Words (comma-separated)", value=",".join(blocked_words))
    rem_days = st.number_input("Reminder Days", min_value=1, value=reminder_days)
    if st.button("💾 Save Settings"):
        settings["blocked_words"] = [w.strip() for w in blocked.split(",") if w.strip()]
        settings["reminder_days"] = rem_days
        save_settings(settings)
        st.success("Settings saved")
