"""Read CSV, Excel, and PDF statements into a raw transaction table.

The parser does not categorize. It finds columns, and when it cannot, it
returns the original table so the user can map them.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field

import pandas as pd

from config.settings import HEADER_ALIASES, SKIP_HEADER_TOKENS
from models.schemas import ColumnMapping
from utils.helpers import public_error

NOT_IN_FILE = "— Not in file —"


@dataclass
class ParsedFile:
    filename: str
    status: str
    message: str
    frame: pd.DataFrame | None = None
    original: pd.DataFrame | None = None
    suggested_mapping: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def _normalize_header(value) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\n", " ").strip().lower()
    text = re.sub(r"[_\-./]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def _skip_header(header: str, field_name: str) -> bool:
    if field_name not in {"debit", "credit", "amount"}:
        return False
    return any(token in header for token in SKIP_HEADER_TOKENS)


def suggest_mapping(headers: list[str]) -> dict[str, str]:
    """Pick the best source column for each canonical field."""
    normalized = [_normalize_header(header) for header in headers]
    used: set[int] = set()
    mapping: dict[str, str] = {}

    def take(predicate) -> None:
        for field_name, aliases in HEADER_ALIASES.items():
            if field_name in mapping:
                continue
            for alias in aliases:
                for index, header in enumerate(normalized):
                    if index in used or not header or _skip_header(header, field_name):
                        continue
                    if predicate(header, alias):
                        mapping[field_name] = str(headers[index])
                        used.add(index)
                        break
                if field_name in mapping:
                    break

    take(lambda header, alias: header == alias)
    take(lambda header, alias: header.startswith(alias + " ") or header.endswith(" " + alias))
    return mapping


def mapping_is_confident(mapping: dict) -> bool:
    model = ColumnMapping(**{key: mapping.get(key) for key in ColumnMapping.model_fields})
    return model.is_sufficient()


def _score_headers(headers: list[str]) -> int:
    mapping = suggest_mapping(headers)
    score = 0
    if mapping.get("date"):
        score += 2
    if mapping.get("description"):
        score += 2
    if mapping.get("debit") or mapping.get("credit") or mapping.get("amount"):
        score += 2
    return score


def _find_header_line(lines: list[str]) -> int | None:
    best_index = None
    best_score = 0
    for index, line in enumerate(lines[:40]):
        if not line.strip():
            continue
        try:
            cells = next(csv.reader([line]))
        except csv.Error:
            continue
        score = _score_headers(cells)
        if score > best_score:
            best_score = score
            best_index = index
    if best_score >= 4:
        return best_index
    return None


def find_header_index(raw: pd.DataFrame) -> int | None:
    best_index = None
    best_score = 0
    limit = min(len(raw), 30)
    for index in range(limit):
        headers = ["" if pd.isna(value) else str(value) for value in raw.iloc[index].tolist()]
        score = _score_headers(headers)
        if score > best_score:
            best_score = score
            best_index = index
    if best_score >= 4:
        return best_index
    return None


def table_from_header_scan(raw: pd.DataFrame) -> tuple[pd.DataFrame | None, list[str]]:
    """Use the first row that looks like a transaction header."""
    warnings = []
    if raw is None or raw.empty:
        return None, ["The file did not contain a table."]
    header_index = find_header_index(raw)
    if header_index is None:
        # Fall back to the first row so the user can map columns manually.
        headers = [_fallback_header(index, value) for index, value in enumerate(raw.iloc[0].tolist())]
        body = raw.iloc[1:].copy()
        body.columns = _unique_headers(headers)
        body = _drop_empty(body)
        warnings.append("A transaction header was not detected automatically. Map the columns to continue.")
        return body, warnings

    headers = ["" if pd.isna(value) else str(value).strip() for value in raw.iloc[header_index].tolist()]
    body = raw.iloc[header_index + 1 :].copy()
    body.columns = _unique_headers(headers)
    if header_index > 0:
        warnings.append(f"Ignored {header_index} preamble row(s) above the transaction table.")
    empty_rows = int(body.isna().all(axis=1).sum()) if len(body) else 0
    body = _drop_empty(body)
    if empty_rows:
        warnings.append(f"Skipped {empty_rows} empty row(s).")
    return body.reset_index(drop=True), warnings


def standardize(table: pd.DataFrame, mapping: dict, filename: str) -> pd.DataFrame:
    """Project a mapped table into the raw columns the cleaner expects."""
    model = ColumnMapping(**{key: mapping.get(key) for key in ColumnMapping.model_fields})
    records = []
    for order, source in enumerate(table.to_dict(orient="records")):
        def cell(column: str | None):
            if not column or column not in source:
                return None
            value = source.get(column)
            if value is None or (isinstance(value, float) and pd.isna(value)):
                return None
            text = str(value).strip()
            return text if text else None

        records.append(
            {
                "date": cell(model.date),
                "description": cell(model.description),
                "debit": cell(model.debit),
                "credit": cell(model.credit),
                "amount": cell(model.amount),
                "drcr": cell(model.drcr),
                "currency": cell(model.currency),
                "account": cell(model.account),
                "source_file": filename,
                "row_order": order,
            }
        )
    return pd.DataFrame.from_records(records)


def parse_delimited(data: bytes, filename: str) -> ParsedFile:
    text, warning = _decode(data)
    if text is None:
        return ParsedFile(filename, "failed", warning or "The file encoding could not be read.")
    warnings = [warning] if warning else []
    lines = text.splitlines()
    header_at = _find_header_line(lines)
    if header_at is None:
        separator = _sniff_separator(text)
        try:
            raw = pd.read_csv(io.StringIO(text), sep=separator, header=None, dtype=str, engine="python")
        except Exception as exc:
            return ParsedFile(filename, "failed", "This CSV could not be read as a table. " + public_error(exc))
        return _from_raw_table(raw.replace({"": pd.NA}), filename, warnings)

    separator = _sniff_separator("\n".join(lines[header_at : header_at + 12]))
    body = "\n".join(lines[header_at:])
    try:
        table = pd.read_csv(io.StringIO(body), sep=separator, dtype=str, keep_default_na=False)
    except Exception as exc:
        return ParsedFile(filename, "failed", "The transaction table in this CSV could not be read. " + public_error(exc))
    table = table.replace({"": pd.NA})
    if header_at:
        warnings.append(f"Ignored {header_at} preamble row(s) above the transaction table.")
    mapping = suggest_mapping([str(column) for column in table.columns])
    if not mapping_is_confident(mapping):
        return ParsedFile(
            filename,
            "needs_mapping",
            "The columns in this file are ambiguous. Map date, description, and amount, then continue.",
            original=table,
            suggested_mapping=mapping,
            warnings=warnings,
        )
    return ParsedFile(
        filename,
        "parsed",
        f"Read {len(table)} row(s) from {filename}.",
        frame=standardize(table, mapping, filename),
        original=table,
        suggested_mapping=mapping,
        warnings=warnings,
    )


def parse_excel(data: bytes, filename: str) -> ParsedFile:
    engine = "xlrd" if filename.lower().endswith(".xls") and not filename.lower().endswith(".xlsx") else "openpyxl"
    try:
        workbook = pd.ExcelFile(io.BytesIO(data), engine=engine)
    except Exception as exc:  # pragma: no cover - engine errors vary by file
        hint = " If this is an old .xls file, try saving it as .xlsx or CSV." if engine == "xlrd" else ""
        return ParsedFile(filename, "failed", "This spreadsheet could not be opened." + hint + " " + public_error(exc))

    warnings = []
    best_frame = None
    best_score = -1
    used_sheets = []
    for sheet in workbook.sheet_names:
        raw = pd.read_excel(workbook, sheet_name=sheet, header=None, dtype=str)
        if raw.empty:
            continue
        header_index = find_header_index(raw)
        score = 0 if header_index is None else _score_headers(
            ["" if pd.isna(value) else str(value) for value in raw.iloc[header_index].tolist()]
        )
        row_bonus = min(len(raw), 20) / 100
        if score + row_bonus > best_score:
            best_score = score + row_bonus
            best_frame = raw
            used_sheets = [sheet]
    if best_frame is None:
        return ParsedFile(filename, "failed", "The workbook has no readable sheets.")
    if len(workbook.sheet_names) > 1:
        warnings.append(f"Used the sheet '{used_sheets[0]}', which looked most like a transaction list.")
    return _from_raw_table(best_frame, filename, warnings)


_DATE = r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}[/-][A-Za-z]{3}[/-]\d{2,4}"
_MONEY = r"\(?\d[\d,]*\.\d{2}\)?"
_LINE_TWO = re.compile(
    rf"^(?P<date>{_DATE})\s+(?P<desc>.+?)\s+(?P<debit>{_MONEY}|-)\s+(?P<credit>{_MONEY}|-)\s*$"
)
_LINE_ONE = re.compile(
    rf"^(?P<date>{_DATE})\s+(?P<desc>.+?)\s+(?P<amount>{_MONEY})(?:\s*(?P<dc>Dr|Cr))?\s*$",
    re.IGNORECASE,
)


def parse_pdf(data: bytes, filename: str) -> ParsedFile:
    try:
        import pdfplumber
    except ImportError:
        return ParsedFile(
            filename,
            "failed",
            "PDF support is not installed in this environment. Upload a CSV or Excel export instead.",
        )

    try:
        pages_text = []
        tables = []
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            page_count = len(pdf.pages)
            selected = pdf.pages[:40]
            for page in selected:
                tables.extend(page.extract_tables() or [])
                pages_text.append(page.extract_text() or "")
    except Exception as exc:
        return ParsedFile(filename, "failed", public_error(exc))

    warnings = []
    if page_count > 40:
        warnings.append(
            f"Only the first 40 of {page_count} pages were read. Split the PDF if later pages contain transactions you need."
        )

    table_attempt = None
    table_result = _pdf_tables_to_frame(tables, filename)
    if table_result is not None and len(table_result) >= 1:
        parsed = _from_raw_table(table_result, filename, warnings)
        if parsed.status == "parsed":
            parsed.message = f"Read a table from {filename}."
            return parsed
        table_attempt = parsed

    lines = _pdf_lines("\n".join(pages_text), filename)
    if lines is not None and len(lines) >= 3:
        warnings.append("Transactions were read from the statement text because a clean table was not found.")
        lines_file = ParsedFile(
            filename,
            "parsed",
            f"Read {len(lines)} transaction line(s) from {filename}.",
            frame=lines,
            warnings=warnings,
        )
        return lines_file

    text_length = sum(len(part.strip()) for part in pages_text)
    if table_attempt is not None and table_attempt.status == "needs_mapping":
        return table_attempt
    if text_length < 40 and not tables:
        return ParsedFile(
            filename,
            "failed",
            "This PDF has no selectable text. It may be a scan or a photo. Export a CSV or Excel transaction history from your bank instead.",
            warnings=warnings,
        )
    return ParsedFile(
        filename,
        "failed",
        "SpendWise could not find transaction rows in this PDF. Banks format statements very differently. Download the transaction history as CSV or Excel and upload that — it is more accurate than a visual statement.",
        warnings=warnings,
    )


def apply_user_mapping(original: pd.DataFrame, mapping: dict, filename: str) -> ParsedFile:
    model = ColumnMapping(**{key: value for key, value in mapping.items() if value and value != NOT_IN_FILE})
    if not model.is_sufficient():
        return ParsedFile(
            filename,
            "needs_mapping",
            "Choose a date column, a description column, and at least one amount column.",
            original=original,
            suggested_mapping=model.assigned(),
        )
    frame = standardize(original, model.assigned(), filename)
    return ParsedFile(
        filename,
        "parsed",
        f"Mapped columns for {filename}.",
        frame=frame,
        original=original,
        suggested_mapping=model.assigned(),
    )


def _from_raw_table(raw: pd.DataFrame, filename: str, warnings: list[str]) -> ParsedFile:
    table, table_warnings = table_from_header_scan(raw)
    warnings = [*warnings, *table_warnings]
    if table is None or table.empty:
        return ParsedFile(filename, "failed", "No transaction rows were found after the header.", warnings=warnings)
    mapping = suggest_mapping(list(table.columns))
    if not mapping_is_confident(mapping):
        return ParsedFile(
            filename,
            "needs_mapping",
            "The columns in this file are ambiguous. Map date, description, and amount, then continue.",
            original=table,
            suggested_mapping=mapping,
            warnings=warnings,
        )
    frame = standardize(table, mapping, filename)
    return ParsedFile(
        filename,
        "parsed",
        f"Read {len(frame)} row(s) from {filename}.",
        frame=frame,
        original=table,
        suggested_mapping=mapping,
        warnings=warnings,
    )


def _pdf_tables_to_frame(tables: list, filename: str) -> pd.DataFrame | None:
    frames = []
    for table in tables:
        if not table or len(table) < 2:
            continue
        raw = pd.DataFrame(table)
        if find_header_index(raw) is None:
            continue
        frames.append(raw)
    if not frames:
        return None
    if len(frames) == 1:
        return frames[0]
    # Keep the largest table. Stacking unlike tables produces false rows.
    frames.sort(key=len, reverse=True)
    return frames[0]


def _pdf_lines(text: str, filename: str) -> pd.DataFrame | None:
    rows = []
    for line in text.splitlines():
        cleaned = re.sub(r"\s+", " ", line).strip()
        if len(cleaned) < 8:
            continue
        two = _LINE_TWO.match(cleaned)
        if two:
            debit = None if two.group("debit") == "-" else two.group("debit")
            credit = None if two.group("credit") == "-" else two.group("credit")
            rows.append((two.group("date"), two.group("desc").strip(), debit, credit, None, None))
            continue
        one = _LINE_ONE.match(cleaned)
        if one:
            marker = (one.group("dc") or "").lower()
            amount = one.group("amount")
            debit = amount if marker == "dr" else None
            credit = amount if marker == "cr" else None
            plain = amount if marker not in {"dr", "cr"} else None
            rows.append((one.group("date"), one.group("desc").strip(), debit, credit, plain, marker or None))
    if len(rows) < 3:
        return None
    return pd.DataFrame(
        [
            {
                "date": item[0],
                "description": item[1],
                "debit": item[2],
                "credit": item[3],
                "amount": item[4],
                "drcr": item[5],
                "currency": None,
                "account": None,
                "source_file": filename,
                "row_order": index,
            }
            for index, item in enumerate(rows)
        ]
    )


def _decode(data: bytes) -> tuple[str | None, str | None]:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(encoding), None
        except UnicodeDecodeError:
            continue
    return None, "The file encoding could not be read. Save the CSV as UTF-8 and try again."


def _sniff_separator(text: str) -> str:
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        return dialect.delimiter
    except csv.Error:
        return ","


def _fallback_header(index: int, value) -> str:
    text = "" if value is None or (isinstance(value, float) and pd.isna(value)) else str(value).strip()
    return text or f"Column {index + 1}"


def _unique_headers(headers: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    unique = []
    for header in headers:
        name = header or "Column"
        count = seen.get(name, 0)
        seen[name] = count + 1
        unique.append(name if count == 0 else f"{name} {count + 1}")
    return unique


def _drop_empty(frame: pd.DataFrame) -> pd.DataFrame:
    def _blank(value) -> bool:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return True
        return str(value).strip() == "" or str(value).strip().lower() == "nan"

    mask = frame.apply(lambda row: all(_blank(value) for value in row), axis=1)
    return frame.loc[~mask].copy()
