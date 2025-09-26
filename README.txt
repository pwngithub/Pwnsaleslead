# Sales Lead Tracker v19.10.11 — Minimal (Read + Add)

## What’s included
- 📋 All Tickets: read-only list of submissions from JotForm
- ➕ Add Ticket: create a new lead and (if Status = Survey Scheduled) auto-fill the Survey Scheduled Date

## Setup
1) Create/activate a virtualenv (optional)
2) Install dependencies:
   pip install -r requirements.txt
3) Run the app:
   streamlit run app.py

## Configuration
- Update your API key / form ID in `config.py` if needed.
- Field IDs are already set to your form:
  - name (3), source (4), status (6), notes (10),
  - survey_scheduled (12), survey_completed (13), scheduled (14),
  - installed (15), waiting_on_customer (16), lost_reason (17), service_type (18)

## JotForm API
- The app reads from: GET https://api.jotform.com/form/{FORM_ID}/submissions?apikey=API_KEY
- It creates tickets via: POST https://api.jotform.com/form/{FORM_ID}/submissions?apiKey=API_KEY
