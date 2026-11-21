"""Think Before You Spend."""

import streamlit as st

from components.cards import render_recommendation_board
from components.header import render_header
from screens.state import build_view


def render_think() -> None:
    view = build_view()
    render_header(
        "Think before you spend",
        "Places your history suggests looking at again. Nothing here says a purchase was wrong.",
        "Calculated from your history.",
    )
    if view["history_expanded"]:
        st.markdown(
            '<div class="sw-banner">This period has too little history for a fair comparison, so these notes use every loaded month.</div>',
            unsafe_allow_html=True,
        )
    items = view["recommendations"]
    if not items:
        st.markdown(
            '<div class="sw-note"><p>Nothing in this history is standing out as a place to reconsider. That can simply mean the months look alike.</p></div>',
            unsafe_allow_html=True,
        )
        return

    groups = [
        ("high", "High priority", "The larger shifts in discretionary spending."),
        ("review", "Worth reviewing", "Real movements, including essentials that may simply have become more expensive."),
        ("habit", "Good habit", "Patterns that are working and do not need a change."),
    ]
    for key, title, subtitle in groups:
        section = [item for item in items if item.priority == key]
        st.markdown(f'<div class="sw-section"><h2>{title}</h2><p class="sw-section-sub">{subtitle}</p></div>', unsafe_allow_html=True)
        if not section:
            st.markdown('<div class="sw-note"><p>Nothing in this group.</p></div>', unsafe_allow_html=True)
            continue
        render_recommendation_board(section)
