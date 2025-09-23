
import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from datetime import date
from streamlit_autorefresh import st_autorefresh
from config import API_KEY, FORM_ID, FIELD_ID

SLA_LIMITS = {"Survey":3,"Scheduling":3,"Install Wait":3}
JOTFORM_API = "https://api.jotform.com"
STATUS_LIST = ["Survey Scheduled","Survey Completed","Scheduled","Installed","Waiting on Customer","Lost"]
SOURCE_LIST = ["Email","Social Media","Phone Call","Walk-in","In Person"]

STATUS_TO_FIELD_KEY = {
    "Survey Scheduled": "survey_scheduled",
    "Survey Completed": "survey_completed",
    "Scheduled": "scheduled",
    "Installed": "installed",
    "Waiting on Customer": "waiting_on_customer",
    "Lost": "lost_reason",
}

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
            "CreatedAt": pd.to_datetime(sub.get("created_at"), errors="coerce", utc=True),
            "SurveyScheduledDate": pd.to_datetime(ans.get(str(FIELD_ID["survey_scheduled"]), {}).get("answer"), errors="coerce", utc=True),
            "SurveyCompletedDate": pd.to_datetime(ans.get(str(FIELD_ID["survey_completed"]), {}).get("answer"), errors="coerce", utc=True),
            "ScheduledDate": pd.to_datetime(ans.get(str(FIELD_ID["scheduled"]), {}).get("answer"), errors="coerce", utc=True),
            "InstalledDate": pd.to_datetime(ans.get(str(FIELD_ID["installed"]), {}).get("answer"), errors="coerce", utc=True),
            "WaitingOnCustomerDate": pd.to_datetime(ans.get(str(FIELD_ID["waiting_on_customer"]), {}).get("answer"), errors="coerce", utc=True),
            "LostReason": ans.get(str(FIELD_ID["lost_reason"]), {}).get("answer"),
        })
    return pd.DataFrame(records)

def duration_days(start,end):
    if pd.isna(start) or pd.isna(end):
        return pd.NA
    return (end-start).days

def enrich(df):
    df = df.copy()
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
    return ok, (resp.json() if ok else {"status_code": resp.status_code, "text": resp.text})

def add_submission(payload: dict):
    form = {f"submission[{qid}]": val for qid,val in payload.items() if val is not None}
    url = f"{JOTFORM_API}/form/{FORM_ID}/submissions?apiKey={API_KEY}"
    resp = requests.post(url, data=form, timeout=30)
    ok = resp.status_code == 200
    return ok, (resp.json() if ok else {"status_code": resp.status_code, "text": resp.text})

st.set_page_config(page_title="Sales Lead Tracker v19.6", page_icon="📊", layout="wide")
st.title("📊 Sales Lead Tracker v19.6 — Lost Reason + Full KPIs")

# Sidebar
refresh_interval = st.sidebar.selectbox("Auto-refresh interval",[30,60,120,300],index=1, key="refresh_sel")
if st.sidebar.button("🔄 Refresh Now", key="refresh_btn"):
    st.experimental_rerun()
st_autorefresh(interval=refresh_interval*1000,key="auto_refresh")

with st.spinner("Loading JotForm submissions..."):
    df_raw = fetch_jotform_data()

if df_raw.empty:
    st.warning("⚠️ No data pulled from JotForm yet.")
    st.stop()

df = enrich(df_raw)

# Filters for KPI tab
st.sidebar.header("KPI Filters")
status_unique = sorted([s for s in df["Status"].dropna().unique().tolist()])
source_unique = sorted([s for s in df["Source"].dropna().unique().tolist()])
status_options = st.sidebar.multiselect("Filter by Status", status_unique, default=status_unique or [], key="filter_status")
source_options = st.sidebar.multiselect("Filter by Source", source_unique, default=source_unique or [], key="filter_source")
sla_only = st.sidebar.checkbox("Show only SLA Breaches", value=False, key="filter_sla")

filtered = df[df["Status"].isin(status_options) & df["Source"].isin(source_options)]
if sla_only:
    breach_mask = (filtered["SurveySLA"].eq("❌") | filtered["SchedulingSLA"].eq("❌") | filtered["InstallSLA"].eq("❌"))
    filtered = filtered[breach_mask]

# Tabs: Add | Edit | KPI
tab_add, tab_edit, tab_kpi = st.tabs(["➕ Add Ticket", "✏️ Edit Ticket", "📊 KPI Dashboard"])

# ---------- Add Ticket ----------
with tab_add:
    st.subheader("Add a New Ticket")
    name = st.text_input("Name", key="add_name")
    source = st.selectbox("Source", SOURCE_LIST, key="add_source")
    status = st.selectbox("Status", STATUS_LIST, key="add_status")

    # dynamic field per status
    if status == "Lost":
        lost_reason = st.text_input("Lost Reason", key="add_lost_reason")
        if st.button("💾 Save New Ticket", key="add_save"):
            payload = {
                str(FIELD_ID["name"]): name,
                str(FIELD_ID["source"]): source,
                str(FIELD_ID["status"]): status,
                str(FIELD_ID["lost_reason"]): lost_reason or "Unspecified",
            }
            ok, resp = add_submission(payload)
            if ok:
                st.success("✅ Ticket added.")
                st.json(resp)
                st.experimental_rerun()
            else:
                st.error("❌ Failed to add ticket."); st.write(resp)
    else:
        # show only the relevant date field and default to today
        field_key = STATUS_TO_FIELD_KEY[status]
        date_label = f"{status} Date"
        chosen_date = st.date_input(date_label, value=date.today(), key=f"add_date_{field_key}")
        if st.button("💾 Save New Ticket", key="add_save"):
            payload = {
                str(FIELD_ID["name"]): name,
                str(FIELD_ID["source"]): source,
                str(FIELD_ID["status"]): status,
                str(FIELD_ID[field_key]): to_str_date(chosen_date),
            }
            ok, resp = add_submission(payload)
            if ok:
                st.success("✅ Ticket added.")
                st.json(resp)
                st.experimental_rerun()
            else:
                st.error("❌ Failed to add ticket."); st.write(resp)

# ---------- Edit Ticket ----------
with tab_edit:
    st.subheader("Edit an Existing Ticket")
    options = df[["SubmissionID","Name","Status","SurveyScheduledDate","SurveyCompletedDate","ScheduledDate","InstalledDate","WaitingOnCustomerDate","LostReason",
                  "SurveySLA","SchedulingSLA","InstallSLA"]].copy()
    options["label"] = options.apply(lambda r: f"{r['Name'] or 'Unknown'} — {r['Status'] or 'Unknown'} — {r['SubmissionID']}", axis=1)
    sel = st.selectbox("Select a ticket", options["label"].tolist(), key="edit_select")
    if sel:
        row = options[options["label"] == sel].iloc[0]
        sid = row["SubmissionID"]
        curr = df[df["SubmissionID"] == sid].iloc[0]

        # History table
        hist = pd.DataFrame({
            "Status": ["Survey Scheduled","Survey Completed","Scheduled","Installed","Waiting on Customer","Lost"],
            "Date/Reason": [
                curr["SurveyScheduledDate"],
                curr["SurveyCompletedDate"],
                curr["ScheduledDate"],
                curr["InstalledDate"],
                curr["WaitingOnCustomerDate"],
                curr["LostReason"]
            ]
        })
        st.dataframe(hist, use_container_width=True)

        # Change form
        new_status = st.selectbox("Edit Status", STATUS_LIST,
                                  index=STATUS_LIST.index(curr["Status"]) if pd.notna(curr["Status"]) and curr["Status"] in STATUS_LIST else 0,
                                  key="edit_status")

        if new_status == "Lost":
            new_reason = st.text_input("Lost Reason", value=curr.get("LostReason","") if isinstance(curr.get("LostReason",""), str) else "", key="edit_lost_reason")
            if st.button("💾 Save Changes", key="edit_save"):
                payload = {
                    str(FIELD_ID["status"]): new_status,
                    str(FIELD_ID["lost_reason"]): new_reason or "Unspecified",
                }
                ok, resp_json = update_submission(sid, payload)
                if ok:
                    st.success("✅ Updated."); st.json(resp_json); st.experimental_rerun()
                else:
                    st.error("❌ Update failed."); st.write(resp_json)
        else:
            field_key2 = STATUS_TO_FIELD_KEY[new_status]
            date_label2 = f"{new_status} Date"
            # pick existing if present, else today
            existing = curr[
                "SurveyScheduledDate" if field_key2=="survey_scheduled" else
                "SurveyCompletedDate" if field_key2=="survey_completed" else
                "ScheduledDate" if field_key2=="scheduled" else
                "InstalledDate" if field_key2=="installed" else
                "WaitingOnCustomerDate"
            ]
            default_edit_date = (pd.to_datetime(existing).date() if pd.notna(existing) else date.today())
            chosen_edit_date = st.date_input(date_label2, value=default_edit_date, key=f"edit_date_{field_key2}")
            if st.button("💾 Save Changes", key="edit_save"):
                payload = {
                    str(FIELD_ID["status"]): new_status,
                    str(FIELD_ID[field_key2]): to_str_date(chosen_edit_date),
                }
                ok, resp_json = update_submission(sid, payload)
                if ok:
                    st.success("✅ Updated."); st.json(resp_json); st.experimental_rerun()
                else:
                    st.error("❌ Update failed."); st.write(resp_json)

# ---------- KPI Dashboard ----------
with tab_kpi:
    st.subheader("📊 KPI Dashboard (Filtered)")
    # SLA Banner
    breach_mask_all = (df["SurveySLA"].eq("❌") | df["SchedulingSLA"].eq("❌") | df["InstallSLA"].eq("❌"))
    breach_count_all = int(breach_mask_all.sum()); st.write(f"🚨 SLA Breaches: {breach_count_all}")

    # Status Overview
    status_counts = filtered["Status"].value_counts().reindex(STATUS_LIST, fill_value=0)
    st.bar_chart(status_counts)

    # KPI metrics
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

    # Source analytics
    st.markdown("### Source Analytics")
    by_src = filtered.groupby("Source").agg(
        Leads=("SubmissionID","count"),
        Installed=("InstalledDate", lambda s: s.notna().sum()),
        AvgInstallDays=("TotalDaysToInstall", "mean"),
    ).reset_index()
    by_src["Conversion%"] = (100*by_src["Installed"]/by_src["Leads"]).round(1)
    st.dataframe(by_src, use_container_width=True)

    # Lost analytics
    st.markdown("### Lost Leads")
    lost = filtered[filtered["Status"]=="Lost"]
    c1,c2,c3 = st.columns(3)
    c1.metric("Total Lost", len(lost))
    if not lost.empty:
        lost_by_source = lost["Source"].value_counts().reset_index()
        lost_by_source.columns = ["Source","Lost"]
        st.bar_chart(lost_by_source.set_index("Source"))

        reasons = lost["LostReason"].fillna("Unspecified").value_counts()
        fig = px.pie(values=reasons.values, names=reasons.index, title="Lost Reasons")
        st.plotly_chart(fig, use_container_width=True)

    # Export filtered
    st.download_button("⬇️ Download Filtered CSV", data=filtered.to_csv(index=False), file_name="filtered_tickets.csv", mime="text/csv")

    # Table
    show_cols = ["SubmissionID","Name","Source","Status","LostReason","SurveyDuration","SurveySLA","SchedulingDuration","SchedulingSLA","InstallWaitDuration","InstallSLA","TotalDaysToInstall"]
    styled = filtered[show_cols].style.applymap(color_sla, subset=["SurveySLA","SchedulingSLA","InstallSLA"])
    st.dataframe(styled, use_container_width=True)
