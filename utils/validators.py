"""Lightweight checks used by the parser and the settings screen."""

from __future__ import annotations

from models.schemas import ColumnMapping, LLMConfig


def mapping_from_dict(payload: dict | None) -> ColumnMapping:
    if not payload:
        return ColumnMapping()
    allowed = set(ColumnMapping.model_fields)
    return ColumnMapping(**{key: value or None for key, value in payload.items() if key in allowed})


def _setting(env: dict[str, str], name: str) -> str:
    """Prefer the HisaabPehle name. The older SpendWise name still works."""
    return (env.get(f"HISAABPEHLE_{name}") or env.get(f"SPENDWISE_{name}") or "").strip()


def llm_config_from_env(env: dict[str, str]) -> LLMConfig:
    xai_key = (env.get("XAI_API_KEY") or "").strip()
    explicit_key = _setting(env, "LLM_API_KEY")
    provider = _setting(env, "LLM_PROVIDER").lower()
    if provider not in {"xai", "openai", "gemini", "openai_compatible"}:
        provider = "xai" if (xai_key or explicit_key) else "openai"
    if provider == "xai":
        return LLMConfig(
            provider="xai",
            api_key=explicit_key or xai_key,
            base_url=(_setting(env, "LLM_BASE_URL") or "https://api.x.ai/v1"),
            model=(_setting(env, "LLM_MODEL") or "grok-4-1-fast-non-reasoning"),
        )
    if provider == "gemini":
        return LLMConfig(
            provider="gemini",
            api_key=explicit_key,
            base_url="",
            model=(_setting(env, "LLM_MODEL") or "gemini-2.0-flash"),
        )
    return LLMConfig(
        provider=provider,  # type: ignore[arg-type]
        api_key=explicit_key,
        base_url=(_setting(env, "LLM_BASE_URL") or "https://api.openai.com/v1"),
        model=(_setting(env, "LLM_MODEL") or "gpt-4o-mini"),
    )
