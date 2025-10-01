
# Pioneer Sales Lead App – v19.10.30
# Pipeline with reliable quick-move controls (no drag lib), KPI tab included
import streamlit as st
import pandas as pd
from datetime import datetime
import os

st.set_page_config(page_title="Pioneer Sales Lead App", page_icon="📶", layout="wide")

LOGO = "https://images.squarespace-cdn.com/content/v1/651eb4433b13e72c1034f375/369c5df0-5363-4827-b041-1add0367f447/PBB+long+logo.png?format=1500w"

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
SEED_FILE = "saleslead_seed.csv"

# Header
left, mid = st.columns([1,5])
with left:
    st.image(LOGO, use_container_width=True)
with mid:
    st.title("Sales Lead Tracker — Pipeline")

# Load data (CSV-first)
if os.path.exists(SEED_FILE):
    df = pd.read_csv(SEED_FILE)
    for c in ["CreatedAt","LastUpdated"]:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")
    st.caption("✅ Loaded tickets from local seed file")
else:
    df = pd.DataFrame(columns=["SubmissionID","Name","ContactSource","Status","TypeOfService","LostReason","Notes","CreatedAt","LastUpdated"])
    st.caption("ℹ️ No local CSV found — JotForm fallback not enabled in this build")

# Tabs
tab_pipe, tab_all, tab_add, tab_edit, tab_kpi = st.tabs(["🧩 Pipeline View","📋 All Tickets","➕ Add Ticket","✏️ Edit Ticket","📈 KPI"])

def kpi_bar(vdf):
    parts = [f"**Total Leads:** {len(vdf)}"]
    for s in STATUS_LIST:
        parts.append(f"**{s}:** {int((vdf['Status']==s).sum())}")
    st.markdown(" | ".join(parts))

with tab_pipe:
    st.subheader("Pipeline")
    if df.empty:
        st.info("No tickets yet.")
    else:
        kpi_bar(df)
        cols = st.columns(6)
        for i, status in enumerate(STATUS_LIST):
            with cols[i]:
                st.markdown(f"<div style='background:{COLORS[status]};padding:8px;border-radius:8px;color:#111;font-weight:700'>{status} ({int((df['Status']==status).sum())})</div>", unsafe_allow_html=True)
                subset = df[df["Status"]==status]
                if subset.empty:
                    st.write("—")
                else:
                    for _, row in subset.sort_values("LastUpdated", ascending=False).iterrows():
                        with st.expander(f"{row['Name']} · {row.get('TypeOfService','')}"):
                            st.caption(f"Updated: {row['LastUpdated']}")
                            st.write(row.get("Notes",""))
                            # quick move control
                            move_to = st.selectbox("Move to", STATUS_LIST, index=STATUS_LIST.index(status), key=f"mv_{row['SubmissionID']}")
                            if move_to != status:
                                # update
                                ix = df.index[df["SubmissionID"]==row["SubmissionID"]]
                                if len(ix):
                                    df.loc[ix, "Status"] = move_to
                                    df.loc[ix, "LastUpdated"] = pd.Timestamp.now()
                                    df.to_csv(SEED_FILE, index=False)
                                st.success(f"Moved to {move_to}")
                                if "ticket" in locals():
        st.session_state["edited_ticket"] = ticket
    st.success("✅ Ticket updated successfully!")

with tab_all:
    st.subheader("All Tickets")
    c0,c1,c2,c3,c4 = st.columns([2,1,1,1,1])
    q = c0.text_input("🔍 Search name")
    src = c1.selectbox("Source", ["All","Email","Phone Call","Walk In","Social Media","In Person"])
    stt = c2.selectbox("Status", ["All"]+STATUS_LIST)
    svc = c3.selectbox("Service", ["All"]+SERVICE_TYPES)
    lost_opts = ["All"] + sorted([x for x in df["LostReason"].dropna().unique()]) if "LostReason" in df.columns else ["All"]
    los = c4.selectbox("Lost Reason", lost_opts)
    v = df.copy()
    if q: v = v[v["Name"].str.contains(q, case=False, na=False)]
    if src!="All": v = v[v["ContactSource"]==src]
    if stt!="All": v = v[v["Status"]==stt]
    if svc!="All": v = v[v["TypeOfService"]==svc]
    if los!="All": v = v[v["LostReason"]==los]
    st.dataframe(v[["SubmissionID","Name","ContactSource","Status","TypeOfService","LostReason","CreatedAt","LastUpdated"]], use_container_width=True)

with tab_add:
    st.subheader("Add Ticket")
    with st.form("add"):
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
        ok = st.form_submit_button("Create Ticket")
    if ok:
        miss = [n for n,vv in [("First Name",first),("Last Name",last),("Source",source),("Status",status),("Service",service)] if not vv]
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
                "LastUpdated": datetime.now(),
            }
            cur = pd.read_csv(SEED_FILE) if os.path.exists(SEED_FILE) else pd.DataFrame(columns=row.keys())
            cur = pd.concat([cur, pd.DataFrame([row])], ignore_index=True)
            cur.to_csv(SEED_FILE, index=False)
            st.success("Ticket created.")
            if "ticket" in locals():
        st.session_state["edited_ticket"] = ticket
    st.success("✅ Ticket updated successfully!")

with tab_edit:
    st.subheader("Edit Ticket")
    if df.empty:
        st.info("No tickets to edit.")
    else:
        opts = {r["Name"]: r["SubmissionID"] for _, r in df.iterrows()}
        sel = st.selectbox("Select by Name", list(opts.keys()))
        sid = opts[sel]
        row = df[df["SubmissionID"]==sid].iloc[0]
        c1,c2 = st.columns(2)
        with c1:
            new_status = st.selectbox("Status", STATUS_LIST, index=STATUS_LIST.index(row["Status"]) if row["Status"] in STATUS_LIST else 0)
            new_service = st.selectbox("Type of Service", SERVICE_TYPES, index=SERVICE_TYPES.index(row["TypeOfService"]) if row["TypeOfService"] in SERVICE_TYPES else 0)
        with c2:
            new_lost = st.text_input("Lost Reason", value=row.get("LostReason") or "")
            new_notes = st.text_area("Notes", value=row.get("Notes") or "")
        if st.button("Save Changes"):
            ix = df.index[df["SubmissionID"]==sid]
            if len(ix):
                df.loc[ix, "Status"] = new_status
                df.loc[ix, "TypeOfService"] = new_service
                df.loc[ix, "LostReason"] = new_lost if new_lost else None
                df.loc[ix, "Notes"] = new_notes
                df.loc[ix, "LastUpdated"] = pd.Timestamp.now()
                df.to_csv(SEED_FILE, index=False)
            st.success("Saved.")
            if "ticket" in locals():
        st.session_state["edited_ticket"] = ticket
    st.success("✅ Ticket updated successfully!")

with tab_kpi:
    st.subheader("KPI Dashboard")
    if df.empty:
        st.info("No data yet.")
    else:
        v = df.copy()
        # Summary bar
        parts = [f"**Total Leads:** {len(v)}"]
        for s in STATUS_LIST:
            parts.append(f"**{s}:** {int((v['Status']==s).sum())}")
        st.markdown(" | ".join(parts))
        # Tables
        st.write("**By Status**")
        st.dataframe(v.groupby("Status").size().reset_index(name="Count"), use_container_width=True)
        st.write("**By Source**")
        st.dataframe(v.groupby("ContactSource").size().reset_index(name="Count"), use_container_width=True)
        st.write("**By Service**")
        st.dataframe(v.groupby("TypeOfService").size().reset_index(name="Count"), use_container_width=True)
        if "LostReason" in v.columns:
            st.write("**Lost Reasons**")
            st.dataframe(v.groupby("LostReason").size().reset_index(name="Count"), use_container_width=True)

st.markdown("<hr/>", unsafe_allow_html=True)
st.caption("Powered by Pioneer Broadband | Internal Use Only")
