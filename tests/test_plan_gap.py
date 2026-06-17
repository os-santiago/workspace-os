from pathlib import Path
import tempfile

from workspace_os.plan_gap import (
    BacklogItem,
    extract_backlog_items,
    get_next_backlog_items,
    get_plan_work_hint,
    render_backlog_item_for_prompt,
)


def test_extract_backlog_items_empty():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("# Empty backlog\n")
        f.flush()
        path = Path(f.name)

    try:
        items = extract_backlog_items(path)
        assert items == ()
    finally:
        path.unlink()


def test_extract_backlog_items_with_sections():
    content = """
# Product Backlog

## Done

### WSOS-001: First Item

Acceptance criteria:
- Criteria 1
- Criteria 2

Initial implementation:
- Note 1
- Note 2

## Next

### WSOS-002: Second Item

Acceptance criteria:
- Criteria A

## Later

### WSOS-003: Third Item
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(content)
        f.flush()
        path = Path(f.name)

    try:
        items = extract_backlog_items(path)
        assert len(items) == 3
        assert items[0].item_id == "WSOS-001"
        assert items[0].title == "First Item"
        assert items[0].status == "done"
        assert "Criteria 1" in items[0].acceptance_criteria
        assert "Note 1" in items[0].implementation_notes

        assert items[1].item_id == "WSOS-002"
        assert items[1].status == "next"

        assert items[2].item_id == "WSOS-003"
        assert items[2].status == "later"
    finally:
        path.unlink()


def test_get_next_backlog_items():
    content = """
## Done
### WSOS-001: Done Item

## Next
### WSOS-002: Next Item 1
### WSOS-003: Next Item 2

## Later
### WSOS-004: Later Item
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(content)
        f.flush()
        path = Path(f.name)

    try:
        next_items = get_next_backlog_items(path, limit=1)
        assert len(next_items) == 1
        assert next_items[0].item_id == "WSOS-002"

        all_next = get_next_backlog_items(path, limit=10)
        assert len(all_next) == 2
    finally:
        path.unlink()


def test_render_backlog_item_for_prompt():
    item = BacklogItem(
        item_id="WSOS-123",
        title="Test Item",
        status="next",
        acceptance_criteria=("Criteria A", "Criteria B", "Criteria C"),
        implementation_notes=("Note 1", "Note 2"),
    )
    rendered = render_backlog_item_for_prompt(item)
    assert "WSOS-123" in rendered
    assert "Test Item" in rendered
    assert "Criteria A" in rendered
    assert "Note 1" in rendered


def test_get_plan_work_hint():
    content = """
## Next
### WSOS-100: First Priority
### WSOS-101: Second Priority
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(content)
        f.flush()
        path = Path(f.name)

    try:
        hint = get_plan_work_hint(path)
        assert "Next backlog work:" in hint
        assert "WSOS-100" in hint
        assert "WSOS-101" in hint
    finally:
        path.unlink()


def test_get_plan_work_hint_no_next_items():
    content = """
## Done
### WSOS-001: Done Item
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(content)
        f.flush()
        path = Path(f.name)

    try:
        hint = get_plan_work_hint(path)
        assert hint == ""
    finally:
        path.unlink()
