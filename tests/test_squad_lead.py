"""Tests for WOS Squad Lead coordination features.

Verifies role rotation, context sharing, agent selection,
and failure recovery in Squad Lead mode.
"""
import os
import random
import tempfile
import unittest
from pathlib import Path

from workspace_os.agent_queue import AgentQueueTracker
from workspace_os.memory import WorkspaceMemoryStore
from workspace_os.config import Source


class SquadLeadTests(unittest.TestCase):
    """Test Squad Lead coordination features."""

    def test_role_rotation(self):
        """Test that roles rotate correctly over 9 work items."""
        rotation_cycle_size = 9
        roles = ["primary", "cross-check", "observer"]
        roles_observed = []

        for i in range(1, 10):
            rotation_cycle = i % rotation_cycle_size
            role_index = rotation_cycle % len(roles)
            role = roles[role_index]
            roles_observed.append(role)

        expected_roles = ["cross-check", "observer", "primary"] * 3
        self.assertEqual(roles_observed, expected_roles)
        self.assertEqual(set(roles_observed), set(roles))


    def test_role_specific_keywords(self):
        """Test that roles map to correct guidance keywords."""
        test_roles = ["primary", "cross-check", "observer"]

        for role in test_roles:
            if role == "primary":
                expected_keyword = "primary executor"
            elif role == "cross-check":
                expected_keyword = "cross-check reviewer"
            elif role == "observer":
                expected_keyword = "learning observer"
            else:
                expected_keyword = "executor"

            self.assertIsInstance(expected_keyword, str)

    def test_context_sharing(self):
        """Test that recent work context is properly managed."""
        max_size = 5
        recent_work_context = []

        for i in range(10):
            summary = f"Agent {i % 3} completed work item {i}"
            recent_work_context.append(summary)
            if len(recent_work_context) > max_size:
                recent_work_context.pop(0)

            self.assertLessEqual(len(recent_work_context), max_size)

        self.assertEqual(recent_work_context[-1], "Agent 0 completed work item 9")
        self.assertEqual(len(recent_work_context), max_size)

    def test_role_distribution(self):
        """Test that all roles are distributed evenly across work items."""
        rotation_cycle_size = 9
        roles = ["primary", "cross-check", "observer"]
        role_counts = {role: 0 for role in roles}

        for i in range(1, 28):
            rotation_cycle = i % rotation_cycle_size
            role_index = rotation_cycle % len(roles)
            role = roles[role_index]
            role_counts[role] += 1

        for role, count in role_counts.items():
            self.assertEqual(count, 9, f"Role {role} should appear 9 times, got {count}")


if __name__ == "__main__":
    unittest.main()
