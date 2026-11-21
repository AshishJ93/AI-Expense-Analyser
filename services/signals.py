"""Shared description signals used by cleaning and categorization."""

from __future__ import annotations

import re

from config.settings import (
    CHANNEL_TRANSFER,
    COMPILED_CASH,
    COMPILED_FEE,
    COMPILED_GENERIC_RULES,
    COMPILED_INCOME,
    COMPILED_MERCHANT_RULES,
    COMPILED_REFUND,
    COMPILED_TRANSFER,
    UPI_PATTERN,
)


def _any(patterns, text: str) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def merchant_hit(text: str):
    """Return (category, subcategory, canonical_name) or None."""
    if not text:
        return None
    for pattern, category, subcategory, canonical in COMPILED_MERCHANT_RULES:
        match = pattern.search(text)
        if not match:
            continue
        name = canonical
        if name is None:
            name = _title_match(match.group(0))
        return category, subcategory, name
    return None


def generic_hit(text: str):
    if not text:
        return None
    for pattern, category, subcategory in COMPILED_GENERIC_RULES:
        if pattern.search(text):
            return category, subcategory
    return None


def is_income(text: str) -> bool:
    return _any(COMPILED_INCOME, text or "")


def is_refund(text: str) -> bool:
    return _any(COMPILED_REFUND, text or "")


def is_fee(text: str) -> bool:
    return _any(COMPILED_FEE, text or "")


def is_cash(text: str) -> bool:
    return _any(COMPILED_CASH, text or "")


def is_explicit_transfer(text: str) -> bool:
    return _any(COMPILED_TRANSFER, text or "")


def is_channel_transfer(text: str) -> bool:
    return bool(text and CHANNEL_TRANSFER.search(text))


def is_upi(text: str) -> bool:
    return bool(text and UPI_PATTERN.search(text))


_ACRONYMS = {"ATM", "BMRCL", "CCD", "GST", "HDFC", "ICICI", "IMPS", "IRCTC", "JIO", "NEFT", "OLA", "PVR", "RTGS", "SIP", "UPI"}


def _title_match(fragment: str) -> str:
    cleaned = re.sub(r"\s+", " ", fragment).strip(" -/")
    if cleaned.upper() in _ACRONYMS:
        return cleaned.upper()
    return cleaned.title()
