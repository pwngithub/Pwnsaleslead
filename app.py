import streamlit as st
import pandas as pd

st.set_page_config(page_title="Sales Lead Tracker v19.10.16", page_icon="📊", layout="wide")

st.title("Sales Lead Tracker v19.10.16")

# Logo with use_container_width (safe for images)
st.image(
    "https://images.squarespace-cdn.com/content/v1/651eb4433b13e72c1034f375/369c5df0-5363-4827-b041-1add0367f447/PBB+long+logo.png?format=1500w",
    use_container_width=True
)

# Dataframe demo with width="auto"
df = pd.DataFrame({"Example": ["Row1", "Row2"]})
st.dataframe(df, width="auto")
