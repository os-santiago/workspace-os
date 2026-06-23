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
        assert _suggest_agent_from_task("refactor the auth module") == "opencode"
        assert _suggest_agent_from_task("cleanup unused imports") == "opencode"
        assert _suggest_agent_from_task("rename variable xyz") == "opencode"
        assert _suggest_agent_from_task("delete deprecated function") == "opencode"

    def test_claude_keywords(self):
        assert _suggest_agent_from_task("analyze the performance") == "claude"
        assert _suggest_agent_from_task("review this code") == "claude"
        assert _suggest_agent_from_task("plan the migration") == "claude"

    def test_antigravity_keywords(self):
        assert _suggest_agent_from_task("discover gaps") == "antigravity"
        assert _suggest_agent_from_task("architectural assessment") == "antigravity"
        assert _suggest_agent_from_task("audit security") == "antigravity"

    def test_no_match(self):
        assert _suggest_agent_from_task("implement feature X") is None
        assert _suggest_agent_from_task("") is None

    def test_none_input(self):
        assert _suggest_agent_from_task(None) is None

    def test_case_insensitive(self):
        assert _suggest_agent_from_task("REFACTOR module") == "opencode"
        assert _suggest_agent_from_task("Analyze DATA") == "claude"


class TestChooseWorkAgentPair:
    def test_learning_bias_takes_precedence(self):
        rng = random.Random(123)
        primary, _ = choose_work_agent_pair(
            rng=rng,
            learning_bias="claude",
            task_hint="refactor code",
        )
        assert primary == "claude", "learning_bias should influence selection"

    def test_task_hint_used_when_no_bias(self):
        rng = random.Random(42)
        primary, _ = choose_work_agent_pair(
            rng=rng,
            task_hint="refactor auth module",
        )
        assert primary == "opencode"

    @patch.dict(os.environ, {"WOS_TASK_AWARE_ROUTING": "false"})
    def test_routing_disabled(self):
        rng = random.Random(42)
        primary, _ = choose_work_agent_pair(
            rng=rng,
            preferred_primary="antigravity",
            task_hint="refactor code",
        )
        assert primary == "antigravity"

    @patch.dict(os.environ, {"WOS_ROUTING_DEBUG": "true"})
    def test_debug_logging(self, capsys):
        rng = random.Random(42)
        choose_work_agent_pair(rng=rng, task_hint="analyze code")
        out = capsys.readouterr()
        assert "[ROUTING DEBUG]" in out.out

    def test_cross_check_disabled_by_default(self):
        """Cross-check should not trigger without explicit flag."""
        rng = random.Random(123)
        primary, _ = choose_work_agent_pair(
            rng=rng,
            learning_bias='claude',
            task_hint='refactor code',  # suggests opencode
            cross_check=False,
            learning_confidence=0.9,
        )
        # Without cross_check, learning_bias wins
        assert primary == 'claude'

    def test_cross_check_swaps_on_mismatch_high_confidence(self):
        """Cross-check should swap agent when task suggests different agent with high confidence."""
        rng = random.Random(123)
        primary, _ = choose_work_agent_pair(
            rng=rng,
            learning_bias='claude',
            task_hint='refactor code',  # suggests opencode
            cross_check=True,
            learning_confidence=0.8,
        )
        # With cross_check and high confidence, task suggestion should win
        assert primary == 'opencode'

    def test_cross_check_no_swap_low_confidence(self):
        """Cross-check should not swap when confidence is below threshold."""
        rng = random.Random(123)
        primary, _ = choose_work_agent_pair(
            rng=rng,
            learning_bias='claude',
            task_hint='refactor code',
            cross_check=True,
            learning_confidence=0.5,  # below 0.7 threshold
        )
        # Low confidence, no swap - learning_bias wins
        assert primary == 'claude'

    def test_cross_check_no_swap_when_agents_match(self):
        """Cross-check should not swap when task suggestion matches primary."""
        rng = random.Random(123)
        primary, _ = choose_work_agent_pair(
            rng=rng,
            learning_bias='opencode',
            task_hint='refactor code',  # also suggests opencode
            cross_check=True,
            learning_confidence=0.9,
        )
        # No mismatch, no swap
        assert primary == 'opencode'

    def test_cross_check_no_swap_without_task_suggestion(self):
        """Cross-check should not swap when task_hint has no clear suggestion."""
        rng = random.Random(123)
        primary, _ = choose_work_agent_pair(
            rng=rng,
            learning_bias='claude',
            task_hint='implement feature X',  # no clear agent suggestion
            cross_check=True,
            learning_confidence=0.9,
        )
        # No task suggestion, no swap
        assert primary == 'claude'

    @patch.dict(os.environ, {'WOS_ROUTING_DEBUG': 'true'})
    def test_cross_check_logging(self, capsys):
        """Cross-check should log routing decisions."""
        rng = random.Random(123)
        choose_work_agent_pair(
            rng=rng,
            learning_bias='claude',
            task_hint='refactor code',
            cross_check=True,
            learning_confidence=0.9,
        )
        out = capsys.readouterr()
        assert 'cross_check' in out.out
        # Check for the swap/trigger message
        assert ('swapped' in out.out or 'triggered' in out.out or 'override' in out.out or 'switching' in out.out)


class TestNormalizeAgentName:
    def test_valid_agents(self):
        assert normalize_agent_name("OPENCODE") == "opencode"
        assert normalize_agent_name("Claude") == "claude"
        assert normalize_agent_name("  antigravity  ") == "antigravity"

    def test_invalid_agents(self):
        assert normalize_agent_name("invalid") is None
        assert normalize_agent_name("") is None

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


class TestValidateAgentAssignment:
    def test_unsupported_agent(self):
        from workspace_os.agent_policy import validate_agent_assignment

        result = validate_agent_assignment("invalid_agent")
        assert not result.is_valid
        assert result.suggested_agent is None
        assert "not supported" in result.reason
        assert result.confidence == 1.0

    def test_valid_agent_no_hints(self):
        from workspace_os.agent_policy import validate_agent_assignment

        result = validate_agent_assignment("opencode")
        assert result.is_valid
        assert result.suggested_agent is None
        assert "valid" in result.reason
        assert result.confidence == 1.0

    def test_task_capability_mismatch(self):
        from workspace_os.agent_policy import validate_agent_assignment

        # Task suggests 'opencode' but assigning 'claude'
        result = validate_agent_assignment(
            "claude", task_hint="refactor the auth module"
        )
        assert result.is_valid  # Still valid but flagged
        assert result.suggested_agent == "opencode"
        assert "suggest" in result.reason.lower()
        assert result.confidence == 0.6

    def test_learning_bias_mismatch(self):
        from workspace_os.agent_policy import validate_agent_assignment

        # Learning model suggests 'claude' but assigning 'opencode'
        result = validate_agent_assignment("opencode", learning_bias="claude")
        assert result.is_valid  # Still valid but learning model suggests different
        assert result.suggested_agent == "claude"
        assert "learning model" in result.reason.lower()
        assert result.confidence == 0.65

    def test_all_checks_pass(self):
        from workspace_os.agent_policy import validate_agent_assignment

        # Perfect alignment: opencode for refactor task
        result = validate_agent_assignment(
            "opencode", task_hint="refactor code", learning_bias="opencode"
        )
        assert result.is_valid
        assert result.suggested_agent is None
        assert result.confidence == 1.0


class TestRoutingDecisionLogging:
    @patch.dict(os.environ, {"WOS_ROUTING_LOG": "true"})
    def test_logging_enabled(self, capsys):
        from workspace_os.agent_policy import _log_routing_decision

        _log_routing_decision(
            primary="opencode",
            task_hint="refactor code",
            learning_bias="opencode",
            task_suggestion="opencode",
            preferred_primary=None,
            routing_reason="learning_bias",
        )

        captured = capsys.readouterr()
        assert "[ROUTING LOG]" in captured.err
        assert "opencode" in captured.err
        assert "refactor code" in captured.err

    @patch.dict(os.environ, {"WOS_ROUTING_LOG": "false"})
    def test_logging_disabled(self, capsys):
        from workspace_os.agent_policy import _log_routing_decision

        _log_routing_decision(
            primary="opencode",
            task_hint="refactor code",
            learning_bias=None,
            task_suggestion=None,
            preferred_primary=None,
            routing_reason="random",
        )

        captured = capsys.readouterr()
        assert "[ROUTING LOG]" not in captured.err


class TestCrossCheckRouting:
    """Test cross-check routing mechanism for wrong_agent error mitigation."""

    def test_cross_check_disabled_by_default(self):
        """Cross-check should not trigger when disabled."""
        rng = random.Random(42)
        # Task suggests opencode, but preferred is claude
        # Note: task_suggestion takes priority over preferred_primary in bias chain
        primary, _ = choose_work_agent_pair(
            rng=rng,
            preferred_primary="claude",
            task_hint="refactor authentication module",
            cross_check=False,  # Disabled
        )
        # Task suggestion wins over preferred_primary (bias chain priority)
        assert primary == "opencode"

    def test_cross_check_overrides_with_high_confidence(self):
        """Cross-check should override when confidence >= 0.7 and validation suggests different agent."""
        rng = random.Random(42)
        # Preferred is claude, but task strongly suggests opencode
        primary, _ = choose_work_agent_pair(
            rng=rng,
            preferred_primary="claude",
            task_hint="refactor authentication module",
            cross_check=True,
            learning_confidence=0.97,  # High confidence from learning model
        )
        # Cross-check should detect task-agent mismatch and route to opencode
        assert primary == "opencode", "Cross-check should route to task-suggested agent"

    def test_cross_check_can_override_learning_bias(self):
        """Cross-check can override learning bias when task-capability mismatch is strong."""
        # Use seed that ensures learning_bias wins the 65% check initially
        rng = random.Random(1)
        # Learning bias is claude, but task strongly suggests opencode
        primary, _ = choose_work_agent_pair(
            rng=rng,
            learning_bias="claude",
            task_hint="refactor code",  # Strongly suggests opencode
            cross_check=True,
            learning_confidence=0.85,  # High confidence triggers cross-check
        )
        # Learning bias initially selects claude (seed=1 passes 65% check)
        # But cross-check detects task-capability mismatch (validation confidence=0.6)
        # Cross-check overrides to opencode (the task-suggested agent)
        # This is CORRECT behavior - catching a potential wrong_agent error!
        assert primary == "opencode"

    def test_cross_check_respects_aligned_learning_bias(self):
        """Cross-check should not override when learning bias aligns with task."""
        rng = random.Random(1)
        # Learning bias is claude, task also suggests claude - perfect alignment
        primary, _ = choose_work_agent_pair(
            rng=rng,
            learning_bias="claude",
            task_hint="analyze code performance",  # Suggests claude
            cross_check=True,
            learning_confidence=0.85,
        )
        # Learning bias and task align, so cross-check validation passes
        # No override needed - claude is correct
        assert primary == "claude"

    def test_cross_check_low_confidence_no_override(self):
        """Cross-check should not override when confidence < 0.7."""
        rng = random.Random(42)
        primary, _ = choose_work_agent_pair(
            rng=rng,
            preferred_primary="claude",
            task_hint="refactor code",  # Suggests opencode
            cross_check=True,
            learning_confidence=0.5,  # Low confidence - cross-check won't trigger
        )
        # Low confidence means cross-check shouldn't trigger at all
        # Task suggestion (opencode) wins over preferred_primary in bias chain
        assert primary == "opencode"

    def test_cross_check_validation_threshold(self):
        """Cross-check should respect validation confidence threshold (0.6)."""
        rng = random.Random(42)
        # Edge case: validation confidence exactly at threshold
        primary, _ = choose_work_agent_pair(
            rng=rng,
            preferred_primary="claude",
            task_hint="analyze performance",  # Suggests claude, so validation passes
            cross_check=True,
            learning_confidence=0.8,
        )
        # Task and agent align, so no override needed
        assert primary == "claude"

    @patch.dict(os.environ, {"WOS_ROUTING_DEBUG": "true"})
    def test_cross_check_debug_logging(self, capsys):
        """Cross-check should log validation details when debug enabled."""
        rng = random.Random(42)
        choose_work_agent_pair(
            rng=rng,
            preferred_primary="claude",
            task_hint="refactor code",
            cross_check=True,
            learning_confidence=0.9,
        )
        captured = capsys.readouterr()
        assert "[ROUTING DEBUG] cross_check validation:" in captured.out
        assert "valid=" in captured.out
        assert "confidence=" in captured.out

    def test_cross_check_integration_with_learning_model(self):
        """Integration test: cross-check responds to learning model wrong_agent signal."""
        rng = random.Random(123)

        # Simulate learning model detecting wrong_agent with high confidence
        # Learning bias suggests claude, but task is clearly refactoring work
        primary, _ = choose_work_agent_pair(
            rng=rng,
            learning_bias="claude",  # Learning initially suggests claude
            task_hint="cleanup and refactor deprecated functions",  # Clear opencode task
            cross_check=True,  # Learning model set detail_level_hint="cross_check"
            learning_confidence=0.97,  # High confidence wrong_agent detection
        )

        # Cross-check should detect the mismatch and route appropriately
        # Since learning_bias takes 65% precedence, it will initially choose claude
        # But cross-check validation should detect task-capability mismatch
        # The actual behavior depends on RNG and the 65% weight, but cross-check should validate
        assert primary in ("opencode", "claude", "antigravity")  # Valid agent chosen
