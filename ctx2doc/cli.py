from __future__ import annotations

import argparse
from pathlib import Path

from ctx2doc.claude_adapter import log_claude_hook_event, read_stdin_text
from ctx2doc.config import DEFAULT_OUTPUT_DIR, SUPPORTED_REDACTION_MODES, SUPPORTED_SOURCES
from ctx2doc.installers import InstallError, install_claude, install_codex, uninstall_claude, uninstall_codex
from ctx2doc.mcp_server import main as mcp_main
from ctx2doc.snapshot import ResumeContextNotFoundError, SessionNotFoundError, SnapshotService


def add_snapshot_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--project-root",
        type=Path,
        help="Optional project root. Defaults to the current working directory.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help=f"Optional snapshot output directory. Defaults to {DEFAULT_OUTPUT_DIR}.",
    )
    parser.add_argument(
        "--source",
        choices=sorted(SUPPORTED_SOURCES),
        default=None,
        help="Session source to use: auto, codex, or claude.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ctx2doc",
        description="Create Markdown snapshots from Codex CLI and Claude Code sessions.",
    )
    subparsers = parser.add_subparsers(dest="command")

    snapshot_parser = subparsers.add_parser("snapshot")
    add_snapshot_options(snapshot_parser)
    snapshot_parser.add_argument(
        "--redaction-mode",
        choices=sorted(SUPPORTED_REDACTION_MODES),
        default=None,
        help="Secret redaction mode to apply before writing snapshots.",
    )

    for command_name in ("status", "resume"):
        subparser = subparsers.add_parser(command_name)
        add_snapshot_options(subparser)

    install_parser = subparsers.add_parser("install")
    install_parser.add_argument("target", choices=("codex", "claude"))
    install_parser.add_argument("--project-root", type=Path, help="Target project root.")
    install_parser.add_argument("--output-dir", default=None, help="Persist a custom snapshot directory in project config.")

    uninstall_parser = subparsers.add_parser("uninstall")
    uninstall_parser.add_argument("target", choices=("codex", "claude"))
    uninstall_parser.add_argument("--project-root", type=Path, help="Target project root.")

    subparsers.add_parser("mcp")

    hook_parser = subparsers.add_parser("claude-hook")
    hook_parser.add_argument("event_name")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "mcp":
        return mcp_main()

    if args.command == "claude-hook":
        return log_claude_hook_event(args.event_name, read_stdin_text())

    if args.command == "install":
        return run_install(args)

    if args.command == "uninstall":
        return run_uninstall(args)

    service = SnapshotService()
    try:
        if args.command == "snapshot":
            result = service.create_snapshot(
                project_root=args.project_root,
                source_preference=args.source,
                output_dir=args.output_dir,
                redaction_mode=args.redaction_mode,
            )
            print(f"Created snapshot: {result.snapshot_path}")
            print(f"Source: {result.session.source}")
            print(f"Session: {result.session.session_id}")
            print(f"Events captured: {result.event_count}")
            return 0

        if args.command == "status":
            result = service.status(
                project_root=args.project_root,
                source_preference=args.source,
                output_dir=args.output_dir,
            )
            print(f"Project root: {result.project_root}")
            print(f"Snapshot directory: {result.snapshot_dir}")
            print(f"Source preference: {result.source_preference}")
            if result.session:
                print(f"Detected session source: {result.session.source}")
                print(f"Detected session: {result.session.session_id}")
            else:
                print("Detected session: not found")
            if result.latest_snapshot:
                print(f"Latest snapshot: {result.latest_snapshot}")
            else:
                print("Latest snapshot: not found")
            return 0

        if args.command == "resume":
            result = service.resume_context(
                project_root=args.project_root,
                output_dir=args.output_dir,
            )
            print(result.content)
            return 0
    except SessionNotFoundError as exc:
        print(str(exc))
        return 1
    except ResumeContextNotFoundError as exc:
        print(str(exc))
        return 1

    parser.print_help()
    return 1


def run_install(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root or Path.cwd()).resolve()
    try:
        if args.target == "codex":
            result = install_codex(project_root, output_dir=args.output_dir)
        else:
            result = install_claude(project_root, output_dir=args.output_dir)
    except InstallError as exc:
        print(str(exc))
        return 1

    print(f"Installed ctx2doc integration for {result.target} in {result.project_root}")
    for detail in result.details:
        print(f"- {detail}")
    return 0


def run_uninstall(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root or Path.cwd()).resolve()
    try:
        if args.target == "codex":
            result = uninstall_codex(project_root)
        else:
            result = uninstall_claude(project_root)
    except InstallError as exc:
        print(str(exc))
        return 1

    print(f"Uninstalled ctx2doc integration for {result.target} in {result.project_root}")
    for detail in result.details:
        print(f"- {detail}")
    return 0
