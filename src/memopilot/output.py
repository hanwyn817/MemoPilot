from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path


def save_generated_minutes(output_dir: Path, *, topic: str, minutes: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_topic = _safe_filename(topic) or "meeting"
    path = output_dir / f"{timestamp}-{safe_topic}.txt"
    path.write_text(minutes.strip() + "\n", encoding="utf-8")
    return path


def _safe_filename(value: str, max_length: int = 80) -> str:
    value = re.sub(r"[\\/:*?\"<>|\\s]+", "-", value.strip())
    value = value.strip("-._")
    return value[:max_length]

