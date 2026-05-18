from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    project_root: Path
    history_file: Path
    output_dir: Path
    model: str
    api_key: str | None
    base_url: str
    token_warn_threshold: int
    token_hard_limit: int


def load_settings() -> Settings:
    project_root = Path.cwd()
    load_dotenv(project_root / ".env")

    history_file = Path(os.getenv("MEMOPILOT_HISTORY_FILE", "data/history_minutes.json"))
    if not history_file.is_absolute():
        history_file = project_root / history_file
    output_dir = Path(os.getenv("MEMOPILOT_OUTPUT_DIR", "outputs"))
    if not output_dir.is_absolute():
        output_dir = project_root / output_dir

    return Settings(
        project_root=project_root,
        history_file=history_file,
        output_dir=output_dir,
        model=os.getenv("MEMOPILOT_MODEL", "deepseek-v4-pro"),
        api_key=os.getenv("OPENAI_API_KEY") or None,
        base_url=os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com"),
        token_warn_threshold=int(os.getenv("MEMOPILOT_TOKEN_WARN_THRESHOLD", "700000")),
        token_hard_limit=int(os.getenv("MEMOPILOT_TOKEN_HARD_LIMIT", "900000")),
    )
