"""Tests for the Slack feedback Block Kit fragment and FeedbackEvent."""

import pytest

from core.hooks import hooks
from integrations.slack.feedback_blocks import (
    FEEDBACK_ACTION_ID,
    FeedbackEvent,
    build_feedback_blocks,
)


@pytest.fixture(autouse=True)
def _clean_hooks():
    """Ensure a clean hook registry for every test."""
    yield
    hooks().clear()


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


class TestFeedbackEvent:
    """FeedbackEvent dataclass tests."""

    def test_creation(self) -> None:
        event = FeedbackEvent(
            user_id="U123",
            channel_id="C456",
            thread_ts="1234.5678",
            message_ts="1234.5679",
            value="positive",
            action_id=FEEDBACK_ACTION_ID,
            body={"raw": True},
        )
        assert event.user_id == "U123"
        assert event.value == "positive"
        assert event.body == {"raw": True}

    def test_frozen(self) -> None:
        event = FeedbackEvent(
            user_id="U1",
            channel_id="C1",
            thread_ts=None,
            message_ts=None,
            value="negative",
            action_id="x",
            body={},
        )
        with pytest.raises(AttributeError):
            event.value = "positive"  # type: ignore[misc]


class TestFeedbackBlocksFilterHook:
    """Tests for the slack.feedback.blocks filter hook."""

    def test_filter_can_add_block(self) -> None:
        extra = {"type": "section", "text": {"type": "mrkdwn", "text": "extra"}}

        def add_extra(blocks: list) -> list:
            return blocks + [extra]

        hooks().add_filter("slack.feedback.blocks", add_extra)
        blocks = build_feedback_blocks()
        assert len(blocks) == 2
        assert blocks[1] == extra

    def test_filter_can_replace_blocks(self) -> None:
        custom = [{"type": "actions", "elements": []}]

        def replace_all(_blocks: list) -> list:
            return custom

        hooks().add_filter("slack.feedback.blocks", replace_all)
        blocks = build_feedback_blocks()
        assert blocks == custom

    def test_no_filter_returns_defaults(self) -> None:
        blocks = build_feedback_blocks()
        assert len(blocks) == 1
        assert blocks[0]["type"] == "context_actions"
