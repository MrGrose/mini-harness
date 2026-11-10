# mini-harness

A small, readable agent harness: the loop, tool registry, path policy, JSONL
trace and tests that turn a chat model into a coding agent.

This is a learning and portfolio project, not a production framework.

## What it does

```bash
mini-harness run "найди, где определяется класс Car" --root ./examples/buggy
```

The agent can list directories, search with a regular expression and read text
files. Every step is written to a trace when `--trace` is passed:

```bash
mini-harness run "почему падает тест discount" \
  --root ./examples/buggy \
  --trace traces/run.jsonl
```

## Install

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

Set `MINI_HARNESS_API_KEY` and optionally `MINI_HARNESS_BASE_URL` and
`MINI_HARNESS_MODEL`. Any OpenAI-compatible endpoint works.

## Architecture

```
task -> CLI -> AgentLoop -> model -> tool calls
                       |
                       v
                 ToolRegistry -> ProjectPolicy
                       |
                       v
             read_file / list_dir / grep
```

The loop stops when the model returns a message without tool calls or when it
reaches `--max-steps`. Tool errors are returned to the model as text instead of
crashing the run.

## Safety

- All paths are resolved and must stay inside `--root`.
- `.env`, `.git`, private keys and files above 200 KB are refused.
- Tool output is truncated before it goes back into the context.
- API keys are read from the environment and never written to the trace.

## Tests

```bash
pytest -q
ruff check src tests
```

The tests use a scripted fake model and do not call the network.

## Status

Stage 1: read-only tools, the loop, policy and tracing. Writing files, running
tests, context compaction and the eval set are next. See the spec at
`~/Hermes/notes/spec-mini-harness.md`.

## License

MIT.
