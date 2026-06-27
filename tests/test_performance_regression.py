from pathlib import Path
import tempfile

from workspace_os.performance_regression import (
    PerformanceBenchmarkMeasurement,
    compare_performance_regression,
    capture_performance_baseline,
    default_baseline_path,
    load_performance_baseline,
    save_performance_baseline,
)


def _measurement(name: str, median_seconds: float, average_seconds: float | None = None) -> PerformanceBenchmarkMeasurement:
    average = average_seconds if average_seconds is not None else median_seconds
    return PerformanceBenchmarkMeasurement(
        name=name,
        description=name.replace("_", " "),
        sample_count=5,
        iterations_per_sample=25,
        average_seconds=average,
        median_seconds=median_seconds,
        min_seconds=median_seconds * 0.9,
        max_seconds=median_seconds * 1.1,
    )


def test_performance_regression_detects_slowdown():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        baseline_path = default_baseline_path(root)
        save_performance_baseline(
            (
                _measurement("decision_metrics_summary", 0.010),
                _measurement("task_outcome_metrics", 0.020),
            ),
            baseline_path,
            threshold_ratio=0.10,
        )

        report = compare_performance_regression(
            (
                _measurement("decision_metrics_summary", 0.0105),
                _measurement("task_outcome_metrics", 0.0205),
            ),
            baseline_path,
            threshold_ratio=0.10,
        )

    assert report.baseline_available
    assert report.benchmark_count == 2
    assert report.regression_count == 0
    assert report.missing_baseline_count == 0
    assert report.measurements[0].passed
    assert "Performance Regression Report" in report.render()


def test_performance_regression_flags_regression():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        baseline_path = default_baseline_path(root)
        save_performance_baseline(
            (
                _measurement("decision_metrics_summary", 0.010),
                _measurement("task_outcome_metrics", 0.020),
            ),
            baseline_path,
            threshold_ratio=0.10,
        )

        report = compare_performance_regression(
            (
                _measurement("decision_metrics_summary", 0.013),
                _measurement("task_outcome_metrics", 0.023),
            ),
            baseline_path,
            threshold_ratio=0.10,
        )

    assert report.regression_count == 2
    assert report.measurements[0].status == "regression"
    assert report.measurements[1].status == "regression"


def test_performance_regression_flags_regression_and_baseline_capture():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        memory = root / "memory.sqlite3"
        baseline_path = default_baseline_path(root)

        report = capture_performance_baseline(
            memory,
            root,
            baseline_path=baseline_path,
            threshold_ratio=0.10,
            sample_count=2,
            iterations_per_sample=1,
        )
        loaded = load_performance_baseline(baseline_path)

    assert loaded is not None
    assert loaded["benchmarks"]
    assert report.baseline_available
    assert report.benchmark_count == len(report.measurements)
    assert "Alert: none" in report.render()
