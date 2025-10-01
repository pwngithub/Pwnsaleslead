# Pioneer Sales Lead Manager — v19.10.35

Live JotForm mode: loads tickets directly from JotForm on startup, writes Add/Edit back to JotForm.
CSV is **export only** via button in All Tickets.

## Run
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Configure (optional)
Create `.streamlit/secrets.toml` with:
```toml
jotform_api_key = "22179825a79dba61013e4fc3b9d30fa4"
jotform_form_id = "252598168633065"
```
