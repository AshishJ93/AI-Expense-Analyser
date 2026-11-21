"""Load the design system once per run."""

from pathlib import Path

import streamlit as st

CSS_PATH = Path(__file__).resolve().parents[1] / "styles" / "custom.css"


def inject_css() -> None:
    css = CSS_PATH.read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
