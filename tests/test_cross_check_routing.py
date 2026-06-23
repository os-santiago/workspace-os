"""Test cross-check routing for issue #97."""
import random
from workspace_os.agent_policy import choose_work_agent_pair

def test_cross_check_swap():
    rng = random.Random(42)
    primary, secondary = choose_work_agent_pair(
        rng=rng,
        learning_bias='claude',
        task_hint='refactor authentication',
        cross_check=True,
    )
    assert primary == 'opencode'
    assert secondary == 'claude'

def test_cross_check_disabled():
    rng = random.Random(42)
    primary, _ = choose_work_agent_pair(
        rng=rng,
        learning_bias='claude',
        task_hint='refactor authentication',
        cross_check=False,
    )
    assert primary == 'claude'
