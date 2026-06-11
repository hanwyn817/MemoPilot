from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any


_TAG_SEPARATORS = re.compile(r"[,，、;；\n]+")


def normalize_tags(tags: Iterable[Any] | str | None) -> list[str]:
    if tags is None:
        return []

    raw_tags: list[str] = []
    if isinstance(tags, str):
        raw_tags.extend(_TAG_SEPARATORS.split(tags))
    else:
        for tag in tags:
            if isinstance(tag, str):
                raw_tags.extend(_TAG_SEPARATORS.split(tag))
            elif tag is not None:
                raw_tags.append(str(tag))

    normalized: list[str] = []
    seen: set[str] = set()
    for tag in raw_tags:
        value = tag.strip()
        if not value or value in seen:
            continue
        normalized.append(value)
        seen.add(value)
    return normalized


def filter_history_by_tags(history: list[Any], selected_tags: Iterable[Any] | str | None) -> list[Any]:
    selected = set(normalize_tags(selected_tags))
    if not selected:
        return list(history)
    return [item for item in history if selected.intersection(normalize_tags(getattr(item, "tags", [])))]
