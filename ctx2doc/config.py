from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


DEFAULT_OUTPUT_DIR = "docs/ctx2doc"
DEFAULT_RUNTIME_DIR = ".ctx2doc/runtime"
DEFAULT_REDACTION_MODE = "standard"
DEFAULT_SOURCE = "auto"
SUPPORTED_SOURCES = {"auto", "codex", "claude"}
SUPPORTED_REDACTION_MODES = {"standard", "off"}


@dataclass(frozen=True)
class AppConfig:
    output_dir: str = DEFAULT_OUTPUT_DIR
    runtime_dir: str = DEFAULT_RUNTIME_DIR
    redaction_mode: str = DEFAULT_REDACTION_MODE
    source: str = DEFAULT_SOURCE

    def snapshot_dir(self, project_root: Path, override: str | Path | None = None) -> Path:
        raw_value = override if override is not None else self.output_dir
        return _resolve_project_relative_path(project_root, raw_value)

    def runtime_path(self, project_root: Path) -> Path:
        return _resolve_project_relative_path(project_root, self.runtime_dir)

    def normalized_source(self, override: str | None = None) -> str:
        candidate = (override or self.source or DEFAULT_SOURCE).strip().lower()
        if candidate not in SUPPORTED_SOURCES:
            return DEFAULT_SOURCE
        return candidate

    def normalized_redaction_mode(self, override: str | None = None) -> str:
        candidate = (override or self.redaction_mode or DEFAULT_REDACTION_MODE).strip().lower()
        if candidate not in SUPPORTED_REDACTION_MODES:
            return DEFAULT_REDACTION_MODE
        return candidate


def load_project_config(project_root: Path) -> AppConfig:
    config_path = project_config_path(project_root)
    if not config_path.exists():
        return AppConfig()
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return AppConfig()
    return AppConfig(
        output_dir=str(payload.get("output_dir", DEFAULT_OUTPUT_DIR)),
        runtime_dir=str(payload.get("runtime_dir", DEFAULT_RUNTIME_DIR)),
        redaction_mode=str(payload.get("redaction_mode", DEFAULT_REDACTION_MODE)),
        source=str(payload.get("source", DEFAULT_SOURCE)),
    )


def save_project_config(project_root: Path, config: AppConfig) -> Path:
    config_path = project_config_path(project_root)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "output_dir": config.output_dir,
        "runtime_dir": config.runtime_dir,
        "redaction_mode": config.redaction_mode,
        "source": config.source,
    }
    config_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return config_path


def project_config_path(project_root: Path) -> Path:
    return project_root / ".ctx2doc" / "config.json"


def _resolve_project_relative_path(project_root: Path, raw_value: str | Path) -> Path:
    path = Path(raw_value).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (project_root / path).resolve()
