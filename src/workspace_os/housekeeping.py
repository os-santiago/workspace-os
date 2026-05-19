from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from workspace_os.config import Source
from workspace_os.search import EXCLUDED_DIRS


TEMP_PATTERNS = (
    "*.bak",
    "*.log",
    "*.orig",
    "*.rej",
    "*.tmp",
    "*-test.md",
    "*.test.md",
    "scratch*",
    "tmp*",
)


@dataclass(frozen=True)
class HousekeepingFinding:
    source_name: str
    path: Path
    pattern: str


def find_temporary_artifacts(sources: list[Source], max_results: int = 100) -> list[HousekeepingFinding]:
    findings: list[HousekeepingFinding] = []
    seen: set[tuple[str, Path]] = set()

    for source in sources:
        if not source.path.exists():
            continue
        for pattern in TEMP_PATTERNS:
            for path in source.path.rglob(pattern):
                if any(part in EXCLUDED_DIRS for part in path.parts):
                    continue
                if not path.is_file():
                    continue
                key = (source.name, path)
                if key in seen:
                    continue
                seen.add(key)
                findings.append(
                    HousekeepingFinding(
                        source_name=source.name,
                        path=path.relative_to(source.path),
                        pattern=pattern,
                    )
                )
                if len(findings) >= max_results:
                    return findings

    return findings
