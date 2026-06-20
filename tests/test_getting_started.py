"""
Tests for Getting Started guide functionality.

Validates that the commands and workflows documented in docs/GETTING_STARTED.md
work as expected.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
import subprocess
import pytest

from workspace_os.cli import main
from workspace_os.config import load_sources


class TestGettingStartedCommands:
    """Test suite for Getting Started guide commands."""

    def test_help_command_works(self):
        """Verify that workspace --help returns success."""
        # argparse --help raises SystemExit(0)
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0

    def test_status_command_with_config(self, tmp_path):
        """Test status command with minimal configuration."""
        # Create a minimal config
        config_path = tmp_path / "test.config.json"
        config_data = {
            "sources": [
                {
                    "name": "test-source",
                    "type": "product",
                    "responsibility": "Test repository",
                    "path": str(tmp_path),
                    "search": True,
                }
            ]
        }
        config_path.write_text(json.dumps(config_data, indent=2))

        # Initialize a git repo in tmp_path
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        # Run status command
        result = main(["--config", str(config_path), "status"])
        assert result == 0

    def test_search_command_basic(self, tmp_path):
        """Test search command with minimal setup."""
        # Create a test file
        test_file = tmp_path / "test.md"
        test_file.write_text("This is a test file with searchable content.")

        # Create minimal config
        config_path = tmp_path / "test.config.json"
        config_data = {
            "sources": [
                {
                    "name": "test-source",
                    "type": "product",
                    "responsibility": "Test repository",
                    "path": str(tmp_path),
                    "search": True,
                }
            ]
        }
        config_path.write_text(json.dumps(config_data, indent=2))

        # Run search command
        result = main(["--config", str(config_path), "search", "searchable"])
        assert result == 0

    def test_classify_command(self):
        """Test classify command with sample text."""
        result = main(["classify", "Agents must validate scripts before release."])
        assert result == 0

    def test_validate_command_with_config(self, tmp_path):
        """Test validate command with minimal configuration."""
        config_path = tmp_path / "test.config.json"
        config_data = {
            "sources": [
                {
                    "name": "test-source",
                    "type": "product",
                    "responsibility": "Test repository",
                    "path": str(tmp_path),
                    "search": True,
                }
            ]
        }
        config_path.write_text(json.dumps(config_data, indent=2))

        # Initialize git repo
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        # Run validate command
        result = main(["--config", str(config_path), "validate", "--skip-housekeeping"])
        assert result == 0

    def test_housekeeping_command(self, tmp_path):
        """Test housekeeping command with minimal setup."""
        config_path = tmp_path / "test.config.json"
        config_data = {
            "sources": [
                {
                    "name": "test-source",
                    "type": "product",
                    "responsibility": "Test repository",
                    "path": str(tmp_path),
                    "search": True,
                }
            ]
        }
        config_path.write_text(json.dumps(config_data, indent=2))

        # Run housekeeping command
        result = main(["--config", str(config_path), "housekeeping"])
        assert result == 0


class TestConfigurationSetup:
    """Test configuration setup as documented in Getting Started."""

    def test_load_example_configuration(self):
        """Verify example configuration can be loaded."""
        example_config = Path("config/workspace.sources.example.json")
        if not example_config.exists():
            pytest.skip("Example config not found")

        sources = load_sources(example_config)
        assert len(sources) > 0
        assert all(hasattr(s, "name") for s in sources)
        assert all(hasattr(s, "type") for s in sources)
        assert all(hasattr(s, "path") for s in sources)

    def test_create_local_configuration(self, tmp_path):
        """Test creating a local configuration from scratch."""
        config_path = tmp_path / "workspace.sources.local.json"
        config_data = {
            "sources": [
                {
                    "name": "workspace-os",
                    "type": "product",
                    "responsibility": "Product roadmap and implementation",
                    "path": ".",
                    "search": True,
                }
            ]
        }

        config_path.write_text(json.dumps(config_data, indent=2))
        sources = load_sources(config_path)

        assert len(sources) == 1
        assert sources[0].name == "workspace-os"
        assert sources[0].type == "product"


class TestWorkflowPatterns:
    """Test workflow patterns documented in Getting Started."""

    def test_daily_workflow_status_check(self, tmp_path):
        """Test the daily workflow status check pattern."""
        config_path = tmp_path / "test.config.json"
        config_data = {
            "sources": [
                {
                    "name": "test-source",
                    "type": "product",
                    "responsibility": "Test repository",
                    "path": str(tmp_path),
                    "search": True,
                }
            ]
        }
        config_path.write_text(json.dumps(config_data, indent=2))

        # Initialize git
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        # Step 1: Check status
        result = main(["--config", str(config_path), "status"])
        assert result == 0

        # Step 2: Search (even if no results)
        result = main(["--config", str(config_path), "search", "test"])
        assert result == 0

        # Step 3: Validate
        result = main(["--config", str(config_path), "validate", "--skip-housekeeping"])
        assert result == 0

    def test_context_building_pattern(self, tmp_path):
        """Test building context for agent delegation."""
        # Create test content
        test_file = tmp_path / "docs" / "test.md"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("# Test Documentation\n\nSome CI/CD guidance.")

        config_path = tmp_path / "test.config.json"
        config_data = {
            "sources": [
                {
                    "name": "test-source",
                    "type": "doctrine",
                    "responsibility": "Test doctrine",
                    "path": str(tmp_path),
                    "search": True,
                }
            ]
        }
        config_path.write_text(json.dumps(config_data, indent=2))

        # Build context
        result = main(["--config", str(config_path), "context", "CI/CD"])
        assert result == 0

    def test_capture_workflow(self, tmp_path):
        """Test capture command workflow."""
        # Create evidence source directory
        evidence_dir = tmp_path / "evidence"
        evidence_dir.mkdir()

        # Initialize git in evidence directory
        subprocess.run(["git", "init"], cwd=evidence_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=evidence_dir,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=evidence_dir,
            check=True,
            capture_output=True,
        )

        config_path = tmp_path / "test.config.json"
        config_data = {
            "sources": [
                {
                    "name": "test-kb",
                    "type": "evidence",
                    "responsibility": "Test knowledge base",
                    "path": str(evidence_dir),
                    "search": True,
                }
            ]
        }
        config_path.write_text(json.dumps(config_data, indent=2))

        # Test capture without write (dry run)
        result = main([
            "--config", str(config_path),
            "capture",
            "--type", "session",
            "--title", "Test session",
            "--text", "Test content"
        ])
        assert result == 0


class TestTroubleshootingScenarios:
    """Test troubleshooting scenarios from Getting Started."""

    def test_missing_source_handling(self, tmp_path):
        """Test that missing sources are reported correctly."""
        config_path = tmp_path / "test.config.json"
        config_data = {
            "sources": [
                {
                    "name": "missing-source",
                    "type": "product",
                    "responsibility": "Test repository",
                    "path": str(tmp_path / "nonexistent"),
                    "search": True,
                }
            ]
        }
        config_path.write_text(json.dumps(config_data, indent=2))

        # Status should still succeed but report missing
        result = main(["--config", str(config_path), "status"])
        assert result == 0

    def test_invalid_config_handling(self, tmp_path):
        """Test that invalid configuration is handled gracefully."""
        config_path = tmp_path / "invalid.json"
        config_path.write_text("{invalid json")

        result = main(["--config", str(config_path), "status"])
        assert result == 2  # Error exit code

    def test_module_invocation(self):
        """Test that module can be invoked with python -m."""
        result = subprocess.run(
            ["python", "-m", "workspace_os", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "Workspace OS" in result.stdout


def test_getting_started_doc_exists():
    """Verify the Getting Started documentation exists."""
    getting_started = Path("docs/GETTING_STARTED.md")
    assert getting_started.exists(), "Getting Started guide should exist"
    content = getting_started.read_text()

    # Verify key sections are present
    assert "# Getting Started" in content
    assert "Installation" in content
    assert "Prerequisites" in content
    assert "Your First Cycle" in content
    assert "Next Steps" in content
    assert "Troubleshooting" in content
    assert "Quick Reference" in content
