from pathlib import Path

from memopilot.output import save_generated_minutes
from memopilot.store import add_many_history, load_history


def test_add_many_history_imports_entries(tmp_path: Path) -> None:
    history_file = tmp_path / "history.json"

    imported = add_many_history(
        history_file,
        [
            ("A专题会", "一、A事项\nA部门完成材料。"),
            ("空正文", ""),
            ("B专题会", "一、B事项\nB部门推进评估。"),
        ],
    )

    assert len(imported) == 2
    assert [item.topic for item in load_history(history_file)] == ["A专题会", "B专题会"]


def test_save_generated_minutes_writes_safe_filename(tmp_path: Path) -> None:
    path = save_generated_minutes(
        tmp_path,
        topic="A/B:专题会",
        minutes="一、主要内容\n相关部门完成事项。",
    )

    assert path.exists()
    assert "A-B-专题会" in path.name
    assert path.read_text(encoding="utf-8").startswith("一、主要内容")

