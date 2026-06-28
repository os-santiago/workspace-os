# Slack Notifications

WOS can send optional Slack notifications for cycle events without making Slack a hard dependency.

## Configuration

Set a webhook URL in the environment:

```powershell
$env:SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
```

Optionally restrict which events are emitted:

```powershell
$env:WOS_SLACK_EVENTS="start,complete,checkpoint,failure"
```

Default events:

- `start`
- `complete`
- `checkpoint`
- `failure`

If `SLACK_WEBHOOK_URL` is not set, WOS skips notifications silently.

## Events

- `start`: emitted when a cycle starts.
- `complete`: emitted when a cycle ends.
- `checkpoint`: emitted when a checkpoint is stored.
- `failure`: emitted when a checkpoint has failing gates.

The payload is a simple Slack webhook `{"text": ...}` message so the integration stays lightweight and portable.

