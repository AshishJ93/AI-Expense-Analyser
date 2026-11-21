"""Category totals and how they moved."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components.charts import category_donut, show_chart
from components.header import render_header
from config.settings import CATEGORY_COLORS, GRID, INK, MUTED
from screens.state import build_view
from utils.formatting import format_inr, format_percent


def render_categories() -> None:
    view = build_view()
    render_header(
        "Categories",
        "What the money went to, and how that changed.",
        "Calculated from the transactions in this period.",
    )
    left, right = st.columns([0.9, 1.1])
    with left:
        show_chart(category_donut(view["categories"]), "No positive category totals in this period.")
    with right:
        show_chart(_grouped(view["monthly_category"]), "Not enough months to compare categories.")

    categories = view["categories"]
    if categories.empty:
        return
    table = categories.copy()
    table["Spending"] = table["spending"].map(lambda value: format_inr(value))
    table["Share"] = table["share"].map(lambda value: format_percent(value, signed=False))
    table = table.rename(columns={"category": "Category", "transactions": "Transactions"})
    st.dataframe(table[["Category", "Spending", "Share", "Transactions"]], width="stretch", hide_index=True)


def _grouped(monthly_category: pd.DataFrame) -> go.Figure | None:
    if monthly_category.empty:
        return None
    totals = monthly_category.groupby("category")["spending"].sum().sort_values(ascending=False)
    keep = list(totals.head(5).index)
    plot = monthly_category.copy()
    plot["series"] = plot["category"].where(plot["category"].isin(keep), "Other categories")
    pivot = plot.groupby(["month", "series"], as_index=False)["spending"].sum()
    fig = go.Figure()
    for series in list(keep) + (["Other categories"] if (pivot["series"] == "Other categories").any() else []):
        part = pivot[pivot["series"] == series]
        fig.add_bar(
            name=series,
            x=part["month"],
            y=part["spending"],
            marker_color=CATEGORY_COLORS.get(series, "#D6D3D1"),
            hovertemplate="%{x}<br>" + series + "<br>%{y:,.0f}<extra></extra>",
        )
    fig.update_layout(
        barmode="stack",
        height=360,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Manrope, Segoe UI, sans-serif", color=INK, size=13),
        legend=dict(orientation="h", y=-0.2),
        margin=dict(l=8, r=8, t=12, b=8),
        yaxis=dict(gridcolor=GRID, tickfont=dict(color=MUTED)),
        xaxis=dict(tickfont=dict(color=MUTED)),
    )
    return fig
