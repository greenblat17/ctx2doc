from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from ctx2doc.config import load_project_config
from ctx2doc.models import SessionEvent, SessionHandle
from ctx2doc.redaction import redact_text


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def parse_iso8601(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class ClaudeCodeSessionAdapter:
    name = "claude"
    source_label = "claude-code"

    def detect_session(self, project_root: Path) -> SessionHandle | None:
        runtime_dir = self._logs_dir(project_root)
        if not runtime_dir.exists():
            return None

        candidates: list[SessionHandle] = []
        for event_log in sorted(runtime_dir.glob("*.jsonl")):
            records = self._read_records(event_log)
            if not records:
                continue
            session_id = str(records[0].get("session_id") or event_log.stem)
            started_at = parse_iso8601(records[0].get("recorded_at"))
            updated_at = parse_iso8601(records[-1].get("recorded_at"))
            metadata = {
                "model": records[0].get("model"),
                "transcript_path": records[0].get("transcript_path"),
            }
            candidates.append(
                SessionHandle(
                    session_id=session_id,
                    project_root=project_root.resolve(),
                    source=self.source_label,
                    source_path=event_log,
                    started_at=started_at,
                    updated_at=updated_at,
                    metadata=metadata,
                )
            )
        if not candidates:
            return None
        candidates.sort(key=lambda handle: handle.updated_at or handle.started_at or utcnow(), reverse=True)
        return candidates[0]

    def load_events(self, handle: SessionHandle) -> list[SessionEvent]:
        if not handle.source_path:
            return []
        events: list[SessionEvent] = []
        for record in self._read_records(handle.source_path):
            kind = record.get("kind")
            if kind is None:
                continue
            events.append(
                SessionEvent(
                    kind=str(kind),
                    timestamp=parse_iso8601(record.get("recorded_at")),
                    text=str(record.get("text", "")),
                    role=record.get("role"),
                    metadata=record.get("metadata", {}),
                )
            )
        return events

    def _logs_dir(self, project_root: Path) -> Path:
        config = load_project_config(project_root.resolve())
        return config.runtime_path(project_root.resolve()) / "claude"

    def _read_records(self, event_log: Path) -> list[dict]:
        records: list[dict] = []
        try:
            lines = event_log.read_text(encoding="utf-8").splitlines()
        except OSError:
            return records
        for line in lines:
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return records


def log_claude_hook_event(event_name: str, stdin_text: str) -> int:
    if not stdin_text.strip():
        return 0
    try:
        payload = json.loads(stdin_text)
    except json.JSONDecodeError:
        return 0
    cwd = payload.get("cwd") or os.getcwd()
    project_root = Path(cwd).expanduser().resolve()
    session_id = str(payload.get("session_id") or "unknown-session")
    normalized = normalize_hook_payload(event_name, payload)
    if normalized is None:
        return 0
    config = load_project_config(project_root)
    log_dir = config.runtime_path(project_root) / "claude"
    log_dir.mkdir(parents=True, exist_ok=True)
    destination = log_dir / f"{session_id}.jsonl"
    with destination.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(normalized, sort_keys=True) + "\n")
    return 0


def normalize_hook_payload(event_name: str, payload: dict) -> dict | None:
    hook_event = payload.get("hook_event_name") or event_name
    session_id = payload.get("session_id")
    recorded_at = utcnow().isoformat().replace("+00:00", "Z")
    base = {
        "schema_version": 1,
        "session_id": session_id,
        "hook_event_name": hook_event,
        "recorded_at": recorded_at,
        "cwd": payload.get("cwd"),
        "transcript_path": payload.get("transcript_path"),
        "model": payload.get("model"),
    }

    if hook_event == "SessionStart":
        base.update(
            {
                "kind": "session",
                "text": f"Claude session started ({payload.get('source', 'startup')}).",
                "metadata": {"source": payload.get("source"), "model": payload.get("model")},
            }
        )
        return base

    if hook_event == "UserPromptSubmit":
        base.update(
            {
                "kind": "message",
                "role": "user",
                "text": redact_text(str(payload.get("prompt", ""))),
                "metadata": {},
            }
        )
        return base

    if hook_event == "PostToolUse":
        tool_name = str(payload.get("tool_name", "")).strip()
        tool_input = payload.get("tool_input", {}) or {}
        summary = summarize_claude_tool_use(tool_name, tool_input)
        kind = "command" if tool_name == "Bash" else "tool_call"
        base.update(
            {
                "kind": kind,
                "text": summary,
                "metadata": {"tool_name": tool_name},
            }
        )
        return base

    if hook_event == "Stop":
        base.update(
            {
                "kind": "message",
                "role": "assistant",
                "text": redact_text(str(payload.get("last_assistant_message", ""))),
                "metadata": {},
            }
        )
        return base

    if hook_event == "SessionEnd":
        base.update(
            {
                "kind": "session",
                "text": f"Claude session ended ({payload.get('reason', 'other')}).",
                "metadata": {"reason": payload.get("reason")},
            }
        )
        return base

    return None


def summarize_claude_tool_use(tool_name: str, tool_input: dict) -> str:
    if tool_name == "Bash":
        command = tool_input.get("command") or tool_input.get("description") or "shell command"
        return redact_text(str(command))
    if tool_name in {"Read", "Edit", "Write", "MultiEdit"}:
        file_path = tool_input.get("file_path") or tool_input.get("filePath") or "unknown file"
        return f"{tool_name}: {file_path}"
    if tool_name in {"Glob", "Grep"}:
        pattern = tool_input.get("pattern") or tool_input.get("query") or "pattern"
        return f"{tool_name}: {pattern}"
    if tool_name in {"WebFetch", "WebSearch"}:
        target = tool_input.get("url") or tool_input.get("query") or "web request"
        return f"{tool_name}: {redact_text(str(target))}"
    if tool_name.startswith("mcp__"):
        return tool_name
    return tool_name or "tool call"


def read_stdin_text() -> str:
    return sys.stdin.read()
