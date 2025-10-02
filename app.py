# Insert this at the top with your other imports
import requests

# --- JOTFORM CONFIGURATION ---
JOTFORM_API_KEY = "YOUR_FULL_ACCESS_API_KEY"
JOTFORM_FORM_ID = "YOUR_FORM_ID" # e.g., '242050311283038'

# --- FIELD MAPPING ---
# You MUST get these QIDs from the JotForm API response for your form
JOTFORM_QID_MAP = {
    "Name_First": "3[first]",   # Example QID mapping for a Name field
    "Name_Last": "3[last]",
    "ContactSource": "4",
    "Status": "5",
    "TypeOfService": "6",
    "LostReason": "7",
    "Notes": "8",
    # Note: JotForm IDs can be single numbers (5) or arrays (3[first]). You must confirm these.
}
# -----------------------------

def submit_to_jotform(lead_data):
    """Submits a new lead to JotForm and returns the new Submission ID."""
    endpoint = f"https://api.jotform.com/form/{JOTFORM_FORM_ID}/submissions"
    
    # Map the lead_data dictionary to the required JotForm QID format
    submission_data = {
        f"submission[{JOTFORM_QID_MAP['Name_First']}]": lead_data["Name_First"],
        f"submission[{JOTFORM_QID_MAP['Name_Last']}]": lead_data["Name_Last"],
        f"submission[{JOTFORM_QID_MAP['ContactSource']}]": lead_data["ContactSource"],
        f"submission[{JOTFORM_QID_MAP['Status']}]": lead_data["Status"],
        f"submission[{JOTFORM_QID_MAP['TypeOfService']}]": lead_data["TypeOfService"],
        f"submission[{JOTFORM_QID_MAP['LostReason']}]": lead_data["LostReason"],
        f"submission[{JOTFORM_QID_MAP['Notes']}]": lead_data["Notes"],
        "apiKey": JOTFORM_API_KEY
    }
    
    try:
        response = requests.post(endpoint, data=submission_data)
        response.raise_for_status()
        result = response.json()
        
        if result['responseCode'] == 200:
            return result['content']['submissionID']
        else:
            st.error(f"JotForm Submission Error: {result['message']}")
            return None
    except requests.exceptions.RequestException as e:
        st.error(f"API Connection Error: {e}")
        return None

def delete_submission_from_jotform(submission_id):
    """Deletes a submission from JotForm using the Submission ID."""
    endpoint = f"https://api.jotform.com/submission/{submission_id}"
    params = {"apiKey": JOTFORM_API_KEY}
    
    try:
        # Note: JotForm requires a PUT request for deletion (to trash it) or DELETE for permanent.
        # We will use DELETE for permanent removal.
        response = requests.delete(endpoint, params=params)
        response.raise_for_status()
        result = response.json()
        
        if result.get('responseCode') == 200:
            return True
        else:
            st.error(f"JotForm Deletion Error: {result.get('message', 'Unknown error')}")
            return False
    except requests.exceptions.RequestException as e:
        st.error(f"API Connection Error: {e}")
        return False
