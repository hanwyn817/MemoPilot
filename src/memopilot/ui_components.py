from __future__ import annotations

import streamlit as st

from memopilot.models import HistoricalMinute
from memopilot.tags import normalize_tags


def show_token_status(estimated: int, warn_threshold: int, hard_limit: int) -> None:
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


def show_selected_history_preview(selected_history: list[HistoricalMinute]) -> None:
    with st.expander("本次将使用的历史样例", expanded=False):
        if not selected_history:
            st.info("当前标签范围下没有样例。")
            return
        preview_items = selected_history[:20]
        st.dataframe(
            [
                {
                    "会议主题": item.topic,
                    "标签": format_tags(item.tags) if item.tags else "无",
                }
                for item in preview_items
            ],
            hide_index=True,
            use_container_width=True,
        )
        if len(selected_history) > len(preview_items):
            st.caption(f"仅预览前 {len(preview_items)} 条；实际将使用 {len(selected_history)} 条。")


def show_token_breakdown(token_breakdown: dict[str, int]) -> None:
    with st.expander("Token 构成", expanded=False):
        cols = st.columns(4)
        cols[0].metric("系统提示", f"{token_breakdown['system_prompt']:,}")
        cols[1].metric("写作规则", f"{token_breakdown['instructions']:,}")
        cols[2].metric("历史样例", f"{token_breakdown['history_examples']:,}")
        cols[3].metric("本次会议", f"{token_breakdown['current_meeting']:,}")


def empty_token_breakdown() -> dict[str, int]:
    return {
        "total": 0,
        "system_prompt": 0,
        "instructions": 0,
        "history_examples": 0,
        "current_meeting": 0,
    }


def all_tags(history: list[HistoricalMinute]) -> list[str]:
    return sorted({tag for item in history for tag in item.tags})


def tag_counts(history: list[HistoricalMinute]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in history:
        for tag in item.tags:
            counts[tag] = counts.get(tag, 0) + 1
    return counts


def tag_editor(label: str, current_tags: list[str], available_tags: list[str], key_prefix: str) -> list[str]:
    options = sorted(set(normalize_tags([*available_tags, *current_tags])))
    selected = st.multiselect(
        label,
        options=options,
        default=[tag for tag in current_tags if tag in options],
        key=f"{key_prefix}_selected_tags",
    )
    new_tags = st.text_input(
        "新增标签（逗号分隔）",
        placeholder="如：原料药药，选药会，制剂，华奥泰",
        key=f"{key_prefix}_new_tags",
    )
    return normalize_tags([*selected, new_tags])


def format_tags(tags: list[str]) -> str:
    return "、".join(tags)
