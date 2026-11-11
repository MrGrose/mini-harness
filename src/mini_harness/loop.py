
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mini_harness.context import compact_messages, context_size, system_prompt
from mini_harness.llm import ModelClient, ModelReply, tool_call_message
from mini_harness.tools.base import ToolRegistry
from mini_harness.trace import TraceWriter


@dataclass
class AgentResult:
    answer: str
    steps: int
    stopped_reason: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)


class AgentLoop:
    def __init__(
        self,
        *,
        model: ModelClient,
        registry: ToolRegistry,
        trace: TraceWriter | None = None,
        max_steps: int = 8,
        max_tool_output: int = 4000,
        max_context_chars: int = 24_000,
        system_extra: str = "",
    ) -> None:
        self.model = model
        self.registry = registry
        self.trace = trace or TraceWriter(None)
        self.max_steps = max_steps
        self.max_tool_output = max_tool_output
        self.max_context_chars = max_context_chars
        self.system_extra = system_extra

    def run(self, task: str, root: str) -> AgentResult:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt(Path(root), self.system_extra)},
            {"role": "user", "content": task},
        ]
        total_usage: dict[str, int] = {}
        self.trace.record("run_start", task=task, root=root, max_steps=self.max_steps)

        for step in range(1, self.max_steps + 1):
            before = context_size(messages)
            messages = compact_messages(messages, max_chars=self.max_context_chars)
            if context_size(messages) != before:
                self.trace.record(
                    "context_compacted",
                    step=step,
                    before=before,
                    after=context_size(messages),
                )
            try:
                reply: ModelReply = self.model.complete(messages, self.registry.specs())
            except Exception as exc:  # noqa: BLE001 - surface model errors as a stopped run
                self.trace.record("model_error", step=step, error=str(exc))
                return AgentResult(str(exc), step, "model_error", messages, total_usage)

            for key, value in reply.usage.items():
                total_usage[key] = total_usage.get(key, 0) + value
            self.trace.record("model_reply", step=step, content=reply.content, usage=reply.usage)

            if not reply.tool_calls:
                self.trace.record("run_end", steps=step, reason="final", usage=total_usage)
                return AgentResult(reply.content or "", step, "final", messages, total_usage)

            messages.append(tool_call_message(reply))
            for call in reply.tool_calls:
                output = self.registry.execute(call.name, call.arguments)
                output = output[: self.max_tool_output]
                self.trace.record(
                    "tool_call",
                    step=step,
                    tool=call.name,
                    arguments=call.arguments,
                    output_preview=output[:300],
                    output_len=len(output),
                )
                messages.append({"role": "tool", "tool_call_id": call.id, "content": output})

        self.trace.record("run_end", steps=self.max_steps, reason="max_steps", usage=total_usage)
        return AgentResult("", self.max_steps, "max_steps", messages, total_usage)
