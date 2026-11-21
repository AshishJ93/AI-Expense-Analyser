"""Who was paid, and the largest individual charges."""

import streamlit as st

from components.charts import merchant_bars, show_chart
from components.header import render_header
from screens.state import build_view
from utils.formatting import format_date, format_inr


def render_merchants() -> None:
    view = build_view()
    render_header(
        "Merchants",
        "The names that account for the spending in this period.",
        "Calculated from the transactions in this period.",
    )
    show_chart(merchant_bars(view["merchants"]), "No merchant spending in this period.")

    left, right = st.columns(2)
    with left:
        st.markdown('<div class="sw-section"><h2>Most frequent</h2></div>', unsafe_allow_html=True)
        frequency = view["frequency"].copy()
        if frequency.empty:
            st.markdown('<div class="sw-note"><p>No merchants yet.</p></div>', unsafe_allow_html=True)
        else:
            frequency["Spending"] = frequency["spending"].map(format_inr)
            frequency = frequency.rename(columns={"merchant": "Merchant", "transactions": "Transactions"})
            st.dataframe(frequency[["Merchant", "Transactions", "Spending"]], width="stretch", hide_index=True)
    with right:
        st.markdown('<div class="sw-section"><h2>Largest charges</h2><p class="sw-section-sub">Including items that are not in the spending total, so a transfer is visible.</p></div>', unsafe_allow_html=True)
        largest = view["largest"]
        if largest.empty:
            st.markdown('<div class="sw-note"><p>No debits in this period.</p></div>', unsafe_allow_html=True)
        else:
            table = pd_records(largest)
            st.dataframe(table, width="stretch", hide_index=True)


def pd_records(frame):
    rows = []
    for record in frame.to_dict(orient="records"):
        rows.append(
            {
                "Date": format_date(record["date"]),
                "Merchant": record["merchant"],
                "Amount": format_inr(record["debit"]),
                "Category": record["category"],
                "In spending total": "Yes" if record["counts_as_spend"] else "No",
            }
        )
    return rows
