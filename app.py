
# Pioneer Sales Lead App – v19.10.29
import streamlit as st
import pandas as pd
from streamlit_sortables import sort_items

st.set_page_config(page_title="Pioneer Sales Lead App", page_icon="📶", layout="wide")

STATUS_LIST = ["Survey Scheduled","Survey Completed","Scheduled","Installed","Waiting on Customer","Lost"]
COLORS = {
    "Survey Scheduled": "#3b82f6",
    "Survey Completed": "#fbbf24",
    "Scheduled": "#fb923c",
    "Installed": "#22c55e",
    "Waiting on Customer": "#a855f7",
    "Lost": "#ef4444"
}

df = pd.read_csv("saleslead_seed.csv")

def build_groups(src_df):
    groups = {s: [] for s in STATUS_LIST}
    for _, r in src_df.iterrows():
        label = f"{r['SubmissionID']} — {r['Name']} · {r.get('TypeOfService','') or ''}"
        s = r["Status"] if r["Status"] in groups else STATUS_LIST[0]
        groups[s].append(label)
    return groups

groups = build_groups(df)

container_names = []
mapped_groups = {}
styles = []
for s in STATUS_LIST:
    header = f"{s} ({len(groups.get(s, []))})"
    container_names.append(header)
    mapped_groups[header] = groups.get(s, [])
    styles.append({"background": COLORS[s], "color":"#111"})

updated = sort_items(
    items=mapped_groups,
    multi_containers=True,
    direction="horizontal",
    container_names=container_names,
    container_styles=styles,
    style={"height":"560px"},
)

st.write(updated)
