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
