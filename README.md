# Sales Lead Tracker v19.10.17

This build corrects width handling for Streamlit:
- `st.image` → use_container_width=True
- `st.dataframe` → use_container_width=True
- `st.plotly_chart` → width="auto"

Run:
```bash
pip install -r requirements.txt
streamlit run app.py
```
