from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Iterable

from ctx2doc.claude_adapter import ClaudeCodeSessionAdapter
from ctx2doc.codex_adapter import CodexSessionAdapter
from ctx2doc.config import AppConfig, load_project_config
from ctx2doc.models import ResumeResult, SessionEvent, SessionHandle, SnapshotResult, StatusResult
from ctx2doc.redaction import redact_text, redact_value
from ctx2doc.session_adapters import AdapterRegistry, SelectedSession


class SnapshotError(RuntimeError):
    pass


class SessionNotFoundError(SnapshotError):
    pass


class ResumeContextNotFoundError(SnapshotError):
    pass


@dataclass(frozen=True)
class SnapshotSections:
    goal: str
    what_was_done: list[str]
    decisions: list[str]
    important_context: list[str]
    risks: list[str]
    next_steps: list[str]


class SnapshotService:
    def __init__(self, registry: AdapterRegistry | None = None, adapter=None) -> None:
        if registry is not None:
            self.registry = registry
        elif adapter is not None:
            self.registry = AdapterRegistry(adapters=[adapter])
        else:
            self.registry = AdapterRegistry(
                adapters=[ClaudeCodeSessionAdapter(), CodexSessionAdapter()]
            )

    def status(
        self,
        project_root: str | Path | None = None,
        source_preference: str | None = None,
        output_dir: str | Path | None = None,
    ) -> StatusResult:
        resolved_root = self._resolve_project_root(project_root)
        config = load_project_config(resolved_root)
        normalized_source = config.normalized_source(source_preference)
        snapshot_dir = config.snapshot_dir(resolved_root, output_dir)
        selection = self.registry.detect(resolved_root, normalized_source)
        latest_snapshot = self.latest_snapshot(snapshot_dir)
        return StatusResult(
            project_root=resolved_root,
            snapshot_dir=snapshot_dir,
            session=selection.handle if selection else None,
            latest_snapshot=latest_snapshot,
            source_preference=normalized_source,
        )

    def create_snapshot(
        self,
        project_root: str | Path | None = None,
        source_preference: str | None = None,
        output_dir: str | Path | None = None,
        redaction_mode: str | None = None,
    ) -> SnapshotResult:
        resolved_root = self._resolve_project_root(project_root)
        config = load_project_config(resolved_root)
        normalized_source = config.normalized_source(source_preference)
        selection = self.registry.detect(resolved_root, normalized_source)
        if not selection:
            raise SessionNotFoundError(
                f"No supported session found for project root {resolved_root} with source preference {normalized_source}"
            )

        events = selection.adapter.load_events(selection.handle)
        sanitized_events = sanitize_events(events, config.normalized_redaction_mode(redaction_mode))
        generated_at = datetime.now(timezone.utc)
        markdown = render_snapshot_markdown(selection.handle, sanitized_events, generated_at)
        markdown = redact_text(markdown, config.normalized_redaction_mode(redaction_mode))
        snapshot_dir = config.snapshot_dir(resolved_root, output_dir)
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        snapshot_path = snapshot_dir / self.snapshot_filename(selection.handle, generated_at)
        snapshot_path.write_text(markdown, encoding="utf-8")
        return SnapshotResult(
            project_root=resolved_root,
            snapshot_path=snapshot_path,
            session=selection.handle,
            event_count=len(sanitized_events),
        )

    def resume_context(
        self,
        project_root: str | Path | None = None,
        output_dir: str | Path | None = None,
    ) -> ResumeResult:
        resolved_root = self._resolve_project_root(project_root)
        config = load_project_config(resolved_root)
        snapshot_dir = config.snapshot_dir(resolved_root, output_dir)
        latest_snapshot = self.latest_snapshot(snapshot_dir)
        if not latest_snapshot:
            raise ResumeContextNotFoundError(f"No snapshots found in {snapshot_dir}")
        content = latest_snapshot.read_text(encoding="utf-8")
        resume_text = (
            "Use the following context snapshot to resume work in a new coding session.\n\n"
            f"{content}"
        )
        return ResumeResult(
            project_root=resolved_root,
            snapshot_path=latest_snapshot,
            content=resume_text,
        )

    def latest_snapshot(self, snapshot_dir: Path) -> Path | None:
        if not snapshot_dir.exists():
            return None
        snapshots = sorted(snapshot_dir.glob("*.md"))
        return snapshots[-1] if snapshots else None

    def snapshot_filename(self, session: SessionHandle, generated_at: datetime) -> str:
        return f"{generated_at.strftime('%Y-%m-%dT%H-%M-%S')}--{session.short_id()}.md"

    def _resolve_project_root(self, project_root: str | Path | None) -> Path:
        return Path(project_root or Path.cwd()).expanduser().resolve()


def sanitize_events(events: list[SessionEvent], redaction_mode: str) -> list[SessionEvent]:
    return [
        SessionEvent(
            kind=event.kind,
            timestamp=event.timestamp,
            text=redact_text(event.text, redaction_mode),
            role=event.role,
            metadata=redact_value(event.metadata, redaction_mode),
        )
        for event in events
    ]


def render_snapshot_markdown(
    session: SessionHandle,
    events: list[SessionEvent],
    generated_at: datetime,
) -> str:
    sections = summarize_events(events)
    generated_label = generated_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    started_label = (
        session.started_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        if session.started_at
        else "unknown"
    )
    source_path = str(session.source_path) if session.source_path else "unknown"

    lines = [
        "# Context Snapshot",
        "",
        f"- Generated at: `{generated_label}`",
        f"- Project root: `{session.project_root}`",
        f"- Source: `{session.source}`",
        f"- Source session: `{session.session_id}`",
        f"- Session started: `{started_label}`",
        f"- Source artifact: `{source_path}`",
        "",
        "## Goal",
        sections.goal,
        "",
        "## What Was Done",
        *render_bullets(sections.what_was_done),
        "",
        "## Decisions",
        *render_bullets(sections.decisions),
        "",
        "## Important Context",
        *render_bullets(sections.important_context),
        "",
        "## Open Risks / Unknowns",
        *render_bullets(sections.risks),
        "",
        "## Next Steps",
        *render_bullets(sections.next_steps),
        "",
    ]
    return "\n".join(lines)


def render_bullets(items: Iterable[str]) -> list[str]:
    return [f"- {item}" for item in items]


def summarize_events(events: list[SessionEvent]) -> SnapshotSections:
    user_messages = [clean_text(event.text) for event in events if event.kind == "message" and event.role == "user"]
    assistant_messages = [
        clean_text(event.text) for event in events if event.kind == "message" and event.role == "assistant"
    ]
    commands = [clean_text(event.text) for event in events if event.kind == "command" and event.text]
    tool_calls = [clean_text(event.text) for event in events if event.kind == "tool_call" and event.text]

    goal = truncate(user_messages[0], 800) if user_messages else "No explicit user goal was found in the session log."
    what_was_done = build_what_was_done(user_messages, assistant_messages, commands, tool_calls)
    decisions = extract_decisions(user_messages + assistant_messages)
    important_context = build_important_context(user_messages, commands, tool_calls, len(events))
    risks = extract_open_questions(user_messages)
    next_steps = build_next_steps(user_messages, assistant_messages)

    return SnapshotSections(
        goal=goal,
        what_was_done=what_was_done,
        decisions=decisions,
        important_context=important_context,
        risks=risks,
        next_steps=next_steps,
    )


def build_what_was_done(
    user_messages: list[str],
    assistant_messages: list[str],
    commands: list[str],
    tool_calls: list[str],
) -> list[str]:
    items = [
        f"Captured {len(user_messages)} user message(s) and {len(assistant_messages)} assistant update(s) in this session."
    ]
    if commands:
        items.append(
            f"Executed {len(commands)} shell command(s), including {format_inline_list(unique_preserving_order(commands), 4)}."
        )
    if tool_calls:
        items.append(
            f"Called {len(tool_calls)} tool(s), including {format_inline_list(unique_preserving_order(tool_calls), 4)}."
        )
    if assistant_messages:
        items.append(f"Recent assistant activity: {truncate(assistant_messages[-1], 240)}")
    return items


def build_important_context(
    user_messages: list[str],
    commands: list[str],
    tool_calls: list[str],
    total_events: int,
) -> list[str]:
    items = [f"Normalized {total_events} relevant session event(s) into this snapshot."]
    if len(user_messages) > 1:
        items.append(f"Latest user request: {truncate(user_messages[-1], 240)}")
    if commands:
        items.append(f"Most recent shell command: `{commands[-1]}`")
    if tool_calls:
        items.append(f"Most recent tool call: `{tool_calls[-1]}`")
    return items


def extract_decisions(messages: list[str]) -> list[str]:
    keywords = (
        "should",
        "will",
        "use ",
        "best",
        "recommended",
        "v1",
        "only",
        "must",
        "snapshot",
        "python",
        "mcp",
        "claude",
        "codex",
        "делать",
        "будет",
        "лучше",
        "достаточно",
        "нужно",
        "только",
        "mvp",
    )
    candidates: list[str] = []
    for message in reversed(messages):
        for fragment in split_fragments(message):
            lowered = fragment.lower()
            if "?" in fragment:
                continue
            if any(keyword in lowered for keyword in keywords):
                candidates.append(truncate(fragment, 220))
        if len(candidates) >= 5:
            break

    unique_candidates = unique_preserving_order(list(reversed(candidates)))
    if unique_candidates:
        return unique_candidates[:5]
    return ["No explicit implementation decisions were extracted; use the sections below as the working context."]


def extract_open_questions(user_messages: list[str]) -> list[str]:
    questions: list[str] = []
    for message in reversed(user_messages):
        for fragment in split_fragments(message):
            if "?" in fragment:
                questions.append(truncate(fragment, 220))
        if len(questions) >= 4:
            break
    unique_questions = unique_preserving_order(list(reversed(questions)))
    if unique_questions:
        return unique_questions[:4]
    return ["No explicit open questions were extracted from the user messages in this session."]


def build_next_steps(user_messages: list[str], assistant_messages: list[str]) -> list[str]:
    if user_messages:
        return [
            f"Continue from the latest user request: {truncate(user_messages[-1], 220)}",
            "Use this snapshot as the bootstrap context for the next session or after a context reset.",
        ]
    if assistant_messages:
        return [
            f"Resume from the latest assistant update: {truncate(assistant_messages[-1], 220)}",
            "Use this snapshot as the bootstrap context for the next session or after a context reset.",
        ]
    return ["Start from the goal above and re-open the relevant project files before making changes."]


def split_fragments(text: str) -> list[str]:
    raw_fragments = re.split(r"[\n\r]+|(?<=[.!?])\s+", text)
    return [clean_text(fragment) for fragment in raw_fragments if clean_text(fragment)]


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def unique_preserving_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    unique_items: list[str] = []
    for item in items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        unique_items.append(item)
    return unique_items


def format_inline_list(items: list[str], max_items: int) -> str:
    chosen = [f"`{truncate(item, 80)}`" for item in items[:max_items]]
    return ", ".join(chosen)
