# ctx2doc

[![CI](https://github.com/greenblat17/ctx2doc/actions/workflows/ci.yml/badge.svg)](https://github.com/greenblat17/ctx2doc/actions/workflows/ci.yml)
[![Publish](https://github.com/greenblat17/ctx2doc/actions/workflows/publish.yml/badge.svg)](https://github.com/greenblat17/ctx2doc/actions/workflows/publish.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

`ctx2doc` turns coding-agent sessions into compact Markdown snapshots you can keep in your project and reuse later.

It is built for the annoying moment when a long conversation gets compressed, reset, or moved into a new session and you need the important context back fast.

Supported integrations:

- `Codex CLI`
- `Claude Code`

## Why use it

- Save the current state of a long agent conversation as a portable Markdown file.
- Resume work in a fresh session without manually reconstructing context.
- Keep context in your project docs instead of trapping it inside a single chat UI.
- Use the same workflow across multiple coding agents.

## What you get

Each `ctx2doc snapshot` creates one new Markdown file, by default in:

- `docs/ctx2doc/*.md`

It also manages a small amount of local integration state:

- `.ctx2doc/config.json`
- `.ctx2doc/runtime/claude/*.jsonl` for Claude hook event logs

Snapshots are append-only. Existing snapshots are not overwritten.

## Install

Recommended:

```bash
uv tool install ctx2doc
```

Alternative:

```bash
pipx install ctx2doc
```

Install from source:

```bash
git clone https://github.com/greenblat17/ctx2doc.git
cd ctx2doc
uv tool install .
```

## Quickstart

### Codex

Inside the target project:

```bash
ctx2doc install codex
```

This configures:

- the `ctx2doc` MCP server in Codex
- a project-local Codex skill
- an `AGENTS.md` snippet for `ctx2doc snapshot`, `ctx2doc resume`, and `ctx2doc status`
- local project config in `.ctx2doc/config.json`

Then, inside Codex, use:

```text
ctx2doc snapshot
```

To restore the latest saved context:

```text
ctx2doc resume
```

### Claude Code

Inside the target project:

```bash
ctx2doc install claude
```

This configures:

- `.mcp.json`
- `.claude/settings.json`
- a project-local Claude skill
- hook-based session logging used by `ctx2doc`

Then, inside Claude Code, use:

```text
/ctx2doc snapshot
```

To restore the latest saved context:

```text
/ctx2doc resume
```

## Visual Examples

### Example command flow

```text
ctx2doc snapshot
-> docs/ctx2doc/2026-04-22T13-32-05--019db485.md
```

### Example snapshot shape

```md
# Context Snapshot

- Generated at: `2026-04-22T13:32:05Z`
- Project root: `/path/to/project`
- Source: `codex-cli`
- Source session: `019db485-...`

## Goal
Build a reusable MCP tool that saves portable context snapshots.

## What Was Done
- Captured the current session state.
- Wrote a full Markdown snapshot into the project.

## Decisions
- Keep one file per snapshot.
- Use MCP as the backend integration layer.

## Next Steps
- Resume from this snapshot in a new session.
```

### What the generated artifact is for

The main output is not a dashboard or web UI. The product is the Markdown snapshot itself: a reusable bootstrap context file you can feed back into a new coding-agent session.

## CLI

Core commands:

```bash
ctx2doc snapshot
ctx2doc status
ctx2doc resume
ctx2doc install codex
ctx2doc uninstall codex
ctx2doc install claude
ctx2doc uninstall claude
ctx2doc mcp
```

Useful flags:

- `--project-root /path/to/project`
- `--source auto|codex|claude`
- `--output-dir docs/ctx2doc`
- `--redaction-mode standard|off`

Examples:

```bash
ctx2doc snapshot --source codex
ctx2doc snapshot --output-dir docs/context
ctx2doc resume --project-root /path/to/project
ctx2doc status --source claude
```

## How snapshots work

Each snapshot is a compact working summary rather than a raw transcript.

The generated Markdown includes:

- goal
- what was done
- decisions
- important context
- open risks or unknowns
- next steps

The intent is to produce a file you can feed back into a new agent session, store with project docs, or share with collaborators.

## Privacy and redaction

By default, `ctx2doc` applies basic secret redaction before writing snapshots.

It attempts to redact:

- bearer tokens
- common API key and token assignments
- private key blocks
- common GitHub token formats
- `sk-*` style secrets

If you explicitly want raw output:

```bash
ctx2doc snapshot --redaction-mode off
```

Use that carefully.

## Uninstall

Remove Codex integration:

```bash
ctx2doc uninstall codex
```

Remove Claude Code integration:

```bash
ctx2doc uninstall claude
```

This removes integration glue, not existing snapshots.

## Status

`ctx2doc` is currently an early public release.

The Codex path is the more mature integration today. Claude Code support is implemented and tested through the official MCP/settings/hooks path, but should still be treated as alpha until it has broader real-world validation across Claude Code versions.

## FAQ

### Why not just ask the model to summarize the conversation manually?

Because that is inconsistent and easy to forget. `ctx2doc` turns snapshotting into an explicit tool-driven workflow with stable output paths and repeatable behavior.

### Is this a raw transcript exporter?

No. `ctx2doc` writes compact working summaries, not full chat logs.

### Does `ctx2doc` send my session data to a server?

No. It works from local files and local integrations. Snapshot generation happens locally in your environment.

### Why does Claude support need hooks?

Because `ctx2doc` uses officially supported Claude Code integration points instead of reverse-engineering undocumented Claude internals.

### Does uninstall remove my old snapshots?

No. Uninstall removes the integration glue, not the generated Markdown files.

### Do I need `uv` to use this?

No. `uv` is the recommended install path, but `pipx` works as well.

## Development

Run tests:

```bash
python -m unittest discover -s tests -v
```

Build package artifacts:

```bash
python -m build
```

## Releasing

This repository uses GitHub Actions with PyPI Trusted Publishing.

Typical flow:

1. Publish to TestPyPI via the `publish` workflow.
2. Verify installation from TestPyPI.
3. Push a version tag such as `v0.2.0`.
4. Let the tagged workflow publish to PyPI.

Relevant workflow files:

- `.github/workflows/ci.yml`
- `.github/workflows/publish.yml`

## License

MIT
