
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timezone
from streamlit_autorefresh import st_autorefresh

SLA_LIMITS = {"Survey":3,"Scheduling":3,"Install Wait":3}

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

def highlight_breach(row):
    if "❌" in row.values:
        return ["background-color: #ffcccc"]*len(row)
    return [""]*len(row)

st.set_page_config(page_title="Sales Lead Tracker v13", page_icon="📊", layout="wide")
st.title("📊 Sales Lead Tracker v13 — Dynamic KPI Updates with Filters")

# Sidebar controls
refresh_interval = st.sidebar.selectbox("Auto-refresh interval",[30,60,120,300],index=1)
refresh_now = st.sidebar.button("🔄 Refresh Now")
if refresh_now:
    st.experimental_rerun()
st_autorefresh(interval=refresh_interval*1000,key="auto_refresh")

df = pd.read_csv("sample_tickets.csv")
df = enrich_with_sla(df)

# Sidebar Filters
st.sidebar.header("Filters")
status_options = st.sidebar.multiselect("Filter by Status", df["Status"].unique().tolist(), default=df["Status"].unique().tolist())
source_options = st.sidebar.multiselect("Filter by Source", df["Source"].unique().tolist(), default=df["Source"].unique().tolist())
sla_only = st.sidebar.checkbox("Show only SLA Breaches", value=False)
date_min = st.sidebar.date_input("Start Date", value=pd.to_datetime(df["CreatedAt"]).min().date())
date_max = st.sidebar.date_input("End Date", value=pd.to_datetime(df["CreatedAt"]).max().date())

# Apply filters
filtered = df[df["Status"].isin(status_options) & df["Source"].isin(source_options)]
filtered = filtered[(pd.to_datetime(filtered["CreatedAt"]).dt.date >= date_min) & (pd.to_datetime(filtered["CreatedAt"]).dt.date <= date_max)]
if sla_only:
    breach_mask = (filtered["SurveySLA"].eq("❌") | filtered["SchedulingSLA"].eq("❌") | filtered["InstallSLA"].eq("❌"))
    filtered = filtered[breach_mask]

# 🔔 SLA Banner Alert
breach_mask_all = (df["SurveySLA"].eq("❌") | df["SchedulingSLA"].eq("❌") | df["InstallSLA"].eq("❌"))
breach_count_all = int(breach_mask_all.sum())
if breach_count_all > 0:
    offenders = df.loc[breach_mask_all, ["Name","Status"]].head(10)
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

# KPI Metrics (live with filters)
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
    show=filtered[["Name","Contact","Source","Status","SurveyDuration","SurveySLA","SchedulingDuration","SchedulingSLA","InstallWaitDuration","InstallSLA","TotalDaysToInstall"]]
    styled=show.style.apply(highlight_breach,axis=1)
    st.dataframe(styled,use_container_width=True)
else:
    st.info("No tickets to show for current filters.")

st.caption(f"🔄 Auto-refresh every {refresh_interval} seconds. Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
