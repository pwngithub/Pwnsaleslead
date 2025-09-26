# Sales Lead Tracker v19.10.13 (Clean)

## Features
- **All Tickets (default)**: KPI dashboard, filters (search, status, service type, date range, lost reason multi-select), highlights (🆕 new, ✏️ edited), Download Excel (multi-sheet, timestamped).
- **Add Ticket**: create new ticket; if Status=Survey Scheduled, the matching date is auto-stamped. Redirects to All Tickets and highlights the new ticket.
- **Edit Ticket**: edit Status, Notes, Lost Reason; auto-stamps the correct status date; appends a history entry in Notes as `[YYYY-MM-DD HH:MM] Status → ...`; redirects to All Tickets and highlights the edited ticket.

## Run
pip install -r requirements.txt
streamlit run app.py
