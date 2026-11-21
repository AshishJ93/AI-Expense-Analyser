"""Run cleaning and categorization as one step."""

from __future__ import annotations

import pandas as pd

from services.categorizer import categorize
from services.transaction_cleaner import clean_transactions, mark_duplicates


def prepare_transactions(
    raw_frames: list[pd.DataFrame],
    user_rules: dict | None = None,
    convention: str = "auto",
    currency: str = "INR",
) -> tuple[pd.DataFrame, list[str]]:
    """Clean and classify every raw row. Nothing is deleted silently."""
    frames = [frame for frame in raw_frames if frame is not None and not frame.empty]
    if not frames:
        return pd.DataFrame(), ["Nothing was available to analyze."]

    combined = pd.concat(frames, ignore_index=True)
    combined["row_order"] = range(len(combined))
    cleaned, notes = clean_transactions(combined, convention=convention, default_currency=currency)
    classified = categorize(cleaned, user_rules or {})
    classified, duplicates = mark_duplicates(classified)
    if duplicates:
        notes.append(
            f"{duplicates} repeated row(s) match an earlier transaction with the same date, amount, and description. "
            "They stay in the list and are left out of spending totals until you restore them."
        )
    review_count = int(classified["needs_review"].sum()) if not classified.empty else 0
    if review_count:
        notes.append(
            f"{review_count} transaction(s) need a look. Low-confidence categories are suggestions, not facts."
        )
    return classified.sort_values(["date", "row_order"], na_position="last").reset_index(drop=True), notes
