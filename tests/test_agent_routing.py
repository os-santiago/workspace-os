"""
Test agent routing and task-aware agent selection.
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
        assert _suggest_agent_from_task('format code') == 'opencode'
        assert _suggest_agent_from_task('lint the codebase') == 'opencode'

    def test_claude_keywords(self):
        assert _suggest_agent_from_task('analyze the performance') == 'claude'
        assert _suggest_agent_from_task('review this code') == 'claude'
        assert _suggest_agent_from_task('plan the migration') == 'claude'
        assert _suggest_agent_from_task('design the API') == 'claude'
        assert _suggest_agent_from_task('cross-check coverage') == 'claude'

    def test_antigravity_keywords(self):
        assert _suggest_agent_from_task('discover gaps') == 'antigravity'
        assert _suggest_agent_from_task('architectural assessment needed') == 'antigravity'
        assert _suggest_agent_from_task('leverage patterns') == 'antigravity'
        assert _suggest_agent_from_task('audit security') == 'antigravity'
        assert _suggest_agent_from_task('strategic opportunities') == 'antigravity'
        assert _suggest_agent_from_task('assess technical debt') == 'antigravity'

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
        rng = random.Random(42)
        wins = 0
        for _ in range(100):
            primary, _ = choose_work_agent_pair(
                rng=rng,
                learning_bias='claude',
                task_hint='refactor code',
            )
            if primary == 'claude':
                wins += 1
        assert 55 <= wins <= 75

    def test_task_hint_used(self):
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
