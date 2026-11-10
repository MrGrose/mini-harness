from dataclasses import dataclass
from pathlib import Path

from mini_harness.llm import ModelReply, ToolCall
from mini_harness.loop import AgentLoop
from mini_harness.policy import ProjectPolicy
from mini_harness.tools.base import ToolRegistry
from mini_harness.tools.fs import build_fs_tools
from mini_harness.trace import TraceWriter


@dataclass
class FakeModel:
    replies: list[ModelReply]

    def complete(self, messages, tools):
        return self.replies.pop(0)


def _loop(tmp_path: Path, replies: list[ModelReply], trace_path: Path | None = None, max_steps=8):
    (tmp_path / "src").mkdir(exist_ok=True)
    (tmp_path / "src" / "app.py").write_text("VALUE = 42\n", encoding="utf-8")
    policy = ProjectPolicy(tmp_path)
    registry = ToolRegistry()
    for tool in build_fs_tools(policy):
        registry.register(tool)
    return AgentLoop(
        model=FakeModel(replies),
        registry=registry,
        trace=TraceWriter(trace_path),
        max_steps=max_steps,
    )


def test_loop_executes_tool_and_returns_answer(tmp_path: Path) -> None:
    trace = tmp_path / "trace.jsonl"
    loop = _loop(
        tmp_path,
        [
            ModelReply(
                content=None,
                tool_calls=[ToolCall("call-1", "read_file", '{"path": "src/app.py"}')],
            ),
            ModelReply(content="Файл src/app.py содержит VALUE = 42."),
        ],
        trace_path=trace,
    )
    result = loop.run("найди VALUE", str(tmp_path))
    assert result.answer == "Файл src/app.py содержит VALUE = 42."
    assert result.stopped_reason == "final"
    assert result.steps == 2
    assert any(message["role"] == "tool" for message in result.messages)
    assert "tool_call" in trace.read_text(encoding="utf-8")


def test_loop_stops_on_max_steps(tmp_path: Path) -> None:
    call = ModelReply(
        content=None,
        tool_calls=[ToolCall("call-1", "read_file", '{"path": "src/app.py"}')],
    )
    loop = _loop(tmp_path, [call, call, call], max_steps=2)
    result = loop.run("читай", str(tmp_path))
    assert result.stopped_reason == "max_steps"
    assert result.steps == 2
