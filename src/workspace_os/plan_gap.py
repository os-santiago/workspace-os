from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(frozen=True)
class BacklogItem:
    item_id: str
    title: str
    status: str  # "done", "next", "later"
    acceptance_criteria: tuple[str, ...]
    implementation_notes: tuple[str, ...]


def extract_backlog_items(backlog_path: Path) -> tuple[BacklogItem, ...]:
    """Extract structured backlog items from the product backlog file."""
    if not backlog_path.exists():
        return ()

    content = backlog_path.read_text(encoding="utf-8")
    items: list[BacklogItem] = []
    current_status = "done"

    # Split by sections
    for section in content.split("\n## "):
        section = section.strip()
        if not section:
            continue

        # Track status
        if section.startswith("Done"):
            current_status = "done"
        elif section.startswith("Next"):
            current_status = "next"
        elif section.startswith("Later"):
            current_status = "later"

        # Extract items (WSOS-XXX headers)
        item_pattern = r"### (WSOS-\d+): (.+)"
        for match in re.finditer(item_pattern, section, re.MULTILINE):
            item_id = match.group(1)
            title = match.group(2)

            # Extract acceptance criteria
            acceptance_criteria: list[str] = []
            criteria_start = section.find("Acceptance criteria:", match.end())
            if criteria_start >= 0:
                criteria_section = section[criteria_start:].split("\n\n")[0]
                for line in criteria_section.splitlines():
                    if line.strip().startswith("- "):
                        acceptance_criteria.append(line.strip()[2:])

            # Extract implementation notes
            implementation_notes: list[str] = []
            impl_start = section.find("Initial implementation:", match.end())
            if impl_start >= 0:
                impl_section = section[impl_start:].split("\n\n")[0]
                for line in impl_section.splitlines():
                    if line.strip().startswith("- "):
                        implementation_notes.append(line.strip()[2:])

            items.append(BacklogItem(
                item_id=item_id,
                title=title,
                status=current_status,
                acceptance_criteria=tuple(acceptance_criteria),
                implementation_notes=tuple(implementation_notes),
            ))

    return tuple(items)


def get_next_backlog_items(backlog_path: Path, limit: int = 3) -> tuple[BacklogItem, ...]:
    """Get the highest-priority backlog items from the 'Next' section."""
    all_items = extract_backlog_items(backlog_path)
    next_items = [item for item in all_items if item.status == "next"]
    return tuple(next_items[:limit])


def render_backlog_item_for_prompt(item: BacklogItem) -> str:
    """Render a backlog item as a compact string for agent prompts."""
    lines = [f"{item.item_id}: {item.title}"]
    if item.acceptance_criteria:
        lines.append(f"  Criteria: {'; '.join(item.acceptance_criteria[:2])}")
    if item.implementation_notes:
        lines.append(f"  Notes: {'; '.join(item.implementation_notes[:2])}")
    return "\n".join(lines)


def get_plan_work_hint(backlog_path: Path) -> str:
    """Generate a concise hint about next backlog work for cycle prompts."""
    next_items = get_next_backlog_items(backlog_path, limit=2)
    if not next_items:
        return ""

    lines = ["Next backlog work:"]
    for item in next_items:
        lines.append(f"- {item.item_id}: {item.title}")
    return "\n".join(lines)
