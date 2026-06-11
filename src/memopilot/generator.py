from __future__ import annotations

from memopilot.config import Settings
from memopilot.llm import LLMClient
from memopilot.models import GenerationResult
from memopilot.prompt import build_generation_messages, estimate_generation_input_tokens
from memopilot.store import load_history
from memopilot.tags import filter_history_by_tags, normalize_tags
from memopilot.token_estimate import estimate_tokens


def generate_minutes(
    settings: Settings,
    *,
    current_topic: str,
    transcript: str,
    selected_tags: list[str] | None = None,
) -> GenerationResult:
    topic = current_topic.strip()
    raw_record = transcript.strip()
    if not topic:
        raise ValueError("本次会议主题不能为空。")
    if not raw_record:
        raise ValueError("本次会议原始记录不能为空。")

    history = filter_history_by_tags(load_history(settings.history_file), selected_tags)
    if not history:
        if normalize_tags(selected_tags):
            raise ValueError("所选标签下没有历史会议纪要样例。")
        raise ValueError("请先录入至少一条历史会议纪要样例。")

    messages = build_generation_messages(history, current_topic=topic, transcript=raw_record)
    estimated_tokens = estimate_generation_input_tokens(
        history,
        current_topic=topic,
        transcript=raw_record,
    )

    full_text = ""
    for chunk in LLMClient(settings).generate_stream(messages):
        full_text += chunk

    full_text = full_text.strip()
    completion_tokens = estimate_tokens(full_text)
    return GenerationResult(
        minutes=full_text,
        estimated_input_tokens=estimated_tokens,
        actual_prompt_tokens=estimated_tokens,
        actual_completion_tokens=completion_tokens,
        history_count=len(history),
        model=settings.model,
    )


def generate_minutes_stream(
    settings: Settings,
    *,
    current_topic: str,
    transcript: str,
    selected_tags: list[str] | None = None,
):
    """Yield text chunks for streaming display."""
    topic = current_topic.strip()
    raw_record = transcript.strip()
    if not topic:
        raise ValueError("本次会议主题不能为空。")
    if not raw_record:
        raise ValueError("本次会议原始记录不能为空。")

    history = filter_history_by_tags(load_history(settings.history_file), selected_tags)
    if not history:
        if normalize_tags(selected_tags):
            raise ValueError("所选标签下没有历史会议纪要样例。")
        raise ValueError("请先录入至少一条历史会议纪要样例。")

    messages = build_generation_messages(history, current_topic=topic, transcript=raw_record)
    yield from LLMClient(settings).generate_stream(messages)
