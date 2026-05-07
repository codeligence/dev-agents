"""Debug logger for Slack feedback button clicks."""

from datetime import UTC, datetime
import json

from core.log import get_logger

_logger = get_logger("SlackFeedback")


def log_feedback(
    *,
    user_id: str,
    channel_id: str,
    thread_ts: str | None,
    message_ts: str | None,
    value: str,
    action_id: str,
) -> None:
    """Log a feedback event at DEBUG as a JSON payload."""
    payload = {
        "event": "slack_feedback",
        "ts": datetime.now(UTC).isoformat(),
        "user_id": user_id,
        "channel_id": channel_id,
        "thread_ts": thread_ts,
        "message_ts": message_ts,
        "value": value,
        "action_id": action_id,
    }
    _logger.debug(json.dumps(payload, default=str, separators=(",", ":")))
