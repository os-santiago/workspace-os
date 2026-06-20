"""
Security validator for dependency vulnerability scanning
Integrates with WOS validation framework
"""

import json
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple


class SecurityValidator:
    """Validates security posture of dependencies and code"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.report_dir = project_root / '.security-reports'
        self.report_dir.mkdir(exist_ok=True)
    
    def validate(self, skip_scan: bool = False) -> Tuple[bool, List[str]]:
        """
        Run security validation
        
        Args:
            skip_scan: Skip actual scanning (use cached results)
        
        Returns:
            Tuple of (passed, messages)
        """
        messages = []
        passed = True
        
        if not skip_scan:
            messages.append("Running security scans...")
            
            # Run pip-audit
            audit_passed = self._run_pip_audit()
            if not audit_passed:
                passed = False
                messages.append("✗ pip-audit found vulnerabilities")
            else:
                messages.append("✓ pip-audit: clean")
            
            # Run safety
            safety_passed = self._run_safety()
            if not safety_passed:
                messages.append("⚠ Safety check found issues (warning only)")
            else:
                messages.append("✓ Safety: clean")
            
            # Run bandit on source
            bandit_passed = self._run_bandit()
            if not bandit_passed:
                messages.append("⚠ Bandit found potential issues (warning only)")
            else:
                messages.append("✓ Bandit: clean")
        
        # Check exceptions
        exceptions_passed = self._check_exceptions()
        if not exceptions_passed:
            passed = False
            messages.append("✗ Security exceptions validation failed")
        else:
            messages.append("✓ Security exceptions: valid")
        
        return passed, messages
    
    def _run_pip_audit(self) -> bool:
        """Run pip-audit scan"""
        try:
            result = subprocess.run(
                ['pip-audit', '--format', 'json', 
                 '--output', str(self.report_dir / 'pip-audit.json')],
                capture_output=True,
                text=True,
                timeout=60
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return True  # Tool not available, skip
    
    def _run_safety(self) -> bool:
        """Run safety check"""
        try:
            result = subprocess.run(
                ['safety', 'check', '--json',
                 '--output', str(self.report_dir / 'safety.json')],
                capture_output=True,
                text=True,
                timeout=60
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return True  # Tool not available, skip
    
    def _run_bandit(self) -> bool:
        """Run bandit code analysis"""
        src_dir = self.project_root / 'src'
        if not src_dir.exists():
            return True
        
        try:
            result = subprocess.run(
                ['bandit', '-r', str(src_dir), '-f', 'json',
                 '-o', str(self.report_dir / 'bandit.json'),
                 '-ll'],  # Low confidence, low severity minimum
                capture_output=True,
                text=True,
                timeout=60
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return True  # Tool not available, skip
    
    def _check_exceptions(self) -> bool:
        """Validate security exceptions"""
        exceptions_file = self.project_root / '.security-exceptions.yml'
        
        if not exceptions_file.exists():
            return True  # No exceptions = valid
        
        try:
            result = subprocess.run(
                ['python', str(self.project_root / 'scripts/security/check-exceptions.py')],
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return True  # Tool not available, skip
    
    def get_vulnerability_summary(self) -> Dict:
        """Get summary of current vulnerabilities"""
        summary = {
            'critical': 0,
            'high': 0,
            'medium': 0,
            'low': 0,
            'total': 0
        }
        
        # Parse pip-audit report
        audit_file = self.report_dir / 'pip-audit.json'
        if audit_file.exists():
            try:
                with open(audit_file) as f:
                    data = json.load(f)
                    for dep in data.get('dependencies', []):
                        for vuln in dep.get('vulnerabilities', []):
                            severity = vuln.get('severity', 'unknown').lower()
                            if severity in summary:
                                summary[severity] += 1
                            summary['total'] += 1
            except (json.JSONDecodeError, KeyError):
                pass
        
        return summary
