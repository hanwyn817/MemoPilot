from __future__ import annotations

import json
from pathlib import Path

import streamlit as st
from pydantic import ValidationError

from memopilot.models import HistoricalMinute
from memopilot.store import (
    add_history,
    add_many_history,
    add_tags_to_history,
    delete_history,
    delete_history_tag,
    merge_history_tags,
    rename_history_tag,
    save_history,
    update_history,
)
from memopilot.ui_components import all_tags, format_tags, tag_counts, tag_editor


def history_tab(history_file, history: list[HistoricalMinute]) -> None:
    left, right = st.columns([0.4, 0.6], gap="large")
    available_tags = all_tags(history)

    with left:
        st.subheader("添加样例")
        add_tab, import_tab = st.tabs(["手动录入", "批量导入"])

        with add_tab:
            with st.form("add_history"):
                topic = st.text_input("会议主题")
                tags = tag_editor("标签", [], available_tags, "add_history")
                body = st.text_area("会议正文", height=340)
                submitted = st.form_submit_button(
                    "保存到历史库",
                    type="primary",
                    width='stretch',
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
            import_tags = tag_editor("导入标签", [], available_tags, "import_history")
            if text_files and st.button("导入 TXT/MD", width='stretch'):
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
                    width='stretch',
                )
                uploaded = st.file_uploader("导入历史库 JSON", type=["json"])
                replace = st.checkbox("导入时替换现有历史库", value=False)
                if uploaded is not None and st.button("执行 JSON 导入", width='stretch'):
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

        _tag_management_panel(history_file, history, available_tags)

        search_col, tag_col, sort_col = st.columns([0.42, 0.28, 0.3])
        with search_col:
            query = st.text_input("搜索主题、标签或正文", placeholder="输入关键词筛选历史样例")
        with tag_col:
            filter_tags = st.multiselect("按标签筛选", options=available_tags, key="history_filter_tags")
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

        visible = _filter_visible_history(history, query, filter_tags)
        _sort_history(visible, sort_option)

        st.caption(f"当前显示 {len(visible)} / {len(history)} 条。")

        with st.expander("批量追加标签到当前筛选结果", expanded=False):
            st.caption(f"将标签追加到当前筛选结果中的 {len(visible)} 条样例。")
            with st.form("bulk_add_tags"):
                bulk_tags = tag_editor("要追加的标签", [], available_tags, "bulk_add_tags")
                bulk_submitted = st.form_submit_button("追加标签", width='stretch')
            if bulk_submitted:
                updated = add_tags_to_history(history_file, [item.id for item in visible], bulk_tags)
                if updated:
                    st.success(f"已更新 {updated} 条样例。")
                    st.rerun()
                else:
                    st.info("没有样例需要更新。")

        page_items = _show_pagination(visible)
        for item in page_items:
            title = item.topic if not item.tags else f"{item.topic}  [{format_tags(item.tags)}]"
            with st.expander(title, expanded=False):
                with st.form(f"edit_{item.id}"):
                    edited_topic = st.text_input("会议主题", value=item.topic, key=f"topic_{item.id}")
                    edited_tags = tag_editor("标签", item.tags, available_tags, f"edit_{item.id}")
                    edited_body = st.text_area("会议正文", value=item.body, height=260, key=f"body_{item.id}")
                    col_save, col_delete = st.columns(2)
                    save_clicked = col_save.form_submit_button("保存修改", width='stretch')
                    delete_clicked = col_delete.form_submit_button("删除", width='stretch')
                if save_clicked:
                    update_history(history_file, item.id, edited_topic, edited_body, tags=edited_tags)
                    st.success("已更新。")
                    st.rerun()
                if delete_clicked:
                    delete_history(history_file, item.id)
                    st.success("已删除。")
                    st.rerun()


def _tag_management_panel(history_file, history: list[HistoricalMinute], available_tags: list[str]) -> None:
    with st.expander("标签管理", expanded=False):
        if not available_tags:
            st.info("当前没有标签。")
            return

        counts = tag_counts(history)
        st.dataframe(
            [{"标签": tag, "样例数": counts[tag]} for tag in available_tags],
            hide_index=True,
            width='stretch',
        )

        rename_col, merge_col, delete_col = st.columns(3)
        with rename_col:
            with st.form("rename_tag"):
                old_tag = st.selectbox("原标签", options=available_tags, key="rename_tag_old")
                new_tag = st.text_input("新标签", key="rename_tag_new")
                rename_submitted = st.form_submit_button("重命名", width='stretch')
            if rename_submitted:
                updated = rename_history_tag(history_file, old_tag, new_tag)
                _show_tag_operation_result(updated)

        with merge_col:
            with st.form("merge_tags"):
                source_tags = st.multiselect("要合并的标签", options=available_tags, key="merge_tag_sources")
                target_tag = st.text_input("合并到标签", key="merge_tag_target")
                merge_submitted = st.form_submit_button("合并", width='stretch')
            if merge_submitted:
                updated = merge_history_tags(history_file, source_tags, target_tag)
                _show_tag_operation_result(updated)

        with delete_col:
            with st.form("delete_tag"):
                tag_to_delete = st.selectbox("要删除的标签", options=available_tags, key="delete_tag_value")
                confirmed = st.checkbox("确认删除该标签", key="delete_tag_confirmed")
                delete_submitted = st.form_submit_button("删除标签", width='stretch')
            if delete_submitted:
                if not confirmed:
                    st.warning("请先勾选确认删除。")
                else:
                    updated = delete_history_tag(history_file, tag_to_delete)
                    _show_tag_operation_result(updated)


def _filter_visible_history(
    history: list[HistoricalMinute],
    query: str,
    filter_tags: list[str],
) -> list[HistoricalMinute]:
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
    return visible


def _sort_history(items: list[HistoricalMinute], sort_option: str) -> None:
    if sort_option == "添加日期（最新在前）":
        items.sort(key=lambda x: x.created_at, reverse=True)
    elif sort_option == "添加日期（最早在前）":
        items.sort(key=lambda x: x.created_at)
    elif sort_option == "名称（A-Z）":
        items.sort(key=lambda x: x.topic.lower())
    elif sort_option == "名称（Z-A）":
        items.sort(key=lambda x: x.topic.lower(), reverse=True)


def _show_pagination(visible: list[HistoricalMinute]) -> list[HistoricalMinute]:
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

    prev_disabled = page_num <= 1
    next_disabled = page_num >= total_pages

    cols = st.columns([1, 1, 2, 1, 1])
    with cols[0]:
        if st.button("◀ 上一页", disabled=prev_disabled, width='stretch', key="btn_prev"):
            st.session_state.page_num = page_num - 1
            st.rerun()
    with cols[1]:
        if st.button("下一页 ▶", disabled=next_disabled, width='stretch', key="btn_next"):
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
    return page_items


def _show_tag_operation_result(updated: int) -> None:
    if updated:
        st.success(f"已更新 {updated} 条样例。")
        st.rerun()
    else:
        st.info("没有样例需要更新。")
