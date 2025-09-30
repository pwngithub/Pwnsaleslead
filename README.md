<p align="center">
  <img src="https://images.squarespace-cdn.com/content/v1/651eb4433b13e72c1034f375/369c5df0-5363-4827-b041-1add0367f447/PBB+long+logo.png?format=1500w" alt="Pioneer Broadband Logo" width="400"/>
</p>

# Sales Lead Tracker – v19.10.23

Live JotForm-powered lead tracker for Pioneer Broadband.

## Features
- Top tabs: **All Tickets**, **Add Ticket**, **KPI Dashboard**, **Audit Log**
- Live JotForm integration (Form ID 252598168633065)
- One-time **auto-seed** of 15–20 `TEST – Pioneer Broadband` tickets on first run
- Filters & search (persist across tabs); KPI is filter-aware
- Inline **Edit** and **Delete** actions in All Tickets
- **Bulk Delete TEST Tickets** button (conditional + confirmation)
- **Audit Log** (`audit_log.csv`) grows indefinitely
- Deprecation-safe rendering with `use_container_width` and Plotly `config={"responsive": True}`

## Run
```bash
pip install -r requirements.txt
streamlit run app.py
```

---

**Maintained by Pioneer Broadband – v19.10.23**
