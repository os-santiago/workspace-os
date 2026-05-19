from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Classification:
    target: str
    confidence: str
    reason: str


def classify_content(value: str, is_path: bool = False) -> Classification:
    text = _load_text(value) if is_path else value
    normalized = text.casefold()
    name = Path(value).name.casefold() if is_path else ""

    if _looks_temporary(name, normalized):
        return Classification("temporary", "high", "Looks like scratch, log, backup, or temporary content.")
    if _contains_any(normalized, ("must", "never", "always", "guardrail", "non-negotiable", "doctrine")):
        return Classification("doctrine", "medium", "Contains durable operating rules or guardrails.")
    if _contains_any(normalized, ("incident", "root cause", "evidence", "validated", "lesson learned")):
        return Classification("evidence", "medium", "Contains evidence, incident material, or lessons learned.")
    if _contains_any(normalized, ("script", "automation", "runbook", "command", "iac", "terraform", "kubernetes")):
        return Classification("execution", "medium", "Contains execution, automation, or infrastructure material.")
    if _contains_any(normalized, ("proposal", "estimate", "presentation", "slides", "spreadsheet")):
        return Classification("deliverable", "medium", "Looks like final business deliverable material.")
    if _contains_any(normalized, ("roadmap", "backlog", "prd", "user story", "acceptance criteria")):
        return Classification("product", "medium", "Contains product planning or roadmap material.")
    return Classification("unknown", "low", "No strong classification signal found.")


def _load_text(value: str) -> str:
    path = Path(value)
    if not path.exists() or not path.is_file():
        return value
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.name
    except OSError:
        return path.name


def _looks_temporary(name: str, normalized: str) -> bool:
    temporary_names = ("scratch", "tmp", "temporary", ".bak", ".log", ".orig", ".rej")
    return any(marker in name for marker in temporary_names) or "temporary artifact" in normalized


def _contains_any(value: str, needles: tuple[str, ...]) -> bool:
    return any(needle in value for needle in needles)
