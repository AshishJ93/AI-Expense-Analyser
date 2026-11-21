"""SpendWise AI — personal spending intelligence."""

from __future__ import annotations

from dotenv import load_dotenv

from components.sidebar import render_sidebar
from components.theme import inject_css
from screens.categories import render_categories
from screens.intelligence import render_intelligence
from screens.merchants import render_merchants
from screens.overview import render_overview
from screens.reports import render_reports
from screens.settings_page import render_settings
from screens.state import init_state
from screens.think import render_think
from screens.transactions import render_transactions
from screens.upload import render_upload
from screens.welcome import render_welcome

load_dotenv()

import streamlit as st


def main() -> None:
    st.set_page_config(
        page_title="SpendWise AI",
        page_icon=":material/account_balance_wallet:",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_css()
    init_state()

    if st.query_params.get("enter") == "1":
        st.session_state.entered = True

    show_tour = (
        st.session_state.transactions is None
        and not st.session_state.get("entered")
        and not st.session_state.get("replacing")
    )
    if show_tour:
        render_welcome()
        return

    if st.session_state.stage != "ready" or st.session_state.transactions is None:
        render_upload()
        return

    with st.sidebar:
        render_sidebar()

    if st.session_state.demo:
        st.markdown(
            '<div class="sw-banner">Demo · These transactions are fictional. Totals are calculated here. The briefing, if shown, is written by Grok from those totals.</div>',
            unsafe_allow_html=True,
        )

    page = st.session_state.page
    screens = {
        "Overview": render_overview,
        "Spending Intelligence": render_intelligence,
        "Think Before You Spend": render_think,
        "Categories": render_categories,
        "Merchants": render_merchants,
        "Transactions": render_transactions,
        "Reports": render_reports,
        "Settings": render_settings,
    }
    screens.get(page, render_overview)()


if __name__ == "__main__":
    main()
