# Copyright 2026 Sergio Canales
# SPDX-License-Identifier: Apache-2.0

"""Tests for agent quota management."""

import time
from pathlib import Path

import pytest

from workspace_os.agent_quota import AgentQuotaManager, AgentQuotaStatus


class TestAgentQuotaManager:
    """Test AgentQuotaManager functionality."""

    def test_init_creates_directory(self, tmp_path):
        """Test that initialization creates state directory."""
        state_file = tmp_path / "quota" / "state.json"
        manager = AgentQuotaManager(state_file)

        assert state_file.parent.exists()

    def test_new_agent_is_available(self, tmp_path):
        """Test that agents without quota info are available."""
        manager = AgentQuotaManager(tmp_path / "state.json")

        assert manager.is_agent_available("opencode")
        assert manager.is_agent_available("claude")

    def test_record_quota_exceeded_disables_agent(self, tmp_path):
        """Test that recording quota exceeded disables agent."""
        manager = AgentQuotaManager(tmp_path / "state.json")

        error = "Free usage exceeded, subscribe to Go [retrying in 21h 10m attempt #1]"
        manager.record_quota_exceeded("opencode", error)

        assert not manager.is_agent_available("opencode")

    def test_parse_retry_time_hours_minutes(self, tmp_path):
        """Test parsing retry time with hours and minutes."""
        manager = AgentQuotaManager(tmp_path / "state.json")

        error = "Free usage exceeded [retrying in 21h 10m]"
        retry_seconds = manager._parse_retry_time(error)

        assert retry_seconds == 21 * 3600 + 10 * 60  # 76200 seconds

    def test_parse_retry_time_minutes_only(self, tmp_path):
        """Test parsing retry time with minutes only."""
        manager = AgentQuotaManager(tmp_path / "state.json")

        error = "Rate limit exceeded, retry after 45m"
        retry_seconds = manager._parse_retry_time(error)

        assert retry_seconds == 45 * 60  # 2700 seconds

    def test_parse_retry_time_hours_only(self, tmp_path):
        """Test parsing retry time with hours only."""
        manager = AgentQuotaManager(tmp_path / "state.json")

        error = "Quota exceeded, reset in 2h"
        retry_seconds = manager._parse_retry_time(error)

        assert retry_seconds == 2 * 3600  # 7200 seconds

    def test_parse_retry_time_no_match(self, tmp_path):
        """Test parsing retry time with no recognizable pattern."""
        manager = AgentQuotaManager(tmp_path / "state.json")

        error = "Some random error message"
        retry_seconds = manager._parse_retry_time(error)

        assert retry_seconds is None

    def test_agent_re_enabled_after_quota_reset(self, tmp_path):
        """Test that agent is automatically re-enabled after quota resets."""
        manager = AgentQuotaManager(tmp_path / "state.json")

        # Record quota exceeded with 1 second retry
        error = "Quota exceeded [retrying in 1s]"

        # Manually set very short reset time for testing
        now = time.time()
        status = AgentQuotaStatus(
            agent="opencode",
            is_available=False,
            error_message=error,
            retry_after_seconds=1,
            reset_at=now + 1,  # 1 second from now
            last_checked=now,
        )
        manager._quota_status["opencode"] = status
        manager._save_state()

        # Agent should be unavailable immediately
        assert not manager.is_agent_available("opencode")

        # Wait for quota to reset
        time.sleep(1.1)

        # Agent should be available again
        assert manager.is_agent_available("opencode")

    def test_state_persistence(self, tmp_path):
        """Test that quota state persists across instances."""
        state_file = tmp_path / "state.json"

        # First manager instance
        manager1 = AgentQuotaManager(state_file)
        error = "Quota exceeded [retrying in 5h]"
        manager1.record_quota_exceeded("opencode", error)

        assert not manager1.is_agent_available("opencode")

        # Second manager instance (load from disk)
        manager2 = AgentQuotaManager(state_file)

        assert not manager2.is_agent_available("opencode")

    def test_get_status_returns_info(self, tmp_path):
        """Test getting status information."""
        manager = AgentQuotaManager(tmp_path / "state.json")

        error = "Quota exceeded [retrying in 2h 30m]"
        manager.record_quota_exceeded("opencode", error)

        status = manager.get_status("opencode")

        assert status is not None
        assert status.agent == "opencode"
        assert not status.is_available
        assert "Quota exceeded" in status.error_message
        assert status.retry_after_seconds == 2 * 3600 + 30 * 60

    def test_get_all_statuses(self, tmp_path):
        """Test getting all agent statuses."""
        manager = AgentQuotaManager(tmp_path / "state.json")

        manager.record_quota_exceeded("opencode", "Quota [retrying in 1h]")
        manager.record_quota_exceeded("claude", "Rate limit [retry after 30m]")

        statuses = manager.get_all_statuses()

        assert len(statuses) == 2
        assert "opencode" in statuses
        assert "claude" in statuses

    def test_clear_agent_status(self, tmp_path):
        """Test manually clearing agent status."""
        manager = AgentQuotaManager(tmp_path / "state.json")

        manager.record_quota_exceeded("opencode", "Quota exceeded")
        assert not manager.is_agent_available("opencode")

        manager.clear_agent_status("opencode")
        assert manager.is_agent_available("opencode")

    def test_different_quota_patterns(self, tmp_path):
        """Test various quota error message patterns."""
        manager = AgentQuotaManager(tmp_path / "state.json")

        patterns = [
            ("retrying in 1h 30m", 5400),
            ("retry after 45m", 2700),
            ("reset in 3h", 10800),
            ("available in 2h 15m", 8100),
        ]

        for pattern, expected_seconds in patterns:
            retry = manager._parse_retry_time(f"Error {pattern}")
            assert retry == expected_seconds, f"Failed for pattern: {pattern}"
