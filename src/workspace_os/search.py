from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from workspace_os.config import Source
from workspace_os.progress import progress


EXCLUDED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
}

TEXT_EXTENSIONS = {
    ".cfg",
    ".css",
    ".csv",
    ".env.example",
    ".hcl",
    ".html",
    ".ini",
    ".java",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".ps1",
    ".py",
    ".sh",
    ".tf",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}


@dataclass(frozen=True)
class SearchMatch:
    source_name: str
    path: Path
    line_number: int
    line: str


def search_sources(
    sources: list[Source],
    query: str,
    source_type: str | None = None,
    max_results: int = 100,
) -> list[SearchMatch]:
    needle = query.casefold()
    matches: list[SearchMatch] = []

    # Count searchable sources for progress tracking
    searchable_sources = [
        s for s in sources
        if s.search and (not source_type or s.type == source_type) and s.path.exists()
    ]

    with progress(f"Searching for '{query}'", total=len(searchable_sources)) as tracker:
        for source in searchable_sources:
            tracker.update(description=f"Searching {source.name}")

            for path in _iter_text_files(source.path):
                for line_number, line in _matching_lines(path, needle):
                    matches.append(
                        SearchMatch(
                            source_name=source.name,
                            path=path.relative_to(source.path),
                            line_number=line_number,
                            line=line.strip(),
                        )
                    )
                    if len(matches) >= max_results:
                        tracker.complete()
                        return matches

            tracker.update()

        tracker.complete()

    return matches


def _iter_text_files(root: Path):
    for path in root.rglob("*"):
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        if not path.is_file():
            continue
        if _is_text_candidate(path):
            yield path


def _is_text_candidate(path: Path) -> bool:
    if path.name in {"Dockerfile", "Makefile", "ADEV.md", "README.md"}:
        return True
    suffix = path.suffix.lower()
    if suffix in TEXT_EXTENSIONS:
        return True
    return "".join(path.suffixes[-2:]).lower() in TEXT_EXTENSIONS


def _matching_lines(path: Path, needle: str):
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if needle in line.casefold():
                    yield line_number, line
    except UnicodeDecodeError:
        return
    except OSError:
        return
