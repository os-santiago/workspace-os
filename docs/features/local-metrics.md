# Local Metrics and Optional Exporters

Workspace OS keeps observability lightweight and local-first.

## What It Collects

- Cycle duration
- Checkpoint count
- Task success, failure, and partial rates
- Queue depth
- Agent utilization
- Basic blockage indicators

## How It Is Used

The web UI surfaces the summary from the local WOS state store. The same data is available as JSON and Markdown so it can be consumed from the CLI or from simple scripts.

## Optional Exporters

Exporters are opt-in and disabled unless explicitly configured with `WOS_METRICS_EXPORTERS`.

Supported exporters:

- `prometheus`
- `grafana-json`

Example:

```powershell
$env:WOS_METRICS_EXPORTERS = "prometheus,grafana-json"
workspace web
```

Then request the exporter endpoint:

```bash
curl "http://127.0.0.1:8765/api/metrics/export?format=prometheus"
```

## Principle

WOS should remain useful without any external observability stack. Exporters are there for users who want to connect WOS to their own tooling, not as a requirement for core operation.
