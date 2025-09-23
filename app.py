
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
}

STATUS_OPTIONS = [
    "Survey Scheduled",
    "Survey Completed",
    "Scheduled",
    "Installed",
    "Waiting on Customer",
]

SLA_LIMITS = {
    "Survey": 3,
    "Scheduling": 3,
    "Install Wait": 3,
}

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
        })
    return pd.DataFrame(rows)

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
        return pd.to_datetime(x, errors="coerce", utc=True)
    except Exception:
        return pd.NaT

def duration_days(start, end):
    if pd.isna(start) or pd.isna(end):
        return pd.NA
    return (end - start).days

def enrich_with_durations(df):
    if df.empty:
        return df.copy()
    out = df.copy()
    for col in ["CreatedAt","SurveyScheduledDate","SurveyCompletedDate","ScheduledDate","InstalledDate","WaitingOnCustomerDate"]:
        out[col] = out[col].apply(parse_dt)
    out["SurveyDuration"]      = [duration_days(s, e) for s, e in zip(out["SurveyScheduledDate"], out["SurveyCompletedDate"])]
    out["SchedulingDuration"]  = [duration_days(s, e) for s, e in zip(out["SurveyCompletedDate"], out["ScheduledDate"])]
    out["InstallWaitDuration"] = [duration_days(s, e) for s, e in zip(out["ScheduledDate"], out["InstalledDate"])]
    out["TotalDaysToInstall"]  = [duration_days(s, e) for s, e in zip(out["CreatedAt"], out["InstalledDate"])]
    return out

def check_sla(duration, stage):
    limit = SLA_LIMITS.get(stage)
    if pd.isna(duration):
        return "N/A"
    return "✅" if duration <= limit else f"❌ ({duration}>{limit})"

def build_timeline_segments(row):
    segs = []
    def add(stage, start, finish, duration):
        if pd.notna(start) and pd.notna(finish) and finish > start:
            breach = (duration is not pd.NA and duration > SLA_LIMITS.get(stage, 999))
            segs.append({"Stage": stage, "Start": start, "Finish": finish, "Breach": breach})
    add("Survey", row["SurveyScheduledDate"], row["SurveyCompletedDate"], row["SurveyDuration"])
    add("Scheduling", row["SurveyCompletedDate"], row["ScheduledDate"], row["SchedulingDuration"])
    add("Install Wait", row["ScheduledDate"], row["InstalledDate"], row["InstallWaitDuration"])
    return pd.DataFrame(segs)

# ────────────────────────────────
# UI
# ────────────────────────────────

st.set_page_config(page_title="Sales Lead Tracker v6", page_icon="📊", layout="wide")
st.title("📊 Sales Lead Tracker v6 with SLA Tracking")

df_raw = fetch_jotform_data()
df = enrich_with_durations(df_raw)

tab_dash, tab_ticket, tab_timeline, tab_export = st.tabs([
    "📋 Dashboard", "🎫 Ticket Detail", "🧭 Timelines", "📤 Export"
])

with tab_dash:
    st.subheader("All Leads")
    st.dataframe(df, use_container_width=True)
    installs = df.dropna(subset=["TotalDaysToInstall"])
    if not installs.empty:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Avg Days to Install", f"{installs['TotalDaysToInstall'].mean():.1f}")
        col2.metric("Median Days", f"{installs['TotalDaysToInstall'].median():.0f}")
        col3.metric("Fastest", f"{installs['TotalDaysToInstall'].min():.0f}")
        col4.metric("Slowest", f"{installs['TotalDaysToInstall'].max():.0f}")

with tab_ticket:
    st.subheader("Ticket Detail View")
    if not df.empty:
        df["LeadDisplay"] = df["Name"].fillna("") + " (" + df["Contact"].fillna("") + ")"
        lead = st.selectbox("Select Lead", df["LeadDisplay"])
        row = df.loc[df["LeadDisplay"] == lead].iloc[0]

        st.write(f"**CreatedAt:** {row['CreatedAt']}")
        st.write(f"**Survey Scheduled:** {row['SurveyScheduledDate']} → Duration {row['SurveyDuration']}d {check_sla(row['SurveyDuration'],'Survey')}")
        st.write(f"**Survey Completed:** {row['SurveyCompletedDate']}")
        st.write(f"**Scheduled:** {row['ScheduledDate']} → Duration {row['SchedulingDuration']}d {check_sla(row['SchedulingDuration'],'Scheduling')}")
        st.write(f"**Installed:** {row['InstalledDate']} → Duration {row['InstallWaitDuration']}d {check_sla(row['InstallWaitDuration'],'Install Wait')}")
        st.write(f"**Total Time:** {row['TotalDaysToInstall']} days")
    else:
        st.info("No leads found.")

with tab_timeline:
    st.subheader("Timelines")
    if not df.empty:
        segs = []
        for _, r in df.iterrows():
            tdf = build_timeline_segments(r)
            if not tdf.empty:
                tdf["Lead"] = r["Name"] or r["Contact"]
                segs.append(tdf)
        if segs:
            gdf = pd.concat(segs, ignore_index=True)
            color = gdf["Breach"].map({True:"red",False:"green"})
            fig = px.timeline(gdf, x_start="Start", x_end="Finish", y="Lead", color="Stage")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No timeline data.")
    else:
        st.info("No leads found.")

with tab_export:
    st.subheader("Export SLA Report")
    if not df.empty:
        export_df = df.copy()
        # Convert datetime columns to strings
        for col in ["CreatedAt","SurveyScheduledDate","SurveyCompletedDate",
                    "ScheduledDate","InstalledDate","WaitingOnCustomerDate"]:
            if col in export_df.columns:
                export_df[col] = export_df[col].astype(str).replace("NaT", "")
        # Replace NA with empty
        export_df = export_df.fillna("")

        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as xw:
            export_df.to_excel(xw, index=False, sheet_name="Leads")

        st.download_button(
            "📥 Download SLA Report (Excel)",
            output.getvalue(),
            "sla_report.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("No data to export.")
