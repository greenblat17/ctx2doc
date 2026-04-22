from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from ctx2doc.cli import main
from ctx2doc.codex_adapter import CodexSessionAdapter
from ctx2doc.snapshot import SnapshotService


def write_sample_session(rollout_path: Path, cwd: Path, session_id: str) -> None:
    rollout_path.parent.mkdir(parents=True, exist_ok=True)
    records = [
        {
            "timestamp": "2026-04-22T10:00:00Z",
            "type": "session_meta",
            "payload": {
                "id": session_id,
                "timestamp": "2026-04-22T10:00:00Z",
                "cwd": str(cwd),
                "cli_version": "0.121.0",
                "source": "cli",
            },
        },
        {
            "timestamp": "2026-04-22T10:00:01Z",
            "type": "event_msg",
            "payload": {
                "type": "user_message",
                "message": "Build a Codex-only snapshot tool with MCP support and one markdown file per snapshot.",
            },
        },
        {
            "timestamp": "2026-04-22T10:00:02Z",
            "type": "event_msg",
            "payload": {
                "type": "agent_message",
                "message": "I will inspect the local session logs and implement a minimal Python CLI plus MCP server.",
            },
        },
        {
            "timestamp": "2026-04-22T10:00:03Z",
            "type": "event_msg",
            "payload": {
                "type": "exec_command_end",
                "command": ["/bin/zsh", "-lc", "codex mcp add --help"],
                "exit_code": 0,
                "status": "completed",
                "cwd": str(cwd),
            },
        },
        {
            "timestamp": "2026-04-22T10:00:04Z",
            "type": "response_item",
            "payload": {
                "type": "function_call",
                "name": "web_lookup",
                "arguments": "{\"q\":\"codex mcp add help\"}",
            },
        },
        {
            "timestamp": "2026-04-22T10:00:05Z",
            "type": "event_msg",
            "payload": {
                "type": "user_message",
                "message": "Store snapshots in docs/ctx2doc and keep the summary compact. What should the MCP tool names be?",
            },
        },
    ]
    with rollout_path.open("w", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record) + "\n")


class SnapshotServiceTest(unittest.TestCase):
    def test_create_snapshot_writes_markdown_with_expected_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_root = root / "project"
            project_root.mkdir()
            codex_home = root / "codex-home"
            rollout = codex_home / "sessions" / "2026" / "04" / "22" / "rollout.jsonl"
            write_sample_session(rollout, project_root, "session-123")
            service = SnapshotService(adapter=CodexSessionAdapter(codex_home=codex_home))

            result = service.create_snapshot(project_root)
            content = result.snapshot_path.read_text(encoding="utf-8")

            self.assertTrue(result.snapshot_path.exists())
            self.assertEqual(
                result.snapshot_path.parent.resolve(),
                (project_root / "docs" / "ctx2doc").resolve(),
            )
            self.assertIn("# Context Snapshot", content)
            self.assertIn("## Goal", content)
            self.assertIn("## What Was Done", content)
            self.assertIn("## Decisions", content)
            self.assertIn("## Open Risks / Unknowns", content)
            self.assertIn("docs/ctx2doc", str(result.snapshot_path))

    def test_resume_context_uses_latest_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_root = root / "project"
            latest_dir = project_root / "docs" / "ctx2doc"
            latest_dir.mkdir(parents=True)
            older = latest_dir / "2026-04-22T10-00-00--old.md"
            newer = latest_dir / "2026-04-22T10-05-00--new.md"
            older.write_text("older", encoding="utf-8")
            newer.write_text("newer", encoding="utf-8")
            service = SnapshotService(adapter=CodexSessionAdapter(codex_home=root / "unused"))

            result = service.resume_context(project_root)

            self.assertEqual(result.snapshot_path.resolve(), newer.resolve())
            self.assertIn("Use the following context snapshot", result.content)
            self.assertIn("newer", result.content)

    def test_cli_snapshot_and_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_root = root / "project"
            project_root.mkdir()
            codex_home = root / "codex-home"
            rollout = codex_home / "sessions" / "2026" / "04" / "22" / "rollout.jsonl"
            write_sample_session(rollout, project_root, "session-cli")
            previous_home = os.environ.get("CTX2DOC_CODEX_HOME")
            os.environ["CTX2DOC_CODEX_HOME"] = str(codex_home)
            cwd = Path.cwd()
            stdout = io.StringIO()
            try:
                os.chdir(project_root)
                with contextlib.redirect_stdout(stdout):
                    exit_code_snapshot = main(["snapshot"])
                    exit_code_status = main(["status"])
            finally:
                os.chdir(cwd)
                if previous_home is None:
                    os.environ.pop("CTX2DOC_CODEX_HOME", None)
                else:
                    os.environ["CTX2DOC_CODEX_HOME"] = previous_home

            output = stdout.getvalue()
            self.assertEqual(exit_code_snapshot, 0)
            self.assertEqual(exit_code_status, 0)
            self.assertIn("Created snapshot:", output)
            self.assertIn("Detected session source: codex-cli", output)
            self.assertIn("Detected session: session-cli", output)
