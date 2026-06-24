# Copyright 2026 Sergio Canales
# SPDX-License-Identifier: Apache-2.0

"""Tests for --debug flag functionality (Issue #115)."""

from pathlib import Path
import unittest
from datetime import datetime
import tempfile
import shutil

from workspace_os.cycle import run_cycle_work_window, run_cycle_work_window_continuous
from workspace_os.memory import WorkspaceMemoryStore
from workspace_os.config import Source


class DebugFlagTests(unittest.TestCase):
    """Test --debug flag enables detailed logging."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.memory_path = Path(self.temp_dir) / "test-memory.db"
        self.store = WorkspaceMemoryStore(self.memory_path)
        self.store.ensure_schema()
        self.sources = [
            Source(
                name="test-repo",
                type="code",
                responsibility="workspace",
                path=Path(self.temp_dir) / "test-repo",
            )
        ]
        # Create the test repo directory
        self.sources[0].path.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_debug_flag_creates_log_file(self):
        """Test that debug=True creates a log file."""
        # Log directory is created in current working directory
        log_dir = Path(".workspace-os") / "debug-logs"

        # Clean up any existing logs before test
        if log_dir.exists():
            for log_file in log_dir.glob("cycle-*.log"):
                log_file.unlink()

        # Run with debug enabled
        result = run_cycle_work_window(
            self.store,
            self.sources,
            duration_minutes=0.01,  # Very short duration
            label="test-debug",
            objective="Test debug logging",
            debug=True,
            agent_runner=lambda *args, **kwargs: type('obj', (), {'duration_seconds': 0.1, 'returncode': 0})(),
        )

        # Verify log file was created
        self.assertTrue(log_dir.exists(), "Debug log directory should be created")
        log_files = list(log_dir.glob("cycle-*.log"))
        self.assertGreaterEqual(len(log_files), 1, "At least one log file should be created")

        # Verify log file contains expected content
        log_content = log_files[-1].read_text()  # Use the latest log file
        self.assertIn("Starting cycle work window", log_content)
        self.assertIn("Cycle Work Window Summary", log_content)

    def test_debug_flag_disabled_creates_no_log(self):
        """Test that debug=False doesn't log to file (may log to console)."""
        # Log directory is in current working directory
        log_dir = Path(".workspace-os") / "debug-logs"

        # Count existing log files before test
        existing_logs = len(list(log_dir.glob("cycle-*.log"))) if log_dir.exists() else 0

        # Run with debug disabled
        result = run_cycle_work_window(
            self.store,
            self.sources,
            duration_minutes=0.01,
            label="test-no-debug",
            objective="Test without debug",
            debug=False,
            agent_runner=lambda *args, **kwargs: type('obj', (), {'duration_seconds': 0.1, 'returncode': 0})(),
        )

        # Verify no additional log files were created
        current_logs = len(list(log_dir.glob("cycle-*.log"))) if log_dir.exists() else 0
        self.assertEqual(current_logs, existing_logs, "No new log files should be created when debug=False")

    def test_continuous_mode_debug_flag_creates_log_file(self):
        """Test that debug=True creates a log file in continuous mode."""
        # Log directory is created in current working directory
        log_dir = Path(".workspace-os") / "debug-logs"

        # Clean up any existing logs before test
        if log_dir.exists():
            for log_file in log_dir.glob("cycle-*.log"):
                log_file.unlink()

        # Run continuous mode with debug enabled
        result = run_cycle_work_window_continuous(
            self.store,
            self.sources,
            duration_minutes=0.01,  # Very short duration
            label="test-continuous-debug",
            objective="Test continuous debug logging",
            debug=True,
            agent_runner=lambda *args, **kwargs: type('obj', (), {'duration_seconds': 0.1, 'returncode': 0})(),
        )

        # Verify log file was created
        self.assertTrue(log_dir.exists(), "Debug log directory should be created")
        log_files = list(log_dir.glob("cycle-*.log"))
        self.assertGreaterEqual(len(log_files), 1, "At least one log file should be created")

        # Verify log file contains expected content for continuous mode
        log_content = log_files[-1].read_text()  # Use the latest log file
        self.assertIn("Starting continuous cycle work window", log_content)
        self.assertIn("Continuous Cycle Work Window Summary", log_content)


if __name__ == "__main__":
    unittest.main()
