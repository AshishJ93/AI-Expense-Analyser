"""Pydantic models for configuration, mappings, and user corrections."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ColumnMapping(BaseModel):
    """Maps source columns onto the canonical transaction fields."""

    date: str | None = None
    description: str | None = None
    debit: str | None = None
    credit: str | None = None
    amount: str | None = None
    drcr: str | None = None
    currency: str | None = None
    account: str | None = None

    def is_sufficient(self) -> bool:
        has_money = any([self.amount, self.debit, self.credit])
        return bool(self.date and self.description and has_money)

    def assigned(self) -> dict[str, str]:
        return {key: value for key, value in self.model_dump().items() if value}


class UserRule(BaseModel):
    merchant_key: str
    category: str
    subcategory: str = "General"

    @field_validator("merchant_key")
    @classmethod
    def normalize_key(cls, value: str) -> str:
        cleaned = " ".join(value.lower().split())
        if not cleaned or cleaned == "unknown merchant":
            raise ValueError("A merchant name is required before a rule can be saved.")
        return cleaned


class LLMConfig(BaseModel):
    """Optional model provider. Empty key means the written briefing stays off."""

    provider: Literal["xai", "openai", "gemini", "openai_compatible"] = "xai"
    api_key: str = ""
    base_url: str = "https://api.x.ai/v1"
    model: str = "grok-4-1-fast-non-reasoning"
    consent: bool = False

    @property
    def enabled(self) -> bool:
        return bool(self.consent and self.api_key.strip())


class AppPreferences(BaseModel):
    currency: str = "INR"
    small_purchase: float = Field(default=500, gt=0)
    large_transaction: float = Field(default=10000, gt=0)
    include_investments_in_spending: bool = False


TRANSACTION_COLUMNS = [
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
