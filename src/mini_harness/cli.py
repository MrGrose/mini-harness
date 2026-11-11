
import argparse
import os
import sys
from pathlib import Path

from mini_harness import __version__
from mini_harness.llm import ModelError, OpenAICompatibleClient
from mini_harness.loop import AgentLoop
from mini_harness.policy import PolicyError, ProjectPolicy
from mini_harness.tools.base import ToolRegistry
from mini_harness.tools.fs import build_fs_tools
from mini_harness.tools.project import build_project_tools
from mini_harness.trace import TraceWriter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mini-harness", description="A small agent harness.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command")
    run = sub.add_parser("run", help="run an agent task against a project")
    run.add_argument("task", help="task in natural language")
    run.add_argument("--root", default=".", help="project root (default: current directory)")
    run.add_argument("--max-steps", type=int, default=int(os.getenv("MINI_HARNESS_MAX_STEPS", "8")))
    run.add_argument("--trace", default=None, help="path to a JSONL trace file")
    run.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="approve write_file without an interactive prompt",
    )
    run.add_argument(
        "--max-context-chars",
        type=int,
        default=24_000,
        help="compact old tool output above this size",
    )
    run.add_argument("--model", default=os.getenv("MINI_HARNESS_MODEL", "deepseek-chat"))
    run.add_argument(
        "--base-url",
        default=os.getenv("MINI_HARNESS_BASE_URL", "https://api.deepseek.com"),
    )
    run.add_argument(
        "--temperature",
        type=float,
        default=float(os.getenv("MINI_HARNESS_TEMPERATURE", "0")),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command != "run":
        parser.print_help()
        return 0

    api_key = os.getenv("MINI_HARNESS_API_KEY") or os.getenv("LLM_API_KEY") or ""
    if not api_key:
        print("MINI_HARNESS_API_KEY is not set", file=sys.stderr)
        return 2

    try:
        policy = ProjectPolicy(args.root)
    except PolicyError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    trace = TraceWriter(args.trace)
    try:
        model = OpenAICompatibleClient(
            base_url=args.base_url,
            api_key=api_key,
            model=args.model,
            temperature=args.temperature,
        )
    except ModelError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    def confirm(tool, tool_args: dict[str, object]) -> bool:
        if args.yes:
            return True
        if not sys.stdin.isatty():
            print(f"DENIED {tool.name}: use --yes in non-interactive mode", file=sys.stderr)
            return False
        target = tool_args.get("path", "")
        print(f"\nАгент хочет выполнить {tool.name}: {target}")
        answer = input("Разрешить? [y/N] ").strip().lower()
        return answer in {"y", "yes", "да"}

    registry = ToolRegistry(confirm=confirm)
    for tool in [*build_fs_tools(policy), *build_project_tools(policy)]:
        registry.register(tool)
    loop = AgentLoop(
        model=model,
        registry=registry,
        trace=trace,
        max_steps=args.max_steps,
        max_context_chars=args.max_context_chars,
    )
    result = loop.run(args.task, str(policy.root))

    if result.stopped_reason == "final":
        print(result.answer)
    else:
        print(f"stopped: {result.stopped_reason} after {result.steps} steps", file=sys.stderr)
    if args.trace:
        print(f"trace: {Path(args.trace)}", file=sys.stderr)
    return 0 if result.stopped_reason == "final" else 1
