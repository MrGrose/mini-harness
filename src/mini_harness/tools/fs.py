
import re

from pydantic import BaseModel, Field

from mini_harness.context import truncate
from mini_harness.policy import PolicyError, ProjectPolicy
from mini_harness.tools.base import Tool

MAX_FILE_BYTES = 200_000
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache"}
MAX_LIST = 200
MAX_GREP = 100


class ReadFileArgs(BaseModel):
    path: str
    start: int | None = Field(default=None, ge=1)
    end: int | None = Field(default=None, ge=1)


class ListDirArgs(BaseModel):
    path: str = "."


class GrepArgs(BaseModel):
    pattern: str
    path: str = "."
    max_results: int = Field(default=50, ge=1, le=MAX_GREP)


def _read_file(policy: ProjectPolicy, args: ReadFileArgs) -> str:
    path = policy.resolve(args.path, must_exist=True)
    if not path.is_file():
        raise PolicyError(f"not a file: {args.path}")
    if path.stat().st_size > MAX_FILE_BYTES:
        raise PolicyError(f"file is too large: {args.path}")
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    start = (args.start or 1) - 1
    end = args.end if args.end is not None else len(lines)
    selected = lines[start:end]
    numbered = [f"{index + start + 1}: {line}" for index, line in enumerate(selected)]
    header = f"{policy.relative(path)} ({len(lines)} lines)\n"
    return truncate(header + "\n".join(numbered))


def _list_dir(policy: ProjectPolicy, args: ListDirArgs) -> str:
    path = policy.resolve(args.path, must_exist=True)
    if not path.is_dir():
        raise PolicyError(f"not a directory: {args.path}")
    entries = sorted(path.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))
    lines = []
    for entry in entries[:MAX_LIST]:
        if policy.is_denied(entry):
            continue
        lines.append(entry.name + ("/" if entry.is_dir() else ""))
    return truncate("\n".join(lines), 4000)


def _grep(policy: ProjectPolicy, args: GrepArgs) -> str:
    root = policy.resolve(args.path, must_exist=True)
    pattern = re.compile(args.pattern)
    matches: list[str] = []
    files = [root] if root.is_file() else sorted(root.rglob("*"))
    for path in files:
        if len(matches) >= args.max_results:
            break
        if not path.is_file() or any(part in SKIP_DIRS for part in path.parts):
            continue
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
            if policy.is_denied(path):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            if pattern.search(line):
                matches.append(f"{policy.relative(path)}:{number}:{line}")
                if len(matches) >= args.max_results:
                    break
    return truncate("\n".join(matches) if matches else "no matches", 4000)


def build_fs_tools(policy: ProjectPolicy) -> list[Tool]:
    return [
        Tool(
            name="read_file",
            description="Read a text file inside the project, optionally a line range.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "start": {"type": "integer", "minimum": 1},
                    "end": {"type": "integer", "minimum": 1},
                },
                "required": ["path"],
            },
            handler=lambda args: _read_file(policy, args),
            args_model=ReadFileArgs,
        ),
        Tool(
            name="list_dir",
            description="List files and directories inside the project.",
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string", "default": "."}},
            },
            handler=lambda args: _list_dir(policy, args),
            args_model=ListDirArgs,
        ),
        Tool(
            name="grep",
            description="Search a regular expression in project files and return path:line matches.",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "path": {"type": "string", "default": "."},
                    "max_results": {"type": "integer", "minimum": 1, "maximum": MAX_GREP},
                },
                "required": ["pattern"],
            },
            handler=lambda args: _grep(policy, args),
            args_model=GrepArgs,
        ),
    ]
