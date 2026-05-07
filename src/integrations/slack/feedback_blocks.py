"""Block Kit fragments for Slack feedback buttons."""

from typing import Any

FEEDBACK_ACTION_ID = "agent_response_feedback"


def build_feedback_blocks() -> list[dict[str, Any]]:
    """Return the Block Kit elements for thumbs-up / thumbs-down feedback.

    Attached to final-response messages so users can rate the agent's
    answer directly in Slack. The action id is wired to the runtime's
    feedback handler.
    """
    return [
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
