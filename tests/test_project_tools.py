from pathlib import Path

import pytest

from mini_harness.policy import CommandPolicy, PolicyError, ProjectPolicy
from mini_harness.tools.base import ToolRegistry
from mini_harness.tools.project import build_project_tools


def _registry(tmp_path: Path, approve: bool = True) -> ToolRegistry:
    policy = ProjectPolicy(tmp_path)
    registry = ToolRegistry(confirm=lambda _tool, _args: approve)
    for tool in build_project_tools(policy):
        registry.register(tool)
    return registry


def test_write_file_requires_confirmation(tmp_path: Path) -> None:
    registry = _registry(tmp_path, approve=False)
    output = registry.execute("write_file", '{"path": "new.txt", "content": "hello"}')
    assert output == "DENIED: confirmation required for write_file"
    assert not (tmp_path / "new.txt").exists()


def test_write_file_writes_inside_root(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    output = registry.execute("write_file", '{"path": "src/new.txt", "content": "hello"}')
    assert "wrote src/new.txt" in output
    assert (tmp_path / "src" / "new.txt").read_text() == "hello"


def test_write_file_cannot_escape_root(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    output = registry.execute("write_file", '{"path": "../escape.txt", "content": "x"}')
    assert output.startswith("ERROR:")
    assert "escapes project root" in output


def test_run_tests_reports_exit_code(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[tool.pytest.ini_options]\n", encoding="utf-8")
    (tmp_path / "test_ok.py").write_text(
        "def test_ok():\n    assert 1 + 1 == 2\n", encoding="utf-8"
    )
    registry = _registry(tmp_path)
    output = registry.execute("run_tests", '{"timeout": 30}')
    assert "exit_code=0" in output


def test_command_policy_blocks_dangerous_commands() -> None:
    policy = CommandPolicy()
    with pytest.raises(PolicyError):
        policy.check(["rm", "-rf", "/"])
    with pytest.raises(PolicyError):
        policy.check(["bash", "-c", "echo hi"])
    with pytest.raises(PolicyError):
        policy.check(["python", "-c", "print(1); import os"])
    policy.check(policy.test_command())
