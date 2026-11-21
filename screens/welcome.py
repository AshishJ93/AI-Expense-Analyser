"""The public tour. Open the app is a separate step."""

from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

SITE = Path(__file__).resolve().parents[1] / "site" / "index.html"


def render_welcome() -> None:
    st.markdown(
        """
        <style>
          .stApp:has(#sw-site) [data-testid="stHeader"],
          .stApp:has(#sw-site) [data-testid="stToolbar"],
          .stApp:has(#sw-site) [data-testid="stDecoration"],
          .stApp:has(#sw-site) [data-testid="stSidebar"],
          .stApp:has(#sw-site) footer { display: none !important; }
          .stApp:has(#sw-site) .block-container { max-width: none !important; padding: 0 !important; }
          .stApp:has(#sw-site) [data-testid="stMain"] { overflow: hidden !important; }
          .stApp:has(#sw-site) iframe {
            position: fixed !important;
            inset: 0 !important;
            width: 100vw !important;
            height: 100vh !important;
            border: 0 !important;
            z-index: 1000;
            background: #f4efe6;
          }
        </style>
        <div id="sw-site"></div>
        """,
        unsafe_allow_html=True,
    )
    st.html(
        "<script>window.addEventListener('message',function(e){if(e.data==='sw-enter'){window.location.href='?enter=1';}});</script>",
        unsafe_allow_javascript=True,
    )
    components.html(SITE.read_text(encoding="utf-8"), height=900, scrolling=True)
