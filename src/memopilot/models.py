from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from memopilot.tags import normalize_tags


class HistoricalMinute(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    topic: str
    body: str
    tags: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    @field_validator("tags", mode="before")
    @classmethod
    def _normalize_tags(cls, value):
        return normalize_tags(value)


class GenerationResult(BaseModel):
    minutes: str
    estimated_input_tokens: int
    actual_prompt_tokens: int
    actual_completion_tokens: int
    history_count: int
    model: str
