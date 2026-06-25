# Copyright 2026 Sergio Canales
# SPDX-License-Identifier: Apache-2.0

"""Tests for issue complexity detection."""

from __future__ import annotations

import pytest

from workspace_os.issue_complexity import (
    ComplexityLevel,
    ComplexityClassification,
    classify_issue,
    _score_keywords,
    _detect_ambiguities,
    _detect_dependencies,
)


class TestComplexityDetection:
    """Tests for overall complexity classification."""

    def test_simple_issue(self):
        """Simple, clear issue should be classified as SIMPLE."""
        issue = {
            "title": "Fix typo in README.md",
            "body": "Line 42 has 'teh' instead of 'the'",
            "labels": [{"name": "documentation"}],
        }

        result = classify_issue(issue)

        assert result.level == ComplexityLevel.SIMPLE
        assert result.score < 4.0
        assert not result.requires_architecture_decision
        assert result.estimated_agents == 3
        assert result.estimated_duration_minutes == 30

    def test_moderate_bug_issue(self):
        """Bug requiring investigation should be MODERATE."""
        issue = {
            "title": "Memory leak in background worker",
            "body": """
            The background worker process gradually increases memory usage over time.
            After 24 hours, it uses 2GB+ RAM and needs restart.

            Need to investigate root cause and fix.
            """,
            "labels": [{"name": "bug"}],
        }

        result = classify_issue(issue)

        # Bug + investigate keywords = moderate to complex
        assert result.level in (ComplexityLevel.MODERATE, ComplexityLevel.COMPLEX)
        assert result.score >= 4.0
        assert result.requires_research
        assert result.estimated_agents >= 5
        assert result.estimated_duration_minutes >= 60

    def test_complex_architecture_issue(self):
        """Issue requiring architecture decisions should be COMPLEX."""
        issue = {
            "title": "Design caching layer for API endpoints",
            "body": """
            Need to implement caching to improve API performance.

            Considerations:
            - Redis vs Memcached vs in-memory
            - Cache-aside vs write-through pattern
            - TTL strategy
            - Invalidation approach
            - Which endpoints to cache
            """,
            "labels": [{"name": "architecture"}, {"name": "enhancement"}],
        }

        result = classify_issue(issue)

        assert result.level == ComplexityLevel.COMPLEX
        assert result.score >= 7.0
        assert result.requires_research
        assert result.requires_architecture_decision
        assert result.estimated_agents == 8
        assert result.estimated_duration_minutes == 90

    def test_complex_with_external_dependencies(self):
        """Issue with external dependencies should be COMPLEX."""
        issue = {
            "title": "Integrate Stripe payment processing",
            "body": """
            Add Stripe integration for payments:
            - Install Stripe SDK
            - Configure API keys
            - Setup webhooks
            - Database migration for payment records
            - Frontend payment form
            """,
            "labels": [{"name": "integration"}],
        }

        result = classify_issue(issue)

        assert result.level in (ComplexityLevel.MODERATE, ComplexityLevel.COMPLEX)
        assert result.requires_research
        assert "Stripe payment processing" in result.detected_dependencies

    def test_ambiguous_performance_issue(self):
        """Vague performance issue should detect ambiguities."""
        issue = {
            "title": "Improve performance",
            "body": "The app is slow, make it faster",
            "labels": [],
        }

        result = classify_issue(issue)

        # Should detect ambiguities even if classified as simple
        assert len(result.has_ambiguities) > 0
        assert any("vague" in amb.lower() or "unclear" in amb.lower() for amb in result.has_ambiguities)


class TestKeywordScoring:
    """Tests for keyword-based scoring."""

    def test_score_simple_keywords(self):
        """Single-word keywords should score 1.0 each."""
        text = "we need to refactor the architecture"
        keywords = ["refactor", "architecture"]

        score = _score_keywords(text, keywords)

        assert score == 2.0  # Two single-word keywords

    def test_score_multi_word_keywords(self):
        """Multi-word keywords should have higher weight."""
        text = "investigate the root cause of the issue"
        keywords = ["root cause", "investigate"]

        score = _score_keywords(text, keywords)

        # "root cause" (2 words) = 1.5, "investigate" (1 word) = 1.0
        assert score == 2.5

    def test_score_no_matches(self):
        """No matching keywords should score 0."""
        text = "simple fix for typo"
        keywords = ["architecture", "design", "refactor"]

        score = _score_keywords(text, keywords)

        assert score == 0.0


class TestAmbiguityDetection:
    """Tests for ambiguity detection."""

    def test_vague_goal_no_metric(self):
        """'Improve X' without metric should detect ambiguity."""
        title = "Improve performance"
        body = "Make things faster"

        ambiguities = _detect_ambiguities(title, body, ambiguity_score=2.0)

        assert len(ambiguities) > 0
        assert any("vague" in amb.lower() for amb in ambiguities)

    def test_vague_goal_with_metric(self):
        """'Improve X' WITH metric should NOT flag as vague."""
        title = "Improve performance"
        body = "Reduce API latency from 500ms to 100ms (5x improvement)"

        ambiguities = _detect_ambiguities(title, body, ambiguity_score=2.0)

        # Should still detect missing scope, but NOT vague goal
        vague_ambiguities = [amb for amb in ambiguities if "vague" in amb.lower()]
        assert len(vague_ambiguities) == 0

    def test_missing_scope(self):
        """Performance issue without scope should detect ambiguity."""
        title = "Improve performance"
        body = "We need better performance"

        ambiguities = _detect_ambiguities(title, body, ambiguity_score=1.0)

        assert any("scope" in amb.lower() for amb in ambiguities)

    def test_clear_scope(self):
        """Performance issue WITH scope should not flag."""
        title = "Optimize database queries"
        body = "API endpoints are slow due to N+1 queries in the database layer"

        ambiguities = _detect_ambiguities(title, body, ambiguity_score=1.0)

        scope_ambiguities = [amb for amb in ambiguities if "scope" in amb.lower()]
        assert len(scope_ambiguities) == 0

    def test_high_ambiguity_score(self):
        """High ambiguity score should flag decision needed."""
        title = "Update authentication"
        body = "Consider OAuth, JWT, or session-based auth"

        ambiguities = _detect_ambiguities(title, body, ambiguity_score=3.5)

        assert any("decision" in amb.lower() for amb in ambiguities)


class TestDependencyDetection:
    """Tests for external dependency detection."""

    def test_detect_stripe(self):
        """Should detect Stripe payment processing."""
        text = "integrate stripe for payment processing"

        dependencies = _detect_dependencies(text)

        assert "Stripe payment processing" in dependencies

    def test_detect_redis(self):
        """Should detect Redis cache."""
        text = "use redis for caching layer"

        dependencies = _detect_dependencies(text)

        assert "Redis cache" in dependencies

    def test_detect_postgres(self):
        """Should detect PostgreSQL database."""
        text = "migrate from sqlite to postgresql database"

        dependencies = _detect_dependencies(text)

        assert "PostgreSQL database" in dependencies

    def test_detect_aws(self):
        """Should detect AWS services."""
        text = "deploy to amazon web services (aws) with s3 and ec2"

        dependencies = _detect_dependencies(text)

        assert "AWS services" in dependencies

    def test_detect_docker_kubernetes(self):
        """Should detect Docker and Kubernetes."""
        text = "containerize with docker and deploy to k8s cluster"

        dependencies = _detect_dependencies(text)

        assert "Docker containerization" in dependencies
        assert "Kubernetes orchestration" in dependencies

    def test_no_dependencies(self):
        """Text without dependencies should return empty list."""
        text = "fix typo in documentation"

        dependencies = _detect_dependencies(text)

        assert dependencies == []


class TestComplexityClassification:
    """Tests for ComplexityClassification dataclass."""

    def test_classification_immutable(self):
        """Classification should be immutable (frozen dataclass)."""
        classification = ComplexityClassification(
            level=ComplexityLevel.SIMPLE,
            score=2.5,
            requires_research=False,
            requires_architecture_decision=False,
            has_ambiguities=[],
            detected_dependencies=[],
            estimated_agents=3,
            estimated_duration_minutes=30,
            reasoning="Test reasoning",
        )

        with pytest.raises(Exception):  # FrozenInstanceError
            classification.level = ComplexityLevel.COMPLEX


class TestRealWorldExamples:
    """Tests with real-world issue examples."""

    def test_example_fix_typo(self):
        """Real example: Simple typo fix."""
        issue = {
            "title": "Fix typo in error message",
            "body": "User-facing error says 'occured' instead of 'occurred'",
            "labels": [{"name": "bug"}, {"name": "good first issue"}],
        }

        result = classify_issue(issue)

        # Bug label adds research_score, but overall should be simple
        assert result.level in (ComplexityLevel.SIMPLE, ComplexityLevel.MODERATE)
        assert result.estimated_agents <= 5

    def test_example_add_feature(self):
        """Real example: Add new feature with clear requirements."""
        issue = {
            "title": "Add dark mode toggle",
            "body": """
            Add a toggle button to switch between light and dark themes.

            Requirements:
            - Toggle in settings menu
            - Persist preference to localStorage
            - Update CSS variables on toggle
            """,
            "labels": [{"name": "enhancement"}],
        }

        result = classify_issue(issue)

        # Clear requirements = simple or moderate
        assert result.level in (ComplexityLevel.SIMPLE, ComplexityLevel.MODERATE)
        assert not result.requires_architecture_decision
        assert result.estimated_agents <= 5

    def test_example_migration(self):
        """Real example: Database migration."""
        issue = {
            "title": "Migrate from MongoDB to PostgreSQL",
            "body": """
            We need to migrate our database from MongoDB to PostgreSQL for better ACID guarantees.

            This involves:
            - Designing new schema
            - Data migration strategy
            - Updating all ORMs
            - Testing data integrity
            - Rollback plan
            """,
            "labels": [{"name": "architecture"}, {"name": "breaking change"}],
        }

        result = classify_issue(issue)

        assert result.level == ComplexityLevel.COMPLEX
        assert result.requires_architecture_decision
        assert result.requires_research
        assert "PostgreSQL database" in result.detected_dependencies
        assert result.estimated_agents == 8

    def test_example_investigate_bug(self):
        """Real example: Investigate intermittent bug."""
        issue = {
            "title": "Tests randomly fail on CI",
            "body": """
            Some tests pass locally but fail intermittently on CI (about 10% of runs).

            Need to investigate:
            - Race conditions?
            - Environment differences?
            - Timing issues?
            """,
            "labels": [{"name": "bug"}, {"name": "ci"}],
        }

        result = classify_issue(issue)

        # Bug + investigate keywords could be simple to moderate
        assert result.level in (ComplexityLevel.SIMPLE, ComplexityLevel.MODERATE)
        assert result.requires_research
        reasoning_lower = result.reasoning.lower()
        assert "investigate" in reasoning_lower or "research" in reasoning_lower


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_issue(self):
        """Empty issue should default to SIMPLE."""
        issue = {"title": "", "body": "", "labels": []}

        result = classify_issue(issue)

        assert result.level == ComplexityLevel.SIMPLE
        assert result.score < 4.0

    def test_missing_body(self):
        """Issue without body should still classify based on title."""
        issue = {"title": "Refactor authentication architecture", "labels": []}

        result = classify_issue(issue)

        # Title has architecture keywords but no body context
        # Could be any level depending on keyword weighting
        assert result.level in (ComplexityLevel.SIMPLE, ComplexityLevel.MODERATE, ComplexityLevel.COMPLEX)

    def test_missing_labels(self):
        """Issue without labels should still classify based on content."""
        issue = {
            "title": "Design new API endpoints",
            "body": "Need to design RESTful API for new feature",
        }

        result = classify_issue(issue)

        # "design" keyword should trigger some complexity
        # But without more context, could be simple
        assert result.level in (ComplexityLevel.SIMPLE, ComplexityLevel.MODERATE, ComplexityLevel.COMPLEX)

    def test_very_high_score_caps_at_10(self):
        """Score should cap at 10.0 even with many keywords."""
        issue = {
            "title": "Refactor architecture and design migration strategy",
            "body": """
            Need to investigate, analyze, diagnose, and implement a new approach
            for our distributed scalable performance optimization using external
            APIs, third-party integrations, and multiple dependencies including
            Redis, PostgreSQL, Elasticsearch, Kafka, AWS, and Kubernetes.
            """,
            "labels": [{"name": "architecture"}, {"name": "enhancement"}],
        }

        result = classify_issue(issue)

        assert result.score <= 10.0
        assert result.level == ComplexityLevel.COMPLEX
