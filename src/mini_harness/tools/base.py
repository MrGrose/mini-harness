
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[[Any], str]
    args_model: type
    requires_confirmation: bool = False

    def spec(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    def __init__(self, confirm: Callable[[Tool, dict[str, Any]], bool] | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        self._confirm = confirm

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"duplicate tool: {tool.name}")
        self._tools[tool.name] = tool

    def specs(self) -> list[dict[str, Any]]:
        return [tool.spec() for tool in self._tools.values()]

    def execute(self, name: str, arguments: str | dict[str, Any]) -> str:
        tool = self._tools.get(name)
        if tool is None:
            return f"ERROR: unknown tool {name!r}"
        try:
            raw = json.loads(arguments) if isinstance(arguments, str) else arguments
            args = tool.args_model.model_validate(raw)
        except (json.JSONDecodeError, ValidationError) as exc:
            return f"ERROR: invalid arguments for {name}: {exc}"
        if tool.requires_confirmation:
            approved = (
                self._confirm(tool, args.model_dump()) if self._confirm is not None else False
            )
            if not approved:
                return f"DENIED: confirmation required for {name}"
        try:
            return tool.handler(args)
        except Exception as exc:  # noqa: BLE001 - tool errors are data for the model
            return f"ERROR: {type(exc).__name__}: {exc}"
