
import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime, date
from streamlit_autorefresh import st_autorefresh
from config import API_KEY, FORM_ID, FIELD_ID

SLA_LIMITS = {"Survey":3,"Scheduling":3,"Install Wait":3}
JOTFORM_API = "https://api.jotform.com"

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
            "CreatedAt": sub.get("created_at"),
            "SurveyScheduledDate": ans.get(str(FIELD_ID["survey_scheduled"]), {}).get("answer"),
            "SurveyCompletedDate": ans.get(str(FIELD_ID["survey_completed"]), {}).get("answer"),
            "ScheduledDate": ans.get(str(FIELD_ID["scheduled"]), {}).get("answer"),
            "InstalledDate": ans.get(str(FIELD_ID["installed"]), {}).get("answer"),
            "WaitingOnCustomerDate": ans.get(str(FIELD_ID["waiting_on_customer"]), {}).get("answer"),
        })
    return pd.DataFrame(records)

def parse_dt(x):
    try:
        return pd.to_datetime(x, errors="coerce", utc=True)
    except Exception:
        return pd.NaT

def duration_days(start,end):
    if pd.isna(start) or pd.isna(end):
        return pd.NA
    return (end-start).days

def enrich_with_sla(df):
    df = df.copy()
    for col in ["CreatedAt","SurveyScheduledDate","SurveyCompletedDate","ScheduledDate","InstalledDate","WaitingOnCustomerDate"]:
        df[col] = df[col].apply(parse_dt)
    df["SurveyDuration"] = [duration_days(s,e) for s,e in zip(df["SurveyScheduledDate"], df["SurveyCompletedDate"])]
    df["SchedulingDuration"] = [duration_days(s,e) for s,e in zip(df["SurveyCompletedDate"], df["ScheduledDate"])]
    df["InstallWaitDuration"] = [duration_days(s,e) for s,e in zip(df["ScheduledDate"], df["InstalledDate"])]
    df["TotalDaysToInstall"] = [duration_days(s,e) for s,e in zip(df["CreatedAt"], df["InstalledDate"])]
    df["SurveySLA"] = df["SurveyDuration"].apply(lambda d:"❌" if pd.notna(d) and d>SLA_LIMITS["Survey"] else "✅")
    df["SchedulingSLA"] = df["SchedulingDuration"].apply(lambda d:"❌" if pd.notna(d) and d>SLA_LIMITS["Scheduling"] else "✅")
    df["InstallSLA"] = df["InstallWaitDuration"].apply(lambda d:"❌" if pd.notna(d) and d>SLA_LIMITS["Install Wait"] else "✅")
    return df

def color_sla(val):
    if val == "❌":
        return "background-color: #ffcccc"
    return ""

def to_str_date(d: date | None):
    if d is None:
        return None
    return d.strftime("%Y-%m-%d")

def update_submission(submission_id: str, payload: dict):
    form = {f"submission[{qid}]": val for qid,val in payload.items() if val is not None}
    url = f"{JOTFORM_API}/submission/{submission_id}?apiKey={API_KEY}"
    resp = requests.post(url, data=form, timeout=30)
    ok = resp.status_code == 200
    return ok, resp.json() if ok else {"status_code": resp.status_code, "text": resp.text}

def add_submission(payload: dict):
    form = {f"submission[{qid}]": val for qid,val in payload.items() if val is not None}
    url = f"{JOTFORM_API}/form/{FORM_ID}/submissions?apiKey={API_KEY}"
    resp = requests.post(url, data=form, timeout=30)
    ok = resp.status_code == 200
    return ok, resp.json() if ok else {"status_code": resp.status_code, "text": resp.text}

st.set_page_config(page_title="Sales Lead Tracker v19", page_icon="🆕", layout="wide")
st.title("🆕 Sales Lead Tracker v19 — Add + Edit Tickets")

# Sidebar controls
refresh_interval = st.sidebar.selectbox("Auto-refresh interval",[30,60,120,300],index=1)
if st.sidebar.button("🔄 Refresh Now"):
    st.experimental_rerun()
st_autorefresh(interval=refresh_interval*1000,key="auto_refresh")

# Ticket Actions Tabs
st.header("🏷 Ticket Actions")
tab_add, tab_edit = st.tabs(["➕ Add Ticket", "✏️ Edit Ticket"])

with tab_add:
    st.subheader("Add a New Ticket")
    name = st.text_input("Name")
    source = st.selectbox("Source", ["Email","Social Media","Phone Call","Walk-in","In Person"])
    status = st.selectbox("Status", ["Survey Scheduled","Survey Completed","Scheduled","Installed","Waiting on Customer"])
    col1, col2, col3 = st.columns(3)
    survey_sched = col1.date_input("Survey Scheduled Date", value=None)
    survey_comp = col1.date_input("Survey Completed Date", value=None)
    scheduled = col2.date_input("Scheduled Date", value=None)
    installed = col2.date_input("Installed Date", value=None)
    waiting_cust = col3.date_input("Waiting on Customer Date", value=None)

    if st.button("💾 Save New Ticket to JotForm"):
        payload = {
            str(FIELD_ID["name"]): name,
            str(FIELD_ID["source"]): source,
            str(FIELD_ID["status"]): status,
            str(FIELD_ID["survey_scheduled"]): to_str_date(survey_sched) if survey_sched else None,
            str(FIELD_ID["survey_completed"]): to_str_date(survey_comp) if survey_comp else None,
            str(FIELD_ID["scheduled"]): to_str_date(scheduled) if scheduled else None,
            str(FIELD_ID["installed"]): to_str_date(installed) if installed else None,
            str(FIELD_ID["waiting_on_customer"]): to_str_date(waiting_cust) if waiting_cust else None,
        }
        ok, resp = add_submission(payload)
        if ok:
            st.success("✅ Ticket added to JotForm.")
            st.json(resp)
            st.experimental_rerun()
        else:
            st.error("❌ Failed to add ticket.")
            st.write(resp)

with tab_edit:
    st.subheader("Edit an Existing Ticket")

    # Load data
    with st.spinner("Loading submissions from JotForm..."):
        df_raw = fetch_jotform_data()
    if df_raw.empty:
        st.warning("⚠️ No data found in JotForm.")
    else:
        df = enrich_with_sla(df_raw)
        options = df[["SubmissionID","Name","Status"]].copy()
        options["label"] = options.apply(lambda r: f"{r['Name'] or 'Unknown'} — {r['Status'] or 'Unknown'} — {r['SubmissionID']}", axis=1)
        sel = st.selectbox("Select a ticket", options["label"].tolist())
        if sel:
            row = options[options["label"] == sel].iloc[0]
            sid = row["SubmissionID"]
            curr = df[df["SubmissionID"] == sid].iloc[0]

            new_status = st.selectbox("Status", ["Survey Scheduled","Survey Completed","Scheduled","Installed","Waiting on Customer"], index=["Survey Scheduled","Survey Completed","Scheduled","Installed","Waiting on Customer"].index(curr["Status"]) if pd.notna(curr["Status"]) else 0)
            colA, colB, colC = st.columns(3)
            survey_sched = colA.date_input("Survey Scheduled Date", value=(pd.to_datetime(curr["SurveyScheduledDate"]).date() if pd.notna(curr["SurveyScheduledDate"]) else date.today()))
            survey_comp  = colA.date_input("Survey Completed Date", value=(pd.to_datetime(curr["SurveyCompletedDate"]).date() if pd.notna(curr["SurveyCompletedDate"]) else date.today()))
            scheduled    = colB.date_input("Scheduled Date", value=(pd.to_datetime(curr["ScheduledDate"]).date() if pd.notna(curr["ScheduledDate"]) else date.today()))
            installed    = colB.date_input("Installed Date", value=(pd.to_datetime(curr["InstalledDate"]).date() if pd.notna(curr["InstalledDate"]) else date.today()))
            waiting_cust = colC.date_input("Waiting on Customer Date", value=(pd.to_datetime(curr["WaitingOnCustomerDate"]).date() if pd.notna(curr["WaitingOnCustomerDate"]) else date.today()))

            if st.button("💾 Save Changes"):
                payload = {
                    str(FIELD_ID["status"]): new_status,
                    str(FIELD_ID["survey_scheduled"]): to_str_date(survey_sched),
                    str(FIELD_ID["survey_completed"]): to_str_date(survey_comp),
                    str(FIELD_ID["scheduled"]): to_str_date(scheduled),
                    str(FIELD_ID["installed"]): to_str_date(installed),
                    str(FIELD_ID["waiting_on_customer"]): to_str_date(waiting_cust),
                }
                ok, resp_json = update_submission(sid, payload)
                if ok:
                    st.success("✅ Updated ticket on JotForm.")
                    st.json(resp_json)
                    st.experimental_rerun()
                else:
                    st.error("❌ Failed to update ticket.")
                    st.write(resp_json)

# The rest of the dashboard is unchanged, reusing the previous logic would go here...
