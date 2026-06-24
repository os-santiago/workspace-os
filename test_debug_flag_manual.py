#!/usr/bin/env python
"""Manual test for --debug flag functionality."""

import subprocess
import sys

def test_debug_flag_help():
    """Verify --debug flag is present in help output."""
    result = subprocess.run(
        ["workspace", "cycle", "work", "--help"],
        capture_output=True,
        text=True,
    )
    assert "--debug" in result.stdout, "Missing --debug flag in help output"
    print("✓ --debug flag present in help")
    return True

def test_debug_flag_syntax():
    """Verify --debug flag is accepted (syntax check)."""
    # Just check that the flag is accepted without actually running a cycle
    result = subprocess.run(
        ["workspace", "cycle", "work", "--duration-minutes", "0.001", "--label", "test", "--objective", "test", "--debug"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    # Should not fail due to unknown argument
    assert "unrecognized arguments: --debug" not in result.stderr, "Flag not recognized"
    print("✓ --debug flag accepted")
    return True

if __name__ == "__main__":
    try:
        test_debug_flag_help()
        print("\nAll manual tests passed!")
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        sys.exit(1)
