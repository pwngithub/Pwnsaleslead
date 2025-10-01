<p align="center">
  <img src="https://images.squarespace-cdn.com/content/v1/651eb4433b13e72c1034f375/369c5df0-5363-4827-b041-1add0367f447/PBB+long+logo.png?format=1500w" alt="Pioneer Broadband Logo" width="400"/>
</p>

# Sales Lead Tracker – v19.10.25

As of **v19.10.25**, **Pipeline View** (drag-and-drop Kanban) is the **default tab** when you open the app.  
The **All Tickets** tab remains available for list/grid management.

## Tabs
- **🧩 Pipeline View** (default): drag-and-drop Kanban by status; updates JotForm and auto-stamps status dates.
- **📋 All Tickets**: table view with filters, search, inline edit/delete.
- **➕ Add Ticket**: add new leads.
- **📈 KPI Dashboard**: charts and conversion metrics.
- **🧾 Audit Log**: shows actions and bulk delete TEST tickets.

## Changing the Default Tab
If you want **All Tickets** as the default again:

1. Open `app.py`.
2. Find where the tabs are declared and move `"📋 All Tickets"` to the first position.
3. Example:
   ```python
   tab_all, tab_pipe, tab_add, tab_kpi, tab_audit = st.tabs([...])
   ```
4. Save and run:
   ```bash
   streamlit run app.py
   ```

## Run
```bash
pip install -r requirements.txt
streamlit run app.py
```
