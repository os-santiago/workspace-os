#!/usr/bin/env bash
set -euo pipefail
WOS_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec python -m workspace_os --config "$WOS_ROOT/config/workspace.sources.example.json" "$@"
