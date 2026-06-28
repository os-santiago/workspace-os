import pytest
from pathlib import Path
import tempfile
import shutil

from workspace_os.agent_queue import AgentQueueTracker, AgentTaskState, AgentTaskTrace


@pytest.fixture
def temp_memory():
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_agent_queue_enqueue(temp_memory):
    tracker = AgentQueueTracker(temp_memory, max_parallel=2)
    trace = tracker.enqueue("task-1", "opencode", "homedir", "Fix the bug")

    assert trace.task_id == "task-1"
    assert trace.agent == "opencode"
    assert trace.workspace == "homedir"
    assert trace.state == AgentTaskState.QUEUED
    assert trace.queued_at is not None


def test_agent_queue_start_complete(temp_memory):
    tracker = AgentQueueTracker(temp_memory)
    tracker.enqueue("task-1", "opencode", "homedir", "Fix the bug", metadata={"issue_number": 123})

    tracker.start("task-1")
    snapshot = tracker.snapshot()
    assert snapshot.running_count == 1
    assert snapshot.queued_count == 0

    completed_metadata = tracker.complete("task-1", returncode=0, duration_seconds=10.5)
    snapshot = tracker.snapshot()
    assert snapshot.completed_count == 1
    assert snapshot.running_count == 0
    assert completed_metadata is not None
    assert completed_metadata["issue_number"] == 123


def test_agent_queue_fail(temp_memory):
    tracker = AgentQueueTracker(temp_memory)
    tracker.enqueue("task-1", "opencode", "homedir", "Fix the bug")
    tracker.start("task-1")
    tracker.fail("task-1", error="Compilation failed")

    snapshot = tracker.snapshot()
    assert snapshot.failed_count == 1
    tasks = tracker.recent_tasks(limit=1)
    assert tasks[0].state == AgentTaskState.FAILED
    assert tasks[0].error == "Compilation failed"


def test_agent_queue_snapshot(temp_memory):
    tracker = AgentQueueTracker(temp_memory, max_parallel=3)
    tracker.enqueue("task-1", "opencode", "homedir", "Task 1")
    tracker.enqueue("task-2", "claude", "workspace-os", "Task 2")
    tracker.start("task-1")

    snapshot = tracker.snapshot()
    assert snapshot.queued_count == 1
    assert snapshot.running_count == 1
    assert snapshot.max_parallel == 3
    assert len(snapshot.tasks) == 2


def test_agent_queue_clear_completed(temp_memory):
    tracker = AgentQueueTracker(temp_memory)

    # Add many completed tasks
    for i in range(150):
        tracker.enqueue(f"task-{i}", "opencode", "homedir", f"Task {i}")
        tracker.start(f"task-{i}")
        tracker.complete(f"task-{i}", returncode=0, duration_seconds=1.0)

    removed = tracker.clear_completed(keep_recent=100)
    assert removed == 50

    snapshot = tracker.snapshot()
    assert snapshot.completed_count == 100


def test_agent_queue_utilization_report(temp_memory):
    tracker = AgentQueueTracker(temp_memory, max_parallel=2)
    tracker.enqueue("task-1", "opencode", "homedir", "Task 1")
    tracker.start("task-1")
    tracker.complete("task-1", returncode=0, duration_seconds=4.0)
    tracker.enqueue("task-2", "claude", "workspace-os", "Task 2")
    tracker.start("task-2")

    report = tracker.utilization_report()

    assert report.max_parallel == 2
    assert report.observed_peak_parallel >= 1
    assert report.recommended_max_parallel >= 1
    assert len(report.hourly_totals) == 24
    assert isinstance(report.idle_hours, tuple)
    assert isinstance(report.recommendations, tuple)
    assert report.agent_summaries
    assert any(summary.agent == "opencode" for summary in report.agent_summaries)
    assert "Agent Utilization Report" in report.render()
    assert "Recommended max workers" in report.render()
    assert "Recommendations:" in report.render()
