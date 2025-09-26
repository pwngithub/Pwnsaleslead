import streamlit as st

st.set_page_config(page_title="Sales Lead Tracker v19.10.15", page_icon="📊", layout="wide")

st.title("Sales Lead Tracker v19.10.15")
st.image("https://www.pioneerbroadband.net/s/long-logo.png", width="auto")
st.dataframe({"Example":["Row1","Row2"]}, width="auto")
