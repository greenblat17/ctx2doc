from __future__ import annotations

import asyncio

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from ctx2doc import __version__
from ctx2doc.snapshot import SnapshotService


def build_server(service: SnapshotService | None = None) -> Server:
    snapshot_service = service or SnapshotService()
    server = Server("ctx2doc", version=__version__, instructions="Create Markdown context snapshots from Codex CLI and Claude Code sessions.")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        schema = {
            "type": "object",
            "properties": {
                "project_root": {
                    "type": "string",
                    "description": "Optional project root. Defaults to the server process current working directory.",
                },
                "source": {
                    "type": "string",
                    "description": "Optional session source: auto, codex, or claude.",
                },
                "output_dir": {
                    "type": "string",
                    "description": "Optional snapshot directory override.",
                },
                "redaction_mode": {
                    "type": "string",
                    "description": "Optional secret redaction mode: standard or off.",
                },
            },
        }
        return [
            Tool(
                name="ctx2doc.snapshot",
                description="Create a new Markdown context snapshot for the current project.",
                inputSchema=schema,
            ),
            Tool(
                name="ctx2doc.status",
                description="Report the detected Codex session and latest snapshot for the current project.",
                inputSchema=schema,
            ),
            Tool(
                name="ctx2doc.resume_context",
                description="Return the latest snapshot content so it can be pasted into a new session.",
                inputSchema=schema,
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        return await dispatch_tool_call(snapshot_service, name, arguments or {})

    return server


async def dispatch_tool_call(
    service: SnapshotService,
    name: str,
    arguments: dict,
) -> list[TextContent]:
    project_root = arguments.get("project_root")
    source = arguments.get("source")
    output_dir = arguments.get("output_dir")
    redaction_mode = arguments.get("redaction_mode")

    if name == "ctx2doc.snapshot":
        result = service.create_snapshot(project_root, source, output_dir, redaction_mode)
        return [
            TextContent(
                type="text",
                text=(
                    f"Created snapshot: {result.snapshot_path}\n"
                    f"Project root: {result.project_root}\n"
                    f"Source: {result.session.source}\n"
                    f"Session: {result.session.session_id}\n"
                    f"Events captured: {result.event_count}"
                ),
            )
        ]

    if name == "ctx2doc.status":
        result = service.status(project_root, source, output_dir)
        session_line = result.session.session_id if result.session else "not found"
        source_line = result.session.source if result.session else "not found"
        latest_line = str(result.latest_snapshot) if result.latest_snapshot else "not found"
        return [
            TextContent(
                type="text",
                text=(
                    f"Project root: {result.project_root}\n"
                    f"Snapshot directory: {result.snapshot_dir}\n"
                    f"Source preference: {result.source_preference}\n"
                    f"Detected session source: {source_line}\n"
                    f"Detected session: {session_line}\n"
                    f"Latest snapshot: {latest_line}"
                ),
            )
        ]

    if name == "ctx2doc.resume_context":
        result = service.resume_context(project_root, output_dir)
        return [TextContent(type="text", text=result.content)]

    raise ValueError(f"Unknown tool: {name}")


async def run_stdio_server() -> None:
    server = build_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main() -> int:
    asyncio.run(run_stdio_server())
    return 0
