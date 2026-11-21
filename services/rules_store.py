"""Persist merchant corrections only. Transaction rows are never written here."""

from __future__ import annotations

import json
from pathlib import Path

RULES_PATH = Path(".spendwise") / "merchant_rules.json"


def load_rules() -> dict:
    if not RULES_PATH.exists():
        return {}
    try:
        payload = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def save_rules(rules: dict) -> None:
    RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
    RULES_PATH.write_text(json.dumps(rules, indent=2), encoding="utf-8")


def delete_rules() -> None:
    if RULES_PATH.exists():
        RULES_PATH.unlink()
