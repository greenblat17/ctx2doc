from __future__ import annotations

import re
from typing import Any


REDACTED = "[REDACTED]"

REPLACEMENTS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
        f"-----BEGIN PRIVATE KEY-----\n{REDACTED}\n-----END PRIVATE KEY-----",
    ),
    (
        re.compile(r"(?i)\b(Bearer)(\s+)[A-Za-z0-9._~+/\-=]+"),
        rf"\1\2{REDACTED}",
    ),
    (
        re.compile(r"(?i)\b(sk-ant-[A-Za-z0-9_-]{10,}|sk-[A-Za-z0-9_-]{10,}|github_pat_[A-Za-z0-9_]{20,}|ghp_[A-Za-z0-9]{20,})\b"),
        REDACTED,
    ),
    (
        re.compile(
            r"(?i)\b(api[_-]?key|token|secret|password|passwd|cookie|session(?:_id)?|access[_-]?token|refresh[_-]?token)\b(\s*[:=]\s*)([^\s,;]+)"
        ),
        rf"\1\2{REDACTED}",
    ),
]


def redact_text(text: str, mode: str = "standard") -> str:
    if mode == "off":
        return text
    redacted = text
    for pattern, replacement in REPLACEMENTS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def redact_value(value: Any, mode: str = "standard") -> Any:
    if isinstance(value, str):
        return redact_text(value, mode)
    if isinstance(value, list):
        return [redact_value(item, mode) for item in value]
    if isinstance(value, dict):
        return {key: redact_value(item, mode) for key, item in value.items()}
    return value
