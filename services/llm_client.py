"""Optional LLM call. The app never requires this module to succeed.

Only aggregated insight text is sent, and only after explicit consent.
API keys are read from the environment or Streamlit secrets.
They are not entered by the person using the app.
"""

from __future__ import annotations

import os

from models.schemas import LLMConfig
from services.ai_insights import Insight, insight_payload, narrative_is_grounded
from services.recommendations import Recommendation
from utils.validators import llm_config_from_env

SYSTEM_PROMPT = (
    "You write a short personal finance briefing for one person. "
    "Use only numbers, merchants, and dates copied from the JSON. "
    "Do not round, invent, or introduce any figure that is not already in the JSON. "
    "Do not shame the reader or say they cannot afford something. "
    "Write 90 to 130 words in plain sentences. No bullet points, no title, no preamble."
)


def config_from_environment() -> LLMConfig:
    try:
        import streamlit as st

        secrets = {key: st.secrets[key] for key in st.secrets}
    except Exception:
        secrets = {}
    env = {**os.environ, **{key: str(value) for key, value in secrets.items()}}
    return llm_config_from_env(env)


def write_briefing(
    insights: list[Insight],
    recommendations: list[Recommendation],
    config: LLMConfig,
) -> tuple[str | None, str | None]:
    """Return (briefing, error). A grounding failure discards the briefing."""
    if not config.enabled:
        return None, None
    source = insight_payload(insights, recommendations)
    user = "Write the briefing from this JSON only:\n" + source
    try:
        text = _complete(config, SYSTEM_PROMPT, user)
    except Exception as exc:
        return None, _safe_provider_error(exc)
    if not narrative_is_grounded(text, source):
        return None, "The model briefing was discarded because it introduced a number that is not in your results."
    return text.strip(), None


def _complete(config: LLMConfig, system: str, user: str) -> str:
    import httpx

    if config.provider == "xai":
        config.base_url = (config.base_url or "https://api.x.ai/v1").strip()
        config.model = (config.model or "grok-4-1-fast-non-reasoning").strip()

    if config.provider == "gemini":
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{config.model}:generateContent?key={config.api_key.strip()}"
        )
        payload = {"contents": [{"role": "user", "parts": [{"text": system + "\n\n" + user}]}]}
        response = httpx.post(url, json=payload, timeout=75)
        response.raise_for_status()
        data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]

    url = config.base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": config.model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    response = httpx.post(
        url,
        json=payload,
        headers={"Authorization": f"Bearer {config.api_key.strip()}"},
        timeout=75,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def _safe_provider_error(exc: Exception) -> str:
    text = str(exc)
    if "401" in text or "403" in text or "api key" in text.lower():
        return "The written briefing could not be completed. Your calculated insights are unchanged."
    return "The AI provider did not respond. Your calculated insights are still shown below."
