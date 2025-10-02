# Pioneer Sales Lead App – v19.10.30
# Pipeline with reliable quick-move controls (no drag lib), KPI included
import streamlit as st
import pandas as pd
from datetime import datetime
import os

# --- CONSTANTS ---
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
# -----------------

def kpi_bar(vdf):
    parts = [f"**Total Leads:** {len(vdf)}"]
    for s in STATUS_LIST:
        parts.append(f"**{s}:** {int((vdf['Status']==s).sum())}")
    st.markdown(" | ".join(parts))

def initialize_data():
    """Initializes or re-loads the DataFrame into session state."""
    if os.path.exists(SEED_FILE):
        try:
            temp_df = pd.read_csv(SEED_FILE)
            for c in ["CreatedAt", "LastUpdated"]:
                if c in temp_df.columns:
                    temp_df[c] = pd.to_datetime(temp_df[c], errors="coerce")
            st.session_state.df = temp_df
            st.caption("✅ Loaded tickets from local seed file")
        except Exception as e:
            st.error(f"Error loading CSV file. Initializing empty DataFrame. Details: {e}")
            st.session_state.df = pd.DataFrame(columns=["SubmissionID","Name","ContactSource","Status","TypeOfService","LostReason","Notes","CreatedAt","LastUpdated"])
    else:
        st.session_state.df = pd.DataFrame(columns=["SubmissionID","Name","ContactSource","Status","TypeOfService","LostReason","Notes","CreatedAt","LastUpdated"])
        st.caption("ℹ️ No local CSV found — JotForm fallback not enabled in this build")

# --- CALLBACK FUNCTIONS FOR WIDGETS ---

def update_ticket_status(submission_id, widget_key):
    """Updates status using the widget's value from session state, then saves."""
    new_status = st.session_state[widget_key]
    
    ix = st.session_state.df.index[st.session_state.df["SubmissionID"] == submission_id]
    if len(ix):
        st.session_state.df.loc[ix, "Status"] = new_status
        st.session_state.df.loc[ix, "LastUpdated"] = pd.Timestamp.now()
        st.session_state.df.to_csv(SEED_FILE, index=False)
        st.success(f"Moved ticket {submission_id} to {new_status}") 

def update_ticket_details(sid, new_status, new_service, new_lost, new_notes):
    """Updates all details and saves the DataFrame, without calling rerun."""
    ix = st.session_state.df.index[st.session_state.df["SubmissionID"] == sid]
    if len(ix):
        st.session_state.df.loc[ix, "Status"] = new_status
        st.session_state.df.loc[ix, "TypeOfService"] = new_service
        st.session_state.df.loc[ix, "LostReason"] = new_lost if new_lost else None
        st.session_state.df.loc[ix, "Notes"] = new_notes
        st.session_state.df.loc[ix, "LastUpdated"] = pd.Timestamp.now()
        st.session_state.df.to_csv(SEED_FILE, index=False)
        st.success(f"Ticket {sid} changes saved.")

def delete_ticket(sid):
    """Deletes a ticket from the DataFrame and saves the file."""
    # Filter the DataFrame to keep everything *except* the selected SubmissionID
    st.session_state.df = st.session_state.df[st.session_state.df["SubmissionID"] != sid]
    
    # Save the new, smaller DataFrame
    st.session_state.df.to_csv(SEED_FILE, index=False)
    
    st.success(f"Ticket {sid} has been permanently deleted. Please refresh the page.")
# ------------------------------------

def main_app():
    # Header
    left, mid = st.columns([1,5])
    with left:
        st.image(LOGO, use_container_width=True)
    with mid:
        st.title("Sales Lead Tracker — Pipeline")

    # ==============================================================================
    # Load and manage data using st.session_state
    # ==============================================================================
    if 'df' not in st.session_state:
        initialize_data()

    # Tabs
    tab_pipe, tab_all, tab_add, tab_edit, tab_kpi = st.tabs(["🧩 Pipeline View","📋 All Tickets","➕ Add Ticket","✏️ Edit Ticket","📈 KPI"])

    with tab_pipe:
        st.subheader("Pipeline")
        if st.session_state.df.empty:
            st.info("No tickets yet.")
        else:
            kpi_bar(st.session_state.df)
            cols = st.columns(6)
            for i, status in enumerate(STATUS_LIST):
                with cols[i]:
                    status_count = int((st.session_state.df['Status']==status).sum())
                    st.markdown(f"<div style='background:{COLORS[status]};padding:8px;border-radius:8px;color:#111;font-weight:700'>{status} ({status_count})</div>", unsafe_allow_html=True)
                    
                    subset = st.session_state.df[st.session_state.df["Status"]==status]
                    
                    if subset.empty:
                        st.write("—")
                    else:
                        for _, row in subset.sort_values("LastUpdated", ascending=False).iterrows():
                            # Set expanded=False to minimize screen space
                            with st.expander(f"{row['Name']} · {row.get('TypeOfService','')}", expanded=False):
                                st.caption(f"Updated: {row['LastUpdated'].strftime('%Y-%m-%d %H:%M')}")
                                st.write(row.get("Notes",""))
                                
                                # quick move control
                                widget_key = f"mv_{row['SubmissionID']}"
                                st.selectbox(
                                    "Move to", 
                                    STATUS_LIST, 
                                    index=STATUS_LIST.index(status), 
                                    key=widget_key, # Use the generated key
                                    on_change=update_ticket_status,
                                    args=(row['SubmissionID'], widget_key) 
                                )


    with tab_all:
        st.subheader("All Tickets")
        c0,c1,c2,c3,c4 = st.columns([2,1,1,1,1])
        q = c0.text_input("🔍 Search name")
        src = c1.selectbox("Source", ["All","Email","Phone Call","Walk In","Social Media","In Person"])
        stt = c2.selectbox("Status", ["All"]+STATUS_LIST)
        svc = c3.selectbox("Service", ["All"]+SERVICE_TYPES)
        
        if "LostReason" in st.session_state.df.columns:
            lost_opts = ["All"] + sorted([x for x in st.session_state.df["LostReason"].dropna().unique()])
        else:
            lost_opts = ["All"]
        los = c4.selectbox("Lost Reason", lost_opts)
        
        v = st.session_state.df.copy()
        
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
                first = st.text_input("First Name *", key="add_first")
                source = st.selectbox("Contact Source *", ["","Email","Phone Call","Walk In","Social Media","In Person"], key="add_source")
                status = st.selectbox("Status *", [""]+STATUS_LIST, key="add_status")
            with c2:
                last = st.text_input("Last Name *", key="add_last")
                service = st.selectbox("Type of Service *", [""]+SERVICE_TYPES, key="add_service")
                notes = st.text_area("Notes", key="add_notes")
            lost = st.text_input("Lost Reason", key="add_lost")
            
            if st.form_submit_button("Create Ticket"):
                # Data validation and adding logic remains the same
                miss = [n for n,vv in [("First Name",st.session_state.add_first),("Last Name",st.session_state.add_last),("Source",st.session_state.add_source),("Status",st.session_state.add_status),("Service",st.session_state.add_service)] if not vv]
                if miss:
                    st.error("Missing: " + ", ".join(miss))
                else:
                    sid = f"seed_{int(datetime.now().timestamp())}"
                    row = {
                        "SubmissionID": sid,
                        "Name": f"{st.session_state.add_first} {st.session_state.add_last}",
                        "ContactSource": st.session_state.add_source,
                        "Status": st.session_state.add_status,
                        "TypeOfService": st.session_state.add_service,
                        "LostReason": st.session_state.add_lost or None,
                        "Notes": st.session_state.add_notes or "",
                        "Street": None,"City": None,"State": None,"Postal": None,
                        "CreatedAt": datetime.now(),
                        "LastUpdated": datetime.now(),
                    }
                    
                    current_df = st.session_state.df
                    new_row_df = pd.DataFrame([row], columns=current_df.columns)
                    
                    st.session_state.df = pd.concat([current_df, new_row_df], ignore_index=True)
                    st.session_state.df.to_csv(SEED_FILE, index=False)
                    
                    st.success("Ticket created. Refresh the page to see it in the Pipeline view.")

    with tab_edit:
        st.subheader("Edit Ticket")
        
        if st.session_state.df.empty: 
            st.info("No tickets to edit.")
        else:
            opts = {r["Name"]: r["SubmissionID"] for _, r in st.session_state.df.iterrows()}
            
            if not opts:
                st.info("No selectable tickets.")
            else:
                sel = st.selectbox("Select by Name", list(opts.keys()), key="edit_sel")
                sid = opts[sel]
                row = st.session_state.df[st.session_state.df["SubmissionID"]==sid].iloc[0]
                
                c1,c2 = st.columns(2)
                with c1:
                    new_status = st.selectbox("Status", STATUS_LIST, 
                                            index=STATUS_LIST.index(row["Status"]) if row["Status"] in STATUS_LIST else 0,
                                            key="edit_status")
                    new_service = st.selectbox("Type of Service", SERVICE_TYPES, 
                                                index=SERVICE_TYPES.index(row["TypeOfService"]) if row["TypeOfService"] in SERVICE_TYPES else 0,
                                                key="edit_service")
                with c2:
                    new_lost = st.text_input("Lost Reason", value=row.get("LostReason") or "", key="edit_lost")
                    new_notes = st.text_area("Notes", value=row.get("Notes") or "", key="edit_notes")
                    
                # Row of buttons
                col_save, col_delete = st.columns([1,1])

                with col_save:
                    if st.button("Save Changes", use_container_width=True):
                        update_ticket_details(
                            sid, 
                            st.session_state.edit_status, 
                            st.session_state.edit_service, 
                            st.session_state.edit_lost, 
                            st.session_state.edit_notes
                        )
                        st.info("Changes saved. Refresh the page to see them applied.")

                with col_delete:
                    # Added Delete Confirmation Logic
                    if st.button("❌ Delete Ticket", type="primary", use_container_width=True):
                        st.session_state['confirm_delete'] = sid
                
                # Confirmation Step
                if st.session_state.get('confirm_delete') == sid:
                    st.warning(f"Are you sure you want to delete ticket for {row['Name']} ({sid})?")
                    c_yes, c_no = st.columns(2)
                    with c_yes:
                        # Call the delete function on confirmation
                        if st.button("Yes, Delete Permanently", type="primary", use_container_width=True):
                            delete_ticket(sid)
                            st.session_state['confirm_delete'] = None # Clear confirmation
                    with c_no:
                        # Clear confirmation if canceled
                        if st.button("No, Keep It", use_container_width=True):
                            st.session_state['confirm_delete'] = None


    with tab_kpi:
        st.subheader("KPI Dashboard")
        if st.session_state.df.empty:
            st.info("No data yet.")
        else:
            v = st.session_state.df.copy()
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

# Call the main function to run the app
if __name__ == "__main__":
    # Ensure the confirmation state exists
    if 'confirm_delete' not in st.session_state:
        st.session_state['confirm_delete'] = None
        
    main_app()
