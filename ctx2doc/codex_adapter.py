from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from ctx2doc.models import SessionEvent, SessionHandle


def parse_iso8601(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


class CodexSessionAdapter:
    name = "codex"
    source_label = "codex-cli"
    EXCLUDED_TOOL_NAMES = {
        "apply_patch",
        "exec_command",
        "request_user_input",
        "resume_agent",
        "send_input",
        "spawn_agent",
        "update_plan",
        "view_image",
        "wait_agent",
        "write_stdin",
    }

    def __init__(self, codex_home: Path | None = None) -> None:
        env_home = os.environ.get("CTX2DOC_CODEX_HOME")
        self.codex_home = Path(env_home).expanduser() if env_home else (
            codex_home.expanduser() if codex_home else Path.home() / ".codex"
        )
        self.sessions_root = self.codex_home / "sessions"

    def detect_session(self, project_root: Path) -> SessionHandle | None:
        project_root = project_root.resolve()
        candidates: list[tuple[datetime, SessionHandle]] = []
        if not self.sessions_root.exists():
            return None

        for rollout_path in sorted(self.sessions_root.rglob("*.jsonl"), reverse=True):
            session_meta = self._load_session_meta(rollout_path)
            if not session_meta:
                continue
            payload = session_meta["payload"]
            cwd = payload.get("cwd")
            if not cwd:
                continue
            try:
                cwd_path = Path(cwd).expanduser().resolve()
            except FileNotFoundError:
                cwd_path = Path(cwd).expanduser()
            if cwd_path != project_root:
                continue
            started_at = parse_iso8601(payload.get("timestamp"))
            updated_at = datetime.fromtimestamp(rollout_path.stat().st_mtime, tz=timezone.utc)
            handle = SessionHandle(
                session_id=payload["id"],
                project_root=project_root,
                source=self.source_label,
                source_path=rollout_path,
                started_at=started_at,
                updated_at=updated_at,
                cli_version=payload.get("cli_version"),
            )
            sort_key = updated_at
            candidates.append((sort_key, handle))

        if not candidates:
            return None
        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1]

    def load_events(self, handle: SessionHandle) -> list[SessionEvent]:
        events: list[SessionEvent] = []
        if not handle.source_path:
            return events
        for raw_line in handle.source_path.read_text(encoding="utf-8").splitlines():
            if not raw_line.strip():
                continue
            try:
                record = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            timestamp = parse_iso8601(record.get("timestamp"))
            record_type = record.get("type")
            payload = record.get("payload", {})

            if record_type == "event_msg":
                event = self._parse_event_msg(timestamp, payload)
                if event:
                    events.append(event)
                continue

            if record_type == "response_item":
                event = self._parse_response_item(timestamp, payload)
                if event:
                    events.append(event)

        return events

    def _load_session_meta(self, rollout_path: Path) -> dict | None:
        with rollout_path.open(encoding="utf-8") as stream:
            for line in stream:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    return None
                if record.get("type") == "session_meta":
                    return record
                break
        return None

    def _parse_event_msg(
        self,
        timestamp: datetime | None,
        payload: dict,
    ) -> SessionEvent | None:
        event_type = payload.get("type")
        if event_type == "user_message":
            return SessionEvent(
                kind="message",
                role="user",
                timestamp=timestamp,
                text=payload.get("message", "").strip(),
            )
        if event_type == "agent_message":
            return SessionEvent(
                kind="message",
                role="assistant",
                timestamp=timestamp,
                text=payload.get("message", "").strip(),
            )
        if event_type == "exec_command_end":
            return SessionEvent(
                kind="command",
                timestamp=timestamp,
                text=self._command_text(payload.get("command")),
                metadata={
                    "exit_code": payload.get("exit_code"),
                    "status": payload.get("status"),
                    "cwd": payload.get("cwd"),
                },
            )
        if event_type == "web_search_end":
            return SessionEvent(
                kind="web_search",
                timestamp=timestamp,
                text=payload.get("query", "").strip(),
            )
        return None

    def _parse_response_item(
        self,
        timestamp: datetime | None,
        payload: dict,
    ) -> SessionEvent | None:
        if payload.get("type") != "function_call":
            return None
        tool_name = payload.get("name", "").strip()
        if not tool_name or tool_name in self.EXCLUDED_TOOL_NAMES:
            return None
        return SessionEvent(
            kind="tool_call",
            timestamp=timestamp,
            text=tool_name,
            metadata={"arguments": payload.get("arguments")},
        )

    def _command_text(self, command: object) -> str:
        if isinstance(command, list):
            if len(command) >= 3 and command[1] == "-lc":
                return str(command[2]).strip()
            return " ".join(str(part) for part in command if str(part).strip())
        return str(command or "").strip()
