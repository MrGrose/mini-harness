
import json
import time
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: str


@dataclass
class ModelReply:
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)


class ModelClient(Protocol):
    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> ModelReply:
        ...


class ModelError(RuntimeError):
    pass


class OpenAICompatibleClient:

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        temperature: float = 0.0,
        timeout: float = 60.0,
        max_retries: int = 3,
    ) -> None:
        if not api_key:
            raise ModelError("LLM API key is empty")
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - dependency is declared
            raise ModelError("openai package is not installed") from exc

        self._client = OpenAI(base_url=base_url, api_key=api_key, timeout=timeout, max_retries=0)
        self._model = model
        self._temperature = temperature
        self._max_retries = max_retries

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> ModelReply:
        from openai import APIConnectionError, APIStatusError, RateLimitError

        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    tools=tools or None,
                    temperature=self._temperature,
                )
                message = response.choices[0].message
                calls = [
                    ToolCall(
                        id=call.id,
                        name=call.function.name,
                        arguments=call.function.arguments or "{}",
                    )
                    for call in (message.tool_calls or [])
                ]
                usage = {}
                if response.usage is not None:
                    usage = {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens,
                    }
                return ModelReply(content=message.content, tool_calls=calls, usage=usage)
            except (RateLimitError, APIConnectionError) as exc:
                last_error = exc
            except APIStatusError as exc:
                last_error = exc
                if exc.status_code < 500:
                    break
            if attempt < self._max_retries:
                time.sleep(2**attempt)
        raise ModelError(f"model request failed: {last_error}")


def tool_call_message(reply: ModelReply) -> dict[str, Any]:
    message: dict[str, Any] = {"role": "assistant", "content": reply.content or ""}
    if reply.tool_calls:
        message["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.name, "arguments": call.arguments},
            }
            for call in reply.tool_calls
        ]
    return message


def parse_arguments(raw: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}
