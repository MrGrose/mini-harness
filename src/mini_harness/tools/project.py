
import os
import subprocess
from pathlib import Path

from pydantic import BaseModel, Field

from mini_harness.context import truncate
from mini_harness.policy import CommandPolicy, PolicyError, ProjectPolicy
from mini_harness.tools.base import Tool

MAX_WRITE_BYTES = 200_000
MAX_TIMEOUT = 300


class WriteFileArgs(BaseModel):
    path: str
    content: str


class RunArgs(BaseModel):
    timeout: int = Field(default=120, ge=5, le=MAX_TIMEOUT)


def _write_file(policy: ProjectPolicy, args: WriteFileArgs) -> str:
    content = args.content.encode("utf-8")
    if len(content) > MAX_WRITE_BYTES:
        raise PolicyError(f"content is too large: {len(content)} bytes")
    path = policy.resolve(args.path)
    if path.is_dir():
        raise PolicyError(f"path is a directory: {args.path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(args.content, encoding="utf-8")
    return f"wrote {policy.relative(path)} ({len(content)} bytes)"


def _safe_env() -> dict[str, str]:
    env = {}
    for key, value in os.environ.items():
        lowered = key.lower()
        if any(word in lowered for word in ("key", "token", "secret", "password")):
            continue
        env[key] = value
    return env


def _run(argv: list[str], root: Path, timeout: int) -> str:
    try:
        completed = subprocess.run(
            argv,
            cwd=root,
            env=_safe_env(),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return f"ERROR: command timed out after {timeout} seconds"
    output = (completed.stdout or "") + (completed.stderr or "")
    return truncate(f"exit_code={completed.returncode}\n{output}", 6000)


def build_project_tools(policy: ProjectPolicy) -> list[Tool]:
    command_policy = CommandPolicy()

    def run_tests(args: RunArgs) -> str:
        argv = command_policy.test_command()
        command_policy.check(argv)
        if not any(
            (policy.root / name).exists() for name in ("pyproject.toml", "pytest.ini", "setup.cfg")
        ):
            return "ERROR: no pytest configuration found in the project root"
        return _run(argv, policy.root, args.timeout)

    def run_lint(args: RunArgs) -> str:
        argv = command_policy.lint_command()
        command_policy.check(argv)
        return _run(argv, policy.root, args.timeout)

    return [
        Tool(
            name="write_file",
            description="Write a UTF-8 text file inside the project. Requires user confirmation.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
            handler=lambda args: _write_file(policy, args),
            args_model=WriteFileArgs,
            requires_confirmation=True,
        ),
        Tool(
            name="run_tests",
            description="Run pytest in the project root and return the tail of the output.",
            parameters={
                "type": "object",
                "properties": {
                    "timeout": {"type": "integer", "minimum": 5, "maximum": MAX_TIMEOUT}
                },
            },
            handler=run_tests,
            args_model=RunArgs,
        ),
        Tool(
            name="run_lint",
            description="Run ruff check in the project root and return the output.",
            parameters={
                "type": "object",
                "properties": {
                    "timeout": {"type": "integer", "minimum": 5, "maximum": MAX_TIMEOUT}
                },
            },
            handler=run_lint,
            args_model=RunArgs,
        ),
    ]
