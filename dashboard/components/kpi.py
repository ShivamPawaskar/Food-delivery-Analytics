"""Reusable styled KPI cards."""
import streamlit as st


def kpi_card(label, value, help_text=None, delta=None):
    with st.container(border=True):
        st.metric(label, value, delta=delta, help=help_text)
