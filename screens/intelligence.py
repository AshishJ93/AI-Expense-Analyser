"""Grounded observations, patterns, recurring payments, and review items."""

from html import escape

import streamlit as st

from components.briefing import render_briefing
from components.cards import render_anomaly, render_story
from components.charts import chart_panel, daily_trend
from components.header import render_header
from screens.state import build_view
from services.subscription_detector import subscription_monthly_total
from utils.formatting import format_date, format_inr


def render_intelligence() -> None:
    view = build_view()
    render_header(
        "Spending intelligence",
        "Patterns in the period you selected.",
        "Pick a lens. Each one answers a single question.",
    )
    choice = _segment()
    render_briefing(view)
    render_story(view["insights"][:3])
    if view["history_expanded"]:
        st.markdown(
            '<div class="sw-banner">This period is short, so comparisons that need history use the other loaded months and say so.</div>',
            unsafe_allow_html=True,
        )

    if choice == "Daily":
        chart_panel(
            "Daily spending",
            "Each point is that day's purchases minus refunds.",
            daily_trend(view["daily"]),
            "No daily spending in this period.",
            "panel_daily",
        )
    elif choice == "Patterns":
        _patterns(view["behavior"], view["consistency"])
    elif choice == "Recurring":
        _recurring(view["recurring"])
    else:
        if not view["anomalies"]:
            st.markdown('<div class="sw-note"><p>Nothing in this period stands out against the rest of the history. That is a fine result.</p></div>', unsafe_allow_html=True)
        for item in view["anomalies"]:
            render_anomaly(item)


def _segment() -> str:
    options = ["Daily", "Patterns", "Recurring", "Review"]
    if st.session_state.get("intel_tab") not in options:
        st.session_state.intel_tab = "Daily"
    st.radio(
        "Choose a view",
        options,
        horizontal=True,
        key="intel_tab",
    )
    prompts = {
        "Daily": "Where the days spiked.",
        "Patterns": "Weekends against weekdays, in one glance.",
        "Recurring": "What is likely to leave again next month.",
        "Review": "Rows that deserve a second look. Not a fraud verdict.",
    }
    st.markdown(f'<p class="sw-source-line">{prompts[st.session_state.intel_tab]}</p>', unsafe_allow_html=True)
    return st.session_state.intel_tab


def _patterns(stats: dict, consistency: dict) -> None:
    weekend = stats["weekend_daily"]
    weekday = stats["weekday_daily"]
    if weekend is None or weekday is None:
        st.markdown('<div class="sw-note"><p>Not enough dated spending to compare weekdays and weekends.</p></div>', unsafe_allow_html=True)
        return
    ratio = None if weekday == 0 else weekend / weekday
    comparison = "Weekends and weekdays are close." if ratio and 0.85 <= ratio <= 1.15 else (
        "Weekend days are running higher." if ratio and ratio > 1 else "Weekday days are running higher."
    )
    delivery_line = ""
    if stats["delivery_weekend_daily"] and stats["delivery_weekday_daily"]:
        delivery_line = (
            f" Food delivery averages {format_inr(stats['delivery_weekend_daily'])} on a weekend day and "
            f"{format_inr(stats['delivery_weekday_daily'])} on a weekday."
        )
    average = format_inr(stats["average_transaction"]) if stats["average_transaction"] else "—"
    st.markdown(
        f"""
        <div class="sw-stat-grid">
          <article class="sw-stat"><div class="label">Weekend day</div><div class="value">{format_inr(weekend)}</div><p>{stats['weekend_days']} days in this span</p></article>
          <article class="sw-stat"><div class="label">Weekday</div><div class="value">{format_inr(weekday)}</div><p>{stats['weekday_days']} days in this span</p></article>
          <article class="sw-stat"><div class="label">Typical purchase</div><div class="value">{average}</div><p>{consistency['label']}</p></article>
        </div>
        <div class="sw-note"><p>{comparison}{delivery_line}</p></div>
        """,
        unsafe_allow_html=True,
    )


def _recurring(items) -> None:
    st.caption("Detected from all loaded months, because a monthly charge needs more than one month to see.")
    if not items:
        st.markdown('<div class="sw-note"><p>No monthly repeat was found. That takes at least three similar amounts about 30 days apart.</p></div>', unsafe_allow_html=True)
        return
    total = subscription_monthly_total(items)
    rows = []
    for item in items:
        rows.append(
            "<article class='sw-sub'>"
            f"<div><strong>{escape(str(item.merchant))}</strong><span>{escape(str(item.kind))} · {item.occurrences} times · last {escape(format_date(item.last_date))}</span></div>"
            f"<div class='amt'>{format_inr(item.typical_amount)}</div>"
            "</article>"
        )
    st.markdown(
        f'<div class="sw-note"><p>Subscriptions here come to about {format_inr(total)} a month. Bills and investments are listed too, and they are not called subscriptions.</p></div>'
        f'<div class="sw-sub-list">{"".join(rows)}</div>',
        unsafe_allow_html=True,
    )
