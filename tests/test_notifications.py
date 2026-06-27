from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from workspace_os.cycle import CycleCheckResult, CycleEvaluation, record_cycle_checkpoint, start_cycle, stop_cycle
from workspace_os.memory import WorkspaceMemoryStore
from workspace_os.notifications import format_cycle_notification, load_slack_events, send_slack_notification


class NotificationTests(unittest.TestCase):
    def test_format_cycle_notification_includes_cycle_context(self) -> None:
        text = format_cycle_notification(
            "start",
            {"id": 7, "label": "cycle-7", "objective": "ship Slack notifications"},
            objective="ship Slack notifications",
        )

        self.assertIn("WOS start: cycle-7 (cycle 7)", text)
        self.assertIn("objective=ship Slack notifications", text)

    def test_cycle_events_emit_slack_notifications_when_configured(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = WorkspaceMemoryStore(root / "memory.sqlite3")
            store.ensure_schema()
            evaluation = CycleEvaluation(
                health=(CycleCheckResult("health", True, "ok"),),
                stability=(CycleCheckResult("stability", True, "ok"),),
                security=(CycleCheckResult("security", True, "ok"),),
                quality=(CycleCheckResult("quality", False, "needs review"),),
            )

            with patch.dict(
                "os.environ",
                {
                    "SLACK_WEBHOOK_URL": "https://example.invalid/slack",
                    "WOS_SLACK_EVENTS": "start,complete,checkpoint,failure",
                },
                clear=False,
            ), patch("workspace_os.cycle.send_slack_notification") as send_notification:
                cycle_id = start_cycle(store, "cycle-1", "notify the team")
                record_cycle_checkpoint(store, evaluation, "iteration-1", iteration_number=1)
                stop_cycle(store)

        self.assertGreater(cycle_id, 0)
        self.assertGreaterEqual(send_notification.call_count, 3)
        self.assertTrue(any("WOS start:" in call.args[0] for call in send_notification.call_args_list))
        self.assertTrue(any("WOS checkpoint:" in call.args[0] for call in send_notification.call_args_list))
        self.assertTrue(any("WOS failure:" in call.args[0] for call in send_notification.call_args_list))
        self.assertTrue(any("WOS complete:" in call.args[0] for call in send_notification.call_args_list))

    def test_cycle_events_do_not_emit_without_webhook(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = WorkspaceMemoryStore(root / "memory.sqlite3")
            store.ensure_schema()

            with patch.dict("os.environ", {}, clear=True), patch("workspace_os.cycle.send_slack_notification") as send_notification:
                start_cycle(store, "cycle-1", "no webhook configured")

        send_notification.assert_not_called()

    def test_default_slack_events_include_core_cycle_events(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            events = load_slack_events()

        self.assertIn("start", events)
        self.assertIn("complete", events)
        self.assertIn("checkpoint", events)
        self.assertIn("failure", events)

    def test_send_slack_notification_uses_https_connection(self) -> None:
        with patch("workspace_os.notifications.http.client.HTTPSConnection") as connection_cls:
            connection = connection_cls.return_value
            response = connection.getresponse.return_value
            response.status = 204
            response.read.return_value = b""

            delivery = send_slack_notification("hello", webhook_url="https://example.invalid/slack")

        connection_cls.assert_called_once_with("example.invalid", timeout=5.0)
        connection.request.assert_called_once()
        self.assertTrue(delivery.ok)
