
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import requests
from io import BytesIO
from datetime import datetime, date
from config import API_KEY, FORM_ID, FIELD_ID, LOGO_URL

st.set_page_config(page_title="Sales Lead Tracker v19.10.14", page_icon="📊", layout="wide")

JOTFORM_API = "https://api.jotform.com"
STATUS_LIST = ["Survey Scheduled","Survey Completed","Scheduled","Installed","Waiting on Customer","Lost"]
SERVICE_TYPES = ["Internet","Phone","TV","Cell Phone","Internet and Phone","Internet and TV","Internet and Cell Phone"]

if "just_added" not in st.session_state: st.session_state["just_added"] = {"id": None}
if "just_edited" not in st.session_state: st.session_state["just_edited"] = {"id": None}

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
        rows.append({
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
        })
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

def colored_status(s):
    if s == "Installed": return "🟢 Installed"
    if s == "Waiting on Customer": return "🟡 Waiting on Customer"
    if s in ["Survey Scheduled","Survey Completed","Scheduled"]: return "🔵 " + s
    if s == "Lost": return "🔴 Lost"
    return s or ""

def append_history(notes: str, entry: str) -> str:
    notes = notes or ""
    if notes and not notes.endswith("\n"):
        notes += "\n"
    return notes + entry

st.markdown("<style>.brand-title{color:#0a5db5} .brand-accent{color:#00a36c}</style>", unsafe_allow_html=True)

tab_info, tab_all, tab_add = st.tabs(["ℹ️ Info","📋 All Tickets","➕ Add Ticket"])

with tab_info:
    if LOGO_URL:
        st.image(LOGO_URL, use_container_width=True)
    st.markdown("## <span class='brand-title'>Pioneer Broadband — Sales Lead Tracker</span>", unsafe_allow_html=True)
    st.write("- Add Ticket: create a new lead (if Status = Survey Scheduled, date auto-stamped)")
    st.write("- All Tickets: view, filter, KPIs, export. Click 'Edit a Ticket' below the table to update Status, Notes, Lost Reason.")
    st.write("- Highlights: 'New' = newly added, 'Edited' = recently updated (shown once)")
    st.write("- Export: 'Download Leads Report' → Excel with tickets + KPI sheets")
    st.markdown(f"[Open JotForm in a new tab](https://form.jotform.com/{FORM_ID})")
    st.write("---")
    st.markdown("Support: support@pioneerbroadband.net")

df = fetch_data()

with tab_all:
    st.header("KPI Dashboard")
    view = df.copy()

    c0,c1,c2,c3 = st.columns([2,1,1,1])
    search = c0.text_input("Search (Name, Source, Status)")
    status_sel = c1.selectbox("Status", ["All"] + STATUS_LIST, index=0)
    service_sel = c2.selectbox("Service Type", ["All"] + SERVICE_TYPES, index=0)
    min_dt = pd.to_datetime(view["Created At"]).min() if not view.empty else None
    max_dt = pd.to_datetime(view["Created At"]).max() if not view.empty else None
    start_def = min_dt.date() if pd.notna(min_dt) else date.today()
    end_def = max_dt.date() if pd.notna(max_dt) else date.today()
    start_date = c3.date_input("Start Date", value=start_def)
    end_date = st.date_input("End Date", value=end_def)

    lost_options = sorted([x for x in view["LostReason"].dropna().unique()])
    lost_sel = st.multiselect("Lost Reason (multi-select)", options=lost_options, default=[])

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
    if not view.empty:
        view = view[(pd.to_datetime(view["Created At"]).dt.date >= start_date) & (pd.to_datetime(view["Created At"]).dt.date <= end_date)]

    total_leads = len(view)
    by_status = view["Status"].value_counts()
    by_service = view["ServiceType"].value_counts()

    col1,col2,col3,col4 = st.columns(4)
    col1.metric("Total Leads", int(total_leads))
    col2.metric("Installed", int(by_status.get("Installed",0)))
    col3.metric("Waiting on Customer", int(by_status.get("Waiting on Customer",0)))
    if (view["Status"]=="Installed").any():
        avg_install_days = (pd.to_datetime(view.loc[view["Status"]=="Installed","Installed Date"]) - pd.to_datetime(view.loc[view["Status"]=="Installed","Created At"])).dt.days.dropna()
        col4.metric("Avg Days to Install", round(avg_install_days.mean(),1) if not avg_install_days.empty else "—")
    else:
        col4.metric("Avg Days to Install", "—")

    durations = {}
    if not view.empty:
        durations["Survey Scheduled"] = (view["Survey Scheduled Date"] - view["Created At"]).dt.days
        durations["Survey Completed"] = (view["Survey Completed Date"] - view["Survey Scheduled Date"]).dt.days
        durations["Scheduled"] = (view["Scheduled Date"] - view["Survey Completed Date"]).dt.days
        durations["Installed"] = (view["Installed Date"] - view["Scheduled Date"]).dt.days
        durations["Waiting on Customer"] = (view["Waiting on Customer Date"] - view["Created At"]).dt.days

    avg_duration_tbl = pd.DataFrame({"Status": list(durations.keys()),
                                     "Avg Days": [round(pd.Series(v).dropna().mean(),1) if isinstance(v,pd.Series) else np.nan for v in durations.values()]})
    st.write("Average Duration per Status (days)")
    st.dataframe(avg_duration_tbl, use_container_width=True)
    try:
        fig_bar = px.bar(avg_duration_tbl.dropna(), x="Status", y="Avg Days", title="Average Duration per Status (days)")
        st.plotly_chart(fig_bar, use_container_width=True)
    except Exception:
        pass

    if not view.empty:
        conv = view.groupby("Source").agg(Leads=("SubmissionID","count"),
                                          Installed=("Status", lambda s: (s=="Installed").sum())).reset_index()
        conv["Conversion %"] = (100*conv["Installed"]/conv["Leads"]).round(1)
        st.write("Conversion Rate by Source")
        st.dataframe(conv, use_container_width=True)

    if not view.empty:
        funnel_counts = view["Status"].value_counts().reindex(STATUS_LIST, fill_value=0).reset_index()
        funnel_counts.columns = ["Stage","Count"]
        try:
            fig_fun = px.funnel(funnel_counts, x="Count", y="Stage", title="Status Funnel")
            st.plotly_chart(fig_fun, use_container_width=True)
        except Exception:
            pass

    if not view.empty:
        st.write("Tickets Created Trend")
        day_counts = view.groupby(pd.to_datetime(view["Created At"]).dt.date).size().reset_index(name="Count")
        day_counts.columns = ["Date","Count"]
        gran = st.radio("Granularity", ["Daily","Weekly"], horizontal=True, index=0)
        plot_df = day_counts.copy()
        if gran == "Weekly":
            plot_df["Week"] = pd.to_datetime(plot_df["Date"]).dt.to_period("W").astype(str)
            plot_df = plot_df.groupby("Week")["Count"].sum().reset_index()
            xcol = "Week"
        else:
            xcol = "Date"
        try:
            fig_trend = px.line(plot_df, x=xcol, y="Count", markers=True, title=f"Tickets Created ({gran})")
            st.plotly_chart(fig_trend, use_container_width=True)
        except Exception:
            pass

    lost_df = view[view["Status"]=="Lost"]
    if not lost_df.empty:
        st.write("Lost Reasons (counts)")
        lost_counts = lost_df["LostReason"].value_counts().reset_index()
        lost_counts.columns = ["Lost Reason","Count"]
        st.dataframe(lost_counts, use_container_width=True)
        try:
            fig_pie = px.pie(lost_counts, names="Lost Reason", values="Count", title="Lost Reasons Distribution")
            st.plotly_chart(fig_pie, use_container_width=True)
        except Exception:
            pass
        st.write("Lost Reasons Over Time")
        lr = lost_df.dropna(subset=["LostReason"]).copy()
        if not lr.empty:
            weekly = True
            view_mode = st.radio("View", ["Weekly","Monthly"], horizontal=True, index=0, key="lost_view")
            if view_mode == "Weekly":
                lr["Bucket"] = pd.to_datetime(lr["Created At"]).dt.to_period("W").astype(str)
            else:
                lr["Bucket"] = pd.to_datetime(lr["Created At"]).dt.to_period("M").astype(str)
            lr_agg = lr.groupby(["Bucket","LostReason"]).size().reset_index(name="Count")
            try:
                fig_lost_trend = px.line(lr_agg, x="Bucket", y="Count", color="LostReason", markers=True, title=f"Lost Reasons Over Time ({view_mode})")
                st.plotly_chart(fig_lost_trend, use_container_width=True)
            except Exception:
                pass

    st.write("---")
    st.subheader("All Tickets (filtered)")
    tbl = view.copy()
    badges = []
    for _, r in tbl.iterrows():
        if st.session_state["just_added"]["id"] and r["SubmissionID"] == st.session_state["just_added"]["id"]:
            badges.append("New")
        elif st.session_state["just_edited"]["id"] and r["SubmissionID"] == st.session_state["just_edited"]["id"]:
            badges.append("Edited")
        else:
            badges.append("")
    tbl.insert(1, "Badge", badges)
    tbl["Status"] = tbl["Status"].apply(colored_status)
    tbl["Created At"] = pd.to_datetime(tbl["Created At"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    st.dataframe(tbl[["Name","Badge","Source","Status","ServiceType","LostReason","Notes","Created At"]], use_container_width=True)

    # Inline editor
    if not view.empty:
        st.write("### Edit a Ticket")
        target = st.selectbox("Select ticket to edit", options=view["Name"] + " — " + view["SubmissionID"], index=0)
        sub_id = target.split(" — ")[-1]
        row = df[df["SubmissionID"]==sub_id].iloc[0]
        ec1, ec2 = st.columns(2)
        with ec1:
            new_status = st.selectbox("Status", STATUS_LIST, index=STATUS_LIST.index(row["Status"]) if row["Status"] in STATUS_LIST else 0, key=f"st_{sub_id}")
            new_lost = st.text_input("Lost Reason", value=row["LostReason"] or "", key=f"lr_{sub_id}")
        with ec2:
            new_notes = st.text_area("Notes (history appended automatically)", value=row["Notes"] or "", height=140, key=f"nt_{sub_id}")
        if st.button("Save Changes", key=f"save_{sub_id}"):
            payload = {}
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
                entry = f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Status → {new_status}"
                new_notes = (new_notes + ("\n" if new_notes and not new_notes.endswith("\n") else "")) + entry
            payload[f"submission[{FIELD_ID['notes']}]"] = new_notes
            payload[f"submission[{FIELD_ID['lost_reason']}]"] = new_lost
            resp = update_submission(sub_id, payload)
            if resp.status_code == 200:
                st.session_state["just_edited"]["id"] = sub_id
                fetch_data.clear()
                st.success("Saved")
                st.experimental_rerun()
            else:
                st.error(f"Save failed ({resp.status_code}): {resp.text}")

    cA, cB = st.columns([1,3])
    if cA.button("Clear Highlights"):
        st.session_state["just_added"] = {"id": None}
        st.session_state["just_edited"] = {"id": None}
        st.experimental_rerun()

    def build_excel_bytes(filtered_df, avg_duration_df, conv_df, by_status_s, by_service_s, lost_counts_df):
        raw = filtered_df.copy()
        raw["Created At"] = pd.to_datetime(raw["Created At"]).dt.strftime("%Y-%m-%d %H:%M:%S")
        bio = BytesIO()
        with pd.ExcelWriter(bio, engine="openpyxl") as writer:
            raw.to_excel(writer, index=False, sheet_name="Tickets")
            by_status_s.rename_axis("Status").reset_index(name="Count").to_excel(writer, index=False, sheet_name="By Status")
            by_service_s.rename_axis("ServiceType").reset_index(name="Count").to_excel(writer, index=False, sheet_name="By Service Type")
            conv_df.to_excel(writer, index=False, sheet_name="Conversion by Source")
            avg_duration_df.to_excel(writer, index=False, sheet_name="Average Duration")
            if lost_counts_df is not None and not lost_counts_df.empty:
                lost_counts_df.to_excel(writer, index=False, sheet_name="Lost Reasons")
        bio.seek(0)
        return bio.getvalue()

    by_status_s = view["Status"].value_counts() if not view.empty else pd.Series(dtype=int)
    by_service_s = view["ServiceType"].value_counts() if not view.empty else pd.Series(dtype=int)
    conv_df = pd.DataFrame()
    if not view.empty:
        conv_df = view.groupby("Source").agg(Leads=("SubmissionID","count"),
                                             Installed=("Status", lambda s: (s=="Installed").sum())).reset_index()
        if not conv_df.empty:
            conv_df["Conversion %"] = (100*conv_df["Installed"]/conv_df["Leads"]).round(1)
    lost_counts_df = None
    lost_df2 = view[view["Status"]=="Lost"]
    if not lost_df2.empty:
        lost_counts_df = lost_df2["LostReason"].value_counts().reset_index()
        lost_counts_df.columns = ["Lost Reason","Count"]

    ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
    excel_bytes = build_excel_bytes(view, avg_duration_tbl, conv_df, by_status_s, by_service_s, lost_counts_df)
    cB.download_button("Download Leads Report", data=excel_bytes, file_name=f"leads_export_{ts}.xlsx")

with tab_add:
    st.header("Add Ticket")
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
            resp = requests.post(f"{JOTFORM_API}/form/{FORM_ID}/submissions?apiKey={API_KEY}", data=payload, timeout=30)
            if resp.status_code == 200:
                new_id = None
                try:
                    j = resp.json()
                    new_id = j.get("content", {}).get("id") or j.get("content", {}).get("submissionID")
                except Exception:
                    pass
                st.session_state["just_added"]["id"] = new_id
                fetch_data.clear()
                st.success("Created. Switching to All Tickets…")
                st.experimental_rerun()
            else:
                st.error(f"Create failed ({resp.status_code}): {resp.text}")
