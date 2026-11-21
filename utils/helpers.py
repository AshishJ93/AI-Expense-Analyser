"""Small shared helpers."""

from __future__ import annotations

import re
import uuid
from datetime import date

import pandas as pd


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def mask_sensitive(text: str) -> str:
    """Hide long account and card numbers. Keep the last four digits."""
    if not text:
        return ""

    def _mask(match: re.Match) -> str:
        digits = re.sub(r"\D", "", match.group(0))
        if len(digits) < 12:
            return match.group(0)
        return "••••" + digits[-4:]

    masked = re.sub(r"\b(?:\d[ -]?){12,18}\d\b", _mask, str(text))
    masked = re.sub(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        "••••@••••",
        masked,
    )
    masked = re.sub(r"\b[6-9]\d{9}\b", lambda match: "••••" + match.group(0)[-4:], masked)
    return masked


def mask_account_label(value: str | None) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = mask_sensitive(str(value).strip())
    digits = re.sub(r"\D", "", text)
    if len(digits) >= 8 and "•" not in text:
        return "Account ••" + digits[-4:]
    return text


def month_key(value) -> str | None:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.strftime("%Y-%m")


def is_partial_month(last_date: date, today: date) -> bool:
    """A month still in progress is partial. A historical extract is not."""
    return (
        last_date.year == today.year
        and last_date.month == today.month
        and last_date.day < 28
    )


def safe_divide(numerator: float, denominator: float) -> float | None:
    if denominator is None or abs(denominator) < 1e-9:
        return None
    return numerator / denominator


def public_error(exc: Exception) -> str:
    """Short error text that does not echo statement rows."""
    message = str(exc)
    if "password" in message.lower() or "encrypted" in message.lower():
        return "This file looks password protected. Export an unlocked CSV from your bank and upload that."
    cleaned = re.sub(r"\d", "#", message)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return exc.__class__.__name__
    return f"{exc.__class__.__name__}: {cleaned[:160]}"
