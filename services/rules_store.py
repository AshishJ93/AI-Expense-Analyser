"""Persist merchant corrections only. Transaction rows are never written here."""

from __future__ import annotations

import json
from pathlib import Path

RULES_PATH = Path(".hisaabpehle") / "merchant_rules.json"
LEGACY_RULES_PATH = Path(".spendwise") / "merchant_rules.json"


def _rules_file() -> Path:
    if RULES_PATH.exists() or not LEGACY_RULES_PATH.exists():
        return RULES_PATH
    return LEGACY_RULES_PATH


def load_rules() -> dict:
    path = _rules_file()
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def save_rules(rules: dict) -> None:
    RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
    RULES_PATH.write_text(json.dumps(rules, indent=2), encoding="utf-8")


def delete_rules() -> None:
    for path in (RULES_PATH, LEGACY_RULES_PATH):
        if path.exists():
            path.unlink()
