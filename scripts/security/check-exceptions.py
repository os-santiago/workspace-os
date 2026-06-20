#!/usr/bin/env python3
"""
Security exceptions validator
Checks if security exceptions are still valid and haven't expired
"""

import sys
from datetime import datetime
from pathlib import Path
import yaml


def check_exceptions(exceptions_file: Path) -> bool:
    """
    Check security exceptions for validity
    
    Returns:
        bool: True if all exceptions valid, False otherwise
    """
    if not exceptions_file.exists():
        print("No security exceptions file found - assuming clean state")
        return True
    
    with open(exceptions_file) as f:
        data = yaml.safe_load(f)
    
    if not data or 'exceptions' not in data or not data['exceptions']:
        print("✓ No active security exceptions")
        return True
    
    exceptions = data['exceptions']
    today = datetime.now().date()
    
    expired = []
    due_review = []
    valid = []
    
    for exc in exceptions:
        cve = exc.get('cve', 'UNKNOWN')
        expiry = exc.get('expiry_date')
        
        if expiry:
            expiry_date = datetime.fromisoformat(str(expiry)).date()
            
            if expiry_date < today:
                expired.append(cve)
            elif (expiry_date - today).days < 30:
                due_review.append(f"{cve} (expires {expiry_date})")
            else:
                valid.append(cve)
        else:
            valid.append(f"{cve} (no expiry)")
    
    # Report results
    if expired:
        print(f"\n✗ EXPIRED EXCEPTIONS ({len(expired)}):")
        for cve in expired:
            print(f"  - {cve}")
        print("\nAction required: Review and remove or extend these exceptions")
    
    if due_review:
        print(f"\n⚠ EXCEPTIONS DUE FOR REVIEW ({len(due_review)}):")
        for item in due_review:
            print(f"  - {item}")
    
    if valid:
        print(f"\n✓ VALID EXCEPTIONS ({len(valid)}):")
        for cve in valid:
            print(f"  - {cve}")
    
    # Fail if any expired
    if expired:
        return False
    
    return True


def main():
    """Main entry point"""
    project_root = Path(__file__).parent.parent.parent
    exceptions_file = project_root / '.security-exceptions.yml'
    
    print("Validating security exceptions...")
    
    if check_exceptions(exceptions_file):
        print("\n✓ Security exceptions check passed")
        sys.exit(0)
    else:
        print("\n✗ Security exceptions check failed")
        sys.exit(1)


if __name__ == '__main__':
    main()
