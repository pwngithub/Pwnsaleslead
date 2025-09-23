
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timezone

SLA_LIMITS = {
    "Survey": 3,
    "Scheduling": 3,
    "Install Wait": 3,
}

def parse_dt(x):
    try:
        return pd.to_datetime(x, errors="coerce", utc=True)
    except Exception:
        return pd.NaT

def duration_days(start, end):
    if pd.isna(start) or pd.isna(end):
        return pd.NA
    return (end - start).days

def enrich_with_sla(df):
    df = df.copy()
    for col in ["CreatedAt","SurveyScheduledDate","SurveyCompletedDate","ScheduledDate","InstalledDate","WaitingOnCustomerDate"]:
        df[col] = df[col].apply(parse_dt)
    df["SurveyDuration"] = [duration_days(s,e) for s,e in zip(df["SurveyScheduledDate"], df["SurveyCompletedDate"])]
    df["SchedulingDuration"] = [duration_days(s,e) for s,e in zip(df["SurveyCompletedDate"], df["ScheduledDate"])]
    df["InstallWaitDuration"] = [duration_days(s,e) for s,e in zip(df["ScheduledDate"], df["InstalledDate"])]
    df["TotalDaysToInstall"] = [duration_days(s,e) for s,e in zip(df["CreatedAt"], df["InstalledDate"])]
    df["SurveySLA"] = df["SurveyDuration"].apply(lambda d: "❌" if pd.notna(d) and d>SLA_LIMITS["Survey"] else "✅")
    df["SchedulingSLA"] = df["SchedulingDuration"].apply(lambda d: "❌" if pd.notna(d) and d>SLA_LIMITS["Scheduling"] else "✅")
    df["InstallSLA"] = df["InstallWaitDuration"].apply(lambda d: "❌" if pd.notna(d) and d>SLA_LIMITS["Install Wait"] else "✅")
    return df

st.set_page_config(page_title="Sales Lead Tracker v7", page_icon="📊", layout="wide")
st.title("📊 Sales Lead Tracker v7 — Status First Dashboard")

# Load sample tickets
df = pd.read_csv("sample_tickets.csv")
df = enrich_with_sla(df)

# Status Summary
st.subheader("🔎 Status Overview")
status_counts = df["Status"].value_counts()
violations = {
    "Survey Scheduled": (df["SurveySLA"]=="❌").sum(),
    "Survey Completed": 0, # no SLA here
    "Scheduled": (df["SchedulingSLA"]=="❌").sum(),
    "Installed": (df["InstallSLA"]=="❌").sum(),
    "Waiting on Customer": 0,
}
cols = st.columns(len(status_counts))
for i,(status,count) in enumerate(status_counts.items()):
    v = violations.get(status,0)
    cols[i].metric(status, f"{count} total", f"{v} late" if v>0 else "On track")

# KPI Wrap
st.subheader("📈 KPI Metrics")
installs = df.dropna(subset=["TotalDaysToInstall"])
if not installs.empty:
    col1,col2,col3,col4,col5 = st.columns(5)
    col1.metric("Avg Days to Install", f"{installs['TotalDaysToInstall'].mean():.1f}")
    col2.metric("Median Days", f"{installs['TotalDaysToInstall'].median():.0f}")
    col3.metric("Fastest", f"{installs['TotalDaysToInstall'].min():.0f}")
    col4.metric("Slowest", f"{installs['TotalDaysToInstall'].max():.0f}")
    breaches = (df["SurveySLA"].eq("❌") | df["SchedulingSLA"].eq("❌") | df["InstallSLA"].eq("❌")).sum()
    total = len(df)
    rate = 100*(total-breaches)/total if total else 0
    col5.metric("SLA Compliance", f"{rate:.1f}%")

# Ticket Table
st.subheader("📋 Ticket Table with SLA")
show = df[["Name","Contact","Status","SurveyDuration","SurveySLA","SchedulingDuration","SchedulingSLA","InstallWaitDuration","InstallSLA","TotalDaysToInstall"]]
st.dataframe(show, use_container_width=True)
