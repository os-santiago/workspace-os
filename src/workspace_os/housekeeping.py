from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from workspace_os.config import Source
from workspace_os.progress import progress
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

    existing_sources = [s for s in sources if s.path.exists()]
    total_checks = len(existing_sources) * len(TEMP_PATTERNS)

    with progress("Scanning for temporary artifacts", total=total_checks) as tracker:
        for source in existing_sources:
            for pattern in TEMP_PATTERNS:
                tracker.update(description=f"Checking {source.name} for {pattern}")

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
                        tracker.complete()
                        return findings

                tracker.update()

        tracker.complete()

    return findings
