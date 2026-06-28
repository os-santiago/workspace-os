# Copyright 2026 Sergio Canales
# SPDX-License-Identifier: Apache-2.0
"""
Tests for security validator module.
"""

from __future__ import annotations

from pathlib import Path

from workspace_os.security.policy import load_security_policy
from workspace_os.security.validator import SecurityValidator


def test_security_validator_init() -> None:
    """Test SecurityValidator initialization."""
    project_root = Path(".")
    validator = SecurityValidator(project_root)

    assert validator.project_root == project_root
    assert validator.report_dir == project_root / ".security-reports"
    assert validator.policy_path == project_root / "config" / "security-policy.yml"


def test_get_vulnerability_summary_empty() -> None:
    """Test vulnerability summary with no reports."""
    validator = SecurityValidator(Path("."))
    summary = validator.get_vulnerability_summary()

    assert summary["total"] == 0
    assert summary["critical"] == 0
    assert summary["high"] == 0
    assert summary["medium"] == 0
    assert summary["low"] == 0
    assert summary["bandit_total"] == 0


def test_validate_returns_tuple() -> None:
    """Test validate method returns tuple."""
    validator = SecurityValidator(Path("."))
    result = validator.validate(skip_scan=True)

    assert isinstance(result, tuple)
    assert len(result) == 2
    assert isinstance(result[0], bool)
    assert isinstance(result[1], list)


def test_check_exceptions_no_file() -> None:
    """Test exception checking with no exceptions file."""
    validator = SecurityValidator(Path("."))
    result = validator._check_exceptions()

    assert result is True


def test_get_vulnerability_summary_includes_bandit_results(tmp_path) -> None:
    validator = SecurityValidator(tmp_path)
    report_dir = validator.report_dir
    report_dir.mkdir(exist_ok=True)
    (report_dir / "bandit.json").write_text(
        """{"results": [
            {"issue_severity": "HIGH"},
            {"issue_severity": "MEDIUM"},
            {"issue_severity": "LOW"}
        ]}""",
        encoding="utf-8",
    )

    summary = validator.get_vulnerability_summary()

    assert summary["bandit_total"] == 3
    assert summary["bandit_high"] == 1
    assert summary["bandit_medium"] == 1
    assert summary["bandit_low"] == 1


def test_security_policy_loader_reads_yaml(tmp_path) -> None:
    policy_path = tmp_path / "security-policy.yml"
    policy_path.write_text(
        """
allowed_dependencies:
  - rich
banned_patterns:
  - name: sample
    pattern: 'shell=True'
    paths:
      - src/**/*.py
required_headers:
  - name: sample_headers
    paths:
      - src/workspace_os/security/*.py
    lines:
      - '# Copyright 2026 Sergio Canales'
      - '# SPDX-License-Identifier: Apache-2.0'
encryption_requirements:
  - name: env_backed_models
    config_path: config/workspace.sources.example.json
    enabled_profile_kind: openai_compatible
    required_fields:
      - api_key_env
    forbidden_fields:
      - api_key
""",
        encoding="utf-8",
    )

    policy = load_security_policy(policy_path)

    assert policy.allowed_dependencies == ("rich",)
    assert policy.banned_patterns[0].name == "sample"
    assert policy.required_headers[0].paths == ("src/workspace_os/security/*.py",)
    assert policy.encryption_requirements[0].enabled_profile_kind == "openai_compatible"


def test_security_policy_summary_reports_compliance() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    validator = SecurityValidator(repo_root)

    report = validator.get_policy_summary()

    assert report["policy_exists"] is True
    assert report["passed"] is True
    assert report["summary"]["declared_dependencies_disallowed"] == 0
    assert report["summary"]["header_rules_failed"] == 0
    assert report["summary"]["encryption_rules_failed"] == 0
