
import streamlit as st
import pandas as pd
import requests
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

        def get_ts(fid):
            val = ans.get(str(fid), {}).get("answer")
            return val if isinstance(val, str) else None

        records.append({
            "SubmissionID": sub.get("id"),
            "Name": name_val if name_val else f"Unnamed ({sub.get('id')})",
            "Source": ans.get(str(FIELD_ID["source"]), {}).get("answer"),
            "Status": ans.get(str(FIELD_ID["status"]), {}).get("answer"),
            "ServiceType": ans.get(str(FIELD_ID["service_type"]), {}).get("answer"),
            "LostReason": ans.get(str(FIELD_ID["lost_reason"]), {}).get("answer"),
            "ts_survey_scheduled": get_ts(FIELD_ID["survey_scheduled"]),
            "ts_survey_completed": get_ts(FIELD_ID["survey_completed"]),
            "ts_scheduled": get_ts(FIELD_ID["scheduled"]),
            "ts_installed": get_ts(FIELD_ID["installed"]),
            "ts_waiting": get_ts(FIELD_ID["waiting_on_customer"]),
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

def add_submission(payload: dict):
    form = {}
    for qid, val in payload.items():
        if qid == FIELD_ID["name"] and isinstance(val, str):
            parts = val.split(" ", 1)
            form[f"submission[{qid}][first]"] = parts[0]
            form[f"submission[{qid}][last]"] = parts[1] if len(parts) > 1 else ""
        else:
            if val is not None:
                form[f"submission[{qid}]"] = val
    url = f"{JOTFORM_API}/form/{FORM_ID}/submissions?apiKey={API_KEY}"
    resp = requests.post(url, data=form, timeout=30)
    return resp.status_code == 200, resp.text

def replace_submission(sub_id, payload: dict):
    del_url = f"{JOTFORM_API}/submission/{sub_id}?apiKey={API_KEY}"
    requests.delete(del_url, timeout=30)
    return add_submission(payload)

def build_status_timestamp(status: str) -> dict:
    now = datetime.now().isoformat()
    stamps = {}
    fid = STATUS_TO_FIELD.get(status)
    if fid:
        stamps[fid] = now
    return stamps

st.set_page_config(page_title="Sales Lead Tracker v19.10.0", page_icon="📊", layout="wide")
st.title("📊 Sales Lead Tracker v19.10.0 — Pipeline & Reminders")

settings = load_settings()
blocked_words = settings.get("blocked_words", DEFAULT_BLOCKED)
reminder_days = int(settings.get("reminder_days", 3))

if st.button("🔄 Refresh Tickets"):
    st.session_state["refresh"] = True

df = fetch_jotform_data()
df, hidden_count = apply_blocklist(df, blocked_words)

st.caption(f"Last synced from JotForm: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
if hidden_count > 0:
    st.info(f"ℹ️ {hidden_count} tickets hidden (blocked words: {', '.join(blocked_words)})")

tab_all, tab_pipeline, tab_reminders, tab_kpi, tab_settings = st.tabs(
    ["📋 All Tickets", "🗂 Pipeline", "⏰ Reminders", "📊 KPI Dashboard", "⚙️ Settings"]
)

with tab_all:
    st.subheader("All Tickets")
    if df.empty:
        st.info("No tickets available.")
    else:
        st.dataframe(df[["Name","Source","Status","ServiceType","LostReason"]])

with tab_pipeline:
    st.subheader("🗂 Pipeline (drag/drop-style)")
    if df.empty:
        st.info("No tickets available.")
    else:
        cols = st.columns(5)
        status_cols = ["Survey Scheduled","Survey Completed","Scheduled","Installed","Waiting on Customer"]
        for i, status in enumerate(status_cols):
            with cols[i]:
                st.markdown(f"**{status}**")
                col_df = df[df["Status"] == status]
                if col_df.empty:
                    st.caption("—")
                for _, row in col_df.iterrows():
                    with st.expander(row["Name"], expanded=False):
                        st.write(f"Source: {row['Source']}")
                        st.write(f"Service: {row['ServiceType']}")
                        new_status = st.selectbox("Move to", STATUS_LIST, index=STATUS_LIST.index(status), key=f"mv_{row['SubmissionID']}")
                        if st.button("Move", key=f"btn_{row['SubmissionID']}"):
                            payload = {
                                FIELD_ID["name"]: row["Name"],
                                FIELD_ID["source"]: row["Source"],
                                FIELD_ID["status"]: new_status,
                                FIELD_ID["service_type"]: row["ServiceType"],
                                FIELD_ID["lost_reason"]: row["LostReason"],
                            }
                            payload.update(build_status_timestamp(new_status))
                            ok, msg = replace_submission(row["SubmissionID"], payload)
                            if ok:
                                st.success("Moved ✔")
                                st.rerun()
                            else:
                                st.error(f"Failed to move: {msg}")

with tab_reminders:
    st.subheader("⏰ Follow-up Reminders")
    if df.empty:
        st.info("No tickets available.")
    else:
        def last_ts(row):
            ts_fields = ["ts_survey_scheduled","ts_survey_completed","ts_scheduled","ts_installed","ts_waiting"]
            vals = [row[f] for f in ts_fields if pd.notna(row[f])]
            if not vals:
                return None
            try:
                parsed = [pd.to_datetime(v, errors="coerce") for v in vals]
                parsed = [p for p in parsed if pd.notna(p)]
                if not parsed:
                    return None
                return max(parsed)
            except Exception:
                return None

        df["LastUpdated"] = df.apply(last_ts, axis=1)
        now = pd.Timestamp.now()
        df["DaysSince"] = (now - df["LastUpdated"]).dt.days
        df_rem = df[(df["LastUpdated"].notna()) & (df["DaysSince"] >= reminder_days)]
        if df_rem.empty:
            st.success(f"👏 All good. No leads inactive ≥ {reminder_days} days.")
        else:
            st.warning(f"⚠️ {len(df_rem)} leads inactive ≥ {reminder_days} days")
            st.dataframe(df_rem[["Name","Status","DaysSince","Source","ServiceType"]])

with tab_kpi:
    st.subheader("📊 KPIs")
    if df.empty:
        st.info("No tickets available.")
    else:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Leads by Source**")
            st.bar_chart(df["Source"].value_counts())
        with c2:
            st.markdown("**Lost Leads by Reason**")
            lost = df[df["Status"] == "Lost"]
            if lost.empty:
                st.caption("No lost leads")
            else:
                st.bar_chart(lost["LostReason"].fillna("Unspecified").value_counts())

with tab_settings:
    st.subheader("⚙️ Settings")
    st.markdown("**Blocked Words** (hide tickets whose names include any of these)")
    current_bw = ", ".join(blocked_words)
    new_bw = st.text_input("Comma-separated list", value=current_bw, key="bw_input")
    st.markdown("**Reminder Threshold (days)**")
    new_rd = st.number_input("Days of inactivity before reminder", min_value=1, max_value=60, value=int(reminder_days), step=1, key="rd_input")

    csave, creset = st.columns(2)
    with csave:
        if st.button("💾 Save Settings"):
            new_list = [w.strip() for w in new_bw.split(",") if w.strip()]
            new_settings = {"blocked_words": new_list, "reminder_days": int(new_rd)}
            save_settings(new_settings)
            st.success("Settings saved.")
            st.rerun()
    with creset:
        if st.button("♻️ Reset to Defaults"):
            if os.path.exists(SETTINGS_FILE):
                os.remove(SETTINGS_FILE)
            st.success("Settings reset to defaults.")
            st.rerun()
