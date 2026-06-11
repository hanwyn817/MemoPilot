from memopilot.models import HistoricalMinute
from memopilot.prompt import (
    build_user_prompt,
    estimate_generation_input_token_breakdown,
    estimate_generation_input_tokens,
)
from memopilot.tags import filter_history_by_tags


def test_prompt_uses_all_history_examples() -> None:
    history = [
        HistoricalMinute(topic="A专题会", body="一、A事项\nA部门完成材料。"),
        HistoricalMinute(topic="B专题会", body="一、B事项\nB部门推进评估。"),
    ]

    prompt = build_user_prompt(history, current_topic="C专题会", transcript="C部门汇报进展。")

    assert "A专题会" in prompt
    assert "B专题会" in prompt
    assert "C专题会" in prompt
    assert "历史样例只用于学习文风" in prompt


def test_token_estimate_is_positive() -> None:
    history = [HistoricalMinute(topic="历史会", body="一、主要内容\n相关部门完成事项。")]

    tokens = estimate_generation_input_tokens(history, current_topic="本次会", transcript="原始记录")

    assert tokens > 0


def test_token_breakdown_reports_history_and_current_meeting() -> None:
    history = [HistoricalMinute(topic="历史会", body="一、主要内容\n相关部门完成事项。", tags=["制剂"])]

    breakdown = estimate_generation_input_token_breakdown(history, current_topic="本次会", transcript="原始记录")

    assert breakdown["total"] == estimate_generation_input_tokens(
        history,
        current_topic="本次会",
        transcript="原始记录",
    )
    assert breakdown["history_examples"] > 0
    assert breakdown["current_meeting"] > 0


def test_filter_history_by_tags_uses_tag_union() -> None:
    history = [
        HistoricalMinute(topic="A专题会", body="一、A事项", tags=["原料药药", "选药会"]),
        HistoricalMinute(topic="B专题会", body="一、B事项", tags=["制剂"]),
        HistoricalMinute(topic="C专题会", body="一、C事项", tags=["华奥泰"]),
    ]

    selected = filter_history_by_tags(history, ["选药会", "制剂"])

    assert [item.topic for item in selected] == ["A专题会", "B专题会"]
    assert filter_history_by_tags(history, []) == history


def test_prompt_does_not_include_history_tags() -> None:
    history = [HistoricalMinute(topic="制剂专题会", body="一、制剂事项", tags=["仅用于筛选的标签"])]

    prompt = build_user_prompt(history, current_topic="本次会", transcript="原始记录")

    assert "仅用于筛选的标签" not in prompt
