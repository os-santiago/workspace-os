#!/usr/bin/env python
"""Demo script showing progress bar and ETA functionality.

This script demonstrates the progress tracking features added to workspace-os
for long-running commands like validation, search, housekeeping, and cycle operations.
"""

from __future__ import annotations

import time
from pathlib import Path

from workspace_os.progress import (
    batch_progress,
    configure_progress,
    is_progress_enabled,
    progress,
)


def demo_simple_progress():
    """Demonstrate simple progress with known total."""
    print("\n=== Demo 1: Simple Progress Bar with ETA ===")
    print("Simulating a validation check with 10 steps...\n")

    with progress("Running validation checks", total=10) as tracker:
        for i in range(10):
            # Simulate work
            time.sleep(0.3)
            tracker.update(description=f"Validating source {i+1}/10")

        tracker.complete()

    print("\nValidation complete!")


def demo_indeterminate_progress():
    """Demonstrate indeterminate progress (unknown total)."""
    print("\n=== Demo 2: Indeterminate Progress (Spinner) ===")
    print("Simulating a search operation with unknown total...\n")

    with progress("Searching repositories") as tracker:
        for i in range(5):
            # Simulate work
            time.sleep(0.5)
            tracker.update(description=f"Searching repository {i+1}")

    print("\nSearch complete!")


def demo_batch_progress():
    """Demonstrate multiple concurrent progress bars."""
    print("\n=== Demo 3: Batch Progress (Multiple Operations) ===")
    print("Simulating multiple parallel operations...\n")

    with batch_progress() as tracker:
        # Add multiple tasks
        tracker.add_task("validation", "Validating workspace", total=5)
        tracker.add_task("search", "Searching sources", total=8)
        tracker.add_task("housekeeping", "Checking temporary files", total=3)

        # Simulate interleaved progress
        for i in range(5):
            time.sleep(0.2)
            tracker.update("validation")

        for i in range(8):
            time.sleep(0.15)
            tracker.update("search")

        for i in range(3):
            time.sleep(0.25)
            tracker.update("housekeeping")

        # Mark all complete
        tracker.complete("validation")
        tracker.complete("search")
        tracker.complete("housekeeping")

    print("\nAll operations complete!")


def demo_dynamic_total():
    """Demonstrate progress with dynamically set total."""
    print("\n=== Demo 4: Dynamic Total (Unknown at Start) ===")
    print("Simulating a file scan that discovers total count during execution...\n")

    with progress("Scanning workspace") as tracker:
        # Simulate discovering total files after initial scan
        time.sleep(0.5)
        tracker.set_total(15)
        tracker.update(description="Processing files")

        for i in range(15):
            time.sleep(0.2)
            tracker.update()

        tracker.complete()

    print("\nFile scan complete!")


def demo_custom_configuration():
    """Demonstrate custom progress configuration."""
    print("\n=== Demo 5: Custom Configuration ===")
    print("Progress bar with custom settings (no ETA, no percentage)...\n")

    # Configure to hide ETA and percentage
    configure_progress(show_eta=False, show_percentage=False)

    with progress("Custom progress display", total=5) as tracker:
        for i in range(5):
            time.sleep(0.4)
            tracker.update()

        tracker.complete()

    # Restore defaults
    configure_progress(show_eta=True, show_percentage=True)

    print("\nCustom configuration demo complete!")


def demo_real_world_validation():
    """Demonstrate a realistic validation scenario."""
    print("\n=== Demo 6: Real-World Validation Scenario ===")
    print("Simulating workspace validation with multiple checks...\n")

    sources = ["workspace-os", "adev", "scanales-kb", "homedir"]
    total_steps = len(sources) + 2  # sources + registry check + housekeeping

    with progress("Validating workspace", total=total_steps) as tracker:
        # Check registry
        tracker.update(description="Checking source registry")
        time.sleep(0.3)
        tracker.update()

        # Check each source
        for source in sources:
            tracker.update(description=f"Validating {source}")
            time.sleep(0.4)
            tracker.update()

        # Check housekeeping
        tracker.update(description="Checking for temporary artifacts")
        time.sleep(0.5)
        tracker.update()

        tracker.complete()

    print("\nWorkspace validation complete!")


def main():
    """Run all demo scenarios."""
    print("=" * 70)
    print("Progress Bar and ETA Demo for Workspace OS")
    print("=" * 70)

    if not is_progress_enabled():
        print("\nWARNING: Rich library not available or progress disabled.")
        print("Progress bars will not be displayed, but operations will continue.\n")

    try:
        demo_simple_progress()
        demo_indeterminate_progress()
        demo_batch_progress()
        demo_dynamic_total()
        demo_custom_configuration()
        demo_real_world_validation()

        print("\n" + "=" * 70)
        print("All demos complete!")
        print("=" * 70)

    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user.")


if __name__ == "__main__":
    main()
