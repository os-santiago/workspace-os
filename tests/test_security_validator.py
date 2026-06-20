"""
Tests for security validator module
"""

import pytest
from pathlib import Path
from workspace_os.security.validator import SecurityValidator


def test_security_validator_init():
    """Test SecurityValidator initialization"""
    project_root = Path('.')
    validator = SecurityValidator(project_root)
    
    assert validator.project_root == project_root
    assert validator.report_dir == project_root / '.security-reports'


def test_get_vulnerability_summary_empty():
    """Test vulnerability summary with no reports"""
    validator = SecurityValidator(Path('.'))
    summary = validator.get_vulnerability_summary()
    
    assert summary['total'] == 0
    assert summary['critical'] == 0
    assert summary['high'] == 0
    assert summary['medium'] == 0
    assert summary['low'] == 0


def test_validate_returns_tuple():
    """Test validate method returns tuple"""
    validator = SecurityValidator(Path('.'))
    result = validator.validate(skip_scan=True)
    
    assert isinstance(result, tuple)
    assert len(result) == 2
    assert isinstance(result[0], bool)  # passed
    assert isinstance(result[1], list)  # messages


def test_check_exceptions_no_file():
    """Test exception checking with no exceptions file"""
    validator = SecurityValidator(Path('.'))
    result = validator._check_exceptions()
    
    # Should pass if no exceptions file exists
    assert result is True
