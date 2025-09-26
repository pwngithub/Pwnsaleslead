# Sales Lead Tracker v19.10.18

This build corrects all Streamlit/Plotly deprecations:
- `st.image` → use_container_width=True
- `st.dataframe` → use_container_width=True
- `st.plotly_chart` → use_container_width=True, config={"responsive": True}

Run:
```bash
pip install -r requirements.txt
streamlit run app.py
```
