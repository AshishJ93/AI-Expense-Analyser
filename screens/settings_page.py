"""Privacy, thresholds, and the optional model provider."""

import streamlit as st

from components.header import render_header
from services.rules_store import delete_rules


def render_settings() -> None:
    render_header(
        "Settings",
        "What stays on this computer.",
        "Statements stay in this session. The written briefing uses only the figures already calculated.",
    )
    st.markdown(
        """
        <div class="sw-note">
          <p>Statements are processed in this session. HisaabPehle does not write transaction amounts or narrations to disk.</p>
          <p>Merchant corrections are saved in <code>.hisaabpehle/merchant_rules.json</code> on the machine running the app, so the same shop is recognized next time. On Streamlit Community Cloud that file lasts only as long as the app container does.</p>
          <p>Card numbers, long account numbers, email addresses, and phone numbers are masked before display. They are not saved, and they are not sent with the briefing.</p>
          <p>Automated analysis can miss a merchant or misread a PDF. It is not a substitute for your bank’s records.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="sw-section"><h2>Thresholds</h2></div>', unsafe_allow_html=True)
    first, second = st.columns(2)
    with first:
        st.session_state.small_purchase = st.number_input(
            "Small purchase under",
            min_value=50.0,
            value=float(st.session_state.small_purchase),
            step=50.0,
            help="Used to find purchases that are small alone and meaningful together.",
        )
    with second:
        st.session_state.currency = st.selectbox(
            "Currency when a file does not name one",
            ["INR", "USD", "EUR", "GBP"],
            index=["INR", "USD", "EUR", "GBP"].index(st.session_state.currency) if st.session_state.currency in ["INR", "USD", "EUR", "GBP"] else 0,
        )

    st.markdown('<div class="sw-section"><h2>Written briefing</h2><p class="sw-section-sub">Included automatically. It uses the totals already on screen, not your account numbers.</p></div>', unsafe_allow_html=True)
    st.session_state.llm_consent = st.checkbox(
        "Include the written briefing",
        value=bool(st.session_state.llm_consent),
    )
    if st.button("Refresh the briefing"):
        st.session_state.briefing_signature = None
        st.session_state.page = "Overview"
        st.rerun()

    st.markdown('<div class="sw-section"><h2>Your corrections</h2></div>', unsafe_allow_html=True)
    rules = st.session_state.user_rules or {}
    if not rules:
        st.caption("No merchant rules yet. Correct a category in Transactions and it will be remembered.")
    else:
        st.dataframe(
            [{"Merchant": key, "Category": value.get("category"), "Subcategory": value.get("subcategory")} for key, value in rules.items()],
            width="stretch",
            hide_index=True,
        )
    if st.button("Delete saved merchant rules"):
        st.session_state.user_rules = {}
        delete_rules()
        st.success("Merchant rules removed from this session and from disk.")

    if st.button("Clear loaded statements"):
        st.session_state.transactions = None
        st.session_state.notes = []
        st.session_state.demo = False
        st.session_state.stage = "onboard"
        st.session_state.parsed_files = []
        st.session_state.briefing = None
        st.rerun()
