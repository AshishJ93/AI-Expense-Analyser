"""Page header with a labeled period control."""

import streamlit as st

from config.settings import PERIODS


def render_header(title: str, subtitle: str, source: str) -> None:
    st.markdown(
        f'<p class="sw-kicker">SpendWise</p>'
        f'<h1 class="sw-page-title">{title}</h1>'
        f'<p class="sw-page-sub">{subtitle}</p>'
        f'<p class="sw-source-line">{source}</p>',
        unsafe_allow_html=True,
    )
    period, action = st.columns([1, 1], vertical_alignment="bottom")
    with period:
        st.selectbox(
            "Period",
            PERIODS,
            key="period",
            help="Limits the figures on this page. Comparisons say when they need older months.",
        )
    with action:
        if st.button("Replace statements", width="stretch", help="Upload a new file or open the demo again."):
            st.session_state.stage = "onboard"
            st.session_state.replacing = True
            st.session_state.parsed_files = []
            st.rerun()
