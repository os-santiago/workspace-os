"""Tests for code coverage tracking and enforcement."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import subprocess

from workspace_os.cycle import (
    _run_coverage_check,
    _run_bandit_security_check,
    CycleCheckResult,
)


def test_run_coverage_check_passes_with_sufficient_coverage():
    """Test that coverage check passes when coverage meets threshold."""
    with tempfile.TemporaryDirectory() as tmpdir:
        source_path = Path(tmpdir)
        config_dir = source_path / "config"
        config_dir.mkdir()
        
        # Create config with 80% threshold
        config = {
            "coverage": {
                "fail_under": 80.0
            }
        }
        with open(config_dir / "quality.json", "w") as f:
            json.dump(config, f)
        
        # Mock subprocess to simulate successful coverage run
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = """
        ------
        TOTAL    100    20    90%
        """
        
        with patch("subprocess.run", return_value=mock_result):
            result = _run_coverage_check(source_path)
        
        assert result.passed is True
        assert "quality:coverage" == result.name
        assert "90.00%" in result.detail or "Coverage check passed" in result.detail


def test_run_coverage_check_fails_below_threshold():
    """Test that coverage check fails when coverage is below threshold."""
    with tempfile.TemporaryDirectory() as tmpdir:
        source_path = Path(tmpdir)
        config_dir = source_path / "config"
        config_dir.mkdir()
        
        # Create config with 80% threshold
        config = {
            "coverage": {
                "fail_under": 80.0
            }
        }
        with open(config_dir / "quality.json", "w") as f:
            json.dump(config, f)
        
        # Mock subprocess to simulate failed coverage run (below threshold)
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = """
        ------
        TOTAL    100    50    50%
        """
        
        with patch("subprocess.run", return_value=mock_result):
            result = _run_coverage_check(source_path)
        
        assert result.passed is False
        assert "quality:coverage" == result.name
        assert "50.00%" in result.detail
        assert "80.0%" in result.detail


def test_run_coverage_check_uses_default_threshold():
    """Test that coverage check uses default 80% when no config exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        source_path = Path(tmpdir)
        
        # Mock subprocess to simulate successful coverage run
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = """
        ------
        TOTAL    100    15    85%
        """
        
        with patch("subprocess.run", return_value=mock_result):
            result = _run_coverage_check(source_path)
        
        assert result.passed is True
        assert "quality:coverage" == result.name


def test_run_coverage_check_handles_timeout():
    """Test that coverage check handles timeout gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        source_path = Path(tmpdir)
        
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 300)):
            result = _run_coverage_check(source_path)
        
        assert result.passed is False
        assert "quality:coverage" == result.name
        assert "timed out" in result.detail.lower()


def test_run_coverage_check_handles_exception():
    """Test that coverage check handles exceptions gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        source_path = Path(tmpdir)
        
        with patch("subprocess.run", side_effect=Exception("Test error")):
            result = _run_coverage_check(source_path)
        
        assert result.passed is True  # Gracefully skip on error
        assert "quality:coverage" == result.name
        assert "Skipped" in result.detail


def test_run_bandit_security_check_passes_with_no_issues():
    """Test that bandit check passes when no security issues found."""
    with tempfile.TemporaryDirectory() as tmpdir:
        source_path = Path(tmpdir)
        (source_path / "src").mkdir()
        
        # Mock subprocess to simulate no issues
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = '{"results": []}'
        
        with patch("subprocess.run", return_value=mock_result):
            result = _run_bandit_security_check(source_path)
        
        assert result.passed is True
        assert "quality:bandit" == result.name
        assert "No security issues" in result.detail


def test_run_bandit_security_check_fails_with_issues():
    """Test that bandit check fails when security issues are found."""
    with tempfile.TemporaryDirectory() as tmpdir:
        source_path = Path(tmpdir)
        (source_path / "src").mkdir()
        
        # Mock subprocess to simulate issues found
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = json.dumps({
            "results": [
                {"issue_severity": "HIGH", "issue_text": "SQL injection"},
                {"issue_severity": "MEDIUM", "issue_text": "Hardcoded password"}
            ]
        })
        
        with patch("subprocess.run", return_value=mock_result):
            result = _run_bandit_security_check(source_path)
        
        assert result.passed is False
        assert "quality:bandit" == result.name
        assert "2 security issues" in result.detail


def test_run_bandit_security_check_skips_without_src():
    """Test that bandit check skips gracefully when no src directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        source_path = Path(tmpdir)
        
        result = _run_bandit_security_check(source_path)
        
        assert result.passed is True
        assert "quality:bandit" == result.name
        assert "skipped" in result.detail.lower()


def test_run_bandit_security_check_handles_not_installed():
    """Test that bandit check handles missing installation gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        source_path = Path(tmpdir)
        (source_path / "src").mkdir()
        
        with patch("subprocess.run", side_effect=FileNotFoundError()):
            result = _run_bandit_security_check(source_path)
        
        assert result.passed is True  # Gracefully skip if not installed
        assert "quality:bandit" == result.name
        assert "not installed" in result.detail.lower()


def test_run_bandit_security_check_respects_config():
    """Test that bandit check respects severity configuration."""
    with tempfile.TemporaryDirectory() as tmpdir:
        source_path = Path(tmpdir)
        (source_path / "src").mkdir()
        config_dir = source_path / "config"
        config_dir.mkdir()
        
        # Create config with high severity threshold
        config = {
            "security": {
                "severity_threshold": "high"
            }
        }
        with open(config_dir / "quality.json", "w") as f:
            json.dump(config, f)
        
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = '{"results": []}'
        
        with patch("subprocess.run", return_value=mock_result):
            result = _run_bandit_security_check(source_path)
        
        assert result.passed is True
        assert "quality:bandit" == result.name
