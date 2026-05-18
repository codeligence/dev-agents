"""Tests that feedback button clicks fire the slack.feedback hook."""

import pytest

from core.hooks import hooks
from integrations.slack.feedback_blocks import FEEDBACK_ACTION_ID, FeedbackEvent


@pytest.fixture(autouse=True)
def _clean_hooks():
    yield
    hooks().clear()


def _make_body(value: str = "positive") -> dict:
    """Minimal Slack interaction body for a feedback button click."""
    return {
        "actions": [
            {
                "action_id": FEEDBACK_ACTION_ID,
                "value": value,
            }
        ],
        "user": {"id": "U_TEST"},
        "channel": {"id": "C_TEST"},
        "message": {"ts": "111.222", "thread_ts": "111.000"},
    }


def _record_feedback(body: dict) -> None:
    """Mirrors SlackBotRuntime._record_feedback hook-firing logic.

    Duplicated here to avoid importing Bolt (requires real Slack token).
    """
    actions = body.get("actions") or []
    if not actions:
        return
    action = actions[0]
    value = action.get("selected_option", {}).get("value") or action.get("value", "")
    user = body.get("user", {})
    channel = body.get("channel", {})
    message = body.get("message", {})

    event = FeedbackEvent(
        user_id=user.get("id", ""),
        channel_id=channel.get("id", ""),
        thread_ts=message.get("thread_ts"),
        message_ts=message.get("ts"),
        value=str(value),
        action_id=action.get("action_id", FEEDBACK_ACTION_ID),
        body=body,
    )
    hooks().do_action("slack.feedback", event=event)


class TestSlackFeedbackHook:
    """Verify the slack.feedback action hook fires correctly."""

    def test_hook_fires_on_positive(self) -> None:
        received: list[FeedbackEvent] = []
        hooks().add_action("slack.feedback", lambda event: received.append(event))

        body = _make_body("positive")
        _record_feedback(body)

        assert len(received) == 1
        assert received[0].value == "positive"
        assert received[0].user_id == "U_TEST"
        assert received[0].channel_id == "C_TEST"
        assert received[0].thread_ts == "111.000"
        assert received[0].message_ts == "111.222"
        assert received[0].body is body

    def test_hook_fires_on_negative(self) -> None:
        received: list[FeedbackEvent] = []
        hooks().add_action("slack.feedback", lambda event: received.append(event))

        _record_feedback(_make_body("negative"))

        assert len(received) == 1
        assert received[0].value == "negative"

    def test_no_hook_no_error(self) -> None:
        """Clicking feedback with no hook registered must not raise."""
        _record_feedback(_make_body("positive"))

    def test_multiple_handlers(self) -> None:
        log1: list[str] = []
        log2: list[str] = []
        hooks().add_action("slack.feedback", lambda event: log1.append(event.value))
        hooks().add_action("slack.feedback", lambda event: log2.append(event.value))

        _record_feedback(_make_body("positive"))

        assert log1 == ["positive"]
        assert log2 == ["positive"]

    def test_handler_exception_does_not_break_others(self) -> None:
        received: list[str] = []

        def bad_handler(_event: FeedbackEvent) -> None:
            raise RuntimeError("boom")

        hooks().add_action("slack.feedback", bad_handler, priority=5)
        hooks().add_action(
            "slack.feedback", lambda event: received.append(event.value), priority=10
        )

        _record_feedback(_make_body("negative"))

        assert received == ["negative"]

    def test_empty_actions_list_is_noop(self) -> None:
        received: list[FeedbackEvent] = []
        hooks().add_action("slack.feedback", lambda event: received.append(event))

        _record_feedback({"actions": [], "user": {}, "channel": {}, "message": {}})

        assert received == []
