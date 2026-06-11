from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from memopilot.models import HistoricalMinute
from memopilot.tags import normalize_tags


def load_history(path: Path) -> list[HistoricalMinute]:
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("历史纪要文件格式错误：顶层必须是列表。")
    return [HistoricalMinute.model_validate(item) for item in raw]


def save_history(path: Path, items: list[HistoricalMinute]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([item.model_dump() for item in items], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def add_history(path: Path, topic: str, body: str, tags: list[str] | None = None) -> HistoricalMinute:
    items = load_history(path)
    item = HistoricalMinute(topic=topic.strip(), body=body.strip(), tags=normalize_tags(tags))
    items.append(item)
    save_history(path, items)
    return item


def add_many_history(path: Path, entries: list[tuple[Any, ...]], tags: list[str] | None = None) -> list[HistoricalMinute]:
    items = load_history(path)
    common_tags = normalize_tags(tags)
    new_items: list[HistoricalMinute] = []
    for entry in entries:
        if len(entry) < 2:
            continue
        topic, body = str(entry[0]), str(entry[1])
        if not topic.strip() or not body.strip():
            continue
        entry_tags = normalize_tags(entry[2]) if len(entry) >= 3 else []
        new_items.append(
            HistoricalMinute(
                topic=topic.strip(),
                body=body.strip(),
                tags=normalize_tags([*common_tags, *entry_tags]),
            )
        )
    items.extend(new_items)
    save_history(path, items)
    return new_items


def update_history(path: Path, item_id: str, topic: str, body: str, tags: list[str] | None = None) -> None:
    items = load_history(path)
    for index, item in enumerate(items):
        if item.id == item_id:
            update = {
                "topic": topic.strip(),
                "body": body.strip(),
                "updated_at": datetime.now().isoformat(timespec="seconds"),
            }
            if tags is not None:
                update["tags"] = normalize_tags(tags)
            items[index] = item.model_copy(update=update)
            save_history(path, items)
            return
    raise KeyError(f"未找到历史纪要：{item_id}")


def add_tags_to_history(path: Path, item_ids: list[str], tags: list[str]) -> int:
    tags_to_add = normalize_tags(tags)
    if not item_ids or not tags_to_add:
        return 0

    target_ids = set(item_ids)
    items = load_history(path)
    updated_count = 0
    now = datetime.now().isoformat(timespec="seconds")
    for index, item in enumerate(items):
        if item.id not in target_ids:
            continue
        merged_tags = normalize_tags([*item.tags, *tags_to_add])
        if merged_tags == item.tags:
            continue
        items[index] = item.model_copy(update={"tags": merged_tags, "updated_at": now})
        updated_count += 1

    if updated_count:
        save_history(path, items)
    return updated_count


def rename_history_tag(path: Path, old_tag: str, new_tag: str) -> int:
    old_tags = normalize_tags([old_tag])
    new_tags = normalize_tags([new_tag])
    if not old_tags or not new_tags or old_tags[0] == new_tags[0]:
        return 0

    old_value = old_tags[0]
    new_value = new_tags[0]
    items = load_history(path)
    updated_count = 0
    now = datetime.now().isoformat(timespec="seconds")
    for index, item in enumerate(items):
        if old_value not in item.tags:
            continue
        tags = [new_value if tag == old_value else tag for tag in item.tags]
        items[index] = item.model_copy(update={"tags": normalize_tags(tags), "updated_at": now})
        updated_count += 1

    if updated_count:
        save_history(path, items)
    return updated_count


def merge_history_tags(path: Path, source_tags: list[str], target_tag: str) -> int:
    sources = set(normalize_tags(source_tags))
    targets = normalize_tags([target_tag])
    if not sources or not targets:
        return 0

    target = targets[0]
    items = load_history(path)
    updated_count = 0
    now = datetime.now().isoformat(timespec="seconds")
    for index, item in enumerate(items):
        if not sources.intersection(item.tags):
            continue
        tags = [tag for tag in item.tags if tag not in sources]
        tags.append(target)
        items[index] = item.model_copy(update={"tags": normalize_tags(tags), "updated_at": now})
        updated_count += 1

    if updated_count:
        save_history(path, items)
    return updated_count


def delete_history_tag(path: Path, tag: str) -> int:
    tags_to_delete = set(normalize_tags([tag]))
    if not tags_to_delete:
        return 0

    items = load_history(path)
    updated_count = 0
    now = datetime.now().isoformat(timespec="seconds")
    for index, item in enumerate(items):
        if not tags_to_delete.intersection(item.tags):
            continue
        tags = [current_tag for current_tag in item.tags if current_tag not in tags_to_delete]
        items[index] = item.model_copy(update={"tags": tags, "updated_at": now})
        updated_count += 1

    if updated_count:
        save_history(path, items)
    return updated_count


def delete_history(path: Path, item_id: str) -> None:
    items = [item for item in load_history(path) if item.id != item_id]
    save_history(path, items)
