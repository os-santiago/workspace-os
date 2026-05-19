from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class Source:
    name: str
    type: str
    responsibility: str
    path: Path
    search: bool = True


def load_sources(config_path: Path) -> list[Source]:
    resolved_config = config_path.expanduser().resolve()
    with resolved_config.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    raw_sources = payload.get("sources")
    if not isinstance(raw_sources, list):
        raise ValueError("Source registry must contain a 'sources' list.")

    sources: list[Source] = []
    for index, raw in enumerate(raw_sources):
        if not isinstance(raw, dict):
            raise ValueError(f"Source entry #{index + 1} must be an object.")

        name = _required_string(raw, "name", index)
        source_type = _required_string(raw, "type", index)
        responsibility = _required_string(raw, "responsibility", index)
        raw_path = _required_string(raw, "path", index)
        search = raw.get("search", True)
        if not isinstance(search, bool):
            raise ValueError(f"Source '{name}' field 'search' must be boolean.")

        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            path = resolved_config.parent / path

        sources.append(
            Source(
                name=name,
                type=source_type,
                responsibility=responsibility,
                path=path.resolve(),
                search=search,
            )
        )

    return sources


def _required_string(raw: dict[str, object], field: str, index: int) -> str:
    value = raw.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Source entry #{index + 1} must define non-empty '{field}'.")
    return value.strip()
