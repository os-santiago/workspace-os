# Performance Regression Detection

Issue: #62 - Performance Regression Detection

## Overview

Workspace OS provides a lightweight local benchmark report for critical paths so the operator can compare current performance against a saved baseline without introducing a remote telemetry stack.

The default benchmark set covers:

- decision summary aggregation
- task outcome aggregation
- queue utilization reporting

## Baseline Workflow

1. Open the web UI and use the `Baseline` action in the regression panel.
2. The baseline is stored locally under `.workspace-os/performance-baselines.json`.
3. Refresh the report to compare current results against the saved baseline.
4. If a measurement is more than 10% slower than baseline, the report flags a regression.

## Web UI

The dashboard exposes:

- JSON report: `/api/performance-regression`
- Markdown report: `/api/performance-regression.md`
- Baseline capture: `POST /api/performance-regression/baseline`

## Development Notes

The benchmark harness is compatible with `pytest-benchmark` for developers who want deeper local timing analysis. The core regression detector does not require remote services.

## Validation

```bash
pytest -q tests/test_performance_regression.py tests/test_web_server.py
```
