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


def validate_workspace(
    sources: list[Source],
    include_housekeeping: bool = True,
    include_smoke_queries: bool = False,
) -> list[ValidationResult]:
    results = [_validate_sources_exist(sources), *_validate_source_states(sources)]
    if include_housekeeping:
        results.append(_validate_housekeeping(sources))
    if include_smoke_queries:
        results.extend(_validate_smoke_queries())
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
            if source.required:
                results.append(ValidationResult(f"source:{source.name}", False, "Configured path is missing."))
            else:
                results.append(ValidationResult(f"source:{source.name}", True, "Optional path is missing."))
            continue
        if not status.is_git_repo:
            if source.required:
                results.append(ValidationResult(f"source:{source.name}", False, "Configured path is not a Git repository."))
            else:
                results.append(ValidationResult(f"source:{source.name}", True, "Optional path is not a Git repository."))
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


def _validate_smoke_queries() -> list[ValidationResult]:
    from workspace_os.smoke import run_smoke_regression_checks

    smoke_results = run_smoke_regression_checks()
    return [
        ValidationResult(f"smoke:{result.name}", result.passed, result.detail)
        for result in smoke_results
    ]
