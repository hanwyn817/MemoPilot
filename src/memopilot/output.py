from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from memopilot.models import GenerationMetadata


def save_generated_minutes(
    output_dir: Path,
    *,
    topic: str,
    minutes: str,
    metadata: GenerationMetadata | dict[str, Any] | None = None,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_topic = _safe_filename(topic) or "meeting"
    path = output_dir / f"{timestamp}-{safe_topic}.txt"
    path.write_text(minutes.strip() + "\n", encoding="utf-8")
    if metadata is not None:
        metadata_path = path.with_suffix(".metadata.json")
        metadata_payload = metadata.model_dump() if isinstance(metadata, BaseModel) else dict(metadata)
        metadata_payload["saved_at"] = metadata_payload.get("saved_at") or datetime.now().isoformat(timespec="seconds")
        metadata_path.write_text(json.dumps(metadata_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _safe_filename(value: str, max_length: int = 80) -> str:
    value = re.sub(r"[\\/:*?\"<>|\\s]+", "-", value.strip())
    value = value.strip("-._")
    return value[:max_length]
