"""The written briefing. The model key stays on the server."""

from html import escape

import streamlit as st

from screens.state import ensure_briefing, llm_settings


def render_briefing(view: dict) -> None:
    ensure_briefing(view)
    config = llm_settings()
    if not config.api_key:
        return
    if st.session_state.briefing:
        st.markdown(
            f"""
            <article class="sw-briefing">
              <div class="sw-meta"><span class="sw-pill">Briefing</span></div>
              <h3>Your briefing</h3>
              <p>{escape(st.session_state.briefing)}</p>
              <p class="why">Written from the calculated cards. If a number here and a card disagree, trust the card.</p>
            </article>
            """,
            unsafe_allow_html=True,
        )
    elif st.session_state.briefing_error:
        st.markdown(
            f'<div class="sw-banner warn">{st.session_state.briefing_error} The cards below are unchanged.</div>',
            unsafe_allow_html=True,
        )
    elif not config.consent:
        st.markdown(
            '<div class="sw-note"><p>The written briefing is paused. Totals and charts on this page are unchanged. Turn it back on in Settings.</p></div>',
            unsafe_allow_html=True,
        )
