import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Sales Lead Tracker v19.10.18", page_icon="📊", layout="wide")

st.title("Sales Lead Tracker v19.10.18")

# Logo with use_container_width (safe for images)
st.image(
    "https://images.squarespace-cdn.com/content/v1/651eb4433b13e72c1034f375/369c5df0-5363-4827-b041-1add0367f447/PBB+long+logo.png?format=1500w",
    use_container_width=True
)

# Dataframe demo with use_container_width
df = pd.DataFrame({"Example": ["Row1", "Row2"]})
st.dataframe(df, use_container_width=True)

# Chart demo with config instead of deprecated args
fig = px.bar(df, x="Example", y=df.index)
st.plotly_chart(fig, use_container_width=True, config={"responsive": True})
