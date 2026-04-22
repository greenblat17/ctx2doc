from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ctx2doc.claude_adapter import ClaudeCodeSessionAdapter, log_claude_hook_event
from ctx2doc.config import AppConfig, save_project_config


class ClaudeAdapterTest(unittest.TestCase):
    def test_logs_hooks_and_detects_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            save_project_config(project_root, AppConfig())

            session_start = {
                "session_id": "claude-session-1",
                "cwd": str(project_root),
                "hook_event_name": "SessionStart",
                "source": "startup",
                "model": "claude-sonnet",
                "transcript_path": "/tmp/transcript.jsonl",
            }
            user_prompt = {
                "session_id": "claude-session-1",
                "cwd": str(project_root),
                "hook_event_name": "UserPromptSubmit",
                "prompt": "Use token=abc123 to deploy",
            }
            post_tool = {
                "session_id": "claude-session-1",
                "cwd": str(project_root),
                "hook_event_name": "PostToolUse",
                "tool_name": "Bash",
                "tool_input": {"command": "npm test"},
            }
            stop = {
                "session_id": "claude-session-1",
                "cwd": str(project_root),
                "hook_event_name": "Stop",
                "last_assistant_message": "Finished the change.",
            }

            for event_name, payload in [
                ("SessionStart", session_start),
                ("UserPromptSubmit", user_prompt),
                ("PostToolUse", post_tool),
                ("Stop", stop),
            ]:
                log_claude_hook_event(event_name, json.dumps(payload))

            adapter = ClaudeCodeSessionAdapter()
            handle = adapter.detect_session(project_root)

            self.assertIsNotNone(handle)
            assert handle is not None
            self.assertEqual(handle.source, "claude-code")
            events = adapter.load_events(handle)
            self.assertEqual([event.kind for event in events], ["session", "message", "command", "message"])
            self.assertIn("[REDACTED]", events[1].text)
            self.assertEqual(events[2].text, "npm test")
