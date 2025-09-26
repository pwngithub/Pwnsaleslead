
import streamlit as st
import pandas as pd
import numpy as np
import requests
from io import BytesIO
from datetime import datetime, date
from config import API_KEY, FORM_ID, FIELD_ID

JOTFORM_API = "https://api.jotform.com"
STATUS_LIST = ["Survey Scheduled","Survey Completed","Scheduled","Installed","Waiting on Customer","Lost"]
SERVICE_TYPES = ["Internet","Phone","TV","Cell Phone","Internet and Phone","Internet and TV","Internet and Cell Phone"]

st.set_page_config(page_title="Sales Lead Tracker v19.10.13 (Clean)", page_icon="📊", layout="wide")
st.title("📊 Sales Lead Tracker v19.10.13 (Clean)")

# one-time highlights
if "just_added" not in st.session_state: st.session_state["just_added"] = {"id": None, "name": None, "kind": None}
if "just_edited" not in st.session_state: st.session_state["just_edited"] = {"id": None, "name": None, "kind": None}

# ---------- Helpers ----------
def _safe_dt(x):
    try:
        return pd.to_datetime(x) if x else pd.NaT
    except Exception:
        return pd.NaT

@st.cache_data(ttl=60)
def fetch_data():
    url = f"{JOTFORM_API}/form/{FORM_ID}/submissions?apikey={API_KEY}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    subs = r.json().get("content", [])
    rows = []
    for sub in subs:
        ans = sub.get("answers", {}) or {}
        name_raw = ans.get(str(FIELD_ID["name"]), {}).get("answer", {})
        if isinstance(name_raw, dict):
            first = (name_raw.get("first","") or "").strip(); last = (name_raw.get("last","") or "").strip()
            name = f"{first} {last}".strip()
        else:
            name = str(name_raw) if name_raw else ""
        row = {
            "SubmissionID": sub.get("id"),
            "Name": name or f"Unnamed ({sub.get('id')})",
            "Source": ans.get(str(FIELD_ID["source"]), {}).get("answer"),
            "Status": ans.get(str(FIELD_ID["status"]), {}).get("answer"),
            "ServiceType": ans.get(str(FIELD_ID["service_type"]), {}).get("answer"),
            "Notes": ans.get(str(FIELD_ID["notes"]), {}).get("answer") or "",
            "LostReason": ans.get(str(FIELD_ID["lost_reason"]), {}).get("answer"),
            "Created At": _safe_dt(sub.get("created_at") or sub.get("createdAt")),
            "Survey Scheduled Date": _safe_dt(ans.get(str(FIELD_ID["survey_scheduled"]), {}).get("answer")),
            "Survey Completed Date": _safe_dt(ans.get(str(FIELD_ID["survey_completed"]), {}).get("answer")),
            "Scheduled Date": _safe_dt(ans.get(str(FIELD_ID["scheduled"]), {}).get("answer")),
            "Installed Date": _safe_dt(ans.get(str(FIELD_ID["installed"]), {}).get("answer")),
            "Waiting on Customer Date": _safe_dt(ans.get(str(FIELD_ID["waiting_on_customer"]), {}).get("answer")),
        }
        rows.append(row)
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df[~df["Name"].str.startswith("Unnamed (")]
        df = df.sort_values("Created At", ascending=False, na_position="last")
    return df

def post_new_ticket(payload):
    url = f"{JOTFORM_API}/form/{FORM_ID}/submissions?apiKey={API_KEY}"
    return requests.post(url, data=payload, timeout=30)

def update_submission(sub_id, payload):
    url = f"{JOTFORM_API}/submission/{sub_id}?apiKey={API_KEY}"
    return requests.post(url, data=payload, timeout=30)

def append_history(notes: str, entry: str) -> str:
    notes = notes or ""
    if notes and not notes.endswith("\n"):
        notes += "\n"
    return notes + entry

def colored_status(s):
    if s == "Installed": return "🟢 Installed"
    if s == "Waiting on Customer": return "🟡 Waiting on Customer"
    if s in ["Survey Scheduled","Survey Completed","Scheduled"]: return "🔵 " + s
    if s == "Lost": return "🔴 Lost"
    return s or ""

# ---------- Tabs ----------
tab_all, tab_add, tab_edit = st.tabs(["📋 All Tickets", "➕ Add Ticket", "✏️ Edit Ticket"])

df = fetch_data()

# ---------------------- ALL TICKETS ----------------------
with tab_all:
    st.subheader("Live KPIs")
    view = df.copy()

    # Filters UI
    c0, c1, c2, c3 = st.columns([2,1,1,1])
    search = c0.text_input("🔍 Search (Name, Source, Status)")
    status_sel = c1.selectbox("Status", ["All"] + STATUS_LIST, index=0)
    service_sel = c2.selectbox("Service Type", ["All"] + SERVICE_TYPES, index=0)
    # Date range
    min_dt = pd.to_datetime(view["Created At"]).min() if not view.empty else None
    max_dt = pd.to_datetime(view["Created At"]).max() if not view.empty else None
    start_def = min_dt.date() if pd.notna(min_dt) else date.today()
    end_def = max_dt.date() if pd.notna(max_dt) else date.today()
    start_date = c3.date_input("Start Date", value=start_def)
    end_date = st.date_input("End Date", value=end_def)

    # Lost reason multi-select
    lost_options = sorted([x for x in view["LostReason"].dropna().unique()])
    lost_sel = st.multiselect("Lost Reason (multi-select)", options=lost_options, default=[])

    # Apply filters
    if search:
        m = (
            view["Name"].astype(str).str.contains(search, case=False, na=False) |
            view["Source"].astype(str).str.contains(search, case=False, na=False) |
            view["Status"].astype(str).str.contains(search, case=False, na=False)
        ); view = view[m]
    if status_sel != "All":
        view = view[view["Status"] == status_sel]
    if service_sel != "All":
        view = view[view["ServiceType"] == service_sel]
    if lost_sel:
        view = view[view["LostReason"].isin(lost_sel)]
    # date range
    if not view.empty:
        view = view[(pd.to_datetime(view["Created At"]).dt.date >= start_date) & (pd.to_datetime(view["Created At"]).dt.date <= end_date)]

    # KPIs
    total_leads = len(view)
    by_status = view["Status"].value_counts().to_dict()
    by_service = view["ServiceType"].value_counts().to_dict()
    installed_mask = view["Status"] == "Installed"
    # average time to install
    if installed_mask.any():
        avg_install_days = (pd.to_datetime(view.loc[installed_mask, "Installed Date"]) - pd.to_datetime(view.loc[installed_mask, "Created At"])).dt.days.dropna()
        avg_install = round(avg_install_days.mean(), 1) if not avg_install_days.empty else None
    else:
        avg_install = None

    k1,k2,k3,k4 = st.columns(4)
    k1.metric("Total Leads", total_leads)
    k2.metric("Installed", by_status.get("Installed", 0))
    k3.metric("Waiting on Customer", by_status.get("Waiting on Customer", 0))
    k4.metric("Avg Days to Install", avg_install if avg_install is not None else "—")

    # Average duration per status (simple: difference between its date and previous meaningful date)
    durations = {}
    def days(a,b):
        if pd.isna(a) or pd.isna(b): return np.nan
        return (a - b).days
    if not view.empty:
        durations["Survey Scheduled"] = (view["Survey Scheduled Date"] - view["Created At"]).dt.days
        durations["Survey Completed"] = (view["Survey Completed Date"] - view["Survey Scheduled Date"]).dt.days
        durations["Scheduled"] = (view["Scheduled Date"] - view["Survey Completed Date"]).dt.days
        durations["Installed"] = (view["Installed Date"] - view["Scheduled Date"]).dt.days
        durations["Waiting on Customer"] = (view["Waiting on Customer Date"] - view["Created At"]).dt.days
    avg_duration_tbl = pd.DataFrame({
        "Status": list(durations.keys()),
        "Avg Days": [round(pd.Series(v).dropna().mean(),1) if isinstance(v, pd.Series) else np.nan for v in durations.values()]
    })
    st.write("**Average Duration per Status (days)**")
    st.dataframe(avg_duration_tbl, use_container_width=True)

    # Conversion by source
    if not view.empty:
        conv = view.groupby("Source").agg(
            Leads=("SubmissionID","count"),
            Installed=("Status", lambda s: (s=="Installed").sum())
        ).reset_index()
        conv["Conversion %"] = (100*conv["Installed"]/conv["Leads"]).round(1)
        st.write("**Conversion Rate by Source**")
        st.dataframe(conv, use_container_width=True)

    # Lost reasons section (only if exists)
    lost_df = view[view["Status"]=="Lost"]
    if not lost_df.empty:
        st.write("**Lost Reasons** (counts)")
        lost_counts = lost_df["LostReason"].value_counts().reset_index()
        lost_counts.columns = ["Lost Reason","Count"]
        st.dataframe(lost_counts, use_container_width=True)

    # Highlights + table
    table = view.copy()
    # badges
    badges = []
    for _, r in table.iterrows():
        if st.session_state["just_added"]["id"] and r["SubmissionID"] == st.session_state["just_added"]["id"]:
            badges.append("🆕")
        elif st.session_state["just_edited"]["id"] and r["SubmissionID"] == st.session_state["just_edited"]["id"]:
            badges.append("✏️")
        else:
            badges.append("")
    table.insert(1, "Badge", badges)
    table["Status"] = table["Status"].apply(colored_status)
    # display
    display_cols = ["Name","Badge","Source","Status","ServiceType","LostReason","Notes","Created At"]
    table["Created At"] = pd.to_datetime(table["Created At"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    st.dataframe(table[display_cols], use_container_width=True)

    # Clear highlights
    if st.button("Clear Highlights"):
        st.session_state["just_added"] = {"id": None, "name": None, "kind": None}
        st.session_state["just_edited"] = {"id": None, "name": None, "kind": None}
        st.rerun()

    # Download Excel (multi-sheet)
    def to_excel_bytes():
        # Raw tickets
        raw = view.copy()
        raw["Created At"] = pd.to_datetime(raw["Created At"]).dt.strftime("%Y-%m-%d %H:%M:%S")
        # KPI sheets
        by_status_df = raw["Status"].value_counts().reset_index()
        by_status_df.columns = ["Status","Count"]
        by_service_df = raw["ServiceType"].value_counts().reset_index()
        by_service_df.columns = ["ServiceType","Count"]
        conv_df = raw.groupby("Source").agg(Leads=("SubmissionID","count"), Installed=("Status", lambda s: (s=="Installed").sum())).reset_index()
        if not conv_df.empty:
            conv_df["Conversion %"] = (100*conv_df["Installed"]/conv_df["Leads"]).round(1)
        avg_dur_df = avg_duration_tbl.copy()

        bio = BytesIO()
        with pd.ExcelWriter(bio, engine="openpyxl") as writer:
            raw.to_excel(writer, index=False, sheet_name="Tickets")
            by_status_df.to_excel(writer, index=False, sheet_name="By Status")
            by_service_df.to_excel(writer, index=False, sheet_name="By Service Type")
            conv_df.to_excel(writer, index=False, sheet_name="Conversion by Source")
            avg_dur_df.to_excel(writer, index=False, sheet_name="Average Duration")
            if not lost_df.empty:
                lost_counts.to_excel(writer, index=False, sheet_name="Lost Reasons")
        bio.seek(0)
        return bio.getvalue()

    ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
    st.download_button("📥 Download Leads Report", to_excel_bytes(), file_name=f"leads_export_{ts}.xlsx")

# ---------------------- ADD TICKET ----------------------
with tab_add:
    st.subheader("➕ Add Ticket")
    with st.form("add_ticket", clear_on_submit=False):
        c1,c2 = st.columns(2)
        with c1:
            first = st.text_input("First Name *")
            source = st.selectbox("Contact Source *", ["","Email","Phone","Walk In","Social Media","In Person"])
            status = st.selectbox("Status *", [""] + STATUS_LIST)
        with c2:
            last = st.text_input("Last Name *")
            service = st.selectbox("Service Type *", [""] + SERVICE_TYPES)
            notes = st.text_area("Notes")

        submit = st.form_submit_button("Create Ticket")
    if submit:
        missing = []
        if not first.strip(): missing.append("First Name")
        if not last.strip(): missing.append("Last Name")
        if not source.strip(): missing.append("Contact Source")
        if not service.strip(): missing.append("Service Type")
        if not status.strip(): missing.append("Status")
        if missing:
            st.error("Please fill required fields: " + ", ".join(missing))
        else:
            payload = {
                f"submission[{FIELD_ID['name']}][first]": first.strip(),
                f"submission[{FIELD_ID['name']}][last]": last.strip(),
                f"submission[{FIELD_ID['source']}]": source,
                f"submission[{FIELD_ID['status']}]": status,
                f"submission[{FIELD_ID['service_type']}]": service,
                f"submission[{FIELD_ID['notes']}]": notes or "",
            }
            if status == "Survey Scheduled":
                payload[f"submission[{FIELD_ID['survey_scheduled']}]"] = datetime.now().isoformat()
            resp = post_new_ticket(payload)
            if resp.status_code == 200:
                new_id = None
                try:
                    j = resp.json()
                    new_id = j.get("content", {}).get("id") or j.get("content", {}).get("submissionID")
                except Exception:
                    pass
                st.session_state["just_added"] = {"id": new_id, "name": f"{first} {last}".strip(), "kind": "new"}
                fetch_data.clear()
                st.success("✅ Created. Redirecting to All Tickets…")
                st.rerun()
            else:
                st.error(f"❌ Create failed ({resp.status_code}): {resp.text}")

# ---------------------- EDIT TICKET ----------------------
with tab_edit:
    st.subheader("✏️ Edit Ticket")
    if df.empty:
        st.info("No tickets to edit.")
    else:
        names = df["Name"].tolist()
        sel_name = st.selectbox("Select Ticket by Name", names)
        row = df[df["Name"]==sel_name].iloc[0]
        new_status = st.selectbox("Status", STATUS_LIST, index=STATUS_LIST.index(row["Status"]) if row["Status"] in STATUS_LIST else 0)
        new_notes = st.text_area("Notes (history log appended automatically)", value=row["Notes"] or "", height=150)
        new_lost = st.text_input("Lost Reason", value=row["LostReason"] or "")

        if st.button("Save Changes"):
            payload = {}
            # Status & date stamping
            if new_status != (row["Status"] or ""):
                payload[f"submission[{FIELD_ID['status']}]"] = new_status
                now_iso = datetime.now().isoformat()
                if new_status == "Survey Scheduled":
                    payload[f"submission[{FIELD_ID['survey_scheduled']}]"] = now_iso
                elif new_status == "Survey Completed":
                    payload[f"submission[{FIELD_ID['survey_completed']}]"] = now_iso
                elif new_status == "Scheduled":
                    payload[f"submission[{FIELD_ID['scheduled']}]"] = now_iso
                elif new_status == "Installed":
                    payload[f"submission[{FIELD_ID['installed']}]"] = now_iso
                elif new_status == "Waiting on Customer":
                    payload[f"submission[{FIELD_ID['waiting_on_customer']}]"] = now_iso
                # history entry
                entry = f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Status → {new_status}"
                new_notes_final = append_history(new_notes, entry)
                payload[f"submission[{FIELD_ID['notes']}]"] = new_notes_final
            else:
                payload[f"submission[{FIELD_ID['notes']}]"] = new_notes

            # Lost reason
            payload[f"submission[{FIELD_ID['lost_reason']}]"] = new_lost

            resp = update_submission(row["SubmissionID"], payload)
            if resp.status_code == 200:
                st.session_state["just_edited"] = {"id": row["SubmissionID"], "name": row["Name"], "kind": "edited"}
                fetch_data.clear()
                st.success("✅ Saved. Redirecting to All Tickets…")
                st.rerun()
            else:
                st.error(f"❌ Save failed ({resp.status_code}): {resp.text}")
