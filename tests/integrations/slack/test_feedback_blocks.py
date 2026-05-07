"""Tests for the Slack feedback Block Kit fragment."""

from integrations.slack.feedback_blocks import (
    FEEDBACK_ACTION_ID,
    build_feedback_blocks,
)


def test_feedback_blocks_shape() -> None:
    blocks = build_feedback_blocks()
    assert len(blocks) == 1
    block = blocks[0]
    assert block["type"] == "context_actions"
    elements = block["elements"]
    assert len(elements) == 1
    element = elements[0]
    assert element["type"] == "feedback_buttons"
    assert element["action_id"] == FEEDBACK_ACTION_ID
    assert element["positive_button"]["value"] == "positive"
    assert element["negative_button"]["value"] == "negative"
