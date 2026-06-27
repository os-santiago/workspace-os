from __future__ import annotations

from dataclasses import dataclass
import http.client
import json
import os
from typing import Any
from urllib.parse import urlparse


DEFAULT_SLACK_EVENTS = {"start", "complete", "checkpoint", "failure", "error", "pr_created"}


@dataclass(frozen=True)
class NotificationDelivery:
    ok: bool
    error: str | None = None


def load_slack_webhook_url() -> str | None:
    url = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
    return url or None


def load_slack_events() -> set[str]:
    raw = os.environ.get("WOS_SLACK_EVENTS", "start,complete,checkpoint,failure,error,pr_created").strip()
    if not raw:
        return set()
    events = {part.strip().lower() for part in raw.split(",") if part.strip()}
    return events or DEFAULT_SLACK_EVENTS


def slack_notifications_enabled() -> bool:
    return load_slack_webhook_url() is not None


def format_cycle_notification(event: str, cycle: dict[str, Any] | None, **details: Any) -> str:
    label = str(cycle.get("label")) if cycle else "workspace cycle"
    objective = str(cycle.get("objective")) if cycle and cycle.get("objective") else ""
    cycle_id = cycle.get("id") if cycle else None
    prefix = f"WOS {event}: {label}"
    if cycle_id is not None:
        prefix = f"{prefix} (cycle {cycle_id})"
    if objective:
        prefix = f"{prefix} - {objective}"

    lines = [prefix]
    for key, value in details.items():
        if value is None:
            continue
        lines.append(f"{key}={value}")
    return "\n".join(lines).strip()


def send_slack_notification(text: str, webhook_url: str | None = None, timeout_seconds: float = 5.0) -> NotificationDelivery:
    url = webhook_url or load_slack_webhook_url()
    if not url:
        return NotificationDelivery(ok=False, error="Slack webhook is not configured.")
    payload = json.dumps({"text": text}, ensure_ascii=False).encode("utf-8")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return NotificationDelivery(ok=False, error="Slack webhook URL must be an absolute http(s) URL.")
    path = parsed.path or "/"
    if parsed.params:
        path = f"{path};{parsed.params}"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    connection_cls = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    connection = connection_cls(parsed.netloc, timeout=timeout_seconds)
    try:
        connection.request("POST", path, body=payload, headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        status = getattr(response, "status", 200)
        response.read()
        return NotificationDelivery(ok=200 <= int(status) < 300)
    except (http.client.HTTPException, TimeoutError, OSError) as exc:
        return NotificationDelivery(ok=False, error=str(exc))
    finally:
        try:
            connection.close()
        except OSError:
            pass
