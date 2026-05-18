from memopilot.models import HistoricalMinute
from memopilot.prompt import build_user_prompt, estimate_generation_input_tokens


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

