"""Session state and the shared analysis used by every screen."""

from __future__ import annotations

from datetime import date

import pandas as pd

from services.analytics import (
    behavior,
    category_breakdown,
    category_by_month,
    compute_kpis,
    consistency,
    daily_totals,
    filter_by_period,
    largest_transactions,
    merchant_frequency,
    merchant_totals,
    month_totals,
    reconciliation,
    spending_view,
)
from services.ai_insights import build_insights
from services.anomaly_detector import detect_anomalies
from services.llm_client import config_from_environment
from services.recommendations import build_recommendations
from services.rules_store import load_rules
from services.subscription_detector import detect_recurring


def init_state() -> None:
    defaults = {
        "stage": "onboard",
        "entered": False,
        "page": "Overview",
        "transactions": None,
        "notes": [],
        "demo": False,
        "replacing": False,
        "parsed_files": [],
        "convention": "auto",
        "currency": "INR",
        "user_rules": load_rules(),
        "small_purchase": 500.0,
        "large_transaction": 10000.0,
        "llm_consent": True,
        "llm_api_key": "",
        "llm_provider": "",
        "llm_model": "",
        "llm_base_url": "",
        "data_version": 0,
        "briefing": None,
        "briefing_error": None,
        "briefing_signature": None,
    }
    for key, value in defaults.items():
        if key not in st_session():
            st_session()[key] = value
    if "period" not in st_session():
        st_session()["period"] = "All months"
    env_config = config_from_environment()
    session = st_session()
    if not session.get("llm_provider"):
        session["llm_provider"] = env_config.provider
    if not session.get("llm_model"):
        session["llm_model"] = env_config.model
    if not session.get("llm_base_url"):
        session["llm_base_url"] = env_config.base_url


def st_session():
    import streamlit as st

    return st.session_state


def active_frame():
    frame = st_session().transactions
    if frame is None:
        return pd.DataFrame()
    return frame


def build_view(today: date | None = None) -> dict:
    """Figures for the selected period, with history used when a comparison needs it."""
    today = today or date.today()
    state = st_session()
    full = active_frame()
    period_name = state.period
    period_df = filter_by_period(full, period_name, today)
    kpis = compute_kpis(period_df, full, period_name, today)
    spend = spending_view(period_df)
    months = pd.to_datetime(period_df["date"], errors="coerce").dt.to_period("M").nunique() if not period_df.empty else 0
    history = full if period_name != "All months" and months < 2 else period_df
    small = float(state.small_purchase)
    return {
        "full": full,
        "period_df": period_df,
        "history": history,
        "history_expanded": history is full and period_df is not full,
        "kpis": kpis,
        "spend": spend,
        "monthly": month_totals(spend),
        "daily": daily_totals(spend),
        "categories": category_breakdown(spend),
        "monthly_category": category_by_month(spend),
        "merchants": merchant_totals(spend),
        "frequency": merchant_frequency(spend),
        "largest": largest_transactions(period_df),
        "behavior": behavior(spend),
        "consistency": consistency(month_totals(spending_view(full))),
        "reconciliation": reconciliation(period_df, kpis.currency),
        "insights": build_insights(period_df, kpis, today, small),
        "recommendations": build_recommendations(history, today, small),
        "anomalies": detect_anomalies(period_df),
        "recurring": detect_recurring(full),
        "today": today,
    }


def llm_settings():
    """The model key comes from the server environment or Streamlit secrets, never from the user."""
    config = config_from_environment()
    config.consent = bool(st_session().llm_consent)
    return config


def ensure_briefing(view: dict) -> None:
    """Ask xAI once per dataset. The cards stay available if the call fails."""
    import streamlit as st

    from services.llm_client import write_briefing

    config = llm_settings()
    signature = (st.session_state.data_version, config.enabled, config.provider, config.model)
    if st.session_state.get("briefing_signature") == signature:
        return
    if not config.enabled:
        st.session_state.briefing = None
        st.session_state.briefing_error = None
        st.session_state.briefing_signature = signature
        return
    with st.spinner("Grok is writing a briefing from the figures already calculated…"):
        text, error = write_briefing(view["insights"], view["recommendations"], config)
    st.session_state.briefing = text
    st.session_state.briefing_error = error
    st.session_state.briefing_signature = signature
