
import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timezone
import plotly.express as px
from io import BytesIO

# ────────────────────────────────
# CONFIG
# ────────────────────────────────

API_KEY = "22179825a79dba61013e4fc3b9d30fa4"
FORM_ID = "252598168633065"

FIELD_IDS = {
    "name": 1,
    "contact": 2,
    "source": 3,
    "status": 4,
    "notes": 5,
    "survey_scheduled_date": 12,
    "survey_completed_date": 13,
    "scheduled_date": 14,
    "installed_date": 15,
    "waiting_on_customer_date": 16,
    "assigned_rep": None  # fill this with qid if added in JotForm
}

STATUS_OPTIONS = [
    "Survey Scheduled",
    "Survey Completed",
    "Scheduled",
    "Installed",
    "Waiting on Customer",
]

# ────────────────────────────────
# DATA ACCESS
# ────────────────────────────────

BASE_URL = f"https://api.jotform.com/form/{FORM_ID}/submissions?apiKey={API_KEY}"

def fetch_jotform_data():
    response = requests.get(BASE_URL)
    if response.status_code != 200:
        st.error("❌ Failed to fetch data from JotForm API.")
        return pd.DataFrame()
    data = response.json()
    rows = []
    for item in data.get("content", []):
        answers = item.get("answers", {})
        get = lambda qid: answers.get(str(qid), {}).get("answer", "")
        rows.append({
            "SubmissionID": item.get("id", ""),
            "CreatedAt": item.get("created_at", ""),
            "Name": get(FIELD_IDS["name"]),
            "Contact": get(FIELD_IDS["contact"]),
            "Source": get(FIELD_IDS["source"]),
            "Status": get(FIELD_IDS["status"]),
            "Notes": get(FIELD_IDS["notes"]),
            "SurveyScheduledDate": get(FIELD_IDS["survey_scheduled_date"]),
            "SurveyCompletedDate": get(FIELD_IDS["survey_completed_date"]),
            "ScheduledDate": get(FIELD_IDS["scheduled_date"]),
            "InstalledDate": get(FIELD_IDS["installed_date"]),
            "WaitingOnCustomerDate": get(FIELD_IDS["waiting_on_customer_date"]),
            "AssignedRep": get(FIELD_IDS["assigned_rep"]) if FIELD_IDS["assigned_rep"] else "",
        })
    return pd.DataFrame(rows)

def submit_lead(name, contact, source, status, notes, rep=None):
    data = {
        f"submission[{FIELD_IDS['name']}]": name,
        f"submission[{FIELD_IDS['contact']}]": contact,
        f"submission[{FIELD_IDS['source']}]": source,
        f"submission[{FIELD_IDS['status']}]": status,
        f"submission[{FIELD_IDS['notes']}]": notes,
    }
    if FIELD_IDS["assigned_rep"] and rep:
        data[f"submission[{FIELD_IDS['assigned_rep']}]"] = rep
    resp = requests.post(f"https://api.jotform.com/form/{FORM_ID}/submissions?apiKey={API_KEY}", data=data)
    return resp.status_code == 200

def update_lead(submission_id, updates: dict):
    url = f"https://api.jotform.com/submission/{submission_id}?apiKey={API_KEY}"
    resp = requests.post(url, data=updates)
    return resp.status_code == 200

# ────────────────────────────────
# TIMESTAMPS & DURATIONS
# ────────────────────────────────

def utcnow_iso():
    return datetime.now(timezone.utc).isoformat()

def parse_dt(x):
    try:
        return pd.to_datetime(x, utc=True)
    except Exception:
        return pd.NaT

def enrich_with_durations(df):
    if df.empty:
        return df.copy()

    out = df.copy()

    # Ensure datetimes
    for col in ["CreatedAt","SurveyScheduledDate","SurveyCompletedDate",
                "ScheduledDate","InstalledDate","WaitingOnCustomerDate"]:
        out[col] = pd.to_datetime(out[col], errors="coerce", utc=True)

    # Helper to calc durations safely
    def duration_days(start, end):
        if pd.isna(start) or pd.isna(end):
            return pd.NA
        return (end - start).days

    out["TotalDaysToInstall"] = [duration_days(s, e) for s, e in zip(out["CreatedAt"], out["InstalledDate"])]
    out["SurveyDuration"]      = [duration_days(s, e) for s, e in zip(out["SurveyScheduledDate"], out["SurveyCompletedDate"])]
    out["SchedulingDuration"]  = [duration_days(s, e) for s, e in zip(out["SurveyCompletedDate"], out["ScheduledDate"])]
    out["InstallWaitDuration"] = [duration_days(s, e) for s, e in zip(out["ScheduledDate"], out["InstalledDate"])]

    return out


def build_timeline_segments(row):
    segs = []
    C, SS, SC, SD, IDT, W = row["CreatedAt"], row["SurveyScheduledDate"], row["SurveyCompletedDate"], row["ScheduledDate"], row["InstalledDate"], row["WaitingOnCustomerDate"]
    def add(stage, start, finish):
        if pd.notna(start) and pd.notna(finish) and finish > start:
            segs.append({"Stage": stage, "Start": start, "Finish": finish})
    add("Initial Contact", C, SS)
    add("Survey", SS, SC)
    add("Scheduling", SC, SD)
    add("Install Wait", SD, IDT)
    if pd.notna(W):
        nexts = [t for t in [SC, SD, IDT] if pd.notna(t) and t > W]
        end = min(nexts) if nexts else datetime.now(timezone.utc)
        add("Waiting on Customer", W, end)
    return pd.DataFrame(segs)

# ────────────────────────────────
# UI
# ────────────────────────────────

st.set_page_config(page_title="Sales Lead Tracker", page_icon="📊", layout="wide")
st.title("📊 Sales Lead Tracker v5")

df_raw = fetch_jotform_data()
df = enrich_with_durations(df_raw)

tab_dash, tab_add, tab_edit, tab_timeline = st.tabs([
    "📋 Dashboard", "➕ Add Lead", "✏️ Edit Lead", "🧭 Timelines"
])

with tab_dash:
    st.subheader("Leads")
    st.dataframe(df, use_container_width=True)

    installs = df.dropna(subset=["TotalDaysToInstall"])
    if not installs.empty:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Avg Days to Install", f"{installs['TotalDaysToInstall'].mean():.1f}")
        col2.metric("Median Days", f"{installs['TotalDaysToInstall'].median():.0f}")
        col3.metric("Fastest", f"{installs['TotalDaysToInstall'].min():.0f}")
        col4.metric("Slowest", f"{installs['TotalDaysToInstall'].max():.0f}")

with tab_add:
    st.subheader("Add New Lead")
    with st.form("add_lead"):
        name = st.text_input("Customer Name")
        contact = st.text_input("Contact Info")
        source = st.selectbox("How they contacted us", ["Email","Social Media","Phone Call","Walk In","In Person"])
        status = st.selectbox("Lead Status", STATUS_OPTIONS)
        notes = st.text_area("Notes")
        submitted = st.form_submit_button("Submit Lead")
        if submitted:
            ok = submit_lead(name, contact, source, status, notes)
            st.success("✅ Lead submitted!") if ok else st.error("❌ Failed to submit lead.")

with tab_edit:
    st.subheader("Update Lead Status")
    if not df.empty:
        df["LeadDisplay"] = df["Name"].fillna("") + " (" + df["Contact"].fillna("") + ")"
        lead_pick = st.selectbox("Select Lead", df["LeadDisplay"])
        rec = df.loc[df["LeadDisplay"] == lead_pick].iloc[0]
        new_status = st.selectbox("New Status", STATUS_OPTIONS)
        if st.button("Update Lead"):
            payload = { f"submission[{FIELD_IDS['status']}]": new_status }
            # timestamp field
            status_to_qid = {
                "Survey Scheduled": FIELD_IDS["survey_scheduled_date"],
                "Survey Completed": FIELD_IDS["survey_completed_date"],
                "Scheduled": FIELD_IDS["scheduled_date"],
                "Installed": FIELD_IDS["installed_date"],
                "Waiting on Customer": FIELD_IDS["waiting_on_customer_date"],
            }
            qid = status_to_qid.get(new_status)
            if qid:
                payload[f"submission[{qid}]"] = utcnow_iso()
            ok = update_lead(rec["SubmissionID"], payload)
            st.success("✅ Lead updated.") if ok else st.error("❌ Failed.")

with tab_timeline:
    st.subheader("Timeline View")
    if not df.empty:
        segs = []
        for _, r in df.iterrows():
            tdf = build_timeline_segments(r)
            if not tdf.empty:
                tdf["Lead"] = r["Name"] or r["Contact"]
                segs.append(tdf)
        if segs:
            gdf = pd.concat(segs, ignore_index=True)
            fig = px.timeline(gdf, x_start="Start", x_end="Finish", y="Lead", color="Stage")
            fig.update_yaxes(autorange="reversed")
            st.plotly_chart(fig, use_container_width=True)
