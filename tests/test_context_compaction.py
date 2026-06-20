"""Test context compaction improvements - verify delegation prompt is lean."""

import tempfile
import unittest
from pathlib import Path

from workspace_os.config import Source
from workspace_os.memory import WorkspaceMemoryStore
from workspace_os.overview import render_workspace_analysis_text, render_workspace_next_action_text


class ContextCompactionTests(unittest.TestCase):
    """Verify context compaction reduces delegation overhead."""

    def test_compact_analysis_reduces_lines(self):
        """Compact mode should reduce analysis output."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            db_path = workspace_root / "wos.db"
            sources = [
                Source(
                    name="test-repo",
                    type="git",
                    responsibility="test workspace",
                    path=workspace_root,
                )
            ]
            memory_store = WorkspaceMemoryStore(db_path)
            memory_store.ensure_schema()

            # Compact mode
            compact_text = render_workspace_analysis_text(
                sources, memory_store, workspace="test", limit=5, compact=True
            )
            compact_lines = len(compact_text.strip().split("\n"))

            # Non-compact mode
            full_text = render_workspace_analysis_text(
                sources, memory_store, workspace="test", limit=5, compact=False
            )
            full_lines = len(full_text.strip().split("\n"))

            # Compact should have fewer lines
            self.assertLess(compact_lines, full_lines)
            # Should save at least 3 lines (from recommendation section compaction)
            self.assertGreaterEqual(full_lines - compact_lines, 3)

    def test_compact_next_action_removes_verbose_guidance(self):
        """Compact next action should remove verbose guidance lines."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            db_path = workspace_root / "wos.db"
            sources = [
                Source(
                    name="test-repo",
                    type="git",
                    responsibility="test workspace",
                    path=workspace_root,
                )
            ]
            memory_store = WorkspaceMemoryStore(db_path)
            memory_store.ensure_schema()

            # Start a process to trigger process-active path
            memory_store.start_process(label="test-process", objective="test objective")

            # Compact mode
            compact_text = render_workspace_next_action_text(
                sources, memory_store, workspace="test", compact=True
            )
            compact_lines = len(compact_text.strip().split("\n"))

            # Non-compact mode
            full_text = render_workspace_next_action_text(
                sources, memory_store, workspace="test", compact=False
            )
            full_lines = len(full_text.strip().split("\n"))

            # Compact should have fewer or equal action lines (at least not more)
            self.assertLessEqual(compact_lines, full_lines)

            # Compact should still include essential next action
            self.assertIn("Next:", compact_text)
            self.assertIn("Suggested command:", compact_text)

    def test_delegation_context_sections_under_target(self):
        """Analysis + next action sections should be under 25 lines in compact mode."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            db_path = workspace_root / "wos.db"
            sources = [
                Source(
                    name="test-repo",
                    type="git",
                    responsibility="test workspace",
                    path=workspace_root,
                )
            ]
            memory_store = WorkspaceMemoryStore(db_path)
            memory_store.ensure_schema()
            memory_store.start_process(label="test-process", objective="test objective")

            # Build analysis and next action in compact mode
            analysis = render_workspace_analysis_text(
                sources, memory_store, workspace="test", limit=5, compact=True
            )
            next_action = render_workspace_next_action_text(
                sources, memory_store, workspace="test", compact=True
            )

            total_lines = len(analysis.split("\n")) + len(next_action.split("\n"))

            # Target: these sections under 25 lines (previously ~28-33 lines)
            # This represents the dynamic context overhead from analysis + next action
            self.assertLess(
                total_lines,
                25,
                f"Context overhead from analysis+next_action too high: {total_lines} lines (target <25)",
            )


if __name__ == "__main__":
    unittest.main()
