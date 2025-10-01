
# Pioneer Sales Lead Manager — v19.10.35 (Live JotForm + Refresh + Full KPI)
import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date
from io import StringIO

st.set_page_config(page_title="Pioneer Sales Lead Manager v19.10.35", page_icon="📶", layout="wide")

# --- Header ---
st.image("https://images.squarespace-cdn.com/content/v1/651eb4433b13e72c1034f375/369c5df0-5363-4827-b041-1add0367f447/PBB+long+logo.png?format=1500w", use_container_width=True)
st.write("Version: v19.10.35 — Live JotForm, Refresh, Full KPI")

# --- Secrets / Config (fallback to known values) ---
API_KEY = st.secrets.get("jotform_api_key", "22179825a79dba61013e4fc3b9d30fa4")
FORM_ID = st.secrets.get("jotform_form_id", "252598168633065")

# Field IDs (as provided)
FIELD_ID = {
    "name": 3,                      # first_3, last_3
    "contact_source": 4,            # e.g., Email, Social, Phone, Walk-in, In Person
    "status": 6,                    # Survey Scheduled, Survey Completed, Scheduled, Installed, Waiting on Customer, Lost
    "notes": 10,                    # Long text
    "lost_reason": 17,              # text
    "service_type": 18,             # dropdown
    "address": 19,                  # composite: addr_line1, addr_line2, city, state, postal
    "survey_scheduled_date": 12,
    "survey_completed_date": 13,
    "scheduled_date": 14,
    "installed_date": 15,
    "waiting_on_customer_date": 16,
}

STATUS_LIST = ["Survey Scheduled","Survey Completed","Scheduled","Installed","Waiting on Customer","Lost"]
SERVICE_TYPES = ["Internet","Phone","TV","Cell Phone","Internet and Phone","Internet and TV","Internet and Cell Phone"]

# --- Helpers ---
def jotform_get(url, params=None):
    r = requests.get(url, params=params or {})
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {"raw": r.text}

def jotform_post(url, data=None):
    r = requests.post(url, data=data or {})
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {"raw": r.text}

def fetch_submissions():
    url = f"https://api.jotform.com/form/{FORM_ID}/submissions?apiKey={API_KEY}"
    code, js = jotform_get(url)
    if code != 200 or js.get("responseCode") != 200:
        st.error(f"JotForm fetch failed ({code}): {js.get('message', js)}")
        return pd.DataFrame()
    rows = []
    for item in js.get("content", []):
        ans = item.get("answers", {}) or {}
        name_ans = (ans.get(str(FIELD_ID["name"]), {}) or {}).get("answer", {}) or {}
        addr_ans = (ans.get(str(FIELD_ID["address"]), {}) or {}).get("answer", {}) or {}
        def get_a(qid):
            return (ans.get(str(qid), {}) or {}).get("answer")
        rows.append({
            "SubmissionID": item.get("id"),
            "Name": f"{name_ans.get('first','').strip()} {name_ans.get('last','').strip()}".strip() or "Unnamed",
            "ContactSource": get_a(FIELD_ID["contact_source"]),
            "Status": get_a(FIELD_ID["status"]),
            "Notes": get_a(FIELD_ID["notes"]) or "",
            "LostReason": get_a(FIELD_ID["lost_reason"]) or "",
            "TypeOfService": get_a(FIELD_ID["service_type"]),
            "Street": addr_ans.get("addr_line1"),
            "Street2": addr_ans.get("addr_line2"),
            "City": addr_ans.get("city"),
            "State": addr_ans.get("state"),
            "Postal": addr_ans.get("postal"),
            "SurveyScheduledDate": get_a(FIELD_ID["survey_scheduled_date"]),
            "SurveyCompletedDate": get_a(FIELD_ID["survey_completed_date"]),
            "ScheduledDate": get_a(FIELD_ID["scheduled_date"]),
            "InstalledDate": get_a(FIELD_ID["installed_date"]),
            "WaitingOnCustomerDate": get_a(FIELD_ID["waiting_on_customer_date"]),
            "CreatedAt": datetime.fromtimestamp(int(item.get("created_at"))).isoformat() if str(item.get("created_at","")).isdigit() else item.get("created_at"),
            "LastUpdated": datetime.fromtimestamp(int(item.get("updated_at"))).isoformat() if str(item.get("updated_at","")).isdigit() else item.get("updated_at"),
        })
    df = pd.DataFrame(rows)
    # Normalize dates for KPI math
    for c in ["SurveyScheduledDate","SurveyCompletedDate","ScheduledDate","InstalledDate","WaitingOnCustomerDate","CreatedAt","LastUpdated"]:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")
    return df

def to_submission_payload(values: dict):
    """
    Map a dict of logical fields to JotForm submission payload.
    JotForm accepts field keys like submission[3][first], submission[3][last], submission[19][addr_line1], etc.
    """
    payload = {}
    # Name
    if values.get("first") or values.get("last"):
        if values.get("first"):
            payload[f"submission[{FIELD_ID['name']}][first]"] = values["first"]
        if values.get("last"):
            payload[f"submission[{FIELD_ID['name']}][last]"] = values["last"]
    # Simple fields
    simple_map = {
        "contact_source": FIELD_ID["contact_source"],
        "status": FIELD_ID["status"],
        "notes": FIELD_ID["notes"],
        "lost_reason": FIELD_ID["lost_reason"],
        "service_type": FIELD_ID["service_type"],
        "survey_scheduled_date": FIELD_ID["survey_scheduled_date"],
        "survey_completed_date": FIELD_ID["survey_completed_date"],
        "scheduled_date": FIELD_ID["scheduled_date"],
        "installed_date": FIELD_ID["installed_date"],
        "waiting_on_customer_date": FIELD_ID["waiting_on_customer_date"],
    }
    for k, qid in simple_map.items():
        if values.get(k) not in [None, ""]:
            payload[f"submission[{qid}]"] = values[k]
    # Address
    if any(values.get(x) for x in ["addr_line1","addr_line2","city","state","postal"]):
        if values.get("addr_line1"): payload[f"submission[{FIELD_ID['address']}][addr_line1]"] = values["addr_line1"]
        if values.get("addr_line2"): payload[f"submission[{FIELD_ID['address']}][addr_line2]"] = values["addr_line2"]
        if values.get("city"):       payload[f"submission[{FIELD_ID['address']}][city]"] = values["city"]
        if values.get("state"):      payload[f"submission[{FIELD_ID['address']}][state]"] = values["state"]
        if values.get("postal"):     payload[f"submission[{FIELD_ID['address']}][postal]"] = values["postal"]
    return payload

def create_submission(values: dict):
    url = f"https://api.jotform.com/form/{FORM_ID}/submissions?apiKey={API_KEY}"
    data = to_submission_payload(values)
    code, js = jotform_post(url, data=data)
    return code, js

def update_submission(submission_id: str, values: dict):
    url = f"https://api.jotform.com/submission/{submission_id}?apiKey={API_KEY}"
    data = to_submission_payload(values)
    code, js = jotform_post(url, data=data)
    return code, js

def kpi_summary(df: pd.DataFrame):
    c1,c2,c3,c4,c5,c6 = st.columns(6)
    c1.metric("Total", len(df))
    for c, s in zip([c2,c3,c4,c5,c6], STATUS_LIST[:5]):
        c.metric(s, int((df["Status"]==s).sum()))
    # Installed separate
    st.metric("Installed", int((df["Status"]=="Installed").sum()))

def kpi_breakdowns(df: pd.DataFrame):
    st.subheader("Breakdowns")
    col1, col2, col3 = st.columns(3)
    col1.write("**By Status**")
    col1.dataframe(df.groupby("Status").size().reset_index(name="Count"), use_container_width=True)
    col2.write("**By Source**")
    col2.dataframe(df.groupby("ContactSource").size().reset_index(name="Count"), use_container_width=True)
    col3.write("**By Service**")
    col3.dataframe(df.groupby("TypeOfService").size().reset_index(name="Count"), use_container_width=True)
    if "LostReason" in df.columns:
        st.write("**Lost Reasons**")
        st.dataframe(df.groupby("LostReason").size().reset_index(name="Count"), use_container_width=True)

# --- Tabs ---
tab_all, tab_add, tab_edit, tab_kpi = st.tabs(["📋 All Tickets","➕ Add Ticket","✏️ Edit Ticket","📈 KPI"])

# Session for edit target
if "edit_sid" not in st.session_state:
    st.session_state.edit_sid = None

with tab_all:
    st.subheader("All Tickets")
    if st.button("🔄 Refresh Tickets"):
        st.cache_data.clear()
        st.experimental_set_query_params(refreshed=str(datetime.now().timestamp()))
    # Fetch live
    df = fetch_submissions()
    if df.empty:
        st.warning("No submissions found in JotForm yet.")
    else:
        # Filters
        fc1, fc2, fc3, fc4 = st.columns([2,1,1,1])
        q = fc1.text_input("Search name")
        src = fc2.selectbox("Source", ["All"]+sorted([x for x in df["ContactSource"].dropna().unique()]))
        stt = fc3.selectbox("Status", ["All"]+STATUS_LIST)
        svc = fc4.selectbox("Service", ["All"]+SERVICE_TYPES)
        view = df.copy()
        if q: view = view[view["Name"].str.contains(q, case=False, na=False)]
        if src!="All": view = view[view["ContactSource"]==src]
        if stt!="All": view = view[view["Status"]==stt]
        if svc!="All": view = view[view["TypeOfService"]==svc]

        st.dataframe(view[["SubmissionID","Name","ContactSource","Status","TypeOfService","LostReason","LastUpdated"]].sort_values("LastUpdated", ascending=False), use_container_width=True)
        # Click-to-edit buttons
        for _, r in view.iterrows():
            if st.button(f"✏️ Edit {r['Name']}", key=f"edit_{r['SubmissionID']}"):
                st.session_state.edit_sid = r["SubmissionID"]
                st.switch_page if hasattr(st, "switch_page") else None  # no-op
                st.experimental_set_query_params(edit=r["SubmissionID"])
                st.toast(f"Editing {r['Name']}")
                # Do not rerun hard; keep context

        # Export
        csv = view.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Export CSV", csv, file_name="tickets_export.csv", mime="text/csv")

with tab_add:
    st.subheader("Add Ticket (Live → JotForm)")
    with st.form("add_ticket"):
        c1,c2 = st.columns(2)
        with c1:
            first = st.text_input("First Name*", key="add_first")
            source = st.selectbox("Contact Source*", ["Email","Phone Call","Walk In","Social Media","In Person"], key="add_source")
            status = st.selectbox("Status*", STATUS_LIST, key="add_status")
            service = st.selectbox("Type of Service*", SERVICE_TYPES, key="add_service")
        with c2:
            last = st.text_input("Last Name*", key="add_last")
            notes = st.text_area("Notes", key="add_notes")
            lost = st.text_input("Lost Reason", key="add_lost")
        a1,a2,a3 = st.columns(3)
        with a1:
            street = st.text_input("Street", key="add_street")
            city = st.text_input("City", key="add_city")
        with a2:
            state = st.text_input("State", key="add_state")
            postal = st.text_input("Postal", key="add_postal")
        with a3:
            auto_today = date.today().isoformat()
            st.caption("Status dates will auto-fill when status is set.")
        ok = st.form_submit_button("➕ Create")
    if ok:
        missing = [("First Name", first), ("Last Name", last)]
        miss = [m for m,v in missing if not v]
        if miss:
            st.error("Missing required: " + ", ".join(miss))
        else:
            values = {
                "first": first, "last": last,
                "contact_source": source, "status": status, "notes": notes, "lost_reason": lost,
                "service_type": service,
                "addr_line1": street, "addr_line2": "", "city": city, "state": state, "postal": postal,
            }
            # Auto date by status
            status_to_field = {
                "Survey Scheduled":"survey_scheduled_date",
                "Survey Completed":"survey_completed_date",
                "Scheduled":"scheduled_date",
                "Installed":"installed_date",
                "Waiting on Customer":"waiting_on_customer_date",
            }
            if status in status_to_field:
                values[status_to_field[status]] = auto_today
            code, js = create_submission(values)
            if code==200 and js.get("responseCode")==200:
                st.success("✅ Created in JotForm.")
            else:
                st.error(f"Create failed ({code}): {js}")

with tab_edit:
    st.subheader("Edit Ticket (Live → JotForm)")
    df_all = fetch_submissions()
    if df_all.empty:
        st.info("No tickets available to edit.")
    else:
        # Determine selection
        opts = {r["Name"]: r["SubmissionID"] for _, r in df_all.iterrows()}
        pre_sid = st.session_state.get("edit_sid")
        default_name = None
        if pre_sid in df_all["SubmissionID"].values:
            default_name = df_all.loc[df_all["SubmissionID"]==pre_sid, "Name"].values[0]
        name_sel = st.selectbox("Select by Name", list(opts.keys()), index=list(opts.keys()).index(default_name) if default_name in opts else 0)
        sid = opts[name_sel]
        row = df_all[df_all["SubmissionID"]==sid].iloc[0]

        with st.form("edit_form"):
            c1,c2 = st.columns(2)
            with c1:
                status = st.selectbox("Status", STATUS_LIST, index=STATUS_LIST.index(row["Status"]) if row["Status"] in STATUS_LIST else 0)
                service = st.selectbox("Type of Service", SERVICE_TYPES, index=SERVICE_TYPES.index(row["TypeOfService"]) if row["TypeOfService"] in SERVICE_TYPES else 0)
                notes = st.text_area("Notes", value=row.get("Notes",""))
            with c2:
                lost = st.text_input("Lost Reason", value=row.get("LostReason",""))
                # Auto date fill for chosen status
                auto_today = date.today().isoformat()
                st.caption("Changing status auto-fills its date to today.")

            save = st.form_submit_button("💾 Save Changes")
        if save:
            values = {
                "status": status,
                "service_type": service,
                "notes": notes,
                "lost_reason": lost,
            }
            status_to_field = {
                "Survey Scheduled":"survey_scheduled_date",
                "Survey Completed":"survey_completed_date",
                "Scheduled":"scheduled_date",
                "Installed":"installed_date",
                "Waiting on Customer":"waiting_on_customer_date",
            }
            if status in status_to_field:
                values[status_to_field[status]] = auto_today
            code, js = update_submission(sid, values)
            if code==200 and js.get("responseCode")==200:
                st.success("✅ Updated in JotForm.")
            else:
                st.error(f"Update failed ({code}): {js}")

with tab_kpi:
    st.subheader("KPI Dashboard (Live)")
    dfk = fetch_submissions()
    if dfk.empty:
        st.info("No data yet.")
    else:
        kpi_summary(dfk)
        # Simple conversion rate: Installed / Leads
        leads = len(dfk)
        installed = int((dfk["Status"]=="Installed").sum())
        conv = round(100*installed/leads,1) if leads else 0.0
        st.metric("Conversion %", f"{conv}%")
        # Avg days from CreatedAt to Installed
        if installed>0 and "InstalledDate" in dfk.columns and "CreatedAt" in dfk.columns:
            done = dfk[dfk["InstalledDate"].notna() & dfk["CreatedAt"].notna()].copy()
            if not done.empty:
                avg_days = (done["InstalledDate"] - done["CreatedAt"]).dt.days.mean()
                st.metric("Avg Days to Install", f"{avg_days:.1f}")
        kpi_breakdowns(dfk)
