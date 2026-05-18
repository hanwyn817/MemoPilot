from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    project_root: Path
    history_file: Path
    model: str
    api_key: str | None
    base_url: str


def load_settings() -> Settings:
    project_root = Path.cwd()
    load_dotenv(project_root / ".env")

    history_file = Path(os.getenv("MEMOPILOT_HISTORY_FILE", "data/history_minutes.json"))
    if not history_file.is_absolute():
        history_file = project_root / history_file

    return Settings(
        project_root=project_root,
        history_file=history_file,
        model=os.getenv("MEMOPILOT_MODEL", "deepseek-v4-pro"),
        api_key=os.getenv("OPENAI_API_KEY") or None,
        base_url=os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com"),
    )

