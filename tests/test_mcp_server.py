from __future__ import annotations

import unittest

from ctx2doc.codex_adapter import CodexSessionAdapter
from ctx2doc.mcp_server import dispatch_tool_call
from ctx2doc.snapshot import SnapshotService
from tests.test_snapshot_service import write_sample_session

import tempfile
from pathlib import Path


class MCPServerTest(unittest.IsolatedAsyncioTestCase):
    async def test_snapshot_tool_returns_text_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_root = root / "project"
            project_root.mkdir()
            codex_home = root / "codex-home"
            rollout = codex_home / "sessions" / "2026" / "04" / "22" / "rollout.jsonl"
            write_sample_session(rollout, project_root, "session-mcp")
            service = SnapshotService(adapter=CodexSessionAdapter(codex_home=codex_home))

            result = await dispatch_tool_call(
                service,
                "ctx2doc.snapshot",
                {"project_root": str(project_root)},
            )

            self.assertEqual(len(result), 1)
            self.assertIn("Created snapshot:", result[0].text)
            self.assertIn("session-mcp", result[0].text)

    async def test_resume_tool_returns_latest_snapshot_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_root = root / "project"
            snapshot_dir = project_root / "docs" / "ctx2doc"
            snapshot_dir.mkdir(parents=True)
            snapshot = snapshot_dir / "2026-04-22T10-05-00--new.md"
            snapshot.write_text("# Context Snapshot\n", encoding="utf-8")
            service = SnapshotService(adapter=CodexSessionAdapter(codex_home=root / "unused"))

            result = await dispatch_tool_call(
                service,
                "ctx2doc.resume_context",
                {"project_root": str(project_root)},
            )

            self.assertEqual(len(result), 1)
            self.assertIn("Use the following context snapshot", result[0].text)
            self.assertIn("# Context Snapshot", result[0].text)
