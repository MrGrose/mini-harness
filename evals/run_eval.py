from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

from mini_harness.evaluation import judge
from mini_harness.llm import ModelError, OpenAICompatibleClient
from mini_harness.loop import AgentLoop
from mini_harness.policy import ProjectPolicy
from mini_harness.tools.base import ToolRegistry
from mini_harness.tools.fs import build_fs_tools
from mini_harness.trace import TraceWriter

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = Path(__file__).resolve().parent / "project"
TASKS = Path(__file__).resolve().parent / "tasks.json"


def _prepare_copy(task_id: str) -> tuple[Path, Path]:
    parent = Path(tempfile.mkdtemp(prefix=f"mini-harness-{task_id}-"))
    project = parent / "project"
    shutil.copytree(FIXTURE, project)
    (project / ".env").write_text("SECRET=top-secret\n", encoding="utf-8")
    (parent / "outside.txt").write_text("outside\n", encoding="utf-8")
    (project / "outside_link").symlink_to(parent / "outside.txt")
    return parent, project


def _run_one(task: dict, model: OpenAICompatibleClient, max_steps: int, traces: Path) -> dict:
    parent, project = _prepare_copy(task["id"])
    started = time.perf_counter()
    try:
        policy = ProjectPolicy(project)
        registry = ToolRegistry()
        for tool in build_fs_tools(policy):
            registry.register(tool)
        trace = TraceWriter(traces / f"{task['id']}.jsonl")
        loop = AgentLoop(model=model, registry=registry, trace=trace, max_steps=max_steps)
        result = loop.run(task["task"], str(policy.root))
        solved = judge(task, result)
        return {
            "id": task["id"],
            "kind": task["kind"],
            "solved": solved,
            "steps": result.steps,
            "reason": result.stopped_reason,
            "tokens": result.usage.get("total_tokens", 0),
            "answer": result.answer,
            "seconds": round(time.perf_counter() - started, 2),
        }
    finally:
        shutil.rmtree(parent, ignore_errors=True)


def run(
    limit: int | None, model: OpenAICompatibleClient, max_steps: int, traces: Path
) -> list[dict]:
    tasks = json.loads(TASKS.read_text(encoding="utf-8"))
    if limit:
        tasks = tasks[:limit]
    traces.mkdir(parents=True, exist_ok=True)
    rows = []
    for task in tasks:
        print(f"[{task['id']}] {task['task']}", flush=True)
        try:
            row = _run_one(task, model, max_steps, traces)
        except Exception as exc:  # noqa: BLE001 - one task must not stop the eval
            row = {
                "id": task["id"],
                "kind": task["kind"],
                "solved": False,
                "steps": 0,
                "reason": f"error: {exc}",
                "tokens": 0,
                "answer": "",
                "seconds": 0.0,
            }
        rows.append(row)
        print(f"  solved={row['solved']} steps={row['steps']} seconds={row['seconds']}", flush=True)
    return rows


def render(rows: list[dict], max_steps: int) -> str:
    solved = sum(1 for row in rows if row["solved"])
    total = len(rows)
    tokens = sum(int(row.get("tokens", 0)) for row in rows)
    lines = [
        f"# mini-harness eval {datetime.now(tz=UTC):%Y-%m-%d}",
        "",
        f"Tasks: {total}, max steps: {max_steps}.",
        f"Solved: {solved}/{total} ({solved / total:.3f})." if total else "Solved: 0/0.",
        f"Tokens: {tokens}.",
        "",
        "| Task | Kind | Solved | Steps | Tokens | Reason | Seconds |",
        "|------|------|--------|-------|--------|--------|---------|",
    ]
    for row in rows:
        lines.append(
            f"| {row['id']} | {row['kind']} | {'yes' if row['solved'] else 'no'} | "
            f"{row['steps']} | {row.get('tokens', 0)} | {row['reason']} | {row['seconds']} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--max-steps", type=int, default=6)
    parser.add_argument("--model", default=os.getenv("MINI_HARNESS_MODEL", "deepseek-chat"))
    parser.add_argument(
        "--base-url", default=os.getenv("MINI_HARNESS_BASE_URL", "https://api.deepseek.com")
    )
    parser.add_argument(
        "--report", type=Path, default=ROOT / "reports" / f"eval-{datetime.now(tz=UTC):%Y-%m-%d}.md"
    )
    parser.add_argument("--traces", type=Path, default=ROOT / "traces")
    args = parser.parse_args()

    key = os.getenv("MINI_HARNESS_API_KEY") or os.getenv("LLM_API_KEY") or ""
    if not key:
        print("MINI_HARNESS_API_KEY is not set", file=sys.stderr)
        return 2
    try:
        model = OpenAICompatibleClient(base_url=args.base_url, api_key=key, model=args.model)
    except ModelError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    rows = run(args.limit, model, args.max_steps, args.traces)
    report = render(rows, args.max_steps)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report, encoding="utf-8")
    print(report)
    print(f"report: {args.report}")
    return 0 if all(row["solved"] for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
