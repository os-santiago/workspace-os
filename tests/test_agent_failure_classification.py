"""
Test agent failure classification to ensure correct wrong_agent tagging.

Tests for Issue #130: Silent agent failures should NOT be tagged as wrong_agent.
"""

from workspace_os.learning import _is_agent_mismatch_error


class TestAgentMismatchErrorDetection:
    """Test _is_agent_mismatch_error correctly classifies different error types."""

    def test_silent_failure_not_mismatch(self):
        """Silent failures (no error message) should NOT be classified as agent mismatch."""
        assert not _is_agent_mismatch_error(None)
        assert not _is_agent_mismatch_error("")
        assert not _is_agent_mismatch_error("   ")

    def test_capability_mismatch_errors(self):
        """Errors indicating missing capabilities should be classified as agent mismatch."""
        capability_errors = [
            "command not found: some_tool",
            "executable not found",
            "dependency not installed",
            "missing dependency: foo",
            "unsupported operation for this agent",
            "agent does not support this feature",
            "capability not available",
            "tool not found in path",
            "unknown command: xyz",
        ]
        for error in capability_errors:
            assert _is_agent_mismatch_error(error), f"Should detect mismatch in: {error}"

    def test_generic_failures_not_mismatch(self):
        """Generic failures should NOT be classified as agent mismatch."""
        generic_errors = [
            "network error: connection timeout",
            "timeout after 30s",
            "request timed out",
            "connection refused",
            "out of memory",
            "killed by signal 9",
            "syntax error in file.py",
            "assertion failed: expected True",
            "test failed: 3 assertions",
            "AssertionError: values do not match",
            "Traceback (most recent call last):\n  File ...",
            "compilation failed with errors",
            "build failed: exit code 1",
            "lint error: undefined variable",
            "silent failure detected",
            "no output from agent",
            "empty output received",
        ]
        for error in generic_errors:
            assert not _is_agent_mismatch_error(error), f"Should NOT detect mismatch in: {error}"

    def test_case_insensitive_detection(self):
        """Error detection should be case-insensitive."""
        assert _is_agent_mismatch_error("COMMAND NOT FOUND")
        assert _is_agent_mismatch_error("Command Not Found")
        assert not _is_agent_mismatch_error("NETWORK ERROR")

    def test_capability_issue_overridden_by_generic_failure(self):
        """When both capability and generic failure markers present, generic takes precedence."""
        mixed_error = "command not found: npm (traceback follows)"
        assert not _is_agent_mismatch_error(mixed_error), \
            "Traceback indicates code bug, not capability issue"

        mixed_error_2 = "tool not found but test failed anyway"
        assert not _is_agent_mismatch_error(mixed_error_2), \
            "Test failure indicates code issue, not capability"
