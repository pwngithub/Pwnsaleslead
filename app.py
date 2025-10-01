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

# ==============================================================================
# 🚀 FIX: Load and manage data using st.session_state for stability
# ==============================================================================

if 'df' not in st.session_state:
    if os.path.exists(SEED_FILE):
        try:
            # Load from CSV if it exists
            st.session_state.df = pd.read_csv(SEED_FILE)
            for c in ["CreatedAt","LastUpdated"]:
                if c in st.session_state.df.columns:
                    st.session_state.df[c] = pd.to_datetime(st.session_state.df[c], errors="coerce")
            st.caption("✅ Loaded tickets from local seed file")
        except Exception as e:
            # Handle potential file read errors
            st.error(f"Error loading CSV file. Initializing empty DataFrame. Details: {e}")
            st.session_state.df = pd.DataFrame(columns=["SubmissionID","Name","ContactSource","Status","TypeOfService","LostReason","Notes","CreatedAt","LastUpdated"])
    else:
        # Initialize an empty DataFrame
        st.session_state.df = pd.DataFrame(columns=["SubmissionID","Name","ContactSource","Status","TypeOfService","LostReason","Notes","CreatedAt","LastUpdated"])
        st.caption("ℹ️ No local CSV found — JotForm fallback not enabled in this build")

# Create a local reference to the session state DataFrame for cleaner code
df = st.session_state.df

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
                            # Use strftime for cleaner timestamp display
                            st.caption(f"Updated: {row['LastUpdated'].strftime('%Y-%m-%d %H:%M')}")
                            st.write(row.get("Notes",""))
                            
                            # quick move control
                            move_to = st.selectbox("Move to", STATUS_LIST, index=STATUS_LIST.index(status), key=f"mv_{row['SubmissionID']}")
                            
                            if move_to != status:
                                # Update session state DataFrame and save
                                ix = st.session_state.df.index[st.session_state.df["SubmissionID"]==row["SubmissionID"]]
                                if len(ix):
                                    st.session_state.df.loc[ix, "Status"] = move_to
                                    st.session_state.df.loc[ix, "LastUpdated"] = pd.Timestamp.now()
                                    st.session_state.df.to_csv(SEED_FILE, index=False)
                                    st.success(f"Moved to {move_to}")
                                    st.experimental_rerun()

with tab_all:
    st.subheader("All Tickets")
    c0,c1,c2,c3,c4 = st.columns([2,1,1,1,1])
    q = c0.text_input("🔍 Search name")
    src = c1.selectbox("Source", ["All","Email","Phone Call","Walk In","Social Media","In Person"])
    stt = c2.selectbox("Status", ["All"]+STATUS_LIST)
    svc = c3.selectbox("Service", ["All"]+SERVICE_TYPES)
    # Ensure LostReason column exists before trying to access unique values
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
            
            # FIX: Use st.session_state.df for the update logic
            # Ensure all required columns are present before concat
            # This is safer than reading the CSV again
            current_df = st.session_state.df
            new_row_df = pd.DataFrame([row], columns=current_df.columns)
            
            st.session_state.df = pd.concat([current_df, new_row_df], ignore_index=True)
            st.session_state.df.to_csv(SEED_FILE, index=False) # Save to file
            
            st.success("Ticket created.")
            st.experimental_rerun()

with tab_edit:
    st.subheader("Edit Ticket")
    if df.empty:
        st.info("No tickets to edit.")
    else:
        opts = {r["Name"]: r["SubmissionID"] for _, r in df.iterrows()}
        
        # Guard clause for empty options
        if not opts:
            st.info("No selectable tickets.")
        else:
            sel = st.selectbox("Select by Name", list(opts.keys()))
            sid = opts[sel]
            row = df[df["SubmissionID"]==sid].iloc[0]
            c1,c2 = st.columns(2)
            with c1:
                new_status = st.selectbox("Status", STATUS_LIST, 
                                          index=STATUS_LIST.index(row["Status"]) if row["Status"] in STATUS_LIST else 0)
                new_service = st.selectbox("Type of Service", SERVICE_TYPES, 
                                           index=SERVICE_TYPES.index(row["TypeOfService"]) if row["TypeOfService"] in SERVICE_TYPES else 0)
            with c2:
                # Use .get() and an empty string fallback for safety
                new_lost = st.text_input("Lost Reason", value=row.get("LostReason") or "")
                new_notes = st.text_area("Notes", value=row.get("Notes") or "")
                
            if st.button("Save Changes"):
                # FIX: Use st.session_state.df for the update logic
                ix = st.session_state.df.index[st.session_state.df["SubmissionID"]==sid]
                
                if len(ix):
                    st.session_state.df.loc[ix, "Status"] = new_status
                    st.session_state.df.loc[ix, "TypeOfService"] = new_service
                    st.session_state.df.loc[ix, "LostReason"] = new_lost if new_lost else None
                    st.session_state.df.loc[ix, "Notes"] = new_notes
                    st.session_state.df.loc[ix, "LastUpdated"] = pd.Timestamp.now()
                    
                    # Save the modified session state DataFrame to the persistent file
                    st.session_state.df.to_csv(SEED_FILE, index=False)
                    
                st.success("Saved.")
                st.experimental_rerun() # Line ~188 fix

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
