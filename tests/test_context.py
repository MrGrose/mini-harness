from pathlib import Path

from mini_harness.context import load_agents_md, system_prompt, truncate


def test_truncate_marks_omitted_text() -> None:
    text = truncate("x" * 100, 10)
    assert text.startswith("x" * 10)
    assert "90 chars omitted" in text


def test_agents_md_is_loaded(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text("Правило: не трогать .env", encoding="utf-8")
    assert "не трогать .env" in load_agents_md(tmp_path)
    assert "не трогать .env" in system_prompt(tmp_path)
