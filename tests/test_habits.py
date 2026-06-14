from pathlib import Path
import tempfile
import unittest

from workspace_os.habits import compute_habits
from workspace_os.memory import WorkspaceMemoryStore
from workspace_os.profile import load_profile, save_profile_key, save_shortcut


class HabitsTests(unittest.TestCase):
    def test_empty_memory_renders_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            store = WorkspaceMemoryStore(Path(directory) / "memory.sqlite3")
            store.ensure_schema()
            profile = load_profile(store)

            habits = compute_habits(store, profile)

        self.assertIsNone(habits.primary_agent)
        self.assertIsNone(habits.preferred_workspace)
        self.assertEqual("neutral", habits.tone)
        self.assertEqual("standard", habits.detail_level)
        self.assertEqual("n/a", habits.render_summary().split("success=")[1].split(" |")[0])
        self.assertEqual("quiet", habits.activity_level)
        self.assertEqual(0, habits.recent_launch_count)
        self.assertEqual(0, habits.conversation_turn_count)
        self.assertEqual(0, habits.workspace_switch_count)
        self.assertEqual(0, habits.high_risk_decision_count)
        self.assertEqual((), habits.common_missing_context)

    def test_compute_habits_prefers_profile_and_recent_launches(self):
        with tempfile.TemporaryDirectory() as directory:
            store = WorkspaceMemoryStore(Path(directory) / "memory.sqlite3")
            store.ensure_schema()
            save_profile_key(store, "tone", "terse")
            save_profile_key(store, "detail_level", "minimal")
            save_profile_key(store, "default_workspace", "adev")
            save_shortcut(store, "s", "/status")
            store.record_agent_launch("claude", "refine shell", "adev")
            store.record_agent_launch("claude", "tighten memory", "adev")
            store.record_agent_launch("codex", "write tests", "kb")
            store.record_turn("session-1", "user", "Remember to batch work")
            store.record_task_outcome("chat", "ctx-1", "success", "note-1")
            store.record_task_outcome("chat", "ctx-2", "failure", "note-2")
            store.record_task_outcome("chat", "ctx-3", "partial", "note-3")
            store.record_task_outcome("capture", "ctx-4", "failure", "note-4")
            store.record_decision("req-1", "high", "defer", ["missing_scope", "missing_tests"])
            store.record_decision("req-2", "high", "defer", ["missing_tests"])

            habits = compute_habits(store, load_profile(store))

        self.assertEqual("claude", habits.primary_agent)
        self.assertEqual("adev", habits.preferred_workspace)
        self.assertEqual("terse", habits.tone)
        self.assertEqual("minimal", habits.detail_level)
        self.assertEqual("0.25", habits.render_summary().split("success=")[1].split(" |")[0])
        self.assertIn("chat", habits.failure_prone_tasks)
        self.assertEqual(2, habits.high_risk_decision_count)
        self.assertEqual(("missing_tests", "missing_scope"), habits.common_missing_context)
        self.assertEqual(1, habits.workspace_switch_count)
        self.assertEqual(3, habits.recent_launch_count)
        self.assertEqual(1, habits.conversation_turn_count)
        self.assertEqual(1, habits.custom_shortcut_count)
        self.assertEqual("light", habits.activity_level)


if __name__ == "__main__":
    unittest.main()
