from pathlib import Path

import pytest

from mini_harness.policy import ProjectPolicy
from mini_harness.tools.base import ToolRegistry
from mini_harness.tools.fs import build_fs_tools


@pytest.fixture()
def registry(tmp_path: Path) -> ToolRegistry:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text(
        "class Calculator:\n    def discount(self):\n        return 0.9\n",
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text("SECRET=1\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("demo\n", encoding="utf-8")
    policy = ProjectPolicy(tmp_path)
    result = ToolRegistry()
    for tool in build_fs_tools(policy):
        result.register(tool)
    return result


def test_read_file_with_line_numbers(registry: ToolRegistry) -> None:
    output = registry.execute("read_file", '{"path": "src/app.py"}')
    assert "1: class Calculator:" in output
    assert "3:         return 0.9" in output


def test_read_file_range(registry: ToolRegistry) -> None:
    output = registry.execute("read_file", '{"path": "src/app.py", "start": 2, "end": 2}')
    assert "2:     def discount" in output
    assert "class Calculator" not in output


def test_list_dir_and_grep(registry: ToolRegistry) -> None:
    listing = registry.execute("list_dir", "{}")
    assert "src/" in listing
    found = registry.execute("grep", '{"pattern": "class ", "path": "."}')
    assert "src/app.py:1:class Calculator" in found


def test_path_escape_is_denied(registry: ToolRegistry) -> None:
    output = registry.execute("read_file", '{"path": "../../../etc/passwd"}')
    assert output.startswith("ERROR:")
    assert "escapes project root" in output


def test_sensitive_file_is_denied(registry: ToolRegistry) -> None:
    output = registry.execute("read_file", '{"path": ".env"}')
    assert output.startswith("ERROR:")
    assert "denied by policy" in output


def test_invalid_arguments_do_not_crash(registry: ToolRegistry) -> None:
    output = registry.execute("read_file", '{"start": 2}')
    assert output.startswith("ERROR: invalid arguments")
