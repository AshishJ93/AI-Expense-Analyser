"""Headline figures, each one labeled with what it counts."""

from html import escape

import streamlit as st

from utils.formatting import format_inr, format_percent


def _tone(change: float | None) -> str:
    if change is None or abs(change) < 0.005:
        return "sw-flat"
    return "sw-up" if change > 0 else "sw-down"


def _rail(label: str, value: str, definition: str) -> str:
    return (
        f"<article><div class='label'>{escape(label)}</div>"
        f"<div class='value'>{escape(value)}</div>"
        f"<p>{escape(definition)}</p></article>"
    )


def render_kpis(kpis) -> None:
    share = format_percent(kpis.top_category_share, signed=False) if kpis.top_category_share is not None else "—"
    change = format_percent(kpis.mom_change)
    category_value = kpis.top_category or "—"
    compare = f"{kpis.mom_label}. {kpis.mom_note}".strip(" .")
    stage = f"""
    <section class="sw-stage">
      <article class="sw-stage-main">
        <div class="label">Total spending</div>
        <div class="figure">{escape(format_inr(kpis.total_spending))}</div>
        <p class="sw-def">{escape(kpis.period_label)}. Purchases minus refunds. Income, transfers, and investments stay out.</p>
      </article>
      <article class="sw-stage-signal">
        <div class="label">Since the previous month</div>
        <div class="figure {_tone(kpis.mom_change)}">{escape(change)}</div>
        <p class="sw-def">{escape(compare)}.</p>
      </article>
    </section>
    <div class="sw-rail">
      {_rail("Average month", format_inr(kpis.average_monthly), kpis.average_note)}
      {_rail("Largest category", category_value, f"{format_inr(kpis.top_category_amount)} · {share} of this period")}
      {_rail("Transactions", str(kpis.all_transactions), f"{kpis.spending_transactions} count toward spending")}
    </div>
    """
    st.markdown(stage, unsafe_allow_html=True)
    if kpis.mixed_currency:
        st.markdown(
            f'<div class="sw-banner warn">More than one currency is loaded. Totals use {escape(kpis.currency)} only and are not converted.</div>',
            unsafe_allow_html=True,
        )


def render_capability_strip() -> None:
    """Says what is calculated locally and what the briefing is."""
    from screens.state import llm_settings

    config = llm_settings()
    if config.api_key and config.consent:
        ai_body = "One paragraph written from the figures already calculated. Account numbers are not sent."
        ai_pill = "Briefing"
    elif config.api_key:
        ai_body = "Paused in Settings. Totals and charts are unchanged."
        ai_pill = "Briefing off"
    else:
        ai_body = "Unavailable right now. Totals and charts are unchanged."
        ai_pill = "Briefing off"
    st.markdown(
        f"""
        <div class="sw-keybar">
          <div><span class="sw-pill">On this computer</span><span>Totals, charts, categories, merchants, and recommendations.</span></div>
          <div><span class="sw-pill">{escape(ai_pill)}</span><span>{escape(ai_body)}</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
