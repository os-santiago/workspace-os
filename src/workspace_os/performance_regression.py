from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from time import perf_counter
from typing import Any, Callable
import json

from workspace_os.agent_queue import AgentQueueTracker
from workspace_os.memory import WorkspaceMemoryStore


DEFAULT_THRESHOLD_RATIO = 0.10
DEFAULT_SAMPLE_COUNT = 5
DEFAULT_ITERATIONS_PER_SAMPLE = 25
DEFAULT_BASELINE_FILENAME = "performance-baselines.json"


@dataclass(frozen=True)
class PerformanceBenchmarkCase:
    name: str
    description: str
    runner: Callable[[], Any]


@dataclass(frozen=True)
class PerformanceBenchmarkMeasurement:
    name: str
    description: str
    sample_count: int
    iterations_per_sample: int
    average_seconds: float
    median_seconds: float
    min_seconds: float
    max_seconds: float
    baseline_average_seconds: float | None = None
    baseline_median_seconds: float | None = None
    slowdown_ratio: float | None = None
    passed: bool = True
    status: str = "ok"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "sample_count": self.sample_count,
            "iterations_per_sample": self.iterations_per_sample,
            "average_seconds": self.average_seconds,
            "median_seconds": self.median_seconds,
            "min_seconds": self.min_seconds,
            "max_seconds": self.max_seconds,
            "baseline_average_seconds": self.baseline_average_seconds,
            "baseline_median_seconds": self.baseline_median_seconds,
            "slowdown_ratio": self.slowdown_ratio,
            "passed": self.passed,
            "status": self.status,
        }


@dataclass(frozen=True)
class PerformanceRegressionReport:
    timestamp: str
    threshold_ratio: float
    baseline_path: str
    baseline_available: bool
    benchmark_count: int
    regression_count: int
    missing_baseline_count: int
    measurements: tuple[PerformanceBenchmarkMeasurement, ...]

    def to_dict(self) -> dict[str, Any]:
        alerts = [
            measurement.name
            for measurement in self.measurements
            if not measurement.passed and measurement.status == "regression"
        ]
        return {
            "timestamp": self.timestamp,
            "threshold_ratio": self.threshold_ratio,
            "baseline_path": self.baseline_path,
            "baseline_available": self.baseline_available,
            "benchmark_count": self.benchmark_count,
            "regression_count": self.regression_count,
            "missing_baseline_count": self.missing_baseline_count,
            "alerts": alerts,
            "measurements": [measurement.to_dict() for measurement in self.measurements],
        }

    def render(self) -> str:
        lines = [
            f"Performance Regression Report @ {self.timestamp}",
            f"Threshold: {self.threshold_ratio:.0%}",
            f"Baseline: {self.baseline_path or 'n/a'}",
            f"Baseline available: {'yes' if self.baseline_available else 'no'}",
            f"Benchmarks: {self.benchmark_count}",
            f"Regressions: {self.regression_count}",
            f"Missing baseline entries: {self.missing_baseline_count}",
            "",
            "Measurements:",
        ]
        for measurement in self.measurements:
            slowdown = (
                f"{measurement.slowdown_ratio:.0%}"
                if measurement.slowdown_ratio is not None
                else "n/a"
            )
            status = measurement.status.replace("_", " ")
            lines.append(
                f"- {measurement.name}: {status} | median={measurement.median_seconds:.6f}s "
                f"| avg={measurement.average_seconds:.6f}s | slowdown={slowdown}"
            )
        if self.regression_count == 0 and self.missing_baseline_count == 0:
            lines.extend(["", "Alert: none"])
        else:
            lines.append("")
            if self.regression_count > 0:
                lines.append("Alerts:")
                for measurement in self.measurements:
                    if measurement.status == "regression":
                        lines.append(
                            f"- {measurement.name} exceeded threshold by {measurement.slowdown_ratio:.0%}"
                        )
            if self.missing_baseline_count > 0:
                lines.append("Baseline gaps:")
                for measurement in self.measurements:
                    if measurement.status == "baseline_missing":
                        lines.append(f"- {measurement.name}")
        return "\n".join(lines) + "\n"


def default_baseline_path(workspace_root: Path) -> Path:
    return workspace_root / ".workspace-os" / DEFAULT_BASELINE_FILENAME


def build_performance_regression_report(
    memory_path: Path,
    workspace_root: Path,
    baseline_path: Path | None = None,
    threshold_ratio: float = DEFAULT_THRESHOLD_RATIO,
    sample_count: int = DEFAULT_SAMPLE_COUNT,
    iterations_per_sample: int = DEFAULT_ITERATIONS_PER_SAMPLE,
) -> PerformanceRegressionReport:
    store = WorkspaceMemoryStore(memory_path)
    store.ensure_schema()
    tracker = AgentQueueTracker(workspace_root)
    cases = _benchmark_cases(store, tracker)
    measurements = measure_benchmark_cases(cases, sample_count=sample_count, iterations_per_sample=iterations_per_sample)
    return compare_performance_regression(
        measurements,
        baseline_path=baseline_path or default_baseline_path(workspace_root),
        threshold_ratio=threshold_ratio,
    )


def capture_performance_baseline(
    memory_path: Path,
    workspace_root: Path,
    baseline_path: Path | None = None,
    threshold_ratio: float = DEFAULT_THRESHOLD_RATIO,
    sample_count: int = DEFAULT_SAMPLE_COUNT,
    iterations_per_sample: int = DEFAULT_ITERATIONS_PER_SAMPLE,
) -> PerformanceRegressionReport:
    store = WorkspaceMemoryStore(memory_path)
    store.ensure_schema()
    tracker = AgentQueueTracker(workspace_root)
    cases = _benchmark_cases(store, tracker)
    measurements = measure_benchmark_cases(cases, sample_count=sample_count, iterations_per_sample=iterations_per_sample)
    resolved_baseline_path = baseline_path or default_baseline_path(workspace_root)
    save_performance_baseline(
        measurements,
        resolved_baseline_path,
        threshold_ratio=threshold_ratio,
        sample_count=sample_count,
        iterations_per_sample=iterations_per_sample,
    )
    return compare_performance_regression(
        measurements,
        baseline_path=resolved_baseline_path,
        threshold_ratio=threshold_ratio,
    )


def measure_benchmark_cases(
    cases: tuple[PerformanceBenchmarkCase, ...],
    sample_count: int = DEFAULT_SAMPLE_COUNT,
    iterations_per_sample: int = DEFAULT_ITERATIONS_PER_SAMPLE,
) -> tuple[PerformanceBenchmarkMeasurement, ...]:
    return tuple(
        _measure_case(case, sample_count=sample_count, iterations_per_sample=iterations_per_sample)
        for case in cases
    )


def compare_performance_regression(
    measurements: tuple[PerformanceBenchmarkMeasurement, ...],
    baseline_path: Path,
    threshold_ratio: float = DEFAULT_THRESHOLD_RATIO,
) -> PerformanceRegressionReport:
    baseline_payload = load_performance_baseline(baseline_path)
    baseline_records = {
        str(item["name"]): item for item in baseline_payload.get("benchmarks", [])
    } if baseline_payload else {}

    compared_measurements: list[PerformanceBenchmarkMeasurement] = []
    regression_count = 0
    missing_baseline_count = 0
    for measurement in measurements:
        baseline_record = baseline_records.get(measurement.name)
        if baseline_record is None:
            compared_measurements.append(
                replace(
                    measurement,
                    baseline_average_seconds=None,
                    baseline_median_seconds=None,
                    slowdown_ratio=None,
                    passed=True,
                    status="baseline_missing",
                ),
            )
            missing_baseline_count += 1
            continue
        baseline_average = float(baseline_record.get("average_seconds", 0.0))
        baseline_median = float(baseline_record.get("median_seconds", 0.0))
        slowdown_ratio = _slowdown_ratio(measurement.median_seconds, baseline_median)
        passed = slowdown_ratio is None or slowdown_ratio <= threshold_ratio
        status = "ok" if passed else "regression"
        if not passed:
            regression_count += 1
        compared_measurements.append(
            replace(
                measurement,
                baseline_average_seconds=baseline_average,
                baseline_median_seconds=baseline_median,
                slowdown_ratio=slowdown_ratio,
                passed=passed,
                status=status,
            ),
        )

    return PerformanceRegressionReport(
        timestamp=_utc_now(),
        threshold_ratio=threshold_ratio,
        baseline_path=str(baseline_path),
        baseline_available=baseline_payload is not None,
        benchmark_count=len(measurements),
        regression_count=regression_count,
        missing_baseline_count=missing_baseline_count,
        measurements=tuple(compared_measurements),
    )


def save_performance_baseline(
    measurements: tuple[PerformanceBenchmarkMeasurement, ...],
    baseline_path: Path,
    threshold_ratio: float = DEFAULT_THRESHOLD_RATIO,
    sample_count: int = DEFAULT_SAMPLE_COUNT,
    iterations_per_sample: int = DEFAULT_ITERATIONS_PER_SAMPLE,
) -> None:
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": _utc_now(),
        "threshold_ratio": threshold_ratio,
        "sample_count": sample_count,
        "iterations_per_sample": iterations_per_sample,
        "benchmarks": [
            {
                "name": measurement.name,
                "description": measurement.description,
                "average_seconds": measurement.average_seconds,
                "median_seconds": measurement.median_seconds,
                "min_seconds": measurement.min_seconds,
                "max_seconds": measurement.max_seconds,
            }
            for measurement in measurements
        ],
    }
    baseline_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def load_performance_baseline(baseline_path: Path) -> dict[str, Any] | None:
    if not baseline_path.exists():
        return None
    try:
        return json.loads(baseline_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _benchmark_cases(store: WorkspaceMemoryStore, tracker: AgentQueueTracker) -> tuple[PerformanceBenchmarkCase, ...]:
    return (
        PerformanceBenchmarkCase(
            name="decision_metrics_summary",
            description="Summarize decision log entries.",
            runner=lambda: store.decision_metrics_summary(limit=20),
        ),
        PerformanceBenchmarkCase(
            name="task_outcome_metrics",
            description="Aggregate task outcome metrics.",
            runner=lambda: store.task_outcome_metrics(limit=20),
        ),
        PerformanceBenchmarkCase(
            name="utilization_report",
            description="Summarize queue utilization.",
            runner=lambda: tracker.utilization_report(),
        ),
    )


def _measure_case(
    case: PerformanceBenchmarkCase,
    sample_count: int,
    iterations_per_sample: int,
) -> PerformanceBenchmarkMeasurement:
    samples: list[float] = []
    for _ in range(sample_count):
        started = perf_counter()
        for _ in range(iterations_per_sample):
            case.runner()
        elapsed = perf_counter() - started
        samples.append(elapsed / max(1, iterations_per_sample))
    average_seconds = sum(samples) / len(samples) if samples else 0.0
    median_seconds = median(samples) if samples else 0.0
    return PerformanceBenchmarkMeasurement(
        name=case.name,
        description=case.description,
        sample_count=sample_count,
        iterations_per_sample=iterations_per_sample,
        average_seconds=average_seconds,
        median_seconds=median_seconds,
        min_seconds=min(samples) if samples else 0.0,
        max_seconds=max(samples) if samples else 0.0,
    )


def _slowdown_ratio(current_seconds: float, baseline_seconds: float) -> float | None:
    if baseline_seconds <= 0:
        return None
    return max(0.0, (current_seconds - baseline_seconds) / baseline_seconds)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
