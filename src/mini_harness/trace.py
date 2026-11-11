
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SENSITIVE_KEYS = {"authorization", "password", "secret", "api_key", "token"}


def _is_sensitive(key: str) -> bool:
    lowered = key.lower()
    if lowered in SENSITIVE_KEYS:
        return True
    return lowered.endswith(("_key", "-key", "_secret", "_password", "_token"))


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if _is_sensitive(str(key)):
                result[key] = "[REDACTED]"
            else:
                result[key] = _redact(item)
        return result
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


class TraceWriter:
    def __init__(self, path: str | Path | None) -> None:
        self.path = Path(path).expanduser() if path else None
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text("", encoding="utf-8")

    def record(self, event: str, **fields: Any) -> None:
        payload = {
            "ts": datetime.now(tz=UTC).isoformat(),
            "event": event,
            **_redact(fields),
        }
        line = json.dumps(payload, ensure_ascii=False, default=str)
        if self.path is None:
            return
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    def close(self) -> None:
        return None
