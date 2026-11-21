"""Rule-based categorization with room for the user's own merchant rules.

Low-confidence rows are flagged. They are never presented as settled facts.
"""

from __future__ import annotations

import re

import pandas as pd

from config.settings import NON_SPEND_CATEGORIES, SUBCATEGORIES
from services.signals import (
    generic_hit,
    is_cash,
    is_channel_transfer,
    is_explicit_transfer,
    is_fee,
    is_income,
    is_refund,
    is_upi,
    merchant_hit,
)

_STOP = {
    "upi", "pos", "neft", "imps", "rtgs", "ach", "nach", "atm", "dr", "cr",
    "in", "to", "from", "payment", "pay", "txn", "ref", "by", "via", "the",
    "and", "for", "ltd", "pvt", "private", "limited",
}


def fallback_merchant(description: str) -> str:
    text = description or ""
    text = re.sub(r"\b[\w.+-]+@[\w.-]+\b", " ", text)
    text = re.sub(r"\b[A-Z]{4}0[A-Z0-9]{6}\b", " ", text, flags=re.I)
    text = re.sub(r"\b\d{5,}\b", " ", text)
    text = re.sub(r"[^A-Za-z\s&]", " ", text)
    words = [word for word in text.split() if word.lower() not in _STOP and len(word) > 1]
    if not words:
        return "Unknown merchant"
    return " ".join(words[:4]).title()


def default_subcategory(category: str) -> str:
    options = SUBCATEGORIES.get(category) or ["General"]
    return options[0]


def _user_rule(description: str, user_rules: dict) -> dict | None:
    lowered = (description or "").lower()
    for key, rule in sorted(user_rules.items(), key=lambda item: len(item[0]), reverse=True):
        if key and key in lowered:
            category = rule.get("category", "Other")
            subcategory = rule.get("subcategory") or default_subcategory(category)
            merchant = rule.get("merchant") or key.title()
            return {
                "merchant": merchant,
                "category": category,
                "subcategory": subcategory,
                "confidence": 0.98,
                "method": "user_rule",
            }
    return None


def classify_description(description: str, user_rules: dict | None = None) -> dict:
    """Classify a single narration. Amount direction is applied separately."""
    user_rules = user_rules or {}
    text = description or ""
    learned = _user_rule(text, user_rules)
    if learned:
        return learned

    hit = merchant_hit(text)
    if hit:
        category, subcategory, merchant = hit
        if category == "Healthcare":
            if re.search(r"hospital|clinic|fortis|manipal", text, re.I):
                subcategory = "Hospital"
            elif re.search(r"pharmacy|pharmeasy|apollo|medplus|netmeds|1mg", text, re.I):
                subcategory = "Pharmacy"
        return {
            "merchant": merchant,
            "category": category,
            "subcategory": subcategory,
            "confidence": 0.9,
            "method": "merchant_rule",
        }

    generic = generic_hit(text)
    if generic:
        category, subcategory = generic
        return {
            "merchant": fallback_merchant(text),
            "category": category,
            "subcategory": subcategory,
            "confidence": 0.62,
            "method": "keyword",
        }

    return {
        "merchant": fallback_merchant(text),
        "category": "Other",
        "subcategory": "General",
        "confidence": 0.34,
        "method": "fallback",
    }


def _apply_type(row: dict) -> dict:
    """Set transaction type, review flags, and whether the row affects spending."""
    text = row["description"]
    category = row["category"]
    debit = float(row["debit"] or 0)
    credit = float(row["credit"] or 0)
    money_in = credit > debit and credit > 0
    reasons = [row.get("review_reason") or ""]
    needs_review = bool(row.get("needs_review"))

    if is_income(text):
        row["category"] = "Income"
        row["subcategory"] = "Salary" if re.search(r"salary|payroll", text, re.I) else "Interest"
        row["transaction_type"] = "income"
        row["confidence"] = max(float(row["confidence"]), 0.9)
        row["method"] = "statement_type" if row["method"] == "fallback" else row["method"]
    elif is_refund(text):
        row["transaction_type"] = "refund"
        if row["category"] in {"Income", "Transfers"}:
            row["category"] = "Other"
            row["subcategory"] = "General"
        if debit > credit:
            needs_review = True
            reasons.append("The description says refund, but the amount is shown as money out.")
    elif is_cash(text) or category == "Cash Withdrawals":
        row["category"] = "Cash Withdrawals"
        row["subcategory"] = "ATM"
        row["transaction_type"] = "cash_withdrawal"
        row["confidence"] = max(float(row["confidence"]), 0.86)
    elif is_explicit_transfer(text):
        row["category"] = "Transfers"
        row["subcategory"] = "Card Payment" if re.search(r"card", text, re.I) else "Self Transfer"
        row["transaction_type"] = "transfer"
        row["confidence"] = max(float(row["confidence"]), 0.84)
        row["method"] = "statement_type"
    elif category == "Investments":
        row["transaction_type"] = "investment"
    elif category == "Transfers":
        row["transaction_type"] = "transfer"
    elif is_fee(text) or category == "Bank Charges & Fees":
        row["category"] = "Bank Charges & Fees"
        row["subcategory"] = row["subcategory"] if row["category"] == "Bank Charges & Fees" else "Account Fees"
        row["transaction_type"] = "fee"
        row["confidence"] = max(float(row["confidence"]), 0.8)
    elif category == "Other" and (is_channel_transfer(text) or is_upi(text)):
        row["category"] = "Transfers"
        row["subcategory"] = "Person"
        row["transaction_type"] = "transfer"
        row["confidence"] = 0.44
        row["method"] = "channel_heuristic"
        needs_review = True
        reasons.append(
            "No merchant was recognized. This is held as a transfer so it does not inflate spending. Recategorize it if it was a purchase."
        )
    elif money_in and category not in NON_SPEND_CATEGORIES:
        row["transaction_type"] = "unclassified_credit"
        needs_review = True
        reasons.append(
            "Money came in at this merchant without a refund marker, so it was not subtracted from spending."
        )
    else:
        row["transaction_type"] = "purchase"

    if float(row["confidence"]) < 0.6 and row["transaction_type"] == "purchase":
        needs_review = True
        reasons.append("The category is a suggestion. Please confirm it.")

    if debit == 0 and credit == 0:
        needs_review = True
        row["transaction_type"] = row.get("transaction_type") or "purchase"
        reasons.append("No amount could be read from this row.")

    row["needs_review"] = needs_review
    row["review_reason"] = " ".join(part for part in reasons if part).strip()
    row["counts_as_spend"] = _counts(row)
    return row


def _counts(row: dict) -> bool:
    if row.get("is_duplicate"):
        return False
    parsed_date = pd.to_datetime(row.get("date"), errors="coerce")
    if pd.isna(parsed_date):
        return False
    debit = float(row.get("debit") or 0)
    credit = float(row.get("credit") or 0)
    if debit == 0 and credit == 0:
        return False
    txn_type = row.get("transaction_type")
    category = row.get("category")
    if txn_type in {"income", "transfer", "investment", "unclassified_credit"}:
        return False
    if category in NON_SPEND_CATEGORIES:
        return False
    return True


def refresh_spend_flags(frame: pd.DataFrame) -> pd.DataFrame:
    """Recompute which rows belong in spending totals after a user edit."""
    if frame.empty:
        return frame.copy()
    result = frame.copy()
    result["counts_as_spend"] = [_counts(record) for record in result.to_dict(orient="records")]
    return result


def categorize(frame: pd.DataFrame, user_rules: dict | None = None) -> pd.DataFrame:
    """Add merchant, category, type, and spend flags. Does not drop rows."""
    user_rules = user_rules or {}
    if frame.empty:
        return frame.copy()

    records = []
    for record in frame.to_dict(orient="records"):
        classified = classify_description(str(record.get("description") or ""), user_rules)
        record.update(classified)
        record.setdefault("is_duplicate", False)
        record.setdefault("flagged", False)
        records.append(_apply_type(record))
    return pd.DataFrame.from_records(records)
