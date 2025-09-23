
import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime, date
from streamlit_autorefresh import st_autorefresh
from config import API_KEY, FORM_ID, FIELD_ID

SLA_LIMITS = {"Survey":3,"Scheduling":3,"Install Wait":3}
JOTFORM_API = "https://api.jotform.com"
STATUS_LIST = ["Survey Scheduled","Survey Completed","Scheduled","Installed","Waiting on Customer"]
SOURCE_LIST = ["Email","Social Media","Phone Call","Walk-in","In Person"]

# ---------- Data helpers ----------
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

# ---------- Page ----------
st.set_page_config(page_title="Sales Lead Tracker v19.2", page_icon="📊", layout="wide")
st.title("📊 Sales Lead Tracker v19.2 — KPI on Top + Ticket Actions")

# Sidebar controls
refresh_interval = st.sidebar.selectbox("Auto-refresh interval",[30,60,120,300],index=1, key="refresh_sel")
if st.sidebar.button("🔄 Refresh Now", key="refresh_btn"):
    st.experimental_rerun()
st_autorefresh(interval=refresh_interval*1000,key="auto_refresh")

# Load data
with st.spinner("Loading submissions from JotForm..."):
    df_raw = fetch_jotform_data()

if df_raw.empty:
    st.warning("⚠️ No data pulled from JotForm yet.")
    st.stop()

df = enrich_with_sla(df_raw)

# Sidebar Filters (apply to dashboard and mini KPI)
st.sidebar.header("Filters")
status_unique = sorted([s for s in df["Status"].dropna().unique().tolist()])
source_unique = sorted([s for s in df["Source"].dropna().unique().tolist()])
status_options = st.sidebar.multiselect("Filter by Status", status_unique, default=status_unique or [], key="filter_status")
source_options = st.sidebar.multiselect("Filter by Source", source_unique, default=source_unique or [], key="filter_source")
sla_only = st.sidebar.checkbox("Show only SLA Breaches", value=False, key="filter_sla")
date_min = st.sidebar.date_input("Start Date", value=pd.to_datetime(df["CreatedAt"]).min().date(), key="filter_start")
date_max = st.sidebar.date_input("End Date", value=pd.to_datetime(df["CreatedAt"]).max().date(), key="filter_end")

# Apply filters
filtered = df[df["Status"].isin(status_options) & df["Source"].isin(source_options)]
filtered = filtered[(pd.to_datetime(filtered["CreatedAt"]).dt.date >= date_min) & (pd.to_datetime(filtered["CreatedAt"]).dt.date <= date_max)]
if sla_only:
    breach_mask = (filtered["SurveySLA"].eq("❌") | filtered["SchedulingSLA"].eq("❌") | filtered["InstallSLA"].eq("❌"))
    filtered = filtered[breach_mask]

# ---------- KPI Dashboard (TOP) ----------
# SLA Banner Alert
breach_mask_all = (df["SurveySLA"].eq("❌") | df["SchedulingSLA"].eq("❌") | df["InstallSLA"].eq("❌"))
breach_count_all = int(breach_mask_all.sum())
if breach_count_all > 0:
    offenders = df.loc[breach_mask_all, ["SubmissionID","Name","Status"]].head(10)
    st.error(f"🚨 {breach_count_all} ticket(s) are breaching SLA right now!", icon="🚨")
    st.dataframe(offenders, use_container_width=True)

# Status Overview
st.subheader("🔎 Status Overview (Filtered)")
status_counts = filtered["Status"].value_counts()
violations = {
    "Survey Scheduled": (filtered["SurveySLA"]=="❌").sum(),
    "Survey Completed": 0,
    "Scheduled": (filtered["SchedulingSLA"]=="❌").sum(),
    "Installed": (filtered["InstallSLA"]=="❌").sum(),
    "Waiting on Customer": 0,
}
if not status_counts.empty:
    cols = st.columns(len(status_counts))
    for i,(status,count) in enumerate(status_counts.items()):
        v = violations.get(status,0)
        cols[i].metric(status,f"{count} total",f"{v} late" if v>0 else "On track")
else:
    st.info("No tickets match filters.")

# KPI Metrics
st.subheader("📈 KPI Metrics (Filtered — Live Updates)")
if not filtered.empty:
    installs = filtered.dropna(subset=["TotalDaysToInstall"])
    col1,col2,col3,col4,col5 = st.columns(5)
    if not installs.empty:
        col1.metric("Avg Days to Install",f"{installs['TotalDaysToInstall'].mean():.1f}")
        col2.metric("Median Days",f"{installs['TotalDaysToInstall'].median():.0f}")
        col3.metric("Fastest",f"{installs['TotalDaysToInstall'].min():.0f}")
        col4.metric("Slowest",f"{installs['TotalDaysToInstall'].max():.0f}")
    breaches = (filtered["SurveySLA"].eq("❌")|filtered["SchedulingSLA"].eq("❌")|filtered["InstallSLA"].eq("❌")).sum()
    total=len(filtered); rate=100*(total-breaches)/total if total else 0
    col5.metric("SLA Compliance",f"{rate:.1f}%")
else:
    st.info("No KPI data — no tickets match filters.")

# Average Duration per Status
st.subheader("⏱ Average Duration by Status (Filtered)")
if not filtered.empty:
    c1, c2, c3 = st.columns(3)
    c1.metric("Survey Avg (days)", f"{filtered['SurveyDuration'].dropna().mean():.1f}" if filtered['SurveyDuration'].notna().any() else "—")
    c2.metric("Scheduling Avg (days)", f"{filtered['SchedulingDuration'].dropna().mean():.1f}" if filtered['SchedulingDuration'].notna().any() else "—")
    c3.metric("Install Wait Avg (days)", f"{filtered['InstallWaitDuration'].dropna().mean():.1f}" if filtered['InstallWaitDuration'].notna().any() else "—")
else:
    st.info("No duration data — no tickets match filters.")

# Funnel
st.subheader("🔻 Funnel View (Filtered)")
if not filtered.empty:
    stage_order = ["Survey Scheduled","Survey Completed","Scheduled","Installed","Waiting on Customer"]
    funnel_data = filtered["Status"].value_counts().reindex(stage_order,fill_value=0)
    funnel_df = pd.DataFrame({"Stage":funnel_data.index,"Count":funnel_data.values})
    fig_funnel = px.funnel(funnel_df,x="Count",y="Stage")
    st.plotly_chart(fig_funnel,use_container_width=True)
else:
    st.info("No funnel data for current filters.")

# Timelines
st.subheader("🧭 SLA Timelines (Filtered)")
segments=[]
for _,r in filtered.iterrows():
    if pd.notna(r["SurveyScheduledDate"]) and pd.notna(r["SurveyCompletedDate"]):
        segments.append({"Lead":r["Name"],"Stage":"Survey","Start":r["SurveyScheduledDate"],"Finish":r["SurveyCompletedDate"],"Color":"red" if r["SurveySLA"]=="❌" else "green"})
    if pd.notna(r["SurveyCompletedDate"]) and pd.notna(r["ScheduledDate"]):
        segments.append({"Lead":r["Name"],"Stage":"Scheduling","Start":r["SurveyCompletedDate"],"Finish":r["ScheduledDate"],"Color":"red" if r["SchedulingSLA"]=="❌" else "green"})
    if pd.notna(r["ScheduledDate"]) and pd.notna(r["InstalledDate"]):
        segments.append({"Lead":r["Name"],"Stage":"Install Wait","Start":r["ScheduledDate"],"Finish":r["InstalledDate"],"Color":"red" if r["InstallSLA"]=="❌" else "green"})
if segments:
    segdf=pd.DataFrame(segments)
    fig_tl=px.timeline(segdf,x_start="Start",x_end="Finish",y="Lead",color="Color",facet_row="Stage")
    fig_tl.update_yaxes(autorange="reversed")
    st.plotly_chart(fig_tl,use_container_width=True)
else:
    st.info("No timeline data for current filters.")

# Table
st.subheader("📋 Ticket Table with SLA (Filtered & Highlighted)")
if not filtered.empty:
    show=filtered[["SubmissionID","Name","Source","Status","SurveyDuration","SurveySLA","SchedulingDuration","SchedulingSLA","InstallWaitDuration","InstallSLA","TotalDaysToInstall"]]
    styled = show.style.applymap(color_sla, subset=["SurveySLA","SchedulingSLA","InstallSLA"])
    st.dataframe(styled, use_container_width=True)
else:
    st.info("No tickets to show for current filters.")

# ---------- Ticket Actions (BOTTOM) ----------
st.header("🏷 Ticket Actions")
tab_add, tab_edit = st.tabs(["➕ Add Ticket", "✏️ Edit Ticket"])

with tab_add:
    # Mini KPI summary (uses same filtered df)
    st.subheader("📌 Mini KPI (Filtered)")
    t_total = len(filtered)
    t_breaches = int((filtered["SurveySLA"].eq("❌")|filtered["SchedulingSLA"].eq("❌")|filtered["InstallSLA"].eq("❌")).sum())
    t_rate = (100*(t_total - t_breaches)/t_total) if t_total else 0
    m1, m2, m3 = st.columns(3)
    m1.metric("Tickets (filtered)", t_total)
    m2.metric("SLA Compliance", f"{t_rate:.1f}%")
    m3.metric("SLA Breaches", t_breaches)

    st.subheader("Add a New Ticket")
    name = st.text_input("Name", key="add_name")
    source = st.selectbox("Source", SOURCE_LIST, key="add_source")
    status = st.selectbox("Status", STATUS_LIST, key="add_status")
    col1, col2, col3 = st.columns(3)
    survey_sched = col1.date_input("Survey Scheduled Date", value=None, key="add_survey_sched")
    survey_comp = col1.date_input("Survey Completed Date", value=None, key="add_survey_comp")
    scheduled = col2.date_input("Scheduled Date", value=None, key="add_scheduled")
    installed = col2.date_input("Installed Date", value=None, key="add_installed")
    waiting_cust = col3.date_input("Waiting on Customer Date", value=None, key="add_waiting")

    if st.button("💾 Save New Ticket to JotForm", key="add_save"):
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
    options = df[["SubmissionID","Name","Status"]].copy()
    options["label"] = options.apply(lambda r: f"{r['Name'] or 'Unknown'} — {r['Status'] or 'Unknown'} — {r['SubmissionID']}", axis=1)
    sel = st.selectbox("Select a ticket", options["label"].tolist(), key="edit_select")
    if sel:
        row = options[options["label"] == sel].iloc[0]
        sid = row["SubmissionID"]
        curr = df[df["SubmissionID"] == sid].iloc[0]

        new_status = st.selectbox("Edit Status", STATUS_LIST, 
            index=STATUS_LIST.index(curr["Status"]) if pd.notna(curr["Status"]) and curr["Status"] in STATUS_LIST else 0,
            key="edit_status")

        colA, colB, colC = st.columns(3)
        survey_sched = colA.date_input("Survey Scheduled Date", value=(pd.to_datetime(curr["SurveyScheduledDate"]).date() if pd.notna(curr["SurveyScheduledDate"]) else date.today()), key="edit_survey_sched")
        survey_comp  = colA.date_input("Survey Completed Date", value=(pd.to_datetime(curr["SurveyCompletedDate"]).date() if pd.notna(curr["SurveyCompletedDate"]) else date.today()), key="edit_survey_comp")
        scheduled    = colB.date_input("Scheduled Date", value=(pd.to_datetime(curr["ScheduledDate"]).date() if pd.notna(curr["ScheduledDate"]) else date.today()), key="edit_scheduled")
        installed    = colB.date_input("Installed Date", value=(pd.to_datetime(curr["InstalledDate"]).date() if pd.notna(curr["InstalledDate"]) else date.today()), key="edit_installed")
        waiting_cust = colC.date_input("Waiting on Customer Date", value=(pd.to_datetime(curr["WaitingOnCustomerDate"]).date() if pd.notna(curr["WaitingOnCustomerDate"]) else date.today()), key="edit_waiting")

        if st.button("💾 Save Changes", key="edit_save"):
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
