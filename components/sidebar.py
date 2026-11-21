"""Sidebar navigation."""

import streamlit as st

from config.settings import NAV_ITEMS


def render_sidebar() -> None:
    st.markdown(
        """
        <div class="sw-brand">
          <div class="sw-logo">S</div>
          <div class="sw-brand-name">SpendWise <span>AI</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    for _key, label in NAV_ITEMS:
        selected = st.session_state.get("page") == label
        if st.button(label, key=f"nav_{label}", type="primary" if selected else "secondary", width="stretch"):
            st.session_state.page = label
            st.rerun()

    frame = st.session_state.transactions
    count = 0 if frame is None else len(frame)
    st.markdown(
        f"""
        <div class="sw-side-card">
          <strong>This session</strong>
          <p>{count} transactions. Statements are not saved to disk.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
