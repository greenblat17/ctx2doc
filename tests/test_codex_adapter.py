from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from ctx2doc.codex_adapter import CodexSessionAdapter


def write_rollout(rollout_path: Path, cwd: Path, session_id: str, timestamp: str) -> None:
    rollout_path.parent.mkdir(parents=True, exist_ok=True)
    records = [
        {
            "timestamp": timestamp,
            "type": "session_meta",
            "payload": {
                "id": session_id,
                "timestamp": timestamp,
                "cwd": str(cwd),
                "cli_version": "0.121.0",
                "source": "cli",
            },
        },
        {
            "timestamp": timestamp,
            "type": "event_msg",
            "payload": {"type": "user_message", "message": "Need a snapshot tool."},
        },
        {
            "timestamp": timestamp,
            "type": "event_msg",
            "payload": {"type": "agent_message", "message": "Inspecting local Codex logs."},
        },
        {
            "timestamp": timestamp,
            "type": "event_msg",
            "payload": {
                "type": "exec_command_end",
                "command": ["/bin/zsh", "-lc", "codex --help"],
                "exit_code": 0,
                "status": "completed",
                "cwd": str(cwd),
            },
        },
        {
            "timestamp": timestamp,
            "type": "response_item",
            "payload": {
                "type": "function_call",
                "name": "weather",
                "arguments": "{\"location\":\"San Francisco, CA\"}",
            },
        },
        {
            "timestamp": timestamp,
            "type": "event_msg",
            "payload": {
                "type": "web_search_end",
                "query": "codex mcp add help",
            },
        },
    ]
    with rollout_path.open("w", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record) + "\n")


class CodexAdapterTest(unittest.TestCase):
    def test_detects_latest_session_for_project_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_root = root / "project"
            project_root.mkdir()
            codex_home = root / "codex-home"
            older = codex_home / "sessions" / "2026" / "04" / "21" / "rollout-old.jsonl"
            newer = codex_home / "sessions" / "2026" / "04" / "22" / "rollout-new.jsonl"
            write_rollout(older, project_root, "session-old", "2026-04-21T10:00:00Z")
            write_rollout(newer, project_root, "session-new", "2026-04-22T10:00:00Z")

            adapter = CodexSessionAdapter(codex_home=codex_home)
            handle = adapter.detect_session(project_root)

            self.assertIsNotNone(handle)
            assert handle is not None
            self.assertEqual(handle.session_id, "session-new")
            self.assertEqual(handle.project_root, project_root.resolve())
            self.assertEqual(handle.started_at, datetime(2026, 4, 22, 10, 0, tzinfo=timezone.utc))

    def test_loads_messages_commands_and_searches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_root = root / "project"
            project_root.mkdir()
            codex_home = root / "codex-home"
            rollout = codex_home / "sessions" / "2026" / "04" / "22" / "rollout.jsonl"
            write_rollout(rollout, project_root, "session-1", "2026-04-22T10:00:00Z")

            adapter = CodexSessionAdapter(codex_home=codex_home)
            handle = adapter.detect_session(project_root)
            assert handle is not None
            events = adapter.load_events(handle)

            self.assertEqual([event.kind for event in events], ["message", "message", "command", "tool_call", "web_search"])
            self.assertEqual(events[0].role, "user")
            self.assertEqual(events[1].role, "assistant")
            self.assertEqual(events[2].text, "codex --help")
            self.assertEqual(events[3].text, "weather")
            self.assertEqual(events[4].text, "codex mcp add help")
