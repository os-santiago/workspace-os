from __future__ import annotations

from dataclasses import dataclass

from workspace_os.config import Source
from workspace_os.git_status import inspect_source
from workspace_os.housekeeping import find_temporary_artifacts
from workspace_os.progress import progress


@dataclass(frozen=True)
class ValidationResult:
    name: str
    passed: bool
    detail: str


def validate_workspace(sources: list[Source], include_housekeeping: bool = True) -> list[ValidationResult]:
    total_steps = len(sources) + (1 if include_housekeeping else 0) + 1  # sources + housekeeping + registry check

    with progress("Validating workspace", total=total_steps) as tracker:
        tracker.update(description="Checking source registry")
        results = [_validate_sources_exist(sources)]
        tracker.update()

        tracker.update(description="Validating source states")
        results.extend(_validate_source_states(sources))

        if include_housekeeping:
            tracker.update(description="Checking for temporary artifacts")
            results.append(_validate_housekeeping(sources))
            tracker.update()

        tracker.complete()

    return results


def validation_failed(results: list[ValidationResult]) -> bool:
    return any(not result.passed for result in results)


def _validate_sources_exist(sources: list[Source]) -> ValidationResult:
    if not sources:
        return ValidationResult("source-registry", False, "No sources are configured.")
    return ValidationResult("source-registry", True, f"{len(sources)} sources configured.")


def _validate_source_states(sources: list[Source]) -> list[ValidationResult]:
    results: list[ValidationResult] = []
    for source in sources:
        status = inspect_source(source)
        if not status.exists:
            results.append(ValidationResult(f"source:{source.name}", False, "Configured path is missing."))
            continue
        if not status.is_git_repo:
            results.append(ValidationResult(f"source:{source.name}", False, "Configured path is not a Git repository."))
            continue
        if status.error:
            results.append(ValidationResult(f"source:{source.name}", False, "Git status inspection failed."))
            continue
        results.append(ValidationResult(f"source:{source.name}", True, f"{status.state} on {status.branch}."))
    return results


def _validate_housekeeping(sources: list[Source]) -> ValidationResult:
    findings = find_temporary_artifacts(sources=sources, max_results=1)
    if findings:
        finding = findings[0]
        return ValidationResult(
            "housekeeping",
            False,
            f"Temporary artifact found at {finding.source_name}:{finding.path}.",
        )
    return ValidationResult("housekeeping", True, "No temporary artifacts found.")
