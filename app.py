# Sales Lead Tracker
# Version: v19.10.23
# Maintained by Pioneer Broadband

import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import datetime, timedelta
import os, csv, random

from config import API_KEY, FORM_ID, FIELD_ID, STATUS_LIST, SERVICE_TYPES, TEST_PREFIX

st.set_page_config(page_title="Sales Lead Tracker – v19.10.23", page_icon="📊", layout="wide")

# Header with logo + version
col_logo, col_title = st.columns([1,3])
with col_logo:
    st.image("https://images.squarespace-cdn.com/content/v1/651eb4433b13e72c1034f375/369c5df0-5363-4827-b041-1add0367f447/PBB+long+logo.png?format=1500w", use_container_width=True)
with col_title:
    st.title("Sales Lead Tracker – v19.10.23")

BASE_URL = "https://api.jotform.com"
AUDIT_FILE = "audit_log.csv"

# ------------- helpers -------------
def jot_get(path, params=None):
    p = {"apiKey": API_KEY}
    if params: p.update(params)
    return requests.get(f"{BASE_URL}{path}", params=p, timeout=30)

def jot_post(path, data):
    p = {"apiKey": API_KEY}
    return requests.post(f"{BASE_URL}{path}", params=p, data=data, timeout=30)

def jot_delete(path):
    p = {"apiKey": API_KEY}
    return requests.delete(f"{BASE_URL}{path}", params=p, timeout=30)

def log_action(action, ticket_id, name, details=""):
    exists = os.path.exists(AUDIT_FILE)
    with open(AUDIT_FILE, "a", newline="") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(["Timestamp","Action","TicketID","Name","Details"])
        w.writerow([datetime.now().isoformat(timespec="seconds"), action, ticket_id or "", name or "", details or ""])

@st.cache_data(ttl=60)
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
        df["IsTest"] = df["Name"].fillna("").str.startswith(TEST_PREFIX)
        df = df.sort_values("Created At", ascending=False, na_position="last")
    return df

def ensure_seed_data_once():
    try:
        r = jot_get(f"/form/{FORM_ID}/submissions")
        r.raise_for_status()
        content = r.json().get("content", [])
        # if any TEST exists, skip
        for it in content:
            ans = it.get("answers", {}) or {}
            first = (ans.get(str(FIELD_ID["name_first"]), {}) or {}).get("answer", "") or ""
            last = (ans.get(str(FIELD_ID["name_last"]), {}) or {}).get("answer", "") or ""
            if f"{first} {last}".strip().startswith(TEST_PREFIX):
                return
        # else seed 15-20
        sources = ["Email","Phone","Social Media","Walk In","In Person"]
        reasons = ["","Price","Competition","No Interest","Timing"]
        today = datetime.now()
        to_make = random.randint(15,20)
        for i in range(to_make):
            days_ago = random.randint(0,29)
            dt = (today - timedelta(days=days_ago)).isoformat()
            status = random.choice(STATUS_LIST)
            service = random.choice(SERVICE_TYPES)
            source = random.choice(sources)
            lost = random.choice(reasons) if status == "Lost" else ""
            payload = {
                f"submission[{FIELD_ID['name_first']}]": TEST_PREFIX,
                f"submission[{FIELD_ID['name_last']}]": f"Lead {i+1}",
                f"submission[{FIELD_ID['source']}]": source,
                f"submission[{FIELD_ID['status']}]": status,
                f"submission[{FIELD_ID['service_type']}]": service,
                f"submission[{FIELD_ID['notes']}]": "Seed Test Ticket",
                f"submission[{FIELD_ID['lost_reason']}]": lost,
            }
            # optional date stamps
            if status == "Survey Scheduled":
                payload[f"submission[{FIELD_ID['survey_scheduled_date']}]"] = dt
            elif status == "Survey Completed":
                payload[f"submission[{FIELD_ID['survey_completed_date']}]"] = dt
            elif status == "Scheduled":
                payload[f"submission[{FIELD_ID['scheduled_date']}]"] = dt
            elif status == "Installed":
                payload[f"submission[{FIELD_ID['installed_date']}]"] = dt
            elif status == "Waiting on Customer":
                payload[f"submission[{FIELD_ID['waiting_on_customer_date']}]"] = dt

            resp = jot_post(f"/form/{FORM_ID}/submissions", payload)
            sid = ""
            try:
                sid = resp.json().get("content", {}).get("submissionID", "")
            except Exception:
                pass
            log_action("Add (Seed)", sid, f"{TEST_PREFIX} Lead {i+1}", f"Status={status}; Source={source}; Service={service}")
    except Exception:
        pass  # don't block UI

# seed once on first run
ensure_seed_data_once()

# ---------------- UI ----------------
tab_all, tab_add, tab_kpi, tab_audit = st.tabs(["📋 All Tickets", "➕ Add Ticket", "📈 KPI Dashboard", "🧾 Audit Log"])
df = fetch_submissions()

# Persist filters
if "filters" not in st.session_state:
    st.session_state["filters"] = {"q":"","src":"All","status":"All","svc":"All","lost":"All"}

def apply_filters(src_df):
    f = st.session_state["filters"]
    v = src_df.copy()
    if v.empty: return v
    if f["q"]: v = v[v["Name"].astype(str).str.contains(f["q"], case=False, na=False)]
    if f["src"]!="All": v = v[v["Source"]==f["src"]]
    if f["status"]!="All": v = v[v["Status"]==f["status"]]
    if f["svc"]!="All": v = v[v["ServiceType"]==f["svc"]]
    if f["lost"]!="All": v = v[v["LostReason"]==f["lost"]]
    return v

# -------- All Tickets --------
with tab_all:
    st.subheader("All Tickets")
    c0,c1,c2,c3,c4 = st.columns([2,1,1,1,1])
    st.session_state["filters"]["q"] = c0.text_input("🔍 Search by name", value=st.session_state["filters"]["q"])
    st.session_state["filters"]["src"] = c1.selectbox("Source", ["All","Email","Phone","Social Media","Walk In","In Person"], index=["All","Email","Phone","Social Media","Walk In","In Person"].index(st.session_state["filters"]["src"]))
    st.session_state["filters"]["status"] = c2.selectbox("Status", ["All"]+STATUS_LIST, index=(["All"]+STATUS_LIST).index(st.session_state["filters"]["status"]))
    st.session_state["filters"]["svc"] = c3.selectbox("Service Type", ["All"]+SERVICE_TYPES, index=(["All"]+SERVICE_TYPES).index(st.session_state["filters"]["svc"]))
    lost_opts = ["All"] + ([] if df.empty else sorted([x for x in df["LostReason"].dropna().unique() if x]))
    if st.session_state["filters"]["lost"] not in lost_opts: st.session_state["filters"]["lost"]="All"
    st.session_state["filters"]["lost"] = c4.selectbox("Lost Reason", lost_opts, index=lost_opts.index(st.session_state["filters"]["lost"]))

    view = apply_filters(df)

    # KPIs inline
    kc1,kc2,kc3,kc4 = st.columns(4)
    kc1.metric("Total", int(len(view)) if not view.empty else 0)
    kc2.metric("Installed", int((view["Status"]=="Installed").sum()) if not view.empty else 0)
    kc3.metric("Waiting on Customer", int((view["Status"]=="Waiting on Customer").sum()) if not view.empty else 0)
    kc4.metric("Lost", int((view["Status"]=="Lost").sum()) if not view.empty else 0)

    if not view.empty:
        # Yellow-highlight marker column so TEST rows stand out
        view_disp = view.copy()
        view_disp["TEST"] = view_disp["IsTest"].map({True:"🟨 TEST", False:""})
        st.dataframe(view_disp[["TEST","Name","Source","Status","ServiceType","LostReason","Created At","Updated At"]], use_container_width=True)

        st.markdown("### Actions")
        for _, r in view.iterrows():
            cols = st.columns([5,1,1])
            cols[0].write(f"**{r['Name']}** · {r['Status']} · {r['Source']}")
            if cols[1].button("✏️ Edit", key=f"edit_{r['SubmissionID']}"):
                st.session_state["edit_ticket"] = r["SubmissionID"]; st.rerun()
            if cols[2].button("🗑️ Delete", key=f"del_{r['SubmissionID']}"):
                resp = jot_delete(f"/submission/{r['SubmissionID']}")
                if resp.status_code == 200:
                    log_action("Delete", r["SubmissionID"], r["Name"])
                    fetch_submissions.clear(); st.success(f"Deleted {r['Name']}"); st.rerun()
                else:
                    st.error(f"Delete failed: {resp.text}")
    else:
        st.info("No tickets to display with current filters.")

    # Inline edit
    if "edit_ticket" in st.session_state:
        sid = st.session_state["edit_ticket"]
        if df.empty or sid not in set(df["SubmissionID"]):
            st.warning("Ticket not found.")
        else:
            row = df[df["SubmissionID"]==sid].iloc[0]
            st.markdown(f"---\n### Edit: **{row['Name']}**")
            ec1,ec2 = st.columns(2)
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
                    fetch_submissions.clear(); del st.session_state["edit_ticket"]; st.success("Saved"); st.rerun()
                else:
                    st.error(f"Save failed: {resp.text}")

# -------- Add Ticket --------
with tab_add:
    st.subheader("Add Ticket")
    with st.form("add_ticket_form"):
        c1,c2 = st.columns(2)
        with c1:
            fname = st.text_input("First Name *")
            source = st.selectbox("Source *", ["","Email","Phone","Social Media","Walk In","In Person"])
            status = st.selectbox("Status *", [""]+STATUS_LIST)
        with c2:
            lname = st.text_input("Last Name *")
            service = st.selectbox("Service Type *", [""]+SERVICE_TYPES)
            notes = st.text_area("Notes")
        lost_reason = st.text_input("Lost Reason")
        submitted = st.form_submit_button("Create Ticket")
    if submitted:
        missing = [lbl for lbl,val in [("First Name",fname),("Last Name",lname),("Source",source),("Status",status),("Service Type",service)] if not val]
        if missing:
            st.error("Missing: "+", ".join(missing))
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
                sid = ""
                try: sid = resp.json().get("content", {}).get("submissionID","")
                except Exception: pass
                log_action("Add", sid, f"{fname} {lname}", f"Source={source}; Status={status}")
                fetch_submissions.clear(); st.success("Ticket created"); st.rerun()
            else:
                st.error(f"Create failed: {resp.text}")

# -------- KPI Dashboard --------
with tab_kpi:
    st.subheader("KPI Dashboard")
    if df.empty:
        st.info("No data yet.")
    else:
        v = apply_filters(df)
        st.metric("Total Leads", int(len(v)))
        st.metric("Installed", int((v["Status"]=="Installed").sum()))
        st.metric("Waiting on Customer", int((v["Status"]=="Waiting on Customer").sum()))
        st.metric("Lost", int((v["Status"]=="Lost").sum()))
        by_status = v.groupby("Status").size().reset_index(name="Count")
        fig1 = px.bar(by_status, x="Status", y="Count", title="By Status")
        st.plotly_chart(fig1, use_container_width=True, config={"responsive": True})
        by_svc = v.groupby("ServiceType").size().reset_index(name="Count")
        fig2 = px.bar(by_svc, x="ServiceType", y="Count", title="By Service Type")
        st.plotly_chart(fig2, use_container_width=True, config={"responsive": True})
        conv = v.groupby("Source").agg(Leads=("SubmissionID","count"),
                                       Installed=("Status", lambda s: (s=="Installed").sum())).reset_index()
        conv["Conversion %"] = (100*conv["Installed"]/conv["Leads"]).round(1)
        st.dataframe(conv, use_container_width=True)

# -------- Audit Log --------
with tab_audit:
    st.subheader("Audit Log")
    if os.path.exists(AUDIT_FILE):
        log_df = pd.read_csv(AUDIT_FILE)
        st.dataframe(log_df, use_container_width=True)
    else:
        st.info("No audit events yet.")
    # Conditional bulk delete TEST tickets
    has_tests = False
    try:
        check = jot_get(f"/form/{FORM_ID}/submissions").json().get("content", [])
        for it in check:
            ans = it.get("answers", {}) or {}
            first = (ans.get(str(FIELD_ID['name_first']), {}) or {}).get("answer","") or ""
            last = (ans.get(str(FIELD_ID['name_last']), {}) or {}).get("answer","") or ""
            if f"{first} {last}".strip().startswith(TEST_PREFIX):
                has_tests = True; break
    except Exception:
        pass
    if has_tests:
        st.markdown("### Bulk Delete TEST Tickets")
        confirm = st.checkbox(f"Yes, permanently delete all tickets starting with '{TEST_PREFIX}'")
        if st.button("Delete All TEST Tickets", disabled=not confirm):
            # iterate and delete
            deleted = 0
            for it in check:
                ans = it.get("answers", {}) or {}
                first = (ans.get(str(FIELD_ID['name_first']), {}) or {}).get("answer","") or ""
                last = (ans.get(str(FIELD_ID['name_last']), {}) or {}).get("answer","") or ""
                if f"{first} {last}".strip().startswith(TEST_PREFIX):
                    jot_delete(f"/submission/{it.get('id')}"); deleted += 1
            log_action("Bulk Delete – Seed Test Tickets", "", "", f"Deleted={deleted}")
            fetch_submissions.clear()
            st.success(f"Deleted {deleted} TEST tickets. Refreshing..."); st.rerun()
