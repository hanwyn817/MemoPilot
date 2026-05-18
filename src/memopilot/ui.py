from __future__ import annotations

import json
from pathlib import Path

import streamlit as st
from pydantic import ValidationError

from memopilot.config import load_settings
from memopilot.generator import generate_minutes
from memopilot.models import HistoricalMinute
from memopilot.output import save_generated_minutes
from memopilot.prompt import estimate_generation_input_tokens
from memopilot.store import (
    add_history,
    add_many_history,
    delete_history,
    load_history,
    save_history,
    update_history,
)
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
        st.write(f"输出目录：`{settings.output_dir}`")
        st.write("API：已配置" if settings.api_key else "API：未配置")

    history = load_history(settings.history_file)
    tab_history, tab_generate = st.tabs(["历史纪要库", "生成纪要"])

    with tab_history:
        _history_tab(settings.history_file, history)

    with tab_generate:
        _generate_tab(settings, history)


def _history_tab(history_file, history: list[HistoricalMinute]) -> None:
    history_tokens = estimate_tokens("".join(item.body for item in history))
    history_chars = sum(len(item.topic) + len(item.body) for item in history)

    metric_count, metric_tokens, metric_chars = st.columns(3)
    metric_count.metric("历史样例", f"{len(history)} 条")
    metric_tokens.metric("估算 tokens", f"{history_tokens:,}")
    metric_chars.metric("总字符数", f"{history_chars:,}")

    st.divider()
    left, right = st.columns([0.4, 0.6], gap="large")

    with left:
        st.subheader("添加样例")
        add_tab, import_tab = st.tabs(["手动录入", "批量导入"])

        with add_tab:
            with st.form("add_history"):
                topic = st.text_input("会议主题")
                body = st.text_area("会议正文", height=340)
                submitted = st.form_submit_button(
                    "保存到历史库",
                    type="primary",
                    use_container_width=True,
                )
            if submitted:
                if not topic.strip() or not body.strip():
                    st.warning("会议主题和会议正文都不能为空。")
                else:
                    add_history(history_file, topic, body)
                    st.success("已保存。")
                    st.rerun()

        with import_tab:
            text_files = st.file_uploader(
                "上传 TXT/MD 文件",
                type=["txt", "md"],
                accept_multiple_files=True,
            )
            st.caption("文件名会作为会议主题，文件内容会作为会议正文。")
            if text_files and st.button("导入 TXT/MD", use_container_width=True):
                entries: list[tuple[str, str]] = []
                failed: list[str] = []
                for file in text_files:
                    try:
                        body = file.read().decode("utf-8").strip()
                    except UnicodeDecodeError:
                        failed.append(file.name)
                        continue
                    topic = Path(file.name).stem
                    if body:
                        entries.append((topic, body))
                imported = add_many_history(history_file, entries)
                if failed:
                    st.warning(f"以下文件不是 UTF-8 文本，已跳过：{', '.join(failed)}")
                st.success(f"已导入 {len(imported)} 条 TXT/MD 历史纪要。")
                st.rerun()

            with st.expander("JSON 备份与恢复"):
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
                if uploaded is not None and st.button("执行 JSON 导入", use_container_width=True):
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
        st.subheader("管理历史库")
        if not history:
            st.info("尚未录入历史纪要。")
            return

        query = st.text_input("搜索主题或正文", placeholder="输入关键词筛选历史样例")
        visible = [
            item
            for item in history
            if not query.strip() or query.strip() in item.topic or query.strip() in item.body
        ]
        st.caption(f"当前显示 {len(visible)} / {len(history)} 条。")

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
    left, right = st.columns([0.44, 0.56], gap="large")
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
        status_col, history_col = st.columns(2)
        status_col.metric("预计输入", f"{estimated:,} tokens")
        history_col.metric("历史样例", f"{len(history)} 条")
        _show_token_status(estimated, settings.token_warn_threshold, settings.token_hard_limit)

        generate = st.button("生成会议纪要", type="primary", use_container_width=True)

    with right:
        st.subheader("生成结果")
        if not generate:
            st.info("录入历史纪要后，输入本次会议主题和原始记录即可生成。")
            return
        if not settings.api_key:
            st.error("请先在 .env 中配置 OPENAI_API_KEY。")
            return
        if estimated >= settings.token_hard_limit:
            st.error("本次请求已超过 token 硬限制，未发送给模型。")
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

        saved_path = save_generated_minutes(
            settings.output_dir,
            topic=current_topic,
            minutes=result.minutes,
        )
        st.text_area("会议纪要正文", value=result.minutes, height=520)
        st.caption(
            f"模型：{result.model}；历史样例：{result.history_count} 条；"
            f"预计输入：{result.estimated_input_tokens:,} tokens。"
        )
        st.success(f"已自动保存到：{saved_path}")
        st.download_button(
            "下载 TXT",
            data=result.minutes,
            file_name="meeting_minutes.txt",
            mime="text/plain",
            use_container_width=True,
        )


def _show_token_status(estimated: int, warn_threshold: int, hard_limit: int) -> None:
    if estimated <= 0:
        st.info("输入会议主题和原始记录后会显示预计上下文规模。")
    elif estimated >= hard_limit:
        st.error(
            f"预计输入超过硬限制 {hard_limit:,} tokens，"
            "请减少历史样例或压缩正文后再生成。"
        )
    elif estimated >= warn_threshold:
        st.warning(
            f"预计输入超过提醒阈值 {warn_threshold:,} tokens，"
            "请求可能较慢且成本较高。"
        )
    else:
        st.success(f"预计输入低于硬限制 {hard_limit:,} tokens。")
