from __future__ import annotations

import json
from pathlib import Path

import streamlit as st
from pydantic import ValidationError

from memopilot.config import load_settings
from memopilot.generator import generate_minutes_stream
from memopilot.models import HistoricalMinute
from memopilot.output import save_generated_minutes
from memopilot.prompt import estimate_generation_input_token_breakdown, estimate_generation_input_tokens
from memopilot.store import (
    add_history,
    add_many_history,
    add_tags_to_history,
    delete_history,
    delete_history_tag,
    load_history,
    merge_history_tags,
    rename_history_tag,
    save_history,
    update_history,
)
from memopilot.tags import filter_history_by_tags, normalize_tags
from memopilot.token_estimate import estimate_tokens


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
        _history_tab(settings.history_file, history)

    with tab_generate:
        _generate_tab(settings, history)


def _history_tab(history_file, history: list[HistoricalMinute]) -> None:
    left, right = st.columns([0.4, 0.6], gap="large")
    all_tags = _all_tags(history)

    with left:
        st.subheader("添加样例")
        add_tab, import_tab = st.tabs(["手动录入", "批量导入"])

        with add_tab:
            with st.form("add_history"):
                topic = st.text_input("会议主题")
                tags = _tag_editor("标签", [], all_tags, "add_history")
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
                    add_history(history_file, topic, body, tags=tags)
                    st.success("已保存。")
                    st.rerun()

        with import_tab:
            text_files = st.file_uploader(
                "上传 TXT/MD 文件",
                type=["txt", "md"],
                accept_multiple_files=True,
            )
            st.caption("文件名会作为会议主题，文件内容会作为会议正文。")
            import_tags = _tag_editor("导入标签", [], all_tags, "import_history")
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
                imported = add_many_history(history_file, entries, tags=import_tags)
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

        _tag_management_panel(history_file, history, all_tags)

        search_col, tag_col, sort_col = st.columns([0.42, 0.28, 0.3])
        with search_col:
            query = st.text_input("搜索主题、标签或正文", placeholder="输入关键词筛选历史样例")
        with tag_col:
            filter_tags = st.multiselect("按标签筛选", options=all_tags, key="history_filter_tags")
        with sort_col:
            sort_option = st.selectbox(
                "排序方式",
                options=[
                    "添加日期（最新在前）",
                    "添加日期（最早在前）",
                    "名称（A-Z）",
                    "名称（Z-A）",
                ],
                index=0,
            )

        query_text = query.strip()
        visible = []
        for item in history:
            query_match = (
                not query_text
                or query_text in item.topic
                or query_text in item.body
                or any(query_text in tag for tag in item.tags)
            )
            tag_match = not filter_tags or set(filter_tags).intersection(item.tags)
            if query_match and tag_match:
                visible.append(item)

        if sort_option == "添加日期（最新在前）":
            visible.sort(key=lambda x: x.created_at, reverse=True)
        elif sort_option == "添加日期（最早在前）":
            visible.sort(key=lambda x: x.created_at)
        elif sort_option == "名称（A-Z）":
            visible.sort(key=lambda x: x.topic.lower())
        elif sort_option == "名称（Z-A）":
            visible.sort(key=lambda x: x.topic.lower(), reverse=True)

        st.caption(f"当前显示 {len(visible)} / {len(history)} 条。")

        with st.expander("批量追加标签到当前筛选结果", expanded=False):
            st.caption(f"将标签追加到当前筛选结果中的 {len(visible)} 条样例。")
            with st.form("bulk_add_tags"):
                bulk_tags = _tag_editor("要追加的标签", [], all_tags, "bulk_add_tags")
                bulk_submitted = st.form_submit_button("追加标签", use_container_width=True)
            if bulk_submitted:
                updated = add_tags_to_history(history_file, [item.id for item in visible], bulk_tags)
                if updated:
                    st.success(f"已更新 {updated} 条样例。")
                    st.rerun()
                else:
                    st.info("没有样例需要更新。")

        # 分页控制（紧凑布局）
        page_size_options = {"5": 5, "10": 10, "20": 20, "50": 50}
        page_size = page_size_options.get(st.session_state.get("page_size", "10"), 10)
        total_pages = max(1, (len(visible) + page_size - 1) // page_size)
        page_num = st.session_state.get("page_num", 1)
        if page_num > total_pages:
            page_num = total_pages
            st.session_state.page_num = page_num

        start_idx = (page_num - 1) * page_size
        end_idx = min(start_idx + page_size, len(visible))
        page_items = visible[start_idx:end_idx]

        # 分页控件行
        prev_disabled = page_num <= 1
        next_disabled = page_num >= total_pages

        cols = st.columns([1, 1, 2, 1, 1])
        with cols[0]:
            if st.button("◀ 上一页", disabled=prev_disabled, use_container_width=True, key="btn_prev"):
                st.session_state.page_num = page_num - 1
                st.rerun()
        with cols[1]:
            if st.button("下一页 ▶", disabled=next_disabled, use_container_width=True, key="btn_next"):
                st.session_state.page_num = page_num + 1
                st.rerun()
        with cols[2]:
            st.markdown(
                f"<div style='text-align:center; padding-top:0.5rem; color:#888; font-size:0.9rem;'>"
                f"第 <b>{page_num}</b> / {total_pages} 页"
                f"</div>",
                unsafe_allow_html=True,
            )
        with cols[3]:
            selected = st.selectbox(
                "每页",
                options=list(page_size_options.keys()),
                index=1,
                key="page_size",
                label_visibility="collapsed",
            )
            page_size = page_size_options[selected]
        with cols[4]:
            st.markdown(
                f"<div style='text-align:right; padding-top:0.5rem; color:#888; font-size:0.9rem;'>"
                f"{start_idx + 1 if visible else 0}-{end_idx} 条"
                f"</div>",
                unsafe_allow_html=True,
            )

        for item in page_items:
            title = item.topic if not item.tags else f"{item.topic}  [{_format_tags(item.tags)}]"
            with st.expander(title, expanded=False):
                with st.form(f"edit_{item.id}"):
                    edited_topic = st.text_input("会议主题", value=item.topic, key=f"topic_{item.id}")
                    edited_tags = _tag_editor("标签", item.tags, all_tags, f"edit_{item.id}")
                    edited_body = st.text_area("会议正文", value=item.body, height=260, key=f"body_{item.id}")
                    col_save, col_delete = st.columns(2)
                    save_clicked = col_save.form_submit_button("保存修改", use_container_width=True)
                    delete_clicked = col_delete.form_submit_button("删除", use_container_width=True)
                if save_clicked:
                    update_history(history_file, item.id, edited_topic, edited_body, tags=edited_tags)
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
        all_tags = _all_tags(history)
        selected_tags = st.multiselect(
            "选择历史样例标签",
            options=all_tags,
            help="可选择一个或多个标签；不选择时使用全部历史样例。",
        )
        selected_history = filter_history_by_tags(history, selected_tags)
        transcript = st.text_area("本次会议原始记录", height=460)
        tag_scope = _format_tags(selected_tags) if selected_tags else "未选择标签，使用全部历史样例"
        st.caption(f"当前标签范围：{tag_scope}；共 {len(selected_history)} 条样例。")
        _show_selected_history_preview(selected_history)

        estimated = 0
        token_breakdown = _empty_token_breakdown()
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
        _show_token_breakdown(token_breakdown)
        _show_token_status(estimated, settings.token_warn_threshold, settings.token_hard_limit)

        generate = st.button("生成会议纪要", type="primary", use_container_width=True)

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
            metadata={
                "model": settings.model,
                "topic": current_topic.strip(),
                "selected_tags": selected_tags,
                "history_count": len(selected_history),
                "history_examples": [
                    {"id": item.id, "topic": item.topic, "tags": item.tags} for item in selected_history
                ],
                "estimated_input_tokens": estimated,
                "token_breakdown": token_breakdown,
                "completion_tokens": completion_tokens,
            },
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


def _tag_management_panel(history_file, history: list[HistoricalMinute], all_tags: list[str]) -> None:
    with st.expander("标签管理", expanded=False):
        if not all_tags:
            st.info("当前没有标签。")
            return

        tag_counts = _tag_counts(history)
        st.dataframe(
            [{"标签": tag, "样例数": tag_counts[tag]} for tag in all_tags],
            hide_index=True,
            use_container_width=True,
        )

        rename_col, merge_col, delete_col = st.columns(3)
        with rename_col:
            with st.form("rename_tag"):
                old_tag = st.selectbox("原标签", options=all_tags, key="rename_tag_old")
                new_tag = st.text_input("新标签", key="rename_tag_new")
                rename_submitted = st.form_submit_button("重命名", use_container_width=True)
            if rename_submitted:
                updated = rename_history_tag(history_file, old_tag, new_tag)
                _show_tag_operation_result(updated)

        with merge_col:
            with st.form("merge_tags"):
                source_tags = st.multiselect("要合并的标签", options=all_tags, key="merge_tag_sources")
                target_tag = st.text_input("合并到标签", key="merge_tag_target")
                merge_submitted = st.form_submit_button("合并", use_container_width=True)
            if merge_submitted:
                updated = merge_history_tags(history_file, source_tags, target_tag)
                _show_tag_operation_result(updated)

        with delete_col:
            with st.form("delete_tag"):
                tag_to_delete = st.selectbox("要删除的标签", options=all_tags, key="delete_tag_value")
                confirmed = st.checkbox("确认删除该标签", key="delete_tag_confirmed")
                delete_submitted = st.form_submit_button("删除标签", use_container_width=True)
            if delete_submitted:
                if not confirmed:
                    st.warning("请先勾选确认删除。")
                else:
                    updated = delete_history_tag(history_file, tag_to_delete)
                    _show_tag_operation_result(updated)


def _show_tag_operation_result(updated: int) -> None:
    if updated:
        st.success(f"已更新 {updated} 条样例。")
        st.rerun()
    else:
        st.info("没有样例需要更新。")


def _show_selected_history_preview(selected_history: list[HistoricalMinute]) -> None:
    with st.expander("本次将使用的历史样例", expanded=False):
        if not selected_history:
            st.info("当前标签范围下没有样例。")
            return
        preview_items = selected_history[:20]
        st.dataframe(
            [
                {
                    "会议主题": item.topic,
                    "标签": _format_tags(item.tags) if item.tags else "无",
                }
                for item in preview_items
            ],
            hide_index=True,
            use_container_width=True,
        )
        if len(selected_history) > len(preview_items):
            st.caption(f"仅预览前 {len(preview_items)} 条；实际将使用 {len(selected_history)} 条。")


def _show_token_breakdown(token_breakdown: dict[str, int]) -> None:
    with st.expander("Token 构成", expanded=False):
        cols = st.columns(4)
        cols[0].metric("系统提示", f"{token_breakdown['system_prompt']:,}")
        cols[1].metric("写作规则", f"{token_breakdown['instructions']:,}")
        cols[2].metric("历史样例", f"{token_breakdown['history_examples']:,}")
        cols[3].metric("本次会议", f"{token_breakdown['current_meeting']:,}")


def _empty_token_breakdown() -> dict[str, int]:
    return {
        "total": 0,
        "system_prompt": 0,
        "instructions": 0,
        "history_examples": 0,
        "current_meeting": 0,
    }


def _all_tags(history: list[HistoricalMinute]) -> list[str]:
    return sorted({tag for item in history for tag in item.tags})


def _tag_counts(history: list[HistoricalMinute]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in history:
        for tag in item.tags:
            counts[tag] = counts.get(tag, 0) + 1
    return counts


def _tag_editor(label: str, current_tags: list[str], all_tags: list[str], key_prefix: str) -> list[str]:
    options = sorted(set(normalize_tags([*all_tags, *current_tags])))
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


def _format_tags(tags: list[str]) -> str:
    return "、".join(tags)
