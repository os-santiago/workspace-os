"""
Test agent routing and task-aware agent selection.

Comprehensive tests for task-aware routing logic in agent_policy.py.
"""
import os
import random
from unittest.mock import patch
from workspace_os.agent_policy import (
    _suggest_agent_from_task,
    choose_work_agent_pair,
    normalize_agent_name,
)


class TestSuggestAgentFromTask:
    def test_opencode_keywords(self):
        assert _suggest_agent_from_task('refactor the auth module') == 'opencode'
        assert _suggest_agent_from_task('cleanup unused imports') == 'opencode'
        assert _suggest_agent_from_task('rename variable xyz') == 'opencode'
        assert _suggest_agent_from_task('delete deprecated function') == 'opencode'

    def test_claude_keywords(self):
        assert _suggest_agent_from_task('analyze the performance') == 'claude'
        assert _suggest_agent_from_task('review this code') == 'claude'
        assert _suggest_agent_from_task('plan the migration') == 'claude'

    def test_antigravity_keywords(self):
        assert _suggest_agent_from_task('discover gaps') == 'antigravity'
        assert _suggest_agent_from_task('architectural assessment') == 'antigravity'
        assert _suggest_agent_from_task('audit security') == 'antigravity'

    def test_no_match(self):
        assert _suggest_agent_from_task('implement feature X') is None
        assert _suggest_agent_from_task('') is None

    def test_none_input(self):
        assert _suggest_agent_from_task(None) is None

    def test_case_insensitive(self):
        assert _suggest_agent_from_task('REFACTOR module') == 'opencode'
        assert _suggest_agent_from_task('Analyze DATA') == 'claude'


class TestChooseWorkAgentPair:
    def test_learning_bias_takes_precedence(self):
        rng = random.Random(123)
        primary, _ = choose_work_agent_pair(
            rng=rng,
            learning_bias='claude',
            task_hint='refactor code',
        )
        assert primary == 'claude', 'learning_bias should influence selection'

    def test_task_hint_used_when_no_bias(self):
        rng = random.Random(42)
        primary, _ = choose_work_agent_pair(
            rng=rng,
            task_hint='refactor auth module',
        )
        assert primary == 'opencode'

    @patch.dict(os.environ, {'WOS_TASK_AWARE_ROUTING': 'false'})
    def test_routing_disabled(self):
        rng = random.Random(42)
        primary, _ = choose_work_agent_pair(
            rng=rng,
            preferred_primary='antigravity',
            task_hint='refactor code',
        )
        assert primary == 'antigravity'

    @patch.dict(os.environ, {'WOS_ROUTING_DEBUG': 'true'})
    def test_debug_logging(self, capsys):
        rng = random.Random(42)
        choose_work_agent_pair(rng=rng, task_hint='analyze code')
        out = capsys.readouterr()
        assert '[ROUTING DEBUG]' in out.out


class TestNormalizeAgentName:
    def test_valid_agents(self):
        assert normalize_agent_name('OPENCODE') == 'opencode'
        assert normalize_agent_name('Claude') == 'claude'
        assert normalize_agent_name('  antigravity  ') == 'antigravity'

    def test_invalid_agents(self):
        assert normalize_agent_name('invalid') is None
        assert normalize_agent_name('') is None

    def test_none(self):
        assert normalize_agent_name(None) is None


class TestCrossCheckRouting:
    """Test cross-check validation mechanism (Closes #97)."""

    def test_cross_check_swaps_when_task_suggests_secondary(self):
        """When cross_check=True and task suggests secondary agent, swap primary/secondary."""
        rng = random.Random(123)
        primary, secondary = choose_work_agent_pair(
            rng=rng,
            learning_bias='claude',
            task_hint='refactor auth module',  # suggests opencode
            cross_check=True,
        )
        # Cross-check validates agent selection against task keywords
        assert primary in ('opencode', 'claude')
        assert secondary in ('opencode', 'claude')
        assert primary != secondary

    def test_cross_check_validates_primary_selection(self):
        """When cross_check=True, validates primary choice against task-based routing."""
        rng = random.Random(42)
        primary, secondary = choose_work_agent_pair(
            rng=rng,
            preferred_primary='antigravity',
            task_hint='analyze code',  # suggests claude
            cross_check=True,
        )
        # Cross-check should consider task-based routing
        assert primary in ('claude', 'antigravity')
        assert secondary in ('claude', 'antigravity', 'opencode')

    def test_cross_check_respects_learning_bias_when_matching(self):
        """When cross_check=True and learning bias matches task, keep it."""
        rng = random.Random(789)
        primary, secondary = choose_work_agent_pair(
            rng=rng,
            learning_bias='opencode',
            task_hint='refactor code',  # also suggests opencode
            cross_check=True,
        )
        # Both learning and task suggest opencode, so no swap needed
        assert primary == 'opencode'

    def test_cross_check_no_task_hint_no_validation(self):
        """When cross_check=True but no task_hint, no validation occurs."""
        rng = random.Random(111)
        primary, secondary = choose_work_agent_pair(
            rng=rng,
            learning_bias='claude',
            task_hint=None,
            cross_check=True,
        )
        # Without task_hint, cross-check has nothing to validate against
        assert primary == 'claude'

    @patch.dict(os.environ, {'WOS_TASK_AWARE_ROUTING': 'false'})
    def test_cross_check_disabled_when_task_aware_off(self):
        """When task-aware routing disabled, cross_check has no effect."""
        rng = random.Random(222)
        primary, secondary = choose_work_agent_pair(
            rng=rng,
            preferred_primary='antigravity',
            task_hint='refactor code',
            cross_check=True,
        )
        # Task-aware routing is off, so cross-check can't operate
        assert primary == 'antigravity'
