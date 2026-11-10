from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mini_harness.context import system_prompt
from mini_harness.llm import ModelClient, ModelReply, tool_call_message
from mini_harness.tools.base import ToolRegistry
from mini_harness.trace import TraceWriter


@dataclass
class AgentResult:
    answer: str
    steps: int
    stopped_reason: str
    messages: list[dict[str, Any]] = field(default_factory=list)


class AgentLoop:
    def __init__(
        self,
        *,
        model: ModelClient,
        registry: ToolRegistry,
        trace: TraceWriter | None = None,
        max_steps: int = 8,
        max_tool_output: int = 4000,
        system_extra: str = "",
    ) -> None:
        self.model = model
        self.registry = registry
        self.trace = trace or TraceWriter(None)
        self.max_steps = max_steps
        self.max_tool_output = max_tool_output
        self.system_extra = system_extra

    def run(self, task: str, root: str) -> AgentResult:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt(Path(root), self.system_extra)},
            {"role": "user", "content": task},
        ]
        total_usage: dict[str, int] = {}
        self.trace.record("run_start", task=task, root=root, max_steps=self.max_steps)

        for step in range(1, self.max_steps + 1):
            try:
                reply: ModelReply = self.model.complete(messages, self.registry.specs())
            except Exception as exc:  # noqa: BLE001 - surface model errors as a stopped run
                self.trace.record("model_error", step=step, error=str(exc))
                return AgentResult(str(exc), step, "model_error", messages)

            for key, value in reply.usage.items():
                total_usage[key] = total_usage.get(key, 0) + value
            self.trace.record("model_reply", step=step, content=reply.content, usage=reply.usage)

            if not reply.tool_calls:
                self.trace.record("run_end", steps=step, reason="final", usage=total_usage)
                return AgentResult(reply.content or "", step, "final", messages)

            messages.append(tool_call_message(reply))
            for call in reply.tool_calls:
                output = self.registry.execute(call.name, call.arguments)
                output = output[: self.max_tool_output]
                self.trace.record(
                    "tool_call",
                    step=step,
                    tool=call.name,
                    arguments=call.arguments,
                    output=output,
                )
                messages.append({"role": "tool", "tool_call_id": call.id, "content": output})

        self.trace.record("run_end", steps=self.max_steps, reason="max_steps", usage=total_usage)
        return AgentResult("", self.max_steps, "max_steps", messages)
