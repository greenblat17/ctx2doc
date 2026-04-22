# ctx2doc

`ctx2doc` creates compact, redacted Markdown snapshots from local coding-agent sessions and stores them in your project. It currently supports:

- `Codex CLI` via local Codex session logs
- `Claude Code` via official MCP + hooks + project skill integration

## Install

From PyPI after the first public release:

```bash
uv tool install ctx2doc
```

Or:

```bash
pipx install ctx2doc
```

Until PyPI is live, install from this repository:

```bash
uv tool install .
```

## Quickstart

### Codex

Inside the target project:

```bash
ctx2doc install codex
```

This will:

- register the `ctx2doc` MCP server in Codex
- install a project-local Codex skill
- add a small `AGENTS.md` block with `ctx2doc snapshot`, `ctx2doc resume`, and `ctx2doc status`
- write `.ctx2doc/config.json`

Then use it from Codex:

```text
ctx2doc snapshot
```

### Claude Code

Inside the target project:

```bash
ctx2doc install claude
```

This will:

- create or update `.mcp.json`
- create or update `.claude/settings.json`
- install a project-local Claude skill at `.claude/skills/ctx2doc/SKILL.md`
- enable hook-based logging for Claude sessions

Then use it from Claude Code:

```text
/ctx2doc snapshot
```

## Core commands

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

## What gets written

- Snapshots: `docs/ctx2doc/*.md`
- Project config: `.ctx2doc/config.json`
- Claude runtime event logs: `.ctx2doc/runtime/claude/*.jsonl`

`ctx2doc` writes one full snapshot per invocation. It does not overwrite old snapshots.

## Privacy and redaction

By default, `ctx2doc` redacts common secrets before writing snapshots:

- bearer tokens
- API keys and token-like assignments
- private key blocks
- common GitHub and `sk-*` token formats

Redaction is configurable with `--redaction-mode off` if you explicitly want raw content.

## Uninstall

```bash
ctx2doc uninstall codex
ctx2doc uninstall claude
```

Uninstall removes integration glue. It does not delete your existing snapshots.

## Development

```bash
python -m unittest discover -s tests -v
python -m build
```

## Publishing

This repository includes a GitHub Actions workflow for PyPI Trusted Publishing.

Before the first release:

- create the `ctx2doc` project on TestPyPI and PyPI
- add this GitHub repository as a Trusted Publisher on both services
- publish a tag like `v0.2.0`

The workflow file is at `.github/workflows/publish.yml`.
