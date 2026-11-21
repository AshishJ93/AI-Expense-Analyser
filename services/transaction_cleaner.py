"""Normalize dates, amounts, duplicates, and sensitive identifiers.

Rows are kept even when a date or amount cannot be read. Those rows are
flagged and left out of spending totals.
"""

from __future__ import annotations

import re
from datetime import date

import pandas as pd

from services.signals import is_income, merchant_hit
from utils.helpers import mask_account_label, mask_sensitive, new_id

RAW_COLUMNS = [
    "date",
    "description",
    "debit",
    "credit",
    "amount",
    "drcr",
    "currency",
    "account",
    "source_file",
    "row_order",
]


def parse_number_and_marker(value) -> tuple[float | None, str | None]:
    """Parse a money cell. Parentheses and a leading minus become negative."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None, None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if pd.isna(value):
            return None, None
        return float(value), None

    text = str(value).strip()
    if text == "" or text.lower() in {"nan", "none", "null", "-", "—", "na"}:
        return None, None

    marker = None
    if re.search(r"\b(dr|debit)\b", text, re.I):
        marker = "dr"
    elif re.search(r"\b(cr|credit)\b", text, re.I):
        marker = "cr"

    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]
    if text.strip().startswith("-"):
        negative = True

    text = (
        text.replace("₹", "")
        .replace("Rs.", "")
        .replace("RS.", "")
        .replace("INR", "")
        .replace("inr", "")
    )
    text = re.sub(r"(?i)\b(dr|cr|debit|credit|rs)\b", "", text)
    text = text.replace(",", "").replace(" ", "").replace("+", "")
    text = text.replace("-", "")
    text = re.sub(r"[^0-9.]", "", text)
    if text.count(".") > 1:
        parts = text.split(".")
        text = "".join(parts[:-1]) + "." + parts[-1]
    if text in {"", "."}:
        return None, marker
    number = float(text)
    if negative and marker is None:
        number = -abs(number)
    else:
        number = abs(number) if marker else number
    return number, marker


def parse_date_value(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return pd.NaT
    if isinstance(value, pd.Timestamp):
        return value
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "nat"}:
        return pd.NaT
    if re.match(r"^\d{4}-\d{2}-\d{2}", text):
        return pd.to_datetime(text, format="%Y-%m-%d", errors="coerce")
    parsed = pd.to_datetime(text, dayfirst=True, errors="coerce")
    if pd.isna(parsed):
        parsed = pd.to_datetime(text, dayfirst=False, errors="coerce")
    return parsed


def _marker(value) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip().lower()
    if text in {"dr", "debit", "d", "withdrawal", "withdrawals", "money out"}:
        return "dr"
    if text in {"cr", "credit", "c", "deposit", "deposits", "money in"}:
        return "cr"
    return None


def infer_convention(descriptions: list[str], signed_amounts: list[float | None]) -> tuple[str, str]:
    """Decide whether a lone amount column is card-style or bank-style."""
    merchant_signs = []
    income_signs = []
    for description, amount in zip(descriptions, signed_amounts):
        if amount is None or amount == 0:
            continue
        sign = 1 if amount > 0 else -1
        if merchant_hit(description or ""):
            merchant_signs.append(sign)
        if is_income(description or ""):
            income_signs.append(sign)

    def _majority(signs: list[int]) -> int:
        if not signs:
            return 0
        return 1 if sum(signs) > 0 else -1 if sum(signs) < 0 else 0

    merchant_way = _majority(merchant_signs)
    income_way = _majority(income_signs)
    bank_score = 0
    card_score = 0
    if merchant_way < 0:
        bank_score += 2
    elif merchant_way > 0:
        card_score += 2
    if income_way > 0:
        bank_score += 2
    elif income_way < 0:
        card_score += 2

    if bank_score > card_score:
        return (
            "negative_is_spend",
            "Positive amounts were read as money in, and negative amounts as spending. This matches a typical bank export. You can switch it if the totals look reversed.",
        )
    if card_score > bank_score:
        return (
            "positive_is_spend",
            "Positive amounts were read as spending, and negative amounts as refunds or payments. This matches a typical card export. You can switch it if the totals look reversed.",
        )
    return (
        "positive_is_spend",
        "The file has a single amount column and the direction was not obvious. Positive amounts are treated as spending for now. Switch the direction in the preview if deposits and purchases look swapped.",
    )


def _resolve_amount(debit_cell, credit_cell, amount_cell, drcr_cell, convention: str) -> tuple[float, float]:
    debit_value, debit_marker = parse_number_and_marker(debit_cell)
    credit_value, credit_marker = parse_number_and_marker(credit_cell)
    amount_value, amount_marker = parse_number_and_marker(amount_cell)
    marker = _marker(drcr_cell) or debit_marker or credit_marker or amount_marker

    debit = 0.0
    credit = 0.0
    used_column = False

    if debit_value is not None and abs(debit_value) > 0:
        used_column = True
        if debit_marker == "cr":
            credit += abs(debit_value)
        else:
            debit += abs(debit_value)
    if credit_value is not None and abs(credit_value) > 0:
        used_column = True
        if credit_marker == "dr":
            debit += abs(credit_value)
        elif credit_value < 0 and credit_marker is None:
            debit += abs(credit_value)
        else:
            credit += abs(credit_value)

    if used_column or amount_value is None or abs(amount_value) == 0:
        return round(debit, 2), round(credit, 2)

    magnitude = abs(amount_value)
    if marker == "dr":
        debit = magnitude
    elif marker == "cr":
        credit = magnitude
    elif amount_value < 0:
        if convention == "positive_is_spend":
            credit = magnitude
        else:
            debit = magnitude
    else:
        if convention == "negative_is_spend":
            credit = magnitude
        else:
            debit = magnitude
    return round(debit, 2), round(credit, 2)


def prepare_raw_frame(frame: pd.DataFrame) -> pd.DataFrame:
    prepared = frame.copy()
    for column in RAW_COLUMNS:
        if column not in prepared.columns:
            prepared[column] = None
    if "row_order" not in frame.columns or prepared["row_order"].isna().all():
        prepared["row_order"] = range(len(prepared))
    return prepared[RAW_COLUMNS]


def clean_transactions(
    frame: pd.DataFrame,
    convention: str = "auto",
    default_currency: str = "INR",
) -> tuple[pd.DataFrame, list[str]]:
    """Return a cleaned frame and user-facing notes. No transaction is deleted."""
    notes: list[str] = []
    raw = prepare_raw_frame(frame)
    if raw.empty:
        notes.append("No transaction rows were found.")
        return _empty_clean_frame(), notes

    descriptions = ["" if pd.isna(value) else str(value) for value in raw["description"]]
    amount_probe = [parse_number_and_marker(value)[0] for value in raw["amount"]]
    has_split_columns = any(
        (parse_number_and_marker(d)[0] not in (None, 0)) or (parse_number_and_marker(c)[0] not in (None, 0))
        for d, c in zip(raw["debit"], raw["credit"])
    )

    resolved_convention = convention
    if has_split_columns and convention in {"auto", "debit_credit"}:
        resolved_convention = "debit_credit"
    elif convention == "auto":
        resolved_convention, explanation = infer_convention(descriptions, amount_probe)
        notes.append(explanation)
    elif convention == "positive_is_spend":
        notes.append("Using your choice: positive amounts count as spending.")
    elif convention == "negative_is_spend":
        notes.append("Using your choice: negative amounts count as spending.")

    currencies = []
    assumed_any = False
    records = []
    for position, source in enumerate(raw.to_dict(orient="records")):
        description = mask_sensitive("" if pd.isna(source["description"]) else str(source["description"]).strip())
        debit, credit = _resolve_amount(
            source["debit"], source["credit"], source["amount"], source["drcr"], resolved_convention
        )
        parsed_date = parse_date_value(source["date"])
        currency_raw = "" if pd.isna(source["currency"]) else str(source["currency"]).strip().upper()
        assumed = False
        if not currency_raw:
            currency_raw = default_currency
            assumed = True
            assumed_any = True
        elif currency_raw in {"RS", "RS.", "₹"}:
            currency_raw = "INR"
        currencies.append(currency_raw)

        reasons = []
        needs_review = False
        if pd.isna(parsed_date):
            needs_review = True
            reasons.append("The date could not be read, so this row is excluded from totals.")
        else:
            as_date = parsed_date.date()
            if as_date > date.today():
                needs_review = True
                reasons.append("The date is in the future.")
            elif as_date.year < 2000:
                needs_review = True
                reasons.append("The date looks unusually old.")
        if debit == 0 and credit == 0:
            needs_review = True
            reasons.append("No amount could be read from this row.")

        records.append(
            {
                "transaction_id": new_id(),
                "date": parsed_date,
                "description": description or "(blank description)",
                "merchant": "",
                "debit": debit,
                "credit": credit,
                "currency": currency_raw,
                "currency_assumed": assumed,
                "account_label": mask_account_label(None if pd.isna(source["account"]) else source["account"]),
                "category": "",
                "subcategory": "",
                "confidence": 0.0,
                "method": "",
                "transaction_type": "",
                "counts_as_spend": False,
                "needs_review": needs_review,
                "review_reason": " ".join(reasons),
                "flagged": False,
                "is_duplicate": False,
                "source_file": "" if pd.isna(source["source_file"]) else str(source["source_file"]),
                "row_order": int(source["row_order"]) if pd.notna(source["row_order"]) else position,
            }
        )

    cleaned = pd.DataFrame.from_records(records)
    if assumed_any:
        notes.append(
            f"Some rows did not name a currency. Those amounts are shown as {default_currency} until you say otherwise."
        )
    distinct = sorted({code for code in currencies if code})
    if len(distinct) > 1:
        notes.append(
            "More than one currency is present ("
            + ", ".join(distinct)
            + "). Totals are not converted, so read each currency on its own."
        )
    return cleaned, notes


def mark_duplicates(frame: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Flag later copies of the same description, amount, and date.

    Identical narrations are held out of totals. Similar-but-not-identical
    rows are left in spending and surfaced by the anomaly review instead.
    """
    if frame.empty:
        return frame.copy(), 0

    working = frame.copy()
    working["_dup_amount"] = working["debit"].round(2).astype(str) + "|" + working["credit"].round(2).astype(str)
    working["_dup_desc"] = (
        working["description"].fillna("").str.lower().str.replace(r"\s+", " ", regex=True).str.strip()
    )
    working["_dup_day"] = pd.to_datetime(working["date"], errors="coerce").dt.strftime("%Y-%m-%d").fillna("")
    duplicate_count = 0
    seen: set[tuple] = set()
    flags = []
    for record in working.sort_values("row_order").to_dict(orient="records"):
        if not record["_dup_day"] or (record["debit"] == 0 and record["credit"] == 0):
            flags.append(False)
            continue
        key = (record["_dup_day"], record["_dup_amount"], record["_dup_desc"])
        if key in seen:
            flags.append(True)
            duplicate_count += 1
        else:
            seen.add(key)
            flags.append(False)

    # Re-align flags to the sorted order, then map back by id.
    ordered_ids = working.sort_values("row_order")["transaction_id"].tolist()
    flag_by_id = dict(zip(ordered_ids, flags))
    result = frame.copy()
    result["is_duplicate"] = result["transaction_id"].map(flag_by_id).fillna(False).astype(bool)
    duplicate_mask = result["is_duplicate"]
    result.loc[duplicate_mask, "counts_as_spend"] = False
    result.loc[duplicate_mask, "needs_review"] = True
    existing = result.loc[duplicate_mask, "review_reason"].fillna("")
    result.loc[duplicate_mask, "review_reason"] = existing.apply(
        lambda text: (text + " " if text else "")
        + "This matches an earlier transaction with the same date, amount, and description. It is left out of totals until you restore it."
    )
    return result, duplicate_count


def _empty_clean_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "transaction_id",
            "date",
            "description",
            "merchant",
            "debit",
            "credit",
            "currency",
            "currency_assumed",
            "account_label",
            "category",
            "subcategory",
            "confidence",
            "method",
            "transaction_type",
            "counts_as_spend",
            "needs_review",
            "review_reason",
            "flagged",
            "is_duplicate",
            "source_file",
            "row_order",
        ]
    )
