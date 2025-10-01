
# Pioneer Sales Lead App – v19.10.27
import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import os, csv
from streamlit_sortables import sort_items

st.set_page_config(page_title="Pioneer Sales Lead App", page_icon="📶", layout="wide")

left, mid = st.columns([1,6])
with left:
    st.image("https://images.squarespace-cdn.com/content/v1/651eb4433b13e72c1034f375/369c5df0-5363-4827-b041-1add0367f447/PBB+long+logo.png?format=1500w", use_container_width=True)
with mid:
    st.title("Sales Lead Tracker — Pipeline")

API_KEY = "22179825a79dba61013e4fc3b9d30fa4"
FORM_ID = "252598168633065"
BASE_URL = "https://api.jotform.com"
AUDIT_FILE = "audit_log.csv"
SEED_FILE = "saleslead_seed.csv"

FIELD_ID = {
    "name_first": "first_3",
    "name_last": "last_3",
    "source": 4,
    "status": 6,
    "notes": 10,
    "lost_reason": 17,
    "service_type": 18,
    "address": 19,
    "survey_scheduled_date": 12,
    "survey_completed_date": 13,
    "scheduled_date": 14,
    "installed_date": 15,
    "waiting_on_customer_date": 16,
}

STATUS_LIST = ["Survey Scheduled","Survey Completed","Scheduled","Installed","Waiting on Customer","Lost"]
SERVICE_TYPES = ["Internet","Phone","TV","Cell Phone","Internet and Phone","Internet and TV","Internet and Cell Phone"]
COLORS = {
    "Survey Scheduled": "#3b82f6",
    "Survey Completed": "#fbbf24",
    "Scheduled": "#fb923c",
    "Installed": "#22c55e",
    "Waiting on Customer": "#a855f7",
    "Lost": "#ef4444"
}

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
    try:
        r = jot_get(f"/form/{FORM_ID}/submissions")
        r.raise_for_status()
        data = r.json()
    except Exception:
        return pd.DataFrame([])
    rows = []
    for item in data.get("content", []):
        answers = item.get("answers", {}) or {}
        first = answers.get(str(FIELD_ID["name_first"]), {}).get("answer", "") or ""
        last = answers.get(str(FIELD_ID["name_last"]), {}).get("answer", "") or ""
        name = f"{first} {last}".strip() or f"Unnamed ({item.get('id')})"
        rows.append({
            "SubmissionID": item.get("id"),
            "Name": name,
            "ContactSource": answers.get(str(FIELD_ID["source"]), {}).get("answer"),
            "Status": answers.get(str(FIELD_ID["status"]), {}).get("answer"),
            "TypeOfService": answers.get(str(FIELD_ID["service_type"]), {}).get("answer"),
            "Notes": answers.get(str(FIELD_ID["notes"]), {}).get("answer"),
            "LostReason": answers.get(str(FIELD_ID["lost_reason"]), {}).get("answer"),
            "Street": None, "City": None, "State": None, "Postal": None,
            "CreatedAt": pd.to_datetime(item.get("created_at")),
            "LastUpdated": pd.to_datetime(item.get("updated_at") or item.get("created_at")),
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("CreatedAt", ascending=False, na_position="last")
    return df

if os.path.exists(SEED_FILE):
    df = pd.read_csv(SEED_FILE)
    for col in ["CreatedAt","LastUpdated"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    st.caption("✅ Loaded tickets from local seed file")
else:
    df = fetch_submissions()
    st.caption("ℹ️ Loaded tickets from JotForm API")

if "filters" not in st.session_state:
    st.session_state["filters"] = {"q":"","src":"All","status":"All","svc":"All","lost":"All"}

def apply_filters(src_df):
    f = st.session_state["filters"]
    v = src_df.copy()
    if v.empty: return v
    if f["q"]:
        v = v[v["Name"].astype(str).str.contains(f["q"], case=False, na=False)]
    if f["src"]!="All":
        v = v[v["ContactSource"]==f["src"]]
    if f["status"]!="All":
        v = v[v["Status"]==f["status"]]
    if f["svc"]!="All":
        v = v[v["TypeOfService"]==f["svc"]]
    if f["lost"]!="All":
        v = v[v["LostReason"]==f["lost"]]
    return v

tab_pipe, tab_all, tab_add, tab_edit, tab_kpi, tab_audit = st.tabs(
    ["🧩 Pipeline View","📋 All Tickets","➕ Add Ticket","✏️ Edit Ticket","📈 KPI Dashboard","🧾 Audit Log"]
)

def build_groups(src_df):
    groups = {s: [] for s in STATUS_LIST}
    for _, r in src_df.iterrows():
        label = f"{r['SubmissionID']} — {r['Name']} · {r.get('TypeOfService','') or ''}"
        s = r["Status"] if r["Status"] in groups else STATUS_LIST[0]
        groups[s].append(label)
    return groups

def parse_sid(label: str) -> str:
    return label.split(" — ", 1)[0].strip()

def header_with_count(name, groups):
    return f"{name} ({len(groups.get(name, []))})"

with tab_pipe:
    st.subheader("Pipeline")
    view = apply_filters(df) if not df.empty else df.copy()
    if not view.empty:
        parts = [f"**Total Leads:** {len(view)}"]
        for s in STATUS_LIST:
            parts.append(f"**{s}:** {int((view['Status']==s).sum())}")
        st.markdown(" | ".join(parts))
    else:
        st.info("No tickets with current filters.")
    if view.empty:
        st.stop()
    groups = build_groups(view)
    colored_names = [header_with_count(s, groups) for s in STATUS_LIST]
    styles = [{"background": COLORS[s], "color": "#111", "padding":"6px", "borderRadius":"6px"} for s in STATUS_LIST]
    updated = sort_items(
        items=groups,
        multi_containers=True,
        direction="horizontal",
        container_names=colored_names,
        container_styles=styles,
        style={"height":"560px"},
    )
    moved = []
    prev_loc = {c: s for s, cards in groups.items() for c in cards}
    for s, cards in updated.items():
        for c in cards:
            old = prev_loc.get(c)
            if old and old != s:
                moved.append((c, old, s))
    if moved:
        for label, old_status, new_status in moved:
            sid = parse_sid(label)
            if os.path.exists(SEED_FILE):
                ix = df.index[df["SubmissionID"]==sid]
                if len(ix):
                    df.loc[ix, "Status"] = new_status
                    df.loc[ix, "LastUpdated"] = pd.Timestamp.now()
                    df.to_csv(SEED_FILE, index=False)
            else:
                payload = {f"submission[{FIELD_ID['status']}]": new_status}
                try:
                    jot_post(f"/submission/{sid}", payload)
                except Exception:
                    pass
            log_action("Move (Pipeline)", sid, "", f"{old_status} → {new_status}")
        st.success("Pipeline updated.")
        st.experimental_rerun()

with tab_all:
    st.subheader("All Tickets")
    c0,c1,c2,c3,c4 = st.columns([2,1,1,1,1])
    st.session_state["filters"]["q"] = c0.text_input("🔍 Search name", value=st.session_state["filters"]["q"])
    st.session_state["filters"]["src"] = c1.selectbox("Source", ["All","Email","Phone Call","Walk In","Social Media","In Person"], index=["All","Email","Phone Call","Walk In","Social Media","In Person"].index(st.session_state["filters"]["src"]))
    st.session_state["filters"]["status"] = c2.selectbox("Status", ["All"]+STATUS_LIST, index=(["All"]+STATUS_LIST).index(st.session_state["filters"]["status"]))
    st.session_state["filters"]["svc"] = c3.selectbox("Service", ["All"]+SERVICE_TYPES, index=(["All"]+SERVICE_TYPES).index(st.session_state["filters"]["svc"]))
    lost_opts = ["All"] + ([] if df.empty else sorted([x for x in df["LostReason"].dropna().unique() if x]))
    if st.session_state["filters"]["lost"] not in lost_opts: st.session_state["filters"]["lost"]="All"
    st.session_state["filters"]["lost"] = c4.selectbox("Lost Reason", lost_opts, index=lost_opts.index(st.session_state["filters"]["lost"]))
    view2 = apply_filters(df) if not df.empty else df
    if view2.empty:
        st.info("No tickets with current filters.")
    else:
        st.dataframe(view2[["SubmissionID","Name","ContactSource","Status","TypeOfService","LostReason","CreatedAt","LastUpdated"]], use_container_width=True)

with tab_add:
    st.subheader("Add Ticket")
    with st.form("add_form"):
        c1,c2 = st.columns(2)
        with c1:
            first = st.text_input("First Name *")
            source = st.selectbox("Contact Source *", ["","Email","Phone Call","Walk In","Social Media","In Person"])
            status = st.selectbox("Status *", [""]+STATUS_LIST)
        with c2:
            last = st.text_input("Last Name *")
            service = st.selectbox("Type of Service *", [""]+SERVICE_TYPES)
            notes = st.text_area("Notes")
        lost = st.text_input("Lost Reason")
        submit = st.form_submit_button("Create Ticket")
    if submit:
        miss = [lbl for lbl, val in [("First Name",first),("Last Name",last),("Source",source),("Status",status),("Service",service)] if not val]
        if miss:
            st.error("Missing: " + ", ".join(miss))
        else:
            sid = f"seed_{int(datetime.now().timestamp())}"
            row = {
                "SubmissionID": sid,
                "Name": f"{first} {last}",
                "ContactSource": source,
                "Status": status,
                "TypeOfService": service,
                "LostReason": lost or None,
                "Notes": notes or "",
                "Street": None,"City": None,"State": None,"Postal": None,
                "CreatedAt": datetime.now(),
                "LastUpdated": datetime.now()
            }
            if os.path.exists(SEED_FILE):
                cur = pd.read_csv(SEED_FILE)
                cur = pd.concat([cur, pd.DataFrame([row])], ignore_index=True)
                cur.to_csv(SEED_FILE, index=False)
                st.success("Ticket created (local seed).")
                st.experimental_rerun()
            else:
                st.info("JotForm create not enabled in this demo build.")

with tab_edit:
    st.subheader("Edit Ticket")
    if df.empty:
        st.info("No tickets to edit.")
    else:
        options = {f"{r['Name']}": r["SubmissionID"] for _, r in df.iterrows()}
        choice = st.selectbox("Select ticket by Name", list(options.keys()))
        sid = options[choice]
        row = df[df["SubmissionID"]==sid].iloc[0]
        c1,c2 = st.columns(2)
        with c1:
            new_status = st.selectbox("Status", STATUS_LIST, index=STATUS_LIST.index(row["Status"]) if row["Status"] in STATUS_LIST else 0)
            new_service = st.selectbox("Type of Service", SERVICE_TYPES, index=SERVICE_TYPES.index(row["TypeOfService"]) if row["TypeOfService"] in SERVICE_TYPES else 0)
        with c2:
            new_lost = st.text_input("Lost Reason", value=row.get("LostReason") or "")
            new_notes = st.text_area("Notes", value=row.get("Notes") or "")
        if st.button("Save Changes"):
            if os.path.exists(SEED_FILE):
                ix = df.index[df["SubmissionID"]==sid]
                if len(ix):
                    df.loc[ix, "Status"] = new_status
                    df.loc[ix, "TypeOfService"] = new_service
                    df.loc[ix, "LostReason"] = new_lost if new_lost else None
                    df.loc[ix, "Notes"] = new_notes
                    df.loc[ix, "LastUpdated"] = pd.Timestamp.now()
                    df.to_csv(SEED_FILE, index=False)
                st.success("Saved (local seed).")
                st.experimental_rerun()
            else:
                st.info("JotForm edit not enabled in this demo build.")
            log_action("Edit", sid, row["Name"], f"Status={new_status}")

with tab_kpi:
    st.subheader("KPI Dashboard")
    if df.empty:
        st.info("No data yet.")
    else:
        v = apply_filters(df)
        parts = [f"**Total Leads:** {len(v)}"]
        for s in STATUS_LIST:
            parts.append(f"**{s}:** {int((v['Status']==s).sum())}")
        st.markdown(" | ".join(parts))
        by_status = v.groupby("Status").size().reset_index(name="Count")
        st.write("**By Status**")
        st.dataframe(by_status, use_container_width=True)
        by_source = v.groupby("ContactSource").size().reset_index(name="Count")
        st.write("**By Contact Source**")
        st.dataframe(by_source, use_container_width=True)
        by_service = v.groupby("TypeOfService").size().reset_index(name="Count")
        st.write("**By Service**")
        st.dataframe(by_service, use_container_width=True)
        if "LostReason" in v.columns:
            by_lost = v.groupby("LostReason").size().reset_index(name="Count")
            st.write("**Lost Reasons**")
            st.dataframe(by_lost, use_container_width=True)

with tab_audit:
    st.subheader("Audit Log")
    if os.path.exists(AUDIT_FILE):
        log_df = pd.read_csv(AUDIT_FILE)
        st.dataframe(log_df, use_container_width=True)
    else:
        st.info("No audit events yet.")

st.markdown("<hr/>", unsafe_allow_html=True)
st.caption("Powered by Pioneer Broadband | Internal Use Only")
