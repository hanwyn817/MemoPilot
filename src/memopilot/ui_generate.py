from __future__ import annotations

import streamlit as st

from memopilot.config import Settings
from memopilot.generator import generate_minutes_stream
from memopilot.models import GenerationMetadata, HistoricalMinute
from memopilot.output import save_generated_minutes
from memopilot.prompt import estimate_generation_input_token_breakdown, estimate_generation_input_tokens
from memopilot.tags import filter_history_by_tags
from memopilot.token_estimate import estimate_tokens
from memopilot.ui_components import (
    all_tags,
    empty_token_breakdown,
    format_tags,
    show_selected_history_preview,
    show_token_breakdown,
    show_token_status,
)


def generate_tab(settings: Settings, history: list[HistoricalMinute]) -> None:
    left, right = st.columns([0.44, 0.56], gap="large")
    with left:
        st.subheader("本次会议")
        current_topic = st.text_input("本次会议主题")
        available_tags = all_tags(history)
        selected_tags = st.multiselect(
            "选择历史样例标签",
            options=available_tags,
            help="可选择一个或多个标签；不选择时使用全部历史样例。",
        )
        selected_history = filter_history_by_tags(history, selected_tags)
        transcript = st.text_area("本次会议原始记录", height=460)
        tag_scope = format_tags(selected_tags) if selected_tags else "未选择标签，使用全部历史样例"
        st.caption(f"当前标签范围：{tag_scope}；共 {len(selected_history)} 条样例。")
        show_selected_history_preview(selected_history)

        estimated = 0
        token_breakdown = empty_token_breakdown()
        if current_topic.strip() and transcript.strip() and selected_history:
            estimated = estimate_generation_input_tokens(
                selected_history,
                current_topic=current_topic,
                transcript=transcript,
            )
            token_breakdown = estimate_generation_input_token_breakdown(
                selected_history,
                current_topic=current_topic,
                transcript=transcript,
            )
        status_col, history_col = st.columns(2)
        status_col.metric("预计输入", f"{estimated:,} tokens")
        history_col.metric("选中样例", f"{len(selected_history)} / {len(history)} 条")
        show_token_breakdown(token_breakdown)
        show_token_status(estimated, settings.token_warn_threshold, settings.token_hard_limit)

        generate = st.button("生成会议纪要", type="primary", width='stretch')

    with right:
        st.markdown("<h3 id='generate-result'>生成结果</h3>", unsafe_allow_html=True)
        if not generate:
            st.info("录入历史纪要后，输入本次会议主题和原始记录即可生成。")
            return
        if not settings.api_key:
            st.error("请先在 .env 中配置 OPENAI_API_KEY。")
            return
        if not selected_history:
            st.error("当前标签范围下没有可用历史样例。")
            return
        if estimated >= settings.token_hard_limit:
            st.error("本次请求已超过 token 硬限制，未发送给模型。")
            return
        st.html(
            "<script>"
            "const el = document.getElementById('generate-result');"
            "if (el) el.scrollIntoView({behavior: 'smooth', block: 'start'});"
            "</script>"
        )
        try:
            stream_container = st.container()
            with stream_container:
                placeholder = st.empty()
                placeholder.info("正在生成会议纪要，请稍候...")
                result_text = placeholder.write_stream(
                    generate_minutes_stream(
                        settings,
                        current_topic=current_topic,
                        transcript=transcript,
                        selected_tags=selected_tags,
                    )
                )
        except Exception as exc:
            st.error(f"生成失败：{exc}")
            return

        result_text = result_text.strip()
        completion_tokens = estimate_tokens(result_text)

        saved_path = save_generated_minutes(
            settings.output_dir,
            topic=current_topic,
            minutes=result_text,
            metadata=GenerationMetadata(
                model=settings.model,
                topic=current_topic.strip(),
                selected_tags=selected_tags,
                history_count=len(selected_history),
                history_examples=[
                    {"id": item.id, "topic": item.topic, "tags": item.tags} for item in selected_history
                ],
                estimated_input_tokens=estimated,
                token_breakdown=token_breakdown,
                completion_tokens=completion_tokens,
            ),
        )
        st.caption(
            f"模型：{settings.model}；标签：{tag_scope}；历史样例：{len(selected_history)} 条；"
            f"预计输入：{estimated:,} tokens；"
            f"实际消耗：输入 {estimated:,} / 输出 {completion_tokens:,} tokens。"
        )
        st.success(f"已自动保存到：{saved_path}")
        st.download_button(
            "下载 TXT",
            data=result_text,
            file_name="meeting_minutes.txt",
            mime="text/plain",
            width='stretch',
        )
