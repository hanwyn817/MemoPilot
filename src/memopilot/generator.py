from __future__ import annotations

from memopilot.config import Settings
from memopilot.llm import LLMClient
from memopilot.models import GenerationResult
from memopilot.prompt import build_generation_messages, estimate_generation_input_tokens
from memopilot.store import load_history


def generate_minutes(
    settings: Settings,
    *,
    current_topic: str,
    transcript: str,
) -> GenerationResult:
    topic = current_topic.strip()
    raw_record = transcript.strip()
    if not topic:
        raise ValueError("本次会议主题不能为空。")
    if not raw_record:
        raise ValueError("本次会议原始记录不能为空。")

    history = load_history(settings.history_file)
    if not history:
        raise ValueError("请先录入至少一条历史会议纪要样例。")

    messages = build_generation_messages(history, current_topic=topic, transcript=raw_record)
    estimated_tokens = estimate_generation_input_tokens(
        history,
        current_topic=topic,
        transcript=raw_record,
    )
    minutes = LLMClient(settings).generate(messages).strip()
    return GenerationResult(
        minutes=minutes,
        estimated_input_tokens=estimated_tokens,
        history_count=len(history),
        model=settings.model,
    )

