from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class SessionHandle:
    session_id: str
    project_root: Path
    source: str
    source_path: Path | None = None
    started_at: datetime | None = None
    updated_at: datetime | None = None
    cli_version: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def short_id(self) -> str:
        return self.session_id.split("-")[0]


@dataclass(frozen=True)
class SessionEvent:
    kind: str
    timestamp: datetime | None
    text: str
    role: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class StatusResult:
    project_root: Path
    snapshot_dir: Path
    session: SessionHandle | None
    latest_snapshot: Path | None
    source_preference: str


@dataclass(frozen=True)
class SnapshotResult:
    project_root: Path
    snapshot_path: Path
    session: SessionHandle
    event_count: int


@dataclass(frozen=True)
class ResumeResult:
    project_root: Path
    snapshot_path: Path
    content: str


@dataclass(frozen=True)
class InstallResult:
    target: str
    project_root: Path
    details: list[str]
