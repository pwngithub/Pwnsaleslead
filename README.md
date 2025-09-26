# Sales Lead Tracker v19.10.16

This build fixes Streamlit deprecation and error issues:
- `st.image` uses `use_container_width=True`
- `st.dataframe` and `st.plotly_chart` use `width="auto"`

Run:
```bash
pip install -r requirements.txt
streamlit run app.py
```
