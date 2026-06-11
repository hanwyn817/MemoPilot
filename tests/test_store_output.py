from pathlib import Path

from memopilot.models import GenerationMetadata
from memopilot.output import save_generated_minutes
from memopilot.store import (
    add_history,
    add_many_history,
    add_tags_to_history,
    delete_history_tag,
    load_history,
    merge_history_tags,
    rename_history_tag,
    update_history,
)


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


def test_history_tags_can_be_added_and_updated(tmp_path: Path) -> None:
    history_file = tmp_path / "history.json"
    item = add_history(history_file, "A专题会", "一、A事项", tags=["原料药药，选药会"])

    assert load_history(history_file)[0].tags == ["原料药药", "选药会"]

    update_history(history_file, item.id, "A专题会", "一、A事项", tags=["制剂", "制剂"])
    assert load_history(history_file)[0].tags == ["制剂"]

    updated = add_tags_to_history(history_file, [item.id], ["制剂", "华奥泰"])
    assert updated == 1
    assert load_history(history_file)[0].tags == ["制剂", "华奥泰"]


def test_history_tags_can_be_renamed_merged_and_deleted(tmp_path: Path) -> None:
    history_file = tmp_path / "history.json"
    add_many_history(
        history_file,
        [
            ("A专题会", "一、A事项", ["原料药药", "选药会"]),
            ("B专题会", "一、B事项", ["制剂"]),
            ("C专题会", "一、C事项", ["华奥泰"]),
        ],
    )

    assert rename_history_tag(history_file, "原料药药", "原料药") == 1
    assert load_history(history_file)[0].tags == ["原料药", "选药会"]

    assert merge_history_tags(history_file, ["选药会", "制剂"], "专题会") == 2
    assert [item.tags for item in load_history(history_file)] == [["原料药", "专题会"], ["专题会"], ["华奥泰"]]

    assert delete_history_tag(history_file, "专题会") == 2
    assert [item.tags for item in load_history(history_file)] == [["原料药"], [], ["华奥泰"]]


def test_load_history_accepts_existing_items_without_tags(tmp_path: Path) -> None:
    history_file = tmp_path / "history.json"
    history_file.write_text('[{"topic":"旧样例","body":"正文"}]', encoding="utf-8")

    assert load_history(history_file)[0].tags == []


def test_save_generated_minutes_writes_safe_filename(tmp_path: Path) -> None:
    path = save_generated_minutes(
        tmp_path,
        topic="A/B:专题会",
        minutes="一、主要内容\n相关部门完成事项。",
    )

    assert path.exists()
    assert "A-B-专题会" in path.name
    assert path.read_text(encoding="utf-8").startswith("一、主要内容")


def test_save_generated_minutes_writes_metadata(tmp_path: Path) -> None:
    path = save_generated_minutes(
        tmp_path,
        topic="测试会",
        minutes="一、主要内容",
        metadata=GenerationMetadata(
            model="test-model",
            topic="测试会",
            selected_tags=["制剂"],
            history_count=1,
            history_examples=[{"id": "history-1", "topic": "历史会", "tags": ["制剂"]}],
            estimated_input_tokens=100,
            token_breakdown={
                "total": 100,
                "system_prompt": 10,
                "instructions": 20,
                "history_examples": 30,
                "current_meeting": 40,
            },
            completion_tokens=50,
        ),
    )
    metadata_path = path.with_suffix(".metadata.json")

    assert metadata_path.exists()
    metadata_text = metadata_path.read_text(encoding="utf-8")
    assert '"model": "test-model"' in metadata_text
    assert '"selected_tags": [' in metadata_text
    assert '"history-1"' in metadata_text
