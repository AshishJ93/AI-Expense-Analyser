"""Apply category corrections and remember merchant rules."""

from __future__ import annotations

import pandas as pd

from config.settings import NON_SPEND_CATEGORIES, SUBCATEGORIES
from services.categorizer import refresh_spend_flags

_KEEP_REFUND = {"refund"}


def type_for_category(category: str, current_type: str) -> str:
    if current_type in _KEEP_REFUND and category not in NON_SPEND_CATEGORIES:
        return "refund"
    if category == "Income":
        return "income"
    if category == "Transfers":
        return "transfer"
    if category == "Investments":
        return "investment"
    if category == "Cash Withdrawals":
        return "cash_withdrawal"
    if category == "Bank Charges & Fees":
        return "fee"
    if current_type in {"transfer", "income", "investment", "unclassified_credit", "fee", "cash_withdrawal"}:
        return "purchase"
    return current_type or "purchase"


def apply_user_edits(
    original: pd.DataFrame,
    edited_view: pd.DataFrame,
    user_rules: dict | None = None,
) -> tuple[pd.DataFrame, dict, int]:
    """Update rows from the editor and extend merchant rules.

    A correction to a named merchant is applied to the other rows for that
    merchant. Unknown merchants are updated only on the edited row.
    """
    rules = {key: dict(value) for key, value in (user_rules or {}).items()}
    if original.empty or edited_view.empty:
        return original.copy(), rules, 0

    updated = original.set_index("transaction_id", drop=False)
    learned: dict[str, dict] = {}
    changed_rows = 0

    for record in edited_view.to_dict(orient="records"):
        transaction_id = record.get("transaction_id")
        if transaction_id not in updated.index:
            continue
        before = updated.loc[transaction_id]
        category = str(record.get("category") or before["category"])
        subcategory = str(record.get("subcategory") or before["subcategory"])
        options = SUBCATEGORIES.get(category, ["General"])
        if subcategory not in options:
            subcategory = options[0]
        flagged = bool(record.get("flagged"))
        is_duplicate = bool(record.get("is_duplicate"))
        new_type = str(record.get("transaction_type") or before["transaction_type"])

        category_changed = category != before["category"]
        subcategory_changed = subcategory != before["subcategory"]
        type_changed = new_type != before["transaction_type"]
        duplicate_changed = is_duplicate != bool(before["is_duplicate"])
        flag_changed = flagged != bool(before["flagged"])
        if not any([category_changed, subcategory_changed, type_changed, duplicate_changed, flag_changed]):
            continue

        changed_rows += 1
        updated.at[transaction_id, "category"] = category
        updated.at[transaction_id, "subcategory"] = subcategory
        updated.at[transaction_id, "flagged"] = flagged
        updated.at[transaction_id, "is_duplicate"] = is_duplicate
        if category_changed and not type_changed:
            new_type = type_for_category(category, str(before["transaction_type"]))
        elif category_changed and type_changed:
            new_type = type_for_category(category, new_type)
        updated.at[transaction_id, "transaction_type"] = new_type
        if duplicate_changed and not is_duplicate:
            updated.at[transaction_id, "needs_review"] = False
            updated.at[transaction_id, "review_reason"] = ""

        if category_changed or subcategory_changed:
            updated.at[transaction_id, "confidence"] = 0.99
            updated.at[transaction_id, "method"] = "user_rule"
            merchant = str(before["merchant"] or "").strip()
            key = merchant.lower()
            if key and key != "unknown merchant":
                rule = {"category": category, "subcategory": subcategory, "merchant": merchant}
                rules[key] = rule
                learned[key] = rule
            if not is_duplicate:
                updated.at[transaction_id, "needs_review"] = False
                updated.at[transaction_id, "review_reason"] = ""

    result = updated.reset_index(drop=True)
    for key, rule in learned.items():
        mask = result["merchant"].fillna("").str.lower() == key
        result.loc[mask, "category"] = rule["category"]
        result.loc[mask, "subcategory"] = rule["subcategory"]
        result.loc[mask, "confidence"] = 0.99
        result.loc[mask, "method"] = "user_rule"
        types = []
        for current, is_dup in zip(result.loc[mask, "transaction_type"], result.loc[mask, "is_duplicate"]):
            types.append(type_for_category(rule["category"], str(current)))
        result.loc[mask, "transaction_type"] = types
        clear = mask & ~result["is_duplicate"].astype(bool)
        result.loc[clear, "needs_review"] = False
        result.loc[clear, "review_reason"] = ""

    result = refresh_spend_flags(result)
    return result, rules, changed_rows
