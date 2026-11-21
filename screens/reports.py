"""Download the same analysis as Excel or PDF."""

import streamlit as st

from components.header import render_header
from screens.state import build_view
from services.report_generator import build_excel, build_pdf


def render_reports() -> None:
    view = build_view()
    render_header(
        "Reports",
        "A review document. The PDF is the narrative. The workbook has every row.",
        "Built from the period selected above.",
    )
    kpis = view["kpis"]
    st.markdown(
        f'<div class="sw-note"><p>This export uses the period in the header ({kpis.period_label}). Recurring payments are detected from all loaded months. Demo data stays labeled as fictional.</p></div>',
        unsafe_allow_html=True,
    )
    demo = bool(st.session_state.demo)
    excel = build_excel(
        view["period_df"],
        kpis,
        view["categories"],
        view["monthly"],
        view["merchants"],
        view["recurring"],
        view["anomalies"],
        view["recommendations"],
        view["insights"],
        demo=demo,
    )
    pdf = build_pdf(
        view["period_df"],
        kpis,
        view["categories"],
        view["monthly"],
        view["merchants"],
        view["recurring"],
        view["anomalies"],
        view["recommendations"],
        view["insights"],
        demo=demo,
    )
    left, right = st.columns(2)
    with left:
        st.download_button(
            "Download Excel workbook",
            excel,
            file_name="spendwise-report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            width="stretch",
        )
    with right:
        st.download_button(
            "Download PDF report",
            pdf,
            file_name="spendwise-report.pdf",
            mime="application/pdf",
            width="stretch",
        )
    st.markdown(
        '<p class="sw-privacy">The report is generated in this session from the transactions already loaded. It is a personal review aid, not tax, credit, or investment advice.</p>',
        unsafe_allow_html=True,
    )
