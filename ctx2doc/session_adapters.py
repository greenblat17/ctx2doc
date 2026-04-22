from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from ctx2doc.models import SessionEvent, SessionHandle


class SessionAdapter(Protocol):
    name: str
    source_label: str

    def detect_session(self, project_root: Path) -> SessionHandle | None:
        ...

    def load_events(self, handle: SessionHandle) -> list[SessionEvent]:
        ...


@dataclass(frozen=True)
class SelectedSession:
    adapter: SessionAdapter
    handle: SessionHandle


class AdapterRegistry:
    def __init__(self, adapters: list[SessionAdapter]) -> None:
        self.adapters = {adapter.name: adapter for adapter in adapters}

    def detect(self, project_root: Path, source_preference: str = "auto") -> SelectedSession | None:
        if source_preference != "auto":
            adapter = self.adapters.get(source_preference)
            if not adapter:
                return None
            handle = adapter.detect_session(project_root)
            return SelectedSession(adapter=adapter, handle=handle) if handle else None

        candidates: list[SelectedSession] = []
        for adapter in self.adapters.values():
            handle = adapter.detect_session(project_root)
            if handle:
                candidates.append(SelectedSession(adapter=adapter, handle=handle))
        if not candidates:
            return None

        def sort_key(item: SelectedSession) -> tuple[datetime, str]:
            timestamp = item.handle.updated_at or item.handle.started_at
            if timestamp is None:
                timestamp = datetime.min.replace(tzinfo=None)
            return timestamp, item.adapter.name

        candidates.sort(key=sort_key, reverse=True)
        return candidates[0]
