"""Currency, date, and percent formatting."""

from __future__ import annotations

import math
from datetime import date, datetime

import pandas as pd


def format_inr(value: float | int | None, decimals: int = 0, with_symbol: bool = True) -> str:
    """Format a number with Indian digit grouping."""
    if value is None or (isinstance(value, float) and (math.isnan(value) or math.isinf(value))):
        return "—"
    sign = "-" if float(value) < 0 else ""
    formatted = f"{abs(float(value)):.{decimals}f}"
    whole, frac = formatted.split(".") if "." in formatted else (formatted, "")
    if len(whole) <= 3:
        grouped = whole
    else:
        head, tail = whole[:-3], whole[-3:]
        parts: list[str] = []
        while len(head) > 2:
            parts.append(head[-2:])
            head = head[:-2]
        if head:
            parts.append(head)
        grouped = ",".join(reversed(parts)) + "," + tail
    number = grouped if decimals == 0 else f"{grouped}.{frac}"
    prefix = "₹" if with_symbol else ""
    return f"{sign}{prefix}{number}"


def format_percent(value: float | None, signed: bool = True) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "—"
    percent = value * 100
    if signed:
        sign = "+" if percent > 0 else ""
        return f"{sign}{percent:.1f}%"
    return f"{percent:.1f}%"


def format_date(value) -> str:
    if value is None or pd.isna(value):
        return "—"
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value.strftime("%d %b %Y")
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return "—"
    return parsed.strftime("%d %b %Y")


def format_month(value) -> str:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return "—"
    return parsed.strftime("%b %Y")


def confidence_label(score: float | None) -> str:
    if score is None or (isinstance(score, float) and math.isnan(score)):
        return "Low"
    if score >= 0.85:
        return "High"
    if score >= 0.6:
        return "Medium"
    return "Low"


def confidence_display(score: float | None) -> str:
    if score is None or (isinstance(score, float) and math.isnan(score)):
        return "Low"
    return f"{confidence_label(score)} · {round(float(score) * 100)}%"


def compact_change(value: float | None) -> str:
    if value is None:
        return "No prior month"
    return format_percent(value)
