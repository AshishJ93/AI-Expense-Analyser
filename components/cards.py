"""Insight and recommendation cards, drawn as one grid so they cannot overlap."""

from html import escape

import streamlit as st

from utils.formatting import format_inr


_PRIORITY = {
    "high": ("High priority", "warn"),
    "review": ("Worth reviewing", "neutral"),
    "habit": ("Good habit", "good"),
}


def insight_html(insight, featured: bool = False) -> str:
    figures = "".join(f'<span class="sw-pill neutral">{escape(str(figure))}</span>' for figure in insight.figures[:3])
    kind = "sw-insight featured" if featured else "sw-insight"
    return (
        f'<article class="{kind}">'
        f'<div class="sw-meta"><span class="sw-pill">{escape(str(insight.period))}</span>{figures}</div>'
        f"<h3>{escape(insight.headline)}</h3>"
        f"<p>{escape(insight.explanation)}</p>"
        f'<p class="why">{escape(insight.why_it_matters)}</p>'
        f'<p class="sw-action">{escape(insight.action)}</p>'
        f"</article>"
    )


def render_story(insights) -> None:
    if not insights:
        st.markdown('<div class="sw-note"><p>Nothing stands out in this period yet.</p></div>', unsafe_allow_html=True)
        return
    featured = insight_html(insights[0], featured=True)
    rest = insights[1:]
    grid = ""
    if rest:
        grid = '<div class="sw-story-grid">' + "".join(insight_html(item) for item in rest) + "</div>"
    st.markdown(featured + grid, unsafe_allow_html=True)


def render_insight(insight) -> None:
    st.markdown(insight_html(insight), unsafe_allow_html=True)


def recommendation_html(item, featured: bool = False) -> str:
    label, tone = _PRIORITY.get(item.priority, ("Note", "neutral"))
    savings = ""
    if item.potential_monthly_savings is not None and item.savings_basis:
        savings = (
            f"<p class='why'>A scenario, not a target. {escape(item.savings_basis)} "
            f"Illustrated difference: {escape(format_inr(item.potential_monthly_savings))} a month.</p>"
        )
    kind = "sw-decide" if featured else "sw-reco"
    amount = f"<div class='amount'>{escape(format_inr(item.amount))}</div>" if featured else ""
    return (
        f'<article class="{kind}">'
        f'<div class="sw-meta"><span class="sw-pill {tone}">{escape(label)}</span>'
        f'<span class="sw-pill neutral">{escape(item.change_text)}</span></div>'
        f"<h3>{escape(item.title)}</h3>"
        f"{amount}"
        f"<p>{escape(item.what)}</p>"
        f"<p>{escape(item.why)}</p>"
        f'<p class="sw-action">{escape(item.action)}</p>'
        f"{savings}"
        f"</article>"
    )


def render_recommendation_board(items) -> None:
    if not items:
        return
    html = ['<div class="sw-reco-grid">']
    html.extend(recommendation_html(item) for item in items)
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def render_decision(items) -> None:
    pick = next((item for item in items if item.priority == "high"), None)
    if pick is None:
        pick = next((item for item in items if item.priority == "review"), None)
    if pick is None:
        return
    st.markdown(recommendation_html(pick, featured=True), unsafe_allow_html=True)


def render_recommendation(item) -> None:
    st.markdown(recommendation_html(item), unsafe_allow_html=True)


def render_anomaly(item) -> None:
    when = item.when.strftime("%d %b %Y") if item.when else "—"
    amount = format_inr(item.amount) if item.amount is not None else "—"
    st.markdown(
        f"""
        <article class="sw-insight">
          <div class="sw-meta"><span class="sw-pill warn">Needs a look</span>
          <span class="sw-pill neutral">{escape(when)}</span>
          <span class="sw-pill neutral">{escape(amount)}</span></div>
          <h3>{escape(item.title)}</h3>
          <p>{escape(item.detail)}</p>
        </article>
        """,
        unsafe_allow_html=True,
    )
