from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from ctx2doc.config import AppConfig, DEFAULT_OUTPUT_DIR, save_project_config
from ctx2doc.models import InstallResult


class InstallError(RuntimeError):
    pass


CTX2DOC_MARKER_START = "<!-- ctx2doc:start -->"
CTX2DOC_MARKER_END = "<!-- ctx2doc:end -->"
AGENTS_SNIPPET = (
    f"{CTX2DOC_MARKER_START}\n"
    "If the user writes `ctx2doc snapshot`, call the `ctx2doc.snapshot` MCP tool.\n"
    "If the user writes `ctx2doc resume`, call the `ctx2doc.resume_context` MCP tool.\n"
    "If the user writes `ctx2doc status`, call the `ctx2doc.status` MCP tool.\n"
    f"{CTX2DOC_MARKER_END}\n"
)

CODEX_SKILL = """---
name: ctx2doc
description: Use this skill when the user wants to create, refresh, inspect, or reuse `ctx2doc` context snapshots for the current project in Codex. This skill routes requests like `ctx2doc snapshot`, `ctx2doc resume`, or `ctx2doc status` to the matching `ctx2doc` MCP tool instead of manually summarizing the session.
metadata:
  short-description: Create or load ctx2doc snapshots
---

# ctx2doc skill

This skill is a thin orchestration layer over the `ctx2doc` MCP server. Do not reimplement snapshot logic in the model. Use the matching MCP tool.

## Trigger mapping

- If the user asks for `ctx2doc snapshot`, call `ctx2doc.snapshot`.
- If the user asks for `ctx2doc resume`, call `ctx2doc.resume_context`.
- If the user asks for `ctx2doc status`, call `ctx2doc.status`.
"""

CODEX_SKILL_UI = """interface:
  display_name: "ctx2doc"
  short_description: "Create, inspect, and reuse ctx2doc project snapshots"
  default_prompt: "Use $ctx2doc to create or load a ctx2doc snapshot for the current project."
"""

CLAUDE_SKILL = """---
name: ctx2doc
description: Create, inspect, or load ctx2doc project snapshots. Use for `/ctx2doc snapshot`, `/ctx2doc resume`, or `/ctx2doc status`.
disable-model-invocation: true
argument-hint: <snapshot|resume|status>
arguments:
  - action
---

Route to the matching ctx2doc MCP tool.

- If `$action` is `snapshot`, call `mcp__ctx2doc__snapshot`.
- If `$action` is `resume`, call `mcp__ctx2doc__resume_context`.
- If `$action` is `status`, call `mcp__ctx2doc__status`.

If the action is omitted, treat it as `snapshot`.
"""

CLAUDE_HOOK_EVENTS = [
    "SessionStart",
    "UserPromptSubmit",
    "PostToolUse",
    "Stop",
    "SessionEnd",
]


def install_codex(project_root: Path, output_dir: str | None = None) -> InstallResult:
    project_root = project_root.resolve()
    _ensure_binary("codex")
    details: list[str] = []
    configured_servers = _codex_mcp_servers()
    if "ctx2doc" not in configured_servers:
        _run_command(["codex", "mcp", "add", "ctx2doc", "--", "ctx2doc", "mcp"])
        details.append("Registered ctx2doc MCP server in Codex.")
    else:
        details.append("Codex MCP server already registered.")

    _write_file(project_root / ".codex" / "skills" / "ctx2doc" / "SKILL.md", CODEX_SKILL)
    _write_file(project_root / ".codex" / "skills" / "ctx2doc" / "agents" / "openai.yaml", CODEX_SKILL_UI)
    details.append("Installed project-local Codex skill.")

    agents_path = project_root / "AGENTS.md"
    _upsert_marked_block(agents_path, AGENTS_SNIPPET)
    details.append("Updated AGENTS.md with ctx2doc triggers.")

    config = AppConfig(output_dir=output_dir or DEFAULT_OUTPUT_DIR)
    config_path = save_project_config(project_root, config)
    details.append(f"Saved project config at {config_path}.")
    return InstallResult(target="codex", project_root=project_root, details=details)


def uninstall_codex(project_root: Path) -> InstallResult:
    project_root = project_root.resolve()
    details: list[str] = []
    if shutil.which("codex"):
        configured_servers = _codex_mcp_servers()
        if "ctx2doc" in configured_servers:
            _run_command(["codex", "mcp", "remove", "ctx2doc"])
            details.append("Removed ctx2doc MCP server from Codex.")

    _remove_path(project_root / ".codex" / "skills" / "ctx2doc")
    _remove_marked_block(project_root / "AGENTS.md")
    details.append("Removed project-local Codex skill and AGENTS snippet.")
    return InstallResult(target="codex", project_root=project_root, details=details)


def install_claude(project_root: Path, output_dir: str | None = None) -> InstallResult:
    project_root = project_root.resolve()
    details: list[str] = []

    mcp_path = project_root / ".mcp.json"
    mcp_payload = _load_json_file(mcp_path, default={"mcpServers": {}})
    mcp_payload.setdefault("mcpServers", {})
    mcp_payload["mcpServers"]["ctx2doc"] = {"command": "ctx2doc", "args": ["mcp"]}
    _write_json_file(mcp_path, mcp_payload)
    details.append("Updated .mcp.json with the ctx2doc MCP server.")

    settings_path = project_root / ".claude" / "settings.json"
    settings_payload = _load_json_file(settings_path, default={})
    enabled_servers = settings_payload.get("enabledMcpjsonServers", [])
    if "ctx2doc" not in enabled_servers:
        enabled_servers.append("ctx2doc")
    settings_payload["enabledMcpjsonServers"] = enabled_servers
    hooks_payload = settings_payload.setdefault("hooks", {})
    for event_name in CLAUDE_HOOK_EVENTS:
        hooks_payload[event_name] = _merge_claude_hook_entries(hooks_payload.get(event_name, []), event_name)
    _write_json_file(settings_path, settings_payload)
    details.append("Updated .claude/settings.json with ctx2doc hook logging.")

    _write_file(project_root / ".claude" / "skills" / "ctx2doc" / "SKILL.md", CLAUDE_SKILL)
    details.append("Installed project-local Claude skill.")

    config = AppConfig(output_dir=output_dir or DEFAULT_OUTPUT_DIR)
    config_path = save_project_config(project_root, config)
    details.append(f"Saved project config at {config_path}.")
    return InstallResult(target="claude", project_root=project_root, details=details)


def uninstall_claude(project_root: Path) -> InstallResult:
    project_root = project_root.resolve()
    details: list[str] = []

    mcp_path = project_root / ".mcp.json"
    mcp_payload = _load_json_file(mcp_path, default={"mcpServers": {}})
    if isinstance(mcp_payload.get("mcpServers"), dict):
        mcp_payload["mcpServers"].pop("ctx2doc", None)
        _write_json_file(mcp_path, mcp_payload)
    details.append("Removed ctx2doc MCP entry from .mcp.json.")

    settings_path = project_root / ".claude" / "settings.json"
    settings_payload = _load_json_file(settings_path, default={})
    enabled_servers = [server for server in settings_payload.get("enabledMcpjsonServers", []) if server != "ctx2doc"]
    if enabled_servers:
        settings_payload["enabledMcpjsonServers"] = enabled_servers
    else:
        settings_payload.pop("enabledMcpjsonServers", None)
    hooks_payload = settings_payload.get("hooks", {})
    for event_name in list(hooks_payload.keys()):
        filtered = _remove_ctx2doc_hook_entries(hooks_payload.get(event_name, []))
        if filtered:
            hooks_payload[event_name] = filtered
        else:
            hooks_payload.pop(event_name, None)
    if hooks_payload:
        settings_payload["hooks"] = hooks_payload
    else:
        settings_payload.pop("hooks", None)
    _write_json_file(settings_path, settings_payload)
    details.append("Removed ctx2doc hook configuration from .claude/settings.json.")

    _remove_path(project_root / ".claude" / "skills" / "ctx2doc")
    details.append("Removed project-local Claude skill.")
    return InstallResult(target="claude", project_root=project_root, details=details)


def _codex_mcp_servers() -> set[str]:
    result = _run_command(["codex", "mcp", "list", "--json"])
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return set()
    if isinstance(payload, list):
        return {str(item.get("name")) for item in payload if isinstance(item, dict)}
    if isinstance(payload, dict):
        return set(payload.keys())
    return set()


def _ensure_binary(name: str) -> None:
    if not shutil.which(name):
        raise InstallError(f"Required binary not found on PATH: {name}")


def _run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        raise InstallError(exc.stderr.strip() or exc.stdout.strip() or f"Command failed: {' '.join(command)}") from exc


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def _load_json_file(path: Path, default: dict) -> dict:
    if not path.exists():
        return json.loads(json.dumps(default))
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return json.loads(json.dumps(default))


def _write_json_file(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _upsert_marked_block(path: Path, block: str) -> None:
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    cleaned = _strip_marked_block(existing)
    new_content = cleaned.rstrip()
    if new_content:
        new_content += "\n\n"
    new_content += block
    path.write_text(new_content, encoding="utf-8")


def _remove_marked_block(path: Path) -> None:
    if not path.exists():
        return
    cleaned = _strip_marked_block(path.read_text(encoding="utf-8")).rstrip() + "\n"
    path.write_text(cleaned, encoding="utf-8")


def _strip_marked_block(content: str) -> str:
    if CTX2DOC_MARKER_START not in content:
        return content
    start = content.index(CTX2DOC_MARKER_START)
    end = content.index(CTX2DOC_MARKER_END) + len(CTX2DOC_MARKER_END)
    return (content[:start] + content[end:]).strip()


def _merge_claude_hook_entries(existing: list, event_name: str) -> list:
    command = f"ctx2doc claude-hook {event_name}"
    filtered = _remove_ctx2doc_hook_entries(existing)
    filtered.append({"hooks": [{"type": "command", "command": command}]})
    return filtered


def _remove_ctx2doc_hook_entries(existing: list) -> list:
    filtered: list = []
    for entry in existing or []:
        hooks = entry.get("hooks", []) if isinstance(entry, dict) else []
        remaining_hooks = [
            hook
            for hook in hooks
            if not (isinstance(hook, dict) and str(hook.get("command", "")).startswith("ctx2doc claude-hook "))
        ]
        if remaining_hooks:
            updated_entry = dict(entry)
            updated_entry["hooks"] = remaining_hooks
            filtered.append(updated_entry)
    return filtered


def _remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
    elif path.exists():
        path.unlink(missing_ok=True)
