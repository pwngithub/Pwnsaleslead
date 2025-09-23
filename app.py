
import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from config import API_KEY, FORM_ID, FIELD_ID

STATUS_LIST = [
    "Survey Scheduled",
    "Survey Completed",
    "Scheduled",
    "Installed",
    "Waiting on Customer",
    "Lost"
]

JOTFORM_API = "https://api.jotform.com"

def fetch_jotform_data():
    url = f"{JOTFORM_API}/form/{FORM_ID}/submissions?apikey={API_KEY}"
    r = requests.get(url)
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
            "LostReason": ans.get(str(FIELD_ID["lost_reason"]), {}).get("answer")
        })
    return pd.DataFrame(records)

st.title("Sales Lead Tracker v19.5 with Lost Reason")

df = fetch_jotform_data()
if df.empty:
    st.warning("No data found.")
else:
    st.dataframe(df)

    # KPI: Lost Leads
    lost_df = df[df["Status"]=="Lost"]
    if not lost_df.empty:
        st.subheader("📉 Lost Leads Analysis")
        st.metric("Total Lost Leads", len(lost_df))

        # By source
        st.bar_chart(lost_df["Source"].value_counts())

        # By reason
        lost_reasons = lost_df["LostReason"].value_counts()
        fig = px.pie(lost_reasons, names=lost_reasons.index, values=lost_reasons.values, title="Lost Reasons")
        st.plotly_chart(fig, use_container_width=True)
