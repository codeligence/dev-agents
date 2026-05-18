"""Block Kit fragments and event model for Slack feedback buttons."""

from dataclasses import dataclass
from typing import Any

from core.hooks import hooks

FEEDBACK_ACTION_ID = "agent_response_feedback"


@dataclass(frozen=True)
class FeedbackEvent:
    """Payload passed to ``slack.feedback`` hook subscribers.

    Attributes:
        user_id: Slack user who clicked the button.
        channel_id: Channel where the rated message lives.
        thread_ts: Thread timestamp (may be None for top-level messages).
        message_ts: Timestamp of the rated message.
        value: ``"positive"`` or ``"negative"``.
        action_id: Block Kit action id (normally ``agent_response_feedback``).
        body: Full Slack interaction payload for advanced consumers.
    """

    user_id: str
    channel_id: str
    thread_ts: str | None
    message_ts: str | None
    value: str
    action_id: str
    body: dict[str, Any]


def build_feedback_blocks() -> list[dict[str, Any]]:
    """Return Block Kit elements for thumbs-up / thumbs-down feedback.

    The base blocks are built first, then passed through the
    ``slack.feedback.blocks`` filter hook so skills can add, remove,
    or replace buttons.
    """
    blocks: list[dict[str, Any]] = [
        {
            "type": "context_actions",
            "elements": [
                {
                    "type": "feedback_buttons",
                    "action_id": FEEDBACK_ACTION_ID,
                    "positive_button": {
                        "text": {"type": "plain_text", "text": "Helpful"},
                        "value": "positive",
                    },
                    "negative_button": {
                        "text": {"type": "plain_text", "text": "Not helpful"},
                        "value": "negative",
                    },
                }
            ],
        }
    ]
    return hooks().apply_filters("slack.feedback.blocks", blocks)
