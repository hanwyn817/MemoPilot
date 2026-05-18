from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from memopilot.models import HistoricalMinute


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


def add_history(path: Path, topic: str, body: str) -> HistoricalMinute:
    items = load_history(path)
    item = HistoricalMinute(topic=topic.strip(), body=body.strip())
    items.append(item)
    save_history(path, items)
    return item


def update_history(path: Path, item_id: str, topic: str, body: str) -> None:
    items = load_history(path)
    for index, item in enumerate(items):
        if item.id == item_id:
            items[index] = item.model_copy(
                update={
                    "topic": topic.strip(),
                    "body": body.strip(),
                    "updated_at": datetime.now().isoformat(timespec="seconds"),
                }
            )
            save_history(path, items)
            return
    raise KeyError(f"未找到历史纪要：{item_id}")


def delete_history(path: Path, item_id: str) -> None:
    items = [item for item in load_history(path) if item.id != item_id]
    save_history(path, items)

