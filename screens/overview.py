"""The main reading of the selected period."""

import streamlit as st

from components.briefing import render_briefing
from components.cards import render_decision, render_story
from components.charts import category_bars, chart_panel, monthly_trend
from components.header import render_header
from components.metric_cards import render_kpis
from screens.state import build_view
from utils.formatting import format_inr


def render_overview() -> None:
    view = build_view()
    render_header(
        "Overview",
        "Where the money in this period went.",
        "One number for the period, then the change that deserves a decision.",
    )
    render_kpis(view["kpis"])
    render_decision(view["recommendations"])
    if any(item.priority in {"high", "review"} for item in view["recommendations"]):
        if st.button("Open the decision"):
            st.session_state.page = "Think Before You Spend"
            st.rerun()
    render_briefing(view)
    _reconciliation(view["reconciliation"])

    left, right = st.columns(2, gap="small")
    with left:
        chart_panel(
            "Monthly spending",
            "Each point is purchases minus refunds. Transfers, income, and investments are not on this line.",
            monthly_trend(view["monthly"]),
            "Not enough dated spending to draw a trend yet.",
            "panel_monthly",
        )
    with right:
        chart_panel(
            "Where it went",
            "Categories ranked by spending in the period selected above.",
            category_bars(view["categories"]),
            "No positive category totals in this period.",
            "panel_categories",
        )

    st.markdown(
        '<div class="sw-section"><h2>What stands out</h2><p class="sw-section-sub">The first note is the one to read. The rest are context.</p></div>',
        unsafe_allow_html=True,
    )
    render_story(view["insights"][:3])
    if st.button("Open spending intelligence"):
        st.session_state.page = "Spending Intelligence"
        st.rerun()


def _reconciliation(figures: dict) -> None:
    with st.expander("How total spending is counted"):
        st.markdown(
            f"""
            Spending is {format_inr(figures['spending'])}. Refunds of {format_inr(figures['refunds'])} already reduce that number.
            Income of {format_inr(figures['income'])}, investments of {format_inr(figures['investments'])}, and transfers of {format_inr(figures['transfers'])} are excluded.
            Cash withdrawals of {format_inr(figures['cash'])} are included, because the cash left the account, even though the statement cannot say what it bought.
            {figures['duplicates']} repeated row(s) are held out. {figures['needs_review']} row(s) are marked for a look — a low-confidence category is a suggestion, not a fact.
            """
        )
