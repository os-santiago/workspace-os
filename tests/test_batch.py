from pathlib import Path
import tempfile
import unittest

from workspace_os.batch import batch_summary, current_batch_report, start_batch, stop_batch
from workspace_os.memory import WorkspaceMemoryStore


class BatchTests(unittest.TestCase):
    def test_batch_report_counts_duration_and_defects(self):
        with tempfile.TemporaryDirectory() as directory:
            store = WorkspaceMemoryStore(Path(directory) / "memory.sqlite3")
            store.ensure_schema()
            start = "2026-06-14T10:00:00+00:00"
            stop = "2026-06-14T10:05:00+00:00"
            batch_id = start_batch(store, "batch-1", "validate shell habits", started_at=start)
            store.record_agent_launch("claude", "review shell batch", "workspace-os", launched_at="2026-06-14T10:01:00+00:00")
            store.record_task_outcome("shell", "ctx-1", "failure", "note-1", created_at="2026-06-14T10:02:00+00:00")
            store.record_task_outcome("shell", "ctx-2", "partial", "note-2", created_at="2026-06-14T10:03:00+00:00")
            store.record_task_outcome("shell", "ctx-3", "success", "note-3", created_at="2026-06-14T10:04:00+00:00")
            store.record_turn("batch-session", "user", "keep batches large", created_at="2026-06-14T10:04:30+00:00")

            report = current_batch_report(store, batch_id=batch_id, now=stop)
            finished = stop_batch(store, ended_at=stop)

        self.assertIsNotNone(report)
        self.assertIsNotNone(finished)
        self.assertEqual(300, report.duration_seconds)
        self.assertEqual(1, report.delegations)
        self.assertEqual(2, report.defect_iterations)
        self.assertEqual(1, report.task_success_count)
        self.assertEqual(1, report.task_failure_count)
        self.assertEqual(1, report.task_partial_count)
        self.assertEqual(1, report.conversation_turns)
        self.assertIn("Batch report", report.render())

    def test_batch_history_lists_recent_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            store = WorkspaceMemoryStore(Path(directory) / "memory.sqlite3")
            store.ensure_schema()
            start_batch(store, "batch-1", "first batch", started_at="2026-06-14T10:00:00+00:00")
            store.finish_active_batch(ended_at="2026-06-14T10:10:00+00:00")
            start_batch(store, "batch-2", "second batch", started_at="2026-06-14T11:00:00+00:00")

            history = store.batch_history(limit=2)

        self.assertEqual(2, len(history))
        self.assertEqual("batch-2", history[0]["label"])
        self.assertEqual("batch-1", history[1]["label"])

    def test_batch_summary_lists_duration_and_defects(self):
        with tempfile.TemporaryDirectory() as directory:
            store = WorkspaceMemoryStore(Path(directory) / "memory.sqlite3")
            store.ensure_schema()
            first = start_batch(store, "batch-1", "first batch", started_at="2026-06-14T10:00:00+00:00")
            store.record_task_outcome("shell", "ctx-1", "failure", "note-1", created_at="2026-06-14T10:02:00+00:00")
            store.finish_active_batch(ended_at="2026-06-14T10:10:00+00:00")
            second = start_batch(store, "batch-2", "second batch", started_at="2026-06-14T11:00:00+00:00")
            store.record_task_outcome("shell", "ctx-2", "partial", "note-2", created_at="2026-06-14T11:02:00+00:00")
            store.finish_active_batch(ended_at="2026-06-14T11:05:00+00:00")

            summary = batch_summary(store, limit=2)

        self.assertEqual(2, summary.total_batches)
        self.assertEqual(first, summary.items[1].batch_id)
        self.assertEqual(second, summary.items[0].batch_id)
        self.assertEqual(600, summary.items[1].duration_seconds)
        self.assertEqual(1, summary.items[1].defect_iterations)
        self.assertEqual(300, summary.items[0].duration_seconds)
        self.assertEqual(1, summary.items[0].defect_iterations)
        self.assertEqual("2026-06-14T10:00:00+00:00", summary.process_started_at)
        self.assertEqual("2026-06-14T11:05:00+00:00", summary.process_ended_at)
        self.assertEqual(3900, summary.process_duration_seconds)
        self.assertEqual(2, summary.total_defect_iterations)
        self.assertIn("batches=2", summary.render())
        self.assertIn("process_started_at=2026-06-14T10:00:00+00:00", summary.render())


if __name__ == "__main__":
    unittest.main()
