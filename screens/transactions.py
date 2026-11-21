"""Searchable ledger with category corrections."""

import io

import pandas as pd
import streamlit as st

from config.settings import CATEGORIES, SUBCATEGORIES
from components.header import render_header
from screens.state import build_view
from services.edits import apply_user_edits
from services.rules_store import save_rules
from utils.formatting import confidence_display, format_date

TYPES = [
    "purchase",
    "refund",
    "income",
    "transfer",
    "investment",
    "fee",
    "cash_withdrawal",
    "unclassified_credit",
]


def render_transactions() -> None:
    view = build_view()
    render_header(
        "Transactions",
        "Search, correct a category, or restore a row that was held out as a duplicate.",
        "Search and correct categories in this session.",
    )
    frame = view["period_df"].copy()
    if frame.empty:
        st.markdown('<div class="sw-note"><p>No transactions in this period.</p></div>', unsafe_allow_html=True)
        return

    search, category, kind, review_only = st.columns([1.3, 1, 1, 0.8])
    with search:
        query = st.text_input("Search merchant or description", placeholder="Swiggy, rent, ATM")
    with category:
        categories = ["All categories", *CATEGORIES]
        chosen = st.selectbox("Category", categories)
    with kind:
        kinds = ["All types", *sorted(frame["transaction_type"].dropna().unique())]
        chosen_type = st.selectbox("Transaction type", kinds)
    with review_only:
        only_review = st.checkbox("Needs a look")

    filtered = _filter(frame, query, chosen, chosen_type, only_review)
    st.caption(f"{len(filtered)} rows · save corrections before changing the filters · {int(filtered['needs_review'].sum())} still need a look")

    editor = _editor_frame(filtered)
    edited = st.data_editor(
        editor,
        width="stretch",
        hide_index=True,
        num_rows="fixed",
        key=f"editor_{st.session_state.data_version}_{chosen}_{chosen_type}_{only_review}_{query}",
        column_config=_column_config(),
        disabled=["transaction_id", "date_label", "merchant", "description", "debit", "credit", "confidence_label", "source_file"],
    )
    if st.button("Save corrections", type="primary"):
        updated, rules, changed = apply_user_edits(st.session_state.transactions, _from_editor(edited), st.session_state.user_rules)
        st.session_state.transactions = updated
        st.session_state.user_rules = rules
        st.session_state.data_version += 1
        try:
            save_rules(rules)
        except OSError:
            st.warning("The correction is applied in this session, but the merchant rule could not be saved to disk.")
        if changed:
            st.success(f"Updated {changed} row(s). A named merchant is corrected everywhere it appears.")
        else:
            st.info("No edits to save.")
        st.rerun()

    export = _export_frame(filtered)
    csv_bytes = export.to_csv(index=False).encode("utf-8")
    excel_buffer = io.BytesIO()
    export.to_excel(excel_buffer, index=False)
    first, second = st.columns(2)
    with first:
        st.download_button("Download this view as CSV", csv_bytes, file_name="spendwise-transactions.csv", mime="text/csv")
    with second:
        st.download_button(
            "Download this view as Excel",
            excel_buffer.getvalue(),
            file_name="spendwise-transactions.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


def _filter(frame: pd.DataFrame, query: str, category: str, kind: str, review_only: bool) -> pd.DataFrame:
    result = frame
    if query:
        mask = (
            result["merchant"].fillna("").str.contains(query, case=False)
            | result["description"].fillna("").str.contains(query, case=False)
        )
        result = result[mask]
    if category != "All categories":
        result = result[result["category"] == category]
    if kind != "All types":
        result = result[result["transaction_type"] == kind]
    if review_only:
        result = result[result["needs_review"].fillna(False) | result["flagged"].fillna(False)]
    return result.sort_values(["date", "row_order"], na_position="last")


def _editor_frame(frame: pd.DataFrame) -> pd.DataFrame:
    editor = frame.copy()
    editor["date_label"] = editor["date"].apply(format_date)
    editor["confidence_label"] = editor["confidence"].apply(confidence_display)
    columns = [
        "transaction_id",
        "date_label",
        "merchant",
        "description",
        "debit",
        "credit",
        "category",
        "subcategory",
        "transaction_type",
        "confidence_label",
        "flagged",
        "is_duplicate",
        "source_file",
    ]
    return editor[columns]


def _from_editor(edited: pd.DataFrame) -> pd.DataFrame:
    mapped = edited.rename(columns={"date_label": "date"})
    return mapped


def _export_frame(frame: pd.DataFrame) -> pd.DataFrame:
    export = frame.copy()
    export["date"] = pd.to_datetime(export["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    export["confidence"] = export["confidence"].apply(confidence_display)
    columns = [
        "date",
        "merchant",
        "description",
        "debit",
        "credit",
        "currency",
        "category",
        "subcategory",
        "transaction_type",
        "confidence",
        "counts_as_spend",
        "needs_review",
        "review_reason",
        "flagged",
        "is_duplicate",
        "account_label",
        "source_file",
    ]
    return export[[column for column in columns if column in export.columns]]


def _column_config():
    subcategories = sorted({item for values in SUBCATEGORIES.values() for item in values})
    return {
        "transaction_id": st.column_config.TextColumn("Id", width="small"),
        "date_label": st.column_config.TextColumn("Date"),
        "merchant": st.column_config.TextColumn("Merchant"),
        "description": st.column_config.TextColumn("Description", width="large"),
        "debit": st.column_config.NumberColumn("Debit", format="₹%.2f"),
        "credit": st.column_config.NumberColumn("Credit", format="₹%.2f"),
        "category": st.column_config.SelectboxColumn("Category", options=CATEGORIES, required=True),
        "subcategory": st.column_config.SelectboxColumn("Subcategory", options=subcategories),
        "transaction_type": st.column_config.SelectboxColumn("Type", options=TYPES, required=True),
        "confidence_label": st.column_config.TextColumn("Confidence"),
        "flagged": st.column_config.CheckboxColumn("Flag"),
        "is_duplicate": st.column_config.CheckboxColumn("Duplicate"),
        "source_file": st.column_config.TextColumn("File"),
    }
