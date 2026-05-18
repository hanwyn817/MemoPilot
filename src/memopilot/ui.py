from __future__ import annotations

import json

import streamlit as st
from pydantic import ValidationError

from memopilot.config import load_settings
from memopilot.generator import generate_minutes
from memopilot.models import HistoricalMinute
from memopilot.prompt import estimate_generation_input_tokens
from memopilot.store import add_history, delete_history, load_history, save_history, update_history
from memopilot.token_estimate import estimate_tokens


def main() -> None:
    st.set_page_config(page_title="MemoPilot", page_icon="MP", layout="wide")
    settings = load_settings()

    st.title("MemoPilot")
    st.caption("基于纯文本历史纪要样例的全上下文会议纪要生成工具")

    with st.sidebar:
        st.subheader("配置")
        st.write(f"模型：`{settings.model}`")
        st.write(f"历史库：`{settings.history_file}`")
        st.write("API：已配置" if settings.api_key else "API：未配置")

    history = load_history(settings.history_file)
    tab_history, tab_generate = st.tabs(["历史纪要库", "生成纪要"])

    with tab_history:
        _history_tab(settings.history_file, history)

    with tab_generate:
        _generate_tab(settings, history)


def _history_tab(history_file, history: list[HistoricalMinute]) -> None:
    left, right = st.columns([0.42, 0.58], gap="large")

    with left:
        st.subheader("录入历史纪要")
        with st.form("add_history"):
            topic = st.text_input("会议主题")
            body = st.text_area("会议正文", height=360)
            submitted = st.form_submit_button("保存到历史库", type="primary", use_container_width=True)
        if submitted:
            if not topic.strip() or not body.strip():
                st.warning("会议主题和会议正文都不能为空。")
            else:
                add_history(history_file, topic, body)
                st.success("已保存。")
                st.rerun()

        st.divider()
        st.subheader("导入/导出")
        exported = json.dumps([item.model_dump() for item in history], ensure_ascii=False, indent=2)
        st.download_button(
            "导出历史库 JSON",
            data=exported,
            file_name="history_minutes.json",
            mime="application/json",
            use_container_width=True,
        )
        uploaded = st.file_uploader("导入历史库 JSON", type=["json"])
        replace = st.checkbox("导入时替换现有历史库", value=False)
        if uploaded is not None and st.button("执行导入", use_container_width=True):
            try:
                raw = json.loads(uploaded.read().decode("utf-8"))
                imported = [HistoricalMinute.model_validate(item) for item in raw]
            except (json.JSONDecodeError, UnicodeDecodeError, ValidationError, TypeError) as exc:
                st.error(f"导入失败：{exc}")
            else:
                items = imported if replace else history + imported
                save_history(history_file, items)
                st.success(f"已导入 {len(imported)} 条。")
                st.rerun()

    with right:
        st.subheader("已录入历史纪要")
        total_chars = sum(len(item.topic) + len(item.body) for item in history)
        st.write(f"共 {len(history)} 条，约 {estimate_tokens(''.join(item.body for item in history)):,} tokens。")
        if not history:
            st.info("尚未录入历史纪要。")
            return

        query = st.text_input("搜索主题或正文")
        visible = [
            item
            for item in history
            if not query.strip() or query.strip() in item.topic or query.strip() in item.body
        ]
        st.caption(f"当前显示 {len(visible)} 条；总字符数 {total_chars:,}。")

        for item in visible:
            with st.expander(item.topic, expanded=False):
                with st.form(f"edit_{item.id}"):
                    edited_topic = st.text_input("会议主题", value=item.topic, key=f"topic_{item.id}")
                    edited_body = st.text_area("会议正文", value=item.body, height=260, key=f"body_{item.id}")
                    col_save, col_delete = st.columns(2)
                    save_clicked = col_save.form_submit_button("保存修改", use_container_width=True)
                    delete_clicked = col_delete.form_submit_button("删除", use_container_width=True)
                if save_clicked:
                    update_history(history_file, item.id, edited_topic, edited_body)
                    st.success("已更新。")
                    st.rerun()
                if delete_clicked:
                    delete_history(history_file, item.id)
                    st.success("已删除。")
                    st.rerun()


def _generate_tab(settings, history: list[HistoricalMinute]) -> None:
    left, right = st.columns([0.46, 0.54], gap="large")
    with left:
        st.subheader("本次会议")
        current_topic = st.text_input("本次会议主题")
        transcript = st.text_area("本次会议原始记录", height=460)

        estimated = 0
        if current_topic.strip() and transcript.strip() and history:
            estimated = estimate_generation_input_tokens(
                history,
                current_topic=current_topic,
                transcript=transcript,
            )
        st.caption(f"预计输入：{estimated:,} tokens；历史样例：{len(history)} 条。")
        if estimated > 900_000:
            st.warning("预计输入接近 1M 上下文上限，建议减少历史样例或压缩正文。")

        generate = st.button("生成会议纪要", type="primary", use_container_width=True)

    with right:
        st.subheader("生成结果")
        if not generate:
            st.info("录入历史纪要后，输入本次会议主题和原始记录即可生成。")
            return
        if not settings.api_key:
            st.error("请先在 .env 中配置 OPENAI_API_KEY。")
            return
        try:
            with st.spinner("正在通过全上下文请求生成纪要..."):
                result = generate_minutes(
                    settings,
                    current_topic=current_topic,
                    transcript=transcript,
                )
        except Exception as exc:
            st.error(f"生成失败：{exc}")
            return

        st.text_area("会议纪要正文", value=result.minutes, height=520)
        st.caption(
            f"模型：{result.model}；历史样例：{result.history_count} 条；"
            f"预计输入：{result.estimated_input_tokens:,} tokens。"
        )
        st.download_button(
            "下载 TXT",
            data=result.minutes,
            file_name="meeting_minutes.txt",
            mime="text/plain",
            use_container_width=True,
        )

