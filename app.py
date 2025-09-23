
import streamlit as st
import pandas as pd
import requests
import os, json
from datetime import datetime
from config import API_KEY, FORM_ID, FIELD_ID, BLOCKED_WORDS as DEFAULT_BLOCKED

JOTFORM_API = "https://api.jotform.com"
SETTINGS_FILE = "settings.json"

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                return json.load(f)
        except:
            return {"blocked_words": DEFAULT_BLOCKED}
    return {"blocked_words": DEFAULT_BLOCKED}

def save_settings(settings: dict):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f)

def reset_settings():
    if os.path.exists(SETTINGS_FILE):
        os.remove(SETTINGS_FILE)

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
        records.append({
            "SubmissionID": sub.get("id"),
            "DisplayName": name_val if name_val else f"Unnamed ({sub.get('id')})",
            "Name": name_val,
            "Source": ans.get(str(FIELD_ID["source"]), {}).get("answer"),
            "Status": ans.get(str(FIELD_ID["status"]), {}).get("answer"),
            "ServiceType": ans.get(str(FIELD_ID["service_type"]), {}).get("answer"),
            "LostReason": ans.get(str(FIELD_ID["lost_reason"]), {}).get("answer")
        })
    return pd.DataFrame(records)

def apply_blocklist(df, blocked_words):
    if df.empty:
        return df, 0
    mask = df["DisplayName"].astype(str).str.lower().apply(
        lambda x: any(word.lower() in x for word in blocked_words)
    )
    hidden_count = mask.sum()
    df = df[~mask]
    return df, hidden_count

st.set_page_config(page_title="Sales Lead Tracker v19.9.20", page_icon="📊", layout="wide")
st.title("📊 Sales Lead Tracker v19.9.20 — Live Sync Only")

settings = load_settings()
blocked_words = settings.get("blocked_words", DEFAULT_BLOCKED)

# Refresh button logic
if st.button("🔄 Refresh Tickets"):
    st.session_state["refresh"] = True

df = fetch_jotform_data()
df, hidden_count = apply_blocklist(df, blocked_words)

sync_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
st.caption(f"Last synced from JotForm: {sync_time}")

if hidden_count > 0:
    st.info(f"ℹ️ {hidden_count} tickets hidden (matched blocked words: {', '.join(blocked_words)})")

tab_all, tab_kpi, tab_settings = st.tabs(["📋 All Tickets", "📊 KPI Dashboard", "⚙️ Settings"])

with tab_all:
    st.subheader("All Tickets Preview")
    if df.empty:
        st.info("No tickets available.")
    else:
        st.dataframe(df[["DisplayName","Source","Status","ServiceType","LostReason"]])

with tab_kpi:
    st.subheader("📊 KPI Dashboard")
    if not df.empty:
        st.markdown("### Tickets by Service Type")
        st.bar_chart(df["ServiceType"].value_counts())
        st.markdown("### Tickets by Status")
        st.bar_chart(df["Status"].value_counts())

with tab_settings:
    st.subheader("⚙️ Settings")
    current = ", ".join(blocked_words)
    new_val = st.text_input("Blocked Words (comma-separated)", value=current)
    if st.button("💾 Save Blocked Words"):
        new_list = [w.strip() for w in new_val.split(",") if w.strip()]
        settings["blocked_words"] = new_list
        save_settings(settings)
        st.success(f"✅ Saved blocked words: {', '.join(new_list)}")
        st.rerun()
    if st.button("♻️ Reset to Default"):
        reset_settings()
        st.success("✅ Settings reset to defaults from config.py")
        st.rerun()
