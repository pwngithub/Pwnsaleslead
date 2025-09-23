
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

STATUS_TO_FIELD_KEY = {
    "Survey Scheduled": "survey_scheduled",
    "Survey Completed": "survey_completed",
    "Scheduled": "scheduled",
    "Installed": "installed",
    "Waiting on Customer": "waiting_on_customer",
}

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
st.set_page_config(page_title="Sales Lead Tracker v19.4", page_icon="🗂️", layout="wide")
st.title("🗂️ Sales Lead Tracker v19.4 — Dynamic Dates + History Timeline")

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

# Sidebar Filters (apply to KPI dashboard only)
st.sidebar.header("Filters")
status_unique = sorted([s for s in df["Status"].dropna().unique().tolist()])
source_unique = sorted([s for s in df["Source"].dropna().unique().tolist()])
status_options = st.sidebar.multiselect("Filter by Status", status_unique, default=status_unique or [], key="filter_status")
source_options = st.sidebar.multiselect("Filter by Source", source_unique, default=source_unique or [], key="filter_source")
sla_only = st.sidebar.checkbox("Show only SLA Breaches", value=False, key="filter_sla")
date_min = st.sidebar.date_input("Start Date", value=pd.to_datetime(df["CreatedAt"]).min().date(), key="filter_start")
date_max = st.sidebar.date_input("End Date", value=pd.to_datetime(df["CreatedAt"]).max().date(), key="filter_end")

filtered = df[df["Status"].isin(status_options) & df["Source"].isin(source_options)]
filtered = filtered[(pd.to_datetime(filtered["CreatedAt"]).dt.date >= date_min) & (pd.to_datetime(filtered["CreatedAt"]).dt.date <= date_max)]
if sla_only:
    breach_mask = (filtered["SurveySLA"].eq("❌") | filtered["SchedulingSLA"].eq("❌") | filtered["InstallSLA"].eq("❌"))
    filtered = filtered[breach_mask]

# ---------- Tabs ----------
tab_add, tab_edit, tab_kpi = st.tabs(["➕ Add Ticket", "✏️ Edit Ticket", "📊 KPI Dashboard"])

# ===== Add Ticket =====
with tab_add:
    st.subheader("Add a New Ticket")
    name = st.text_input("Name", key="add_name")
    source = st.selectbox("Source", SOURCE_LIST, key="add_source")
    status = st.selectbox("Status", STATUS_LIST, key="add_status")

    # auto-set today's date when status changes
    if "add_last_status" not in st.session_state:
        st.session_state.add_last_status = status
    if status != st.session_state.add_last_status:
        st.session_state.add_date_value = date.today()
        st.session_state.add_last_status = status

    # relevant date field only
    fld_key = STATUS_TO_FIELD_KEY[status]
    date_label = f"{status} Date"
    default_date = st.session_state.get("add_date_value", date.today())
    chosen_date = st.date_input(date_label, value=default_date, key=f"add_date_{fld_key}")

    if st.button("💾 Save New Ticket to JotForm", key="add_save"):
        payload = {
            str(FIELD_ID["name"]): name,
            str(FIELD_ID["source"]): source,
            str(FIELD_ID["status"]): status,
            str(FIELD_ID[fld_key]): to_str_date(chosen_date),
        }
        ok, resp = add_submission(payload)
        if ok:
            st.success("✅ Ticket added to JotForm.")
            st.json(resp)
            st.experimental_rerun()
        else:
            st.error("❌ Failed to add ticket.")
            st.write(resp)

# ===== Edit Ticket =====
with tab_edit:
    st.subheader("Edit an Existing Ticket")
    options = df[["SubmissionID","Name","Status","SurveyScheduledDate","SurveyCompletedDate","ScheduledDate","InstalledDate","WaitingOnCustomerDate",
                  "SurveySLA","SchedulingSLA","InstallSLA"]].copy()
    options["label"] = options.apply(lambda r: f"{r['Name'] or 'Unknown'} — {r['Status'] or 'Unknown'} — {r['SubmissionID']}", axis=1)
    sel = st.selectbox("Select a ticket", options["label"].tolist(), key="edit_select")
    if sel:
        row = options[options["label"] == sel].iloc[0]
        sid = row["SubmissionID"]
        curr = df[df["SubmissionID"] == sid].iloc[0]

        # ---- Status History Log (Table) ----
        st.markdown("**Status History** (read-only)")
        hist = pd.DataFrame({
            "Status": ["Survey Scheduled","Survey Completed","Scheduled","Installed","Waiting on Customer"],
            "Date": [
                curr["SurveyScheduledDate"],
                curr["SurveyCompletedDate"],
                curr["ScheduledDate"],
                curr["InstalledDate"],
                curr["WaitingOnCustomerDate"]
            ],
            "SLA Flag": [
                curr["SurveySLA"],
                "",  # no SLA on completed directly
                curr["SchedulingSLA"],
                curr["InstallSLA"],
                ""   # none
            ]
        })
        # Highlight current status row
        def highlight_current(row_):
            return ["background-color: #e8f4ff" if row_["Status"] == curr["Status"] else "" for _ in row_.index]
        st.dataframe(hist.style.apply(highlight_current, axis=1), use_container_width=True)

        # ---- Mini Timeline (Gantt) ----
        segments = []
        # Survey
        if pd.notna(curr["SurveyScheduledDate"]) and pd.notna(curr["SurveyCompletedDate"]):
            segments.append({"Stage":"Survey","Start":curr["SurveyScheduledDate"],"Finish":curr["SurveyCompletedDate"],
                             "Color":"Late" if curr["SurveySLA"]=="❌" else "On Time"})
        # Scheduling
        if pd.notna(curr["SurveyCompletedDate"]) and pd.notna(curr["ScheduledDate"]):
            segments.append({"Stage":"Scheduling","Start":curr["SurveyCompletedDate"],"Finish":curr["ScheduledDate"],
                             "Color":"Late" if curr["SchedulingSLA"]=="❌" else "On Time"})
        # Install Wait
        if pd.notna(curr["ScheduledDate"]) and pd.notna(curr["InstalledDate"]):
            segments.append({"Stage":"Install Wait","Start":curr["ScheduledDate"],"Finish":curr["InstalledDate"],
                             "Color":"Late" if curr["InstallSLA"]=="❌" else "On Time"})
        if segments:
            segdf = pd.DataFrame(segments)
            fig = px.timeline(segdf, x_start="Start", x_end="Finish", y="Stage", color="Color",
                              color_discrete_map={"On Time":"green","Late":"red"})
            fig.update_yaxes(autorange="reversed")
            st.plotly_chart(fig, use_container_width=True)

        # ---- Change Status (only relevant date) ----
        st.markdown("---")
        st.subheader("Change Status")
        new_status = st.selectbox("Edit Status", STATUS_LIST,
            index=STATUS_LIST.index(curr["Status"]) if pd.notna(curr["Status"]) and curr["Status"] in STATUS_LIST else 0,
            key="edit_status")

        # auto set date when status changes
        if "edit_last_status" not in st.session_state:
            st.session_state.edit_last_status = new_status
        if new_status != st.session_state.edit_last_status:
            st.session_state.edit_date_value = date.today()
            st.session_state.edit_last_status = new_status

        fld_key2 = STATUS_TO_FIELD_KEY[new_status]
        date_label2 = f"{new_status} Date"
        existing_date = curr[
            "SurveyScheduledDate" if fld_key2=="survey_scheduled" else
            "SurveyCompletedDate" if fld_key2=="survey_completed" else
            "ScheduledDate" if fld_key2=="scheduled" else
            "InstalledDate" if fld_key2=="installed" else
            "WaitingOnCustomerDate"
        ]
        default_edit_date = st.session_state.get("edit_date_value", (pd.to_datetime(existing_date).date() if pd.notna(existing_date) else date.today()))
        chosen_edit_date = st.date_input(date_label2, value=default_edit_date, key=f"edit_date_{fld_key2}")

        if st.button("💾 Save Changes", key="edit_save"):
            payload = {
                str(FIELD_ID["status"]): new_status,
                str(FIELD_ID[fld_key2]): to_str_date(chosen_edit_date),
            }
            ok, resp_json = update_submission(sid, payload)
            if ok:
                st.success("✅ Updated ticket on JotForm.")
                st.json(resp_json)
                st.experimental_rerun()
            else:
                st.error("❌ Failed to update ticket.")
                st.write(resp_json)

# ===== KPI TAB =====
with tab_kpi:
    st.subheader("📊 KPI Dashboard (Filtered)")
    # SLA Banner
    breach_mask_all = (df["SurveySLA"].eq("❌") | df["SchedulingSLA"].eq("❌") | df["InstallSLA"].eq("❌"))
    breach_count_all = int(breach_mask_all.sum())
    if breach_count_all > 0:
        offenders = df.loc[breach_mask_all, ["SubmissionID","Name","Status"]].head(10)
        st.error(f"🚨 {breach_count_all} ticket(s) are breaching SLA right now!", icon="🚨")
        st.dataframe(offenders, use_container_width=True)
    # Status Overview
    status_counts = filtered["Status"].value_counts()
    if not status_counts.empty:
        cols = st.columns(len(status_counts))
        for i,(status,count) in enumerate(status_counts.items()):
            v = (filtered["SurveySLA"]=="❌").sum() if status=="Survey Scheduled" else \
                (filtered["SchedulingSLA"]=="❌").sum() if status=="Scheduled" else \
                (filtered["InstallSLA"]=="❌").sum() if status=="Installed" else 0
            cols[i].metric(status,f"{count} total",f"{v} late" if v>0 else "On track")
    else:
        st.info("No tickets match filters.")
    # KPI Metrics
    installs = filtered.dropna(subset=["TotalDaysToInstall"])
    if not filtered.empty:
        col1,col2,col3,col4,col5 = st.columns(5)
        if not installs.empty:
            col1.metric("Avg Days to Install",f"{installs['TotalDaysToInstall'].mean():.1f}")
            col2.metric("Median Days",f"{installs['TotalDaysToInstall'].median():.0f}")
            col3.metric("Fastest",f"{installs['TotalDaysToInstall'].min():.0f}")
            col4.metric("Slowest",f"{installs['TotalDaysToInstall'].max():.0f}")
        breaches = (filtered["SurveySLA"].eq("❌")|filtered["SchedulingSLA"].eq("❌")|filtered["InstallSLA"].eq("❌")).sum()
        total=len(filtered); rate=100*(total-breaches)/total if total else 0
        col5.metric("SLA Compliance",f"{rate:.1f}%")
    # Average Duration
    if not filtered.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("Survey Avg (days)", f"{filtered['SurveyDuration'].dropna().mean():.1f}" if filtered['SurveyDuration'].notna().any() else "—")
        c2.metric("Scheduling Avg (days)", f"{filtered['SchedulingDuration'].dropna().mean():.1f}" if filtered['SchedulingDuration'].notna().any() else "—")
        c3.metric("Install Wait Avg (days)", f"{filtered['InstallWaitDuration'].dropna().mean():.1f}" if filtered['InstallWaitDuration'].notna().any() else "—")
    # Funnel
    if not filtered.empty:
        stage_order = STATUS_LIST
        funnel_data = filtered["Status"].value_counts().reindex(stage_order,fill_value=0)
        funnel_df = pd.DataFrame({"Stage":funnel_data.index,"Count":funnel_data.values})
        fig_funnel = px.funnel(funnel_df,x="Count",y="Stage")
        st.plotly_chart(fig_funnel,use_container_width=True)
    # Timelines
    segments=[]
    for _,r in filtered.iterrows():
        if pd.notna(r["SurveyScheduledDate"]) and pd.notna(r["SurveyCompletedDate"]):
            segments.append({"Lead":r["Name"],"Stage":"Survey","Start":r["SurveyScheduledDate"],"Finish":r["SurveyCompletedDate"],
                             "Color":"Late" if r["SurveySLA"]=="❌" else "On Time"})
        if pd.notna(r["SurveyCompletedDate"]) and pd.notna(r["ScheduledDate"]):
            segments.append({"Lead":r["Name"],"Stage":"Scheduling","Start":r["SurveyCompletedDate"],"Finish":r["ScheduledDate"],
                             "Color":"Late" if r["SchedulingSLA"]=="❌" else "On Time"})
        if pd.notna(r["ScheduledDate"]) and pd.notna(r["InstalledDate"]):
            segments.append({"Lead":r["Name"],"Stage":"Install Wait","Start":r["ScheduledDate"],"Finish":r["InstalledDate"],
                             "Color":"Late" if r["InstallSLA"]=="❌" else "On Time"})
    if segments:
        segdf=pd.DataFrame(segments)
        fig_tl=px.timeline(segdf,x_start="Start",x_end="Finish",y="Lead",color="Color",
                           color_discrete_map={"On Time":"green","Late":"red"})
        fig_tl.update_yaxes(autorange="reversed")
        st.plotly_chart(fig_tl,use_container_width=True)
    # Table
    if not filtered.empty:
        show=filtered[["SubmissionID","Name","Source","Status","SurveyDuration","SurveySLA","SchedulingDuration","SchedulingSLA","InstallWaitDuration","InstallSLA","TotalDaysToInstall"]]
        styled = show.style.applymap(color_sla, subset=["SurveySLA","SchedulingSLA","InstallSLA"])
        st.dataframe(styled, use_container_width=True)
