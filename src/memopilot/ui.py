from __future__ import annotations

import streamlit as st

from memopilot.config import load_settings
from memopilot.store import load_history
from memopilot.ui_generate import generate_tab
from memopilot.ui_history import history_tab


def main() -> None:
    st.set_page_config(page_title="MemoPilot", page_icon="MP", layout="wide")
    settings = load_settings()

    st.markdown(
        """
        <style>
        .stApp > header {
            height: 0rem;
        }
        .stApp {
            padding-top: 0.5rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("MemoPilot")
    st.caption("基于纯文本历史纪要样例的全上下文会议纪要生成工具")

    with st.sidebar:
        st.subheader("配置")
        st.write(f"模型：`{settings.model}`")
        st.write(f"历史库：`{settings.history_file}`")
        st.write(f"输出目录：`{settings.output_dir}`")
        st.write("API：已配置" if settings.api_key else "API：未配置")

    history = load_history(settings.history_file)
    tab_history, tab_generate = st.tabs(["历史纪要库", "生成纪要"])

    with tab_history:
        history_tab(settings.history_file, history)

    with tab_generate:
        generate_tab(settings, history)
