from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ctx2doc.installers import install_claude, install_codex, uninstall_claude, uninstall_codex


class InstallerTest(unittest.TestCase):
    @mock.patch("ctx2doc.installers._codex_mcp_servers", return_value=set())
    @mock.patch("ctx2doc.installers._run_command")
    @mock.patch("ctx2doc.installers._ensure_binary")
    def test_install_codex_writes_skill_and_agents(self, _ensure_binary, _run_command, _servers) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            result = install_codex(project_root)

            self.assertEqual(result.target, "codex")
            self.assertTrue((project_root / ".codex" / "skills" / "ctx2doc" / "SKILL.md").exists())
            self.assertTrue((project_root / "AGENTS.md").exists())
            self.assertTrue((project_root / ".ctx2doc" / "config.json").exists())
            _run_command.assert_called()

    def test_install_and_uninstall_claude_updates_project_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)

            result = install_claude(project_root)
            self.assertEqual(result.target, "claude")

            mcp_payload = json.loads((project_root / ".mcp.json").read_text(encoding="utf-8"))
            self.assertIn("ctx2doc", mcp_payload["mcpServers"])
            settings_payload = json.loads((project_root / ".claude" / "settings.json").read_text(encoding="utf-8"))
            self.assertIn("ctx2doc", settings_payload["enabledMcpjsonServers"])
            self.assertTrue((project_root / ".claude" / "skills" / "ctx2doc" / "SKILL.md").exists())

            uninstall_claude(project_root)
            mcp_payload = json.loads((project_root / ".mcp.json").read_text(encoding="utf-8"))
            self.assertNotIn("ctx2doc", mcp_payload.get("mcpServers", {}))

    @mock.patch("ctx2doc.installers._codex_mcp_servers", return_value={"ctx2doc"})
    @mock.patch("ctx2doc.installers._run_command")
    def test_uninstall_codex_removes_project_files(self, _run_command, _servers) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            (project_root / ".codex" / "skills" / "ctx2doc").mkdir(parents=True)
            (project_root / "AGENTS.md").write_text("<!-- ctx2doc:start -->x<!-- ctx2doc:end -->", encoding="utf-8")

            uninstall_codex(project_root)

            self.assertFalse((project_root / ".codex" / "skills" / "ctx2doc").exists())
            self.assertTrue((project_root / "AGENTS.md").exists())
            _run_command.assert_called()
