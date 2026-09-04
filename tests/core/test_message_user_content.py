from datetime import UTC, datetime

from pydantic_ai import BinaryContent
from pydantic_ai.messages import ModelRequest

from core.message import MessageList
from entrypoints.slack_entrypoint.models import SlackFile, SlackMessage


def _msg(content: str, files: list[SlackFile]) -> SlackMessage:
    return SlackMessage(
        channel_id="C",
        message_id="111.0",
        user_id="U",
        username="Alice",
        content=content,
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        thread_ts="111.0",
        files=files,
    )


class TestUserContent:
    def test_no_files_returns_plain_string(self) -> None:
        msg = _msg("hello", [])
        assert isinstance(msg.get_user_content(), str)

    def test_binary_file_becomes_binary_content(self) -> None:
        msg = _msg(
            "look",
            [SlackFile("F1", "shot.png", "image/png", data=b"PNGDATA")],
        )
        parts = msg.get_user_content()
        assert isinstance(parts, list)
        assert isinstance(parts[0], str)  # formatted text
        assert isinstance(parts[1], BinaryContent)
        assert parts[1].media_type == "image/png"

    def test_text_file_is_inlined(self) -> None:
        msg = _msg(
            "code",
            [SlackFile("F2", "main.py", "text/x-python", data=b"print(1)")],
        )
        parts = msg.get_user_content()
        assert isinstance(parts, list)
        assert "print(1)" in parts[1]

    def test_missing_data_becomes_marker(self) -> None:
        msg = _msg(
            "big",
            [
                SlackFile(
                    "F3", "big.pdf", "application/pdf", data=None, note="too large"
                )
            ],
        )
        parts = msg.get_user_content()
        # Fallback marker keeps the file id so the agent can still fetch it.
        assert "too large" in parts[1]
        assert "id=F3" in parts[1]

    def test_chat_history_carries_multimodal_parts(self) -> None:
        msg = _msg("look", [SlackFile("F1", "s.png", "image/png", data=b"X")])
        history = MessageList([msg]).to_pydantic_chat_history()
        assert isinstance(history[0], ModelRequest)
        content = history[0].parts[0].content
        assert isinstance(content, list)
        assert any(isinstance(p, BinaryContent) for p in content)
