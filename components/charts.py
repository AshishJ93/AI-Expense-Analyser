"""Plotly charts in the HisaabPehle palette."""

import pandas as pd
import plotly.graph_objects as go

from config.settings import ACCENT, CATEGORY_COLORS, GRID, INK, MUTED
from utils.formatting import format_inr

_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Manrope, Segoe UI, sans-serif", color=INK, size=13),
    hoverlabel=dict(bgcolor="#1A1A1C", font_color="#F4F1EA", font_family="Manrope, Segoe UI, sans-serif"),
    margin=dict(l=8, r=8, t=12, b=8),
    showlegend=False,
)


def _base(fig: go.Figure, height: int = 360) -> go.Figure:
    fig.update_layout(height=height, **_LAYOUT)
    fig.update_xaxes(showgrid=False, zeroline=False, tickfont=dict(color=MUTED))
    fig.update_yaxes(gridcolor=GRID, zeroline=False, tickfont=dict(color=MUTED))
    return fig


def monthly_trend(monthly: pd.DataFrame) -> go.Figure | None:
    if monthly.empty:
        return None
    labels = pd.to_datetime(monthly["month_start"]).dt.strftime("%b %Y")
    custom = [format_inr(value) for value in monthly["spending"]]
    fig = go.Figure(
        go.Scatter(
            x=labels,
            y=monthly["spending"],
            mode="lines+markers",
            line=dict(color=ACCENT, width=2.4),
            marker=dict(size=7, color=ACCENT),
            customdata=custom,
            hovertemplate="%{x}<br>%{customdata}<extra></extra>",
        )
    )
    return _base(fig, 340)


def daily_trend(daily: pd.DataFrame) -> go.Figure | None:
    if daily.empty:
        return None
    custom = [format_inr(value) for value in daily["spending"]]
    fig = go.Figure(
        go.Scatter(
            x=daily["date"],
            y=daily["spending"],
            mode="lines",
            line=dict(color=ACCENT, width=1.8),
            customdata=custom,
            hovertemplate="%{x|%d %b}<br>%{customdata}<extra></extra>",
        )
    )
    return _base(fig, 320)


def category_bars(categories: pd.DataFrame, limit: int = 8) -> go.Figure | None:
    if categories.empty:
        return None
    plot = categories[categories["spending"] > 0].head(limit).iloc[::-1]
    if plot.empty:
        return None
    colors = [CATEGORY_COLORS.get(name, "#A8A29E") for name in plot["category"]]
    custom = [format_inr(value) for value in plot["spending"]]
    fig = go.Figure(
        go.Bar(
            x=plot["spending"],
            y=plot["category"],
            orientation="h",
            marker=dict(color=colors),
            customdata=custom,
            hovertemplate="%{y}<br>%{customdata}<extra></extra>",
        )
    )
    fig = _base(fig, 360)
    fig.update_xaxes(showgrid=True, gridcolor=GRID)
    fig.update_yaxes(showgrid=False)
    return fig


def category_donut(categories: pd.DataFrame) -> go.Figure | None:
    positive = categories[categories["spending"] > 0]
    if positive.empty:
        return None
    top = positive.head(6).copy()
    rest = float(positive.iloc[6:]["spending"].sum()) if len(positive) > 6 else 0
    if rest > 0:
        top = pd.concat([top, pd.DataFrame([{"category": "Other categories", "spending": rest}])], ignore_index=True)
    colors = [CATEGORY_COLORS.get(name, "#D6D3D1") for name in top["category"]]
    custom = [format_inr(value) for value in top["spending"]]
    fig = go.Figure(
        go.Pie(
            labels=top["category"],
            values=top["spending"],
            hole=0.68,
            marker=dict(colors=colors),
            sort=False,
            customdata=custom,
            hovertemplate="%{label}<br>%{customdata}<br>%{percent}<extra></extra>",
            textinfo="none",
        )
    )
    fig.update_layout(
        height=360,
        **{
            **_LAYOUT,
            "showlegend": True,
            "legend": dict(orientation="v", y=0.5, yanchor="middle", font=dict(size=12)),
        },
    )
    return fig


def merchant_bars(merchants: pd.DataFrame) -> go.Figure | None:
    if merchants.empty:
        return None
    plot = merchants.iloc[::-1]
    custom = [format_inr(value) for value in plot["spending"]]
    fig = go.Figure(
        go.Bar(
            x=plot["spending"],
            y=plot["merchant"],
            orientation="h",
            marker=dict(color=ACCENT),
            customdata=custom,
            hovertemplate="%{y}<br>%{customdata}<extra></extra>",
        )
    )
    fig = _base(fig, 380)
    fig.update_xaxes(showgrid=True, gridcolor=GRID)
    fig.update_yaxes(showgrid=False)
    return fig


def chart_panel(title: str, definition: str, fig: go.Figure | None, empty: str, key: str) -> None:
    import streamlit as st

    with st.container(key=key):
        st.markdown(
            f'<div class="sw-panel-head"><h2>{title}</h2><p>{definition}</p></div>',
            unsafe_allow_html=True,
        )
        show_chart(fig, empty)


def show_chart(fig: go.Figure | None, empty: str) -> None:
    import streamlit as st

    if fig is None:
        st.markdown(f'<div class="sw-note"><p>{empty}</p></div>', unsafe_allow_html=True)
        return
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
