from __future__ import annotations

from pathlib import Path

DEFAULT_LIMIT = 6000


def truncate(text: str, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n[truncated, {len(text) - limit} chars omitted]"


def load_agents_md(root: Path, limit: int = DEFAULT_LIMIT) -> str:
    path = root / "AGENTS.md"
    if not path.is_file():
        return ""
    return truncate(path.read_text(encoding="utf-8", errors="replace"), limit)


def system_prompt(root: Path, extra: str = "") -> str:
    base = (
        "Ты терминальный агент для работы с кодом. Отвечай по-русски, кратко.\n"
        "Используй инструменты, чтобы проверить факты, не выдумывай содержимое файлов.\n"
        "Сначала найди файл, потом читай только нужные строки.\n"
        "Не выходи за корень проекта и не запускай опасные команды.\n"
        "В конце ответа перечисли измененные файлы и результат проверки."
    )
    rules = load_agents_md(root)
    if rules:
        base += f"\n\nПравила проекта (AGENTS.md):\n{rules}"
    if extra:
        base += f"\n\n{extra}"
    return base


def compact_messages(
    messages: list[dict[str, object]],
    *,
    max_chars: int = 24_000,
    keep_last: int = 6,
) -> list[dict[str, object]]:
    """Replace old tool output with a short marker when the context grows too large."""
    if sum(len(str(message.get("content", ""))) for message in messages) <= max_chars:
        return messages

    compacted: list[dict[str, object]] = []
    cutoff = max(1, len(messages) - keep_last)
    for index, message in enumerate(messages):
        content = str(message.get("content", ""))
        if index > 0 and index < cutoff and message.get("role") in {"tool", "assistant"}:
            compacted.append({**message, "content": f"[compacted: {len(content)} chars]"})
        else:
            compacted.append(message)
    return compacted


def context_size(messages: list[dict[str, object]]) -> int:
    return sum(len(str(message.get("content", ""))) for message in messages)
