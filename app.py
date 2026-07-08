"""
PAN Mitra – Entry Point
Redirects to the main interface (streamlit_app.py).
Run with: streamlit run app.py
"""

import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

st.set_page_config(
    page_title="PAN Mitra",
    page_icon="🪪",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.switch_page("streamlit_app.py")
