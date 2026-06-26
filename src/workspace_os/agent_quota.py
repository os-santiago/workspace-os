# Copyright 2026 Sergio Canales
# SPDX-License-Identifier: Apache-2.0

"""Agent quota and rate limit management.

Automatically disables agents when they hit rate limits and re-enables
them when quotas reset.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


@dataclass
class AgentQuotaStatus:
    """Status of an agent's quota/rate limit."""

    agent: str
    is_available: bool  # False if quota exceeded
    error_message: str | None  # Original error message
    retry_after_seconds: int | None  # Seconds until quota resets
    reset_at: float | None  # Unix timestamp when quota resets
    last_checked: float  # Unix timestamp of last check


class AgentQuotaManager:
    """Manages agent quotas and automatic disable/enable."""

    def __init__(self, state_file: Path | None = None):
        """Initialize quota manager.

        Args:
            state_file: Path to persist quota state (default: ~/.workspace-os/agent-quota.json)
        """
        if state_file is None:
            from pathlib import Path
            state_file = Path.home() / ".workspace-os" / "agent-quota.json"

        self.state_file = state_file
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        # Load existing state
        self._quota_status: dict[str, AgentQuotaStatus] = {}
        self._load_state()

    def _load_state(self) -> None:
        """Load quota state from disk."""
        if not self.state_file.exists():
            return

        try:
            with open(self.state_file) as f:
                data = json.load(f)

            for agent, info in data.items():
                self._quota_status[agent] = AgentQuotaStatus(
                    agent=agent,
                    is_available=info["is_available"],
                    error_message=info.get("error_message"),
                    retry_after_seconds=info.get("retry_after_seconds"),
                    reset_at=info.get("reset_at"),
                    last_checked=info.get("last_checked", time.time()),
                )
        except Exception as e:
            print(f"[quota] Warning: Could not load quota state: {e}")

    def _save_state(self) -> None:
        """Save quota state to disk."""
        try:
            data = {
                agent: {
                    "is_available": status.is_available,
                    "error_message": status.error_message,
                    "retry_after_seconds": status.retry_after_seconds,
                    "reset_at": status.reset_at,
                    "last_checked": status.last_checked,
                }
                for agent, status in self._quota_status.items()
            }

            with open(self.state_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[quota] Warning: Could not save quota state: {e}")

    def is_agent_available(self, agent: str) -> bool:
        """Check if agent is available (quota not exceeded).

        Automatically re-enables agents whose quota has reset.

        Args:
            agent: Agent name

        Returns:
            True if agent is available, False if quota exceeded
        """
        # Check if we have quota info for this agent
        if agent not in self._quota_status:
            return True  # No quota info = assume available

        status = self._quota_status[agent]

        # If currently unavailable, check if quota has reset
        if not status.is_available and status.reset_at:
            now = time.time()
            if now >= status.reset_at:
                # Quota has reset - re-enable agent
                print(f"[quota] ✓ Agent '{agent}' quota reset - re-enabling")
                status.is_available = True
                status.error_message = None
                status.retry_after_seconds = None
                status.reset_at = None
                status.last_checked = now
                self._save_state()
                return True

        return status.is_available

    def record_quota_exceeded(
        self, agent: str, error_output: str, returncode: int | None = None
    ) -> None:
        """Record that an agent hit its quota limit.

        Parses error message to extract retry time and automatically
        disables the agent until quota resets.

        Args:
            agent: Agent name
            error_output: Error message from agent
            returncode: Exit code (optional)
        """
        # Parse retry time from error message
        retry_seconds = self._parse_retry_time(error_output)

        now = time.time()
        reset_at = now + retry_seconds if retry_seconds else None

        # Create or update status
        status = AgentQuotaStatus(
            agent=agent,
            is_available=False,
            error_message=error_output[:500],  # Truncate long errors
            retry_after_seconds=retry_seconds,
            reset_at=reset_at,
            last_checked=now,
        )

        self._quota_status[agent] = status
        self._save_state()

        # Log the quota exceeded event
        if retry_seconds:
            hours = retry_seconds // 3600
            minutes = (retry_seconds % 3600) // 60
            reset_time = datetime.fromtimestamp(reset_at).strftime("%Y-%m-%d %H:%M:%S")
            print(
                f"[quota] ⏸️  Agent '{agent}' quota exceeded - disabled for {hours}h {minutes}m (until {reset_time})"
            )
        else:
            print(f"[quota] ⏸️  Agent '{agent}' quota exceeded - disabled indefinitely (manual check required)")

    def _parse_retry_time(self, error_output: str) -> int | None:
        """Parse retry time from error message.

        Supports formats like:
        - "retrying in 21h 10m"
        - "retry after 2h 30m"
        - "reset in 1d 5h"

        Args:
            error_output: Error message

        Returns:
            Seconds until retry, or None if not parseable
        """
        # Pattern: "retrying in XXh XXm" or similar
        patterns = [
            r"retrying in (\d+)h\s*(\d+)m",
            r"retry after (\d+)h\s*(\d+)m",
            r"reset in (\d+)h\s*(\d+)m",
            r"available in (\d+)h\s*(\d+)m",
        ]

        for pattern in patterns:
            match = re.search(pattern, error_output, re.IGNORECASE)
            if match:
                hours = int(match.group(1))
                minutes = int(match.group(2))
                return hours * 3600 + minutes * 60

        # Pattern: "retrying in XXm" (minutes only)
        patterns_min = [
            r"retrying in (\d+)m",
            r"retry after (\d+)m",
            r"reset in (\d+)m",
        ]

        for pattern in patterns_min:
            match = re.search(pattern, error_output, re.IGNORECASE)
            if match:
                minutes = int(match.group(1))
                return minutes * 60

        # Pattern: "retrying in XXh" (hours only)
        patterns_hour = [
            r"retrying in (\d+)h",
            r"retry after (\d+)h",
            r"reset in (\d+)h",
        ]

        for pattern in patterns_hour:
            match = re.search(pattern, error_output, re.IGNORECASE)
            if match:
                hours = int(match.group(1))
                return hours * 3600

        return None

    def get_status(self, agent: str) -> AgentQuotaStatus | None:
        """Get quota status for an agent.

        Args:
            agent: Agent name

        Returns:
            AgentQuotaStatus or None if no quota info
        """
        return self._quota_status.get(agent)

    def get_all_statuses(self) -> dict[str, AgentQuotaStatus]:
        """Get quota status for all agents.

        Returns:
            Dict mapping agent name to status
        """
        return self._quota_status.copy()

    def clear_agent_status(self, agent: str) -> None:
        """Clear quota status for an agent (manual re-enable).

        Args:
            agent: Agent name
        """
        if agent in self._quota_status:
            del self._quota_status[agent]
            self._save_state()
            print(f"[quota] ✓ Cleared quota status for '{agent}'")


# Global instance
_quota_manager: AgentQuotaManager | None = None


def get_quota_manager() -> AgentQuotaManager:
    """Get global quota manager instance."""
    global _quota_manager
    if _quota_manager is None:
        _quota_manager = AgentQuotaManager()
    return _quota_manager
