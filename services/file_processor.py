"""Route an uploaded file to the right reader."""

from __future__ import annotations

from services.statement_parser import ParsedFile, parse_delimited, parse_excel, parse_pdf


def process_bytes(filename: str, data: bytes) -> ParsedFile:
    """Parse one upload. Failures return a reason and a recovery hint."""
    name = filename or "statement"
    lower = name.lower()
    if not data:
        return ParsedFile(name, "failed", "The file is empty.")
    try:
        if lower.endswith(".csv") or lower.endswith(".txt"):
            return parse_delimited(data, name)
        if lower.endswith(".xlsx") or lower.endswith(".xls"):
            return parse_excel(data, name)
        if lower.endswith(".pdf"):
            return parse_pdf(data, name)
    except Exception as exc:  # last-resort guard so one file cannot crash the batch
        from utils.helpers import public_error

        return ParsedFile(
            name,
            "failed",
            "This file could not be processed. Export it again as CSV if the problem continues. "
            + public_error(exc),
        )
    return ParsedFile(
        name,
        "failed",
        "This file type is not supported. Upload a CSV, XLSX, XLS, or PDF statement.",
    )
