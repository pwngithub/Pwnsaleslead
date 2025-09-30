
import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import datetime
import csv, os

from config import API_KEY, FORM_ID, FIELD_ID

st.set_page_config(page_title="Sales Lead Tracker v19.10.22", page_icon="📊", layout="wide")

BASE_URL = "https://api.jotform.com"
STATUS_LIST = ["Survey Scheduled","Survey Completed","Scheduled","Installed","Waiting on Customer","Lost"]
SERVICE_TYPES = ["Internet","Phone","TV","Cell Phone","Internet and Phone","Internet and TV","Internet and Cell Phone"]

# -------- Helpers --------
def jot_get(path):
    return requests.get(f"{BASE_URL}{path}?apiKey={API_KEY}", timeout=30)

def jot_post(path, data):
    return requests.post(f"{BASE_URL}{path}?apiKey={API_KEY}", data=data, timeout=30)

def jot_delete(path):
    return requests.delete(f"{BASE_URL}{path}?apiKey={API_KEY}", timeout=30)

def fetch_submissions():
    r = jot_get(f"/form/{FORM_ID}/submissions")
    r.raise_for_status()
    data = r.json()
    rows = []
    for item in data.get("content", []):
        answers = item.get("answers", {}) or {}
        first = answers.get(str(FIELD_ID["name_first"]), {}).get("answer", "") or ""
        last = answers.get(str(FIELD_ID["name_last"]), {}).get("answer", "") or ""
        name = f"{first} {last}".strip() or f"Unnamed ({item.get('id')})"
        rows.append({
            "SubmissionID": item.get("id"),
            "Name": name,
            "Source": answers.get(str(FIELD_ID["source"]), {}).get("answer"),
            "Status": answers.get(str(FIELD_ID["status"]), {}).get("answer"),
            "ServiceType": answers.get(str(FIELD_ID["service_type"]), {}).get("answer"),
            "Notes": answers.get(str(FIELD_ID["notes"]), {}).get("answer"),
            "LostReason": answers.get(str(FIELD_ID["lost_reason"]), {}).get("answer"),
            "Created At": pd.to_datetime(item.get("created_at")),
            "Updated At": pd.to_datetime(item.get("updated_at") or item.get("created_at")),
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("Created At", ascending=False, na_position="last")
    return df

def log_action(action, ticket_id, name, details=""):
    path = "audit_log.csv"
    exists = os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(["Timestamp","Action","TicketID","Name","Details"])
        w.writerow([datetime.now().isoformat(timespec="seconds"), action, ticket_id, name, details])

def clear_audit_log():
    path = "audit_log.csv"
    if os.path.exists(path):
        os.remove(path)

# -------- UI Top Nav --------
tab_all, tab_add, tab_kpi, tab_audit = st.tabs(["📋 All Tickets", "➕ Add Ticket", "📈 KPI Dashboard", "🧾 Audit Log"])

# Cache fetch for 60s
@st.cache_data(ttl=60)
def _get_df():
    return fetch_submissions()

df = _get_df()

# -------- All Tickets --------
with tab_all:
    st.subheader("All Tickets")
    # Filters row
    c0, c1, c2, c3, c4 = st.columns([2,1,1,1,1])
    search = c0.text_input("🔍 Search by name")
    src_sel = c1.selectbox("Source", ["All"] + ["Email","Phone","Social Media","Walk In","In Person"], index=0)
    status_sel = c2.selectbox("Status", ["All"] + STATUS_LIST, index=0)
    svc_sel = c3.selectbox("Service Type", ["All"] + SERVICE_TYPES, index=0)
    # Build list of lost reason options from data
    lr_opts = sorted([x for x in df["LostReason"].dropna().unique()]) if not df.empty else []
    lr_sel = c4.selectbox("Lost Reason", ["All"] + lr_opts if lr_opts else ["All"], index=0)

    view = df.copy()
    if not view.empty:
        if search:
            view = view[view["Name"].astype(str).str.contains(search, case=False, na=False)]
        if src_sel != "All":
            view = view[view["Source"] == src_sel]
        if status_sel != "All":
            view = view[view["Status"] == status_sel]
        if svc_sel != "All":
            view = view[view["ServiceType"] == svc_sel]
        if lr_sel != "All":
            view = view[view["LostReason"] == lr_sel]

    # KPIs inline
    kc1, kc2, kc3, kc4 = st.columns(4)
    kc1.metric("Total", int(len(view)) if not view.empty else 0)
    kc2.metric("Installed", int((view["Status"]=="Installed").sum()) if not view.empty else 0)
    kc3.metric("Waiting on Customer", int((view["Status"]=="Waiting on Customer").sum()) if not view.empty else 0)
    if not view.empty and (view["Status"]=="Installed").any():
        days = (pd.to_datetime(view.loc[view["Status"]=="Installed","Updated At"]) - pd.to_datetime(view.loc[view["Status"]=="Installed","Created At"])).dt.days
        kc4.metric("Avg Days to Install", round(days.dropna().mean(),1) if not days.dropna().empty else "—")
    else:
        kc4.metric("Avg Days to Install", "—")

    st.dataframe(view, use_container_width=True)

    st.markdown("### Actions")
    if not view.empty:
        for _, r in view.iterrows():
            cols = st.columns([5,1,1])
            cols[0].write(f"**{r['Name']}** · {r['Status']} · {r['Source']}")
            if cols[1].button("✏️ Edit", key=f"edit_{r['SubmissionID']}"):
                st.session_state["edit_ticket"] = r["SubmissionID"]
                st.rerun()
            if cols[2].button("🗑️ Delete", key=f"del_{r['SubmissionID']}"):
                resp = jot_delete(f"/submission/{r['SubmissionID']}")
                if resp.status_code == 200:
                    log_action("Delete", r["SubmissionID"], r["Name"])
                    _get_df.clear()
                    st.success(f"Deleted {r['Name']}")
                    st.rerun()
                else:
                    st.error(f"Delete failed: {resp.text}")

    # Inline Edit Panel
    if "edit_ticket" in st.session_state:
        sid = st.session_state["edit_ticket"]
        if df.empty or sid not in set(df["SubmissionID"]):
            st.warning("Ticket not found.")
        else:
            row = df[df["SubmissionID"]==sid].iloc[0]
            st.markdown(f"---\n### Edit: **{row['Name']}**")
            ec1, ec2 = st.columns(2)
            with ec1:
                new_status = st.selectbox("Status", STATUS_LIST, index=STATUS_LIST.index(row["Status"]) if row["Status"] in STATUS_LIST else 0, key=f"st_{sid}")
                new_service = st.selectbox("Service Type", SERVICE_TYPES, index=SERVICE_TYPES.index(row["ServiceType"]) if row["ServiceType"] in SERVICE_TYPES else 0, key=f"svc_{sid}")
            with ec2:
                new_lost = st.text_input("Lost Reason", value=row["LostReason"] or "", key=f"lr_{sid}")
                new_notes = st.text_area("Notes", value=row["Notes"] or "", height=120, key=f"nt_{sid}")

            if st.button("Save Changes", key=f"save_{sid}"):
                payload = {
                    f"submission[{FIELD_ID['status']}]": new_status,
                    f"submission[{FIELD_ID['service_type']}]": new_service,
                    f"submission[{FIELD_ID['lost_reason']}]": new_lost,
                    f"submission[{FIELD_ID['notes']}]": new_notes,
                }
                # auto date stamp for key statuses
                now_iso = datetime.now().isoformat()
                if new_status == "Survey Scheduled":
                    payload[f"submission[{FIELD_ID['survey_scheduled_date']}]"] = now_iso
                elif new_status == "Survey Completed":
                    payload[f"submission[{FIELD_ID['survey_completed_date']}]"] = now_iso
                elif new_status == "Scheduled":
                    payload[f"submission[{FIELD_ID['scheduled_date']}]"] = now_iso
                elif new_status == "Installed":
                    payload[f"submission[{FIELD_ID['installed_date']}]"] = now_iso
                elif new_status == "Waiting on Customer":
                    payload[f"submission[{FIELD_ID['waiting_on_customer_date']}]"] = now_iso

                resp = jot_post(f"/submission/{sid}", payload)
                if resp.status_code == 200:
                    log_action("Edit", sid, row["Name"], f"Status={new_status}; Service={new_service}; LostReason={new_lost}")
                    _get_df.clear()
                    del st.session_state["edit_ticket"]
                    st.success("Saved")
                    st.rerun()
                else:
                    st.error(f"Save failed: {resp.text}")

# -------- Add Ticket --------
with tab_add:
    st.subheader("Add Ticket")
    with st.form("add_ticket_form", clear_on_submit=False):
        c1, c2 = st.columns(2)
        with c1:
            fname = st.text_input("First Name *")
            source = st.selectbox("Source *", ["","Email","Phone","Social Media","Walk In","In Person"])
            status = st.selectbox("Status *", [""] + STATUS_LIST)
        with c2:
            lname = st.text_input("Last Name *")
            service = st.selectbox("Service Type *", [""] + SERVICE_TYPES)
            notes = st.text_area("Notes")
        lost_reason = st.text_input("Lost Reason")
        submitted = st.form_submit_button("Create Ticket")

    if submitted:
        missing = [lbl for lbl, val in [("First Name", fname), ("Last Name", lname), ("Source", source), ("Status", status), ("Service Type", service)] if not val]
        if missing:
            st.error("Missing: " + ", ".join(missing))
        else:
            payload = {
                f"submission[{FIELD_ID['name_first']}]": fname,
                f"submission[{FIELD_ID['name_last']}]": lname,
                f"submission[{FIELD_ID['source']}]": source,
                f"submission[{FIELD_ID['status']}]": status,
                f"submission[{FIELD_ID['service_type']}]": service,
                f"submission[{FIELD_ID['notes']}]": notes or "",
                f"submission[{FIELD_ID['lost_reason']}]": lost_reason or "",
            }
            if status == "Survey Scheduled":
                payload[f"submission[{FIELD_ID['survey_scheduled_date']}]"] = datetime.now().isoformat()

            resp = jot_post(f"/form/{FORM_ID}/submissions", payload)
            if resp.status_code == 200:
                sid = None
                try:
                    sid = resp.json().get("content", {}).get("submissionID")
                except Exception:
                    pass
                log_action("Add", sid or "", f"{fname} {lname}", f"Source={source}, Status={status}")
                _get_df.clear()
                st.success("Ticket created")
                st.rerun()
            else:
                st.error(f"Create failed: {resp.text}")

# -------- KPI Dashboard --------
with tab_kpi:
    st.subheader("KPI Dashboard")
    if df.empty:
        st.info("No data yet.")
    else:
        # Counts
        st.metric("Total Leads", int(len(df)))
        st.metric("Installed", int((df["Status"]=="Installed").sum()))
        st.metric("Waiting on Customer", int((df["Status"]=="Waiting on Customer").sum()))
        # By Status chart
        by_status = df.groupby("Status").size().reset_index(name="Count")
        try:
            fig1 = px.bar(by_status, x="Status", y="Count", title="By Status")
            st.plotly_chart(fig1, use_container_width=True, config={"responsive": True})
        except Exception:
            pass
        # By Service Type
        by_svc = df.groupby("ServiceType").size().reset_index(name="Count")
        try:
            fig2 = px.bar(by_svc, x="ServiceType", y="Count", title="By Service Type")
            st.plotly_chart(fig2, use_container_width=True, config={"responsive": True})
        except Exception:
            pass
        # Conversion by Source
        conv = df.groupby("Source").agg(Leads=("SubmissionID","count"),
                                        Installed=("Status", lambda s: (s=="Installed").sum())).reset_index()
        conv["Conversion %"] = (100*conv["Installed"]/conv["Leads"]).round(1)
        st.dataframe(conv, use_container_width=True)

# -------- Audit Log --------
with tab_audit:
    st.subheader("Audit Log")
    path = "audit_log.csv"
    if os.path.exists(path):
        log_df = pd.read_csv(path)
        st.dataframe(log_df, use_container_width=True)
        if st.button("Clear Audit Log"):
            clear_audit_log()
            st.success("Audit log cleared")
            st.rerun()
    else:
        st.info("No audit events yet.")
