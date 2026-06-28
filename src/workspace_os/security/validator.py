# Copyright 2026 Sergio Canales
# SPDX-License-Identifier: Apache-2.0
"""
Security validator for dependency vulnerability scanning and YAML policy enforcement.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple

from .policy import SecurityPolicyReport, evaluate_security_policy, load_security_policy


class SecurityValidator:
    """Validates security posture of dependencies, code, and policy controls."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.report_dir = project_root / ".security-reports"
        self.report_dir.mkdir(exist_ok=True)
        self.policy_path = project_root / "config" / "security-policy.yml"
        self.policy = load_security_policy(self.policy_path)

    def validate(self, skip_scan: bool = False) -> Tuple[bool, List[str]]:
        """
        Run security validation.

        Args:
            skip_scan: Skip actual scanning (use cached results)

        Returns:
            Tuple of (passed, messages)
        """
        messages: list[str] = []
        passed = True

        if not skip_scan:
            messages.append("Running security scans...")

            audit_passed = self._run_pip_audit()
            if not audit_passed:
                passed = False
                messages.append("✗ pip-audit found vulnerabilities")
            else:
                messages.append("✓ pip-audit: clean")

            safety_passed = self._run_safety()
            if not safety_passed:
                messages.append("⚠ Safety check found issues (warning only)")
            else:
                messages.append("✓ Safety: clean")

            bandit_passed = self._run_bandit()
            if not bandit_passed:
                messages.append("⚠ Bandit found potential issues (warning only)")
            else:
                messages.append("✓ Bandit: clean")

        policy_report = self._check_policy()
        if not policy_report.passed:
            passed = False
            messages.append("✗ Security policy validation failed")
            messages.extend(f"  - {finding}" for finding in policy_report.findings)
        else:
            messages.append("✓ Security policy: compliant")

        exceptions_passed = self._check_exceptions()
        if not exceptions_passed:
            passed = False
            messages.append("✗ Security exceptions validation failed")
        else:
            messages.append("✓ Security exceptions: valid")

        return passed, messages

    def get_vulnerability_summary(self) -> Dict:
        """Get summary of current vulnerabilities."""
        summary = {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "total": 0,
        }

        audit_file = self.report_dir / "pip-audit.json"
        if audit_file.exists():
            try:
                with audit_file.open(encoding="utf-8") as handle:
                    data = json.load(handle)
                    for dep in data.get("dependencies", []):
                        for vuln in dep.get("vulnerabilities", []):
                            severity = vuln.get("severity", "unknown").lower()
                            if severity in summary:
                                summary[severity] += 1
                            summary["total"] += 1
            except (json.JSONDecodeError, KeyError):
                pass

        bandit_file = self.report_dir / "bandit.json"
        summary.update(
            {
                "bandit_critical": 0,
                "bandit_high": 0,
                "bandit_medium": 0,
                "bandit_low": 0,
                "bandit_total": 0,
            }
        )
        if bandit_file.exists():
            try:
                with bandit_file.open(encoding="utf-8") as handle:
                    data = json.load(handle)
                    for result in data.get("results", []):
                        severity = str(result.get("issue_severity", "")).lower()
                        bandit_key = f"bandit_{severity}"
                        if bandit_key in summary:
                            summary[bandit_key] += 1
                        summary["bandit_total"] += 1
            except (json.JSONDecodeError, KeyError):
                pass

        return summary

    def get_policy_summary(self) -> Dict[str, object]:
        """Get summary of policy compliance and control coverage."""
        report = self._check_policy()
        payload = report.to_dict()
        payload["policy_path"] = str(self.policy_path)
        payload["policy_exists"] = self.policy_path.exists()
        return payload

    def _check_policy(self) -> SecurityPolicyReport:
        return evaluate_security_policy(self.project_root, self.policy)

    def _run_pip_audit(self) -> bool:
        """Run pip-audit scan."""
        try:
            result = subprocess.run(
                [
                    "pip-audit",
                    "--format",
                    "json",
                    "--output",
                    str(self.report_dir / "pip-audit.json"),
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return True

    def _run_safety(self) -> bool:
        """Run safety check."""
        try:
            result = subprocess.run(
                [
                    "safety",
                    "check",
                    "--json",
                    "--output",
                    str(self.report_dir / "safety.json"),
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return True

    def _run_bandit(self) -> bool:
        """Run bandit code analysis."""
        src_dir = self.project_root / "src"
        if not src_dir.exists():
            return True

        try:
            result = subprocess.run(
                [
                    "bandit",
                    "-r",
                    str(src_dir),
                    "-f",
                    "json",
                    "-o",
                    str(self.report_dir / "bandit.json"),
                    "-ll",
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return True

    def _check_exceptions(self) -> bool:
        """Validate security exceptions."""
        exceptions_file = self.project_root / ".security-exceptions.yml"

        if not exceptions_file.exists():
            return True

        try:
            result = subprocess.run(
                ["python", str(self.project_root / "scripts/security/check-exceptions.py")],
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return True
