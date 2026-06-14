from pathlib import Path
import tempfile
import unittest

from workspace_os.batch import current_process_report, process_summary, start_batch, start_process, stop_batch, stop_process
from workspace_os.memory import WorkspaceMemoryStore


class ProcessTests(unittest.TestCase):
    def test_process_report_counts_batches_and_defects(self):
        with tempfile.TemporaryDirectory() as directory:
            store = WorkspaceMemoryStore(Path(directory) / "memory.sqlite3")
            store.ensure_schema()
            process_id = start_process(store, "process-1", "10 batch iteration", started_at="2026-06-14T08:00:00+00:00")

            start_batch(store, "batch-1", "first batch", started_at="2026-06-14T08:05:00+00:00")
            store.record_agent_launch("claude", "review first batch", "workspace-os", launched_at="2026-06-14T08:05:30+00:00")
            store.record_task_outcome("shell", "ctx-1", "failure", "note-1", created_at="2026-06-14T08:06:00+00:00")
            stop_batch(store, ended_at="2026-06-14T08:10:00+00:00")

            start_batch(store, "batch-2", "second batch", started_at="2026-06-14T08:15:00+00:00")
            store.record_agent_launch("codex", "review second batch", "workspace-os", launched_at="2026-06-14T08:15:30+00:00")
            store.record_task_outcome("shell", "ctx-2", "partial", "note-2", created_at="2026-06-14T08:16:00+00:00")
            stop_batch(store, ended_at="2026-06-14T08:20:00+00:00")

            report = current_process_report(store, process_id=process_id, now="2026-06-14T08:20:00+00:00")
            summary = process_summary(store, process_id=process_id, now="2026-06-14T08:20:00+00:00")
            finished = stop_process(store, ended_at="2026-06-14T08:20:00+00:00")

        self.assertIsNotNone(report)
        self.assertIsNotNone(summary)
        self.assertIsNotNone(finished)
        self.assertEqual(2, summary.batch_count)
        self.assertEqual(2, summary.delegations)
        self.assertEqual(2, summary.defect_iterations)
        self.assertEqual("2026-06-14T08:00:00+00:00", summary.started_at)
        self.assertEqual("2026-06-14T08:20:00+00:00", summary.ended_at)
        self.assertEqual(1200, summary.duration_seconds)
        self.assertIn("Process summary", summary.render())

    def test_process_history_lists_recent_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            store = WorkspaceMemoryStore(Path(directory) / "memory.sqlite3")
            store.ensure_schema()
            start_process(store, "process-1", "first process", started_at="2026-06-14T08:00:00+00:00")
            store.finish_active_process(ended_at="2026-06-14T08:10:00+00:00")
            start_process(store, "process-2", "second process", started_at="2026-06-14T09:00:00+00:00")

            history = store.process_history(limit=2)

        self.assertEqual(2, len(history))
        self.assertEqual("process-2", history[0]["label"])
        self.assertEqual("process-1", history[1]["label"])


if __name__ == "__main__":
    unittest.main()
