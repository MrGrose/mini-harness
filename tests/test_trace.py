import json
from pathlib import Path

from mini_harness.trace import TraceWriter


def test_trace_keeps_usage_and_redacts_secrets(tmp_path: Path) -> None:
    path = tmp_path / "trace.jsonl"
    trace = TraceWriter(path)
    trace.record(
        "model_reply",
        usage={"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
        api_key="sk-secret",
        access_token="token-value",
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["usage"]["prompt_tokens"] == 10
    assert payload["usage"]["total_tokens"] == 12
    assert payload["api_key"] == "[REDACTED]"
    assert payload["access_token"] == "[REDACTED]"
