from __future__ import annotations

import re


SECRET_ASSIGNMENT = re.compile(
    r"(?i)(password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|credential)(\s*[:=]\s*)([^\s,;]+)"
)


def sanitize_text(value: str) -> str:
    return SECRET_ASSIGNMENT.sub(r"\1\2[REDACTED]", value)
