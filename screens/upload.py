"""Onboarding, column mapping, and the preview before analysis."""

from __future__ import annotations

import streamlit as st

from services.file_processor import process_bytes
from services.pipeline import prepare_transactions
from services.statement_parser import NOT_IN_FILE, apply_user_mapping
from utils.formatting import format_date
from utils.helpers import mask_sensitive

FIELDS = [
    ("date", "Date"),
    ("description", "Description"),
    ("debit", "Withdrawal / debit"),
    ("credit", "Deposit / credit"),
    ("amount", "Single amount column"),
    ("drcr", "Dr / Cr marker"),
    ("currency", "Currency"),
    ("account", "Account or card"),
]


def render_upload() -> None:
    replacing = bool(st.session_state.get("replacing")) and st.session_state.transactions is not None
    st.markdown(
        """
        <div class="sw-hero">
          <p class="sw-kicker">The app</p>
          <h1>Upload a statement.</h1>
          <p class="sw-lead">CSV, Excel, or a text PDF. You preview every row before the reading begins. Card numbers, emails, and phone numbers are masked, and the file is not saved.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.container(key="bring_file"):
        uploads = st.file_uploader(
            "Upload a statement",
            type=["csv", "xlsx", "xls", "pdf"],
            accept_multiple_files=True,
            help="CSV, Excel, or a text-based PDF. Card numbers, emails, and phone numbers are masked and are not stored.",
        )
        read = st.button("Read statements", type="primary", disabled=not uploads, width="stretch")
    if replacing and st.button("Back to dashboard", width="stretch"):
        st.session_state.stage = "ready"
        st.session_state.parsed_files = []
        st.rerun()

    if read and uploads:
        _read_uploads(uploads)

    parsed = st.session_state.get("parsed_files") or []
    if parsed:
        _render_preview(parsed, replacing)


def _read_uploads(uploads) -> None:
    parsed = []
    for upload in uploads:
        outcome = process_bytes(upload.name, upload.getvalue())
        parsed.append(outcome)
    st.session_state.parsed_files = parsed


def _render_preview(parsed, replacing: bool) -> None:
    st.markdown('<div class="sw-section"><h2>Check the read</h2><p class="sw-section-sub">Nothing is analyzed until you continue. Fix a mapping or the amount direction if a file looks wrong.</p></div>', unsafe_allow_html=True)
    for index, item in enumerate(parsed):
        _file_card(item)
        if item.status == "needs_mapping" and item.original is not None:
            _mapping_form(index, item)

    direction_labels = {
        "Detect it": "auto",
        "Positive amounts are purchases": "positive_is_spend",
        "Negative amounts are purchases": "negative_is_spend",
    }
    if "convention_label" not in st.session_state:
        st.session_state.convention_label = "Detect it"
    choice = st.radio(
        "Amount direction, if the file has one amount column",
        list(direction_labels),
        key="convention_label",
        horizontal=True,
    )
    st.session_state.convention = direction_labels[choice]

    frames = [item.frame for item in st.session_state.parsed_files if item.status == "parsed" and item.frame is not None]
    failed = [item for item in st.session_state.parsed_files if item.status == "failed"]
    if not frames:
        if failed:
            st.markdown(
                '<div class="sw-note"><p>None of the files could be read. Use the reason on each file, or export a CSV from your bank and try that.</p></div>',
                unsafe_allow_html=True,
            )
        return

    prepared, notes = prepare_transactions(
        frames,
        st.session_state.user_rules,
        convention=st.session_state.convention,
        currency=st.session_state.currency,
    )
    for note in notes:
        st.markdown(f'<div class="sw-note"><p>{note}</p></div>', unsafe_allow_html=True)

    dated = prepared["date"].dropna()
    span = "No dated rows"
    if not dated.empty:
        span = f"{format_date(dated.min())} – {format_date(dated.max())}"
    review = int(prepared["needs_review"].sum())
    st.markdown(
        f'<div class="sw-file"><div><strong>{len(prepared)} rows ready</strong><span>{span} · {review} need a look</span></div></div>',
        unsafe_allow_html=True,
    )
    preview = prepared[["date", "description", "debit", "credit", "merchant", "category", "needs_review", "source_file"]].head(40).copy()
    preview["date"] = preview["date"].apply(format_date)
    st.dataframe(preview, width="stretch", hide_index=True)

    label = "Replace and analyze" if replacing else "Analyze spending"
    if st.button(label, type="primary"):
        file_notes = [f"{item.filename}: {item.message}" for item in failed]
        _commit(prepared, file_notes + notes, demo=False)


def _file_card(item) -> None:
    tone = {"parsed": "good", "needs_mapping": "warn", "failed": "bad"}.get(item.status, "neutral")
    label = {"parsed": "Ready", "needs_mapping": "Map columns", "failed": "Needs a different file"}.get(item.status, item.status)
    warning = " ".join(item.warnings)
    st.markdown(
        f'<div class="sw-file"><div><strong>{item.filename}</strong><span>{item.message} {warning}</span></div><span class="sw-pill {tone}">{label}</span></div>',
        unsafe_allow_html=True,
    )


def _mapping_form(index: int, item) -> None:
    columns = [NOT_IN_FILE, *[str(column) for column in item.original.columns]]
    st.caption(f"Map columns for {item.filename}")
    st.dataframe(_masked_preview(item.original.head(5)), width="stretch", hide_index=True)
    mapping = {}
    picks = st.columns(4)
    for position, (field, label) in enumerate(FIELDS):
        current = item.suggested_mapping.get(field) or NOT_IN_FILE
        if current not in columns:
            current = NOT_IN_FILE
        with picks[position % 4]:
            mapping[field] = st.selectbox(label, columns, index=columns.index(current), key=f"map_{index}_{field}")
    if st.button("Apply mapping", key=f"apply_map_{index}"):
        updated = apply_user_mapping(item.original, mapping, item.filename)
        item.status = updated.status
        item.frame = updated.frame
        item.message = updated.message
        item.suggested_mapping = updated.suggested_mapping or mapping
        st.session_state.parsed_files[index] = item
        st.rerun()


def _masked_preview(frame):
    shown = frame.copy()
    for column in shown.columns:
        shown[column] = shown[column].map(lambda value: mask_sensitive(str(value)) if value is not None else value)
    return shown


def _commit(frame, notes, demo: bool) -> None:
    st.session_state.transactions = frame
    st.session_state.notes = notes
    st.session_state.demo = demo
    st.session_state.stage = "ready"
    st.session_state.replacing = False
    st.session_state.parsed_files = []
    st.session_state.page = "Overview"
    st.session_state.nav_radio = "Overview"
    st.session_state.data_version = int(st.session_state.get("data_version", 0)) + 1
    st.session_state.briefing = None
    st.session_state.briefing_error = None
    st.rerun()
