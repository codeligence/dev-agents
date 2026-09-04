from unittest.mock import AsyncMock, MagicMock

import pytest

from integrations.slack import slack_client_service as scs_module
from integrations.slack.slack_client_service import SlackClientService


class _FakeContent:
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = chunks

    async def iter_chunked(self, _size: int):  # noqa: ANN201
        for chunk in self._chunks:
            yield chunk


class _FakeResponse:
    def __init__(self, chunks: list[bytes], headers: dict | None = None) -> None:
        self.content = _FakeContent(chunks)
        self.headers = headers or {}

    def raise_for_status(self) -> None:
        pass

    async def __aenter__(self) -> "_FakeResponse":
        return self

    async def __aexit__(self, *args: object) -> bool:
        return False


class _FakeSession:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response

    def get(self, _url: str) -> _FakeResponse:
        return self._response

    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, *args: object) -> bool:
        return False


def _patch_session(monkeypatch: pytest.MonkeyPatch, response: _FakeResponse) -> None:
    monkeypatch.setattr(
        scs_module.aiohttp,
        "ClientSession",
        lambda **_kwargs: _FakeSession(response),
    )


@pytest.fixture
def slack_config() -> MagicMock:
    cfg = MagicMock()
    cfg.get_bot_token.return_value = "xoxb-test"
    cfg.get_app_token.return_value = "xapp-test"
    cfg.get_always_respond.return_value = False
    cfg.get_attachments_enabled.return_value = True
    cfg.get_attachment_max_size_mb.return_value = 25
    cfg.get_attachment_max_inline_text_kb.return_value = 50
    return cfg


@pytest.fixture
def service(slack_config: MagicMock) -> SlackClientService:
    svc = SlackClientService(slack_config)
    svc.bot_id = "BOT123"
    # Avoid real API calls during message construction.
    svc.get_user_real_name = AsyncMock(return_value="Alice")  # type: ignore[method-assign]
    svc.replace_user_mentions_with_names = AsyncMock(  # type: ignore[method-assign]
        side_effect=lambda text: text
    )
    return svc


def _msg(files: list[dict]) -> dict:
    return {
        "ts": "111.0",
        "user": "U1",
        "text": "see attached",
        "thread_ts": "111.0",
        "files": files,
    }


class TestCreateSlackMessageFromApi:
    @pytest.mark.asyncio
    async def test_supported_file_is_downloaded(
        self, service: SlackClientService
    ) -> None:
        service.download_file_content = AsyncMock(return_value=b"PNGDATA")  # type: ignore[method-assign]
        slack_msg = _msg(
            [
                {
                    "id": "F1",
                    "name": "shot.png",
                    "mimetype": "image/png",
                    "size": 100,
                    "url_private_download": "https://files.slack.com/F1",
                }
            ]
        )

        result = await service.create_slack_message_from_api(slack_msg, "C1")

        assert len(result.files) == 1
        f = result.files[0]
        assert f.data == b"PNGDATA"
        assert f.note is None
        service.download_file_content.assert_awaited_once_with(
            "https://files.slack.com/F1", 25 * 1024 * 1024
        )

    @pytest.mark.asyncio
    async def test_unsupported_type_is_not_downloaded(
        self, service: SlackClientService
    ) -> None:
        service.download_file_content = AsyncMock()  # type: ignore[method-assign]
        slack_msg = _msg(
            [
                {
                    "id": "F2",
                    "name": "archive.zip",
                    "mimetype": "application/zip",
                    "size": 100,
                    "url_private_download": "https://files.slack.com/F2",
                }
            ]
        )

        result = await service.create_slack_message_from_api(slack_msg, "C1")

        assert result.files[0].data is None
        service.download_file_content.assert_not_called()

    @pytest.mark.asyncio
    async def test_oversized_file_is_skipped_with_note(
        self, service: SlackClientService
    ) -> None:
        service.download_file_content = AsyncMock()  # type: ignore[method-assign]
        slack_msg = _msg(
            [
                {
                    "id": "F3",
                    "name": "big.pdf",
                    "mimetype": "application/pdf",
                    "size": 26 * 1024 * 1024,
                    "url_private_download": "https://files.slack.com/F3",
                }
            ]
        )

        result = await service.create_slack_message_from_api(slack_msg, "C1")

        assert result.files[0].data is None
        assert "too large" in (result.files[0].note or "")
        service.download_file_content.assert_not_called()

    @pytest.mark.asyncio
    async def test_text_file_uses_tighter_inline_cap(
        self, service: SlackClientService
    ) -> None:
        # 60 KB text file: within the 25 MB binary cap but over the 50 KB
        # inline-text cap.
        service.download_file_content = AsyncMock()  # type: ignore[method-assign]
        slack_msg = _msg(
            [
                {
                    "id": "F5",
                    "name": "big.log",
                    "mimetype": "text/plain",
                    "size": 60 * 1024,
                    "url_private_download": "https://files.slack.com/F5",
                }
            ]
        )

        result = await service.create_slack_message_from_api(slack_msg, "C1")

        assert result.files[0].data is None
        assert result.files[0].note == "too large (>50 KB)"
        service.download_file_content.assert_not_called()

    @pytest.mark.asyncio
    async def test_text_file_within_cap_downloads_with_text_cap(
        self, service: SlackClientService
    ) -> None:
        service.download_file_content = AsyncMock(return_value=b"hello")  # type: ignore[method-assign]
        slack_msg = _msg(
            [
                {
                    "id": "F6",
                    "name": "notes.txt",
                    "mimetype": "text/plain",
                    "size": 5,
                    "url_private_download": "https://files.slack.com/F6",
                }
            ]
        )

        result = await service.create_slack_message_from_api(slack_msg, "C1")

        assert result.files[0].data == b"hello"
        service.download_file_content.assert_awaited_once_with(
            "https://files.slack.com/F6", 50 * 1024
        )

    @pytest.mark.asyncio
    async def test_disabled_skips_all_downloads(self, slack_config: MagicMock) -> None:
        slack_config.get_attachments_enabled.return_value = False
        svc = SlackClientService(slack_config)
        svc.bot_id = "BOT123"
        svc.get_user_real_name = AsyncMock(return_value="Alice")  # type: ignore[method-assign]
        svc.replace_user_mentions_with_names = AsyncMock(side_effect=lambda t: t)  # type: ignore[method-assign]
        svc.download_file_content = AsyncMock()  # type: ignore[method-assign]
        slack_msg = _msg(
            [
                {
                    "id": "F4",
                    "name": "shot.png",
                    "mimetype": "image/png",
                    "size": 100,
                    "url_private_download": "https://files.slack.com/F4",
                }
            ]
        )

        result = await svc.create_slack_message_from_api(slack_msg, "C1")

        assert result.files[0].data is None
        assert result.files[0].note == "attachment processing disabled"
        svc.download_file_content.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_files_yields_empty_list(
        self, service: SlackClientService
    ) -> None:
        result = await service.create_slack_message_from_api(_msg([]), "C1")
        assert result.files == []

    @pytest.mark.asyncio
    async def test_malformed_metadata_does_not_crash(
        self, service: SlackClientService
    ) -> None:
        # Null mimetype and a non-numeric size must not abort thread processing.
        service.download_file_content = AsyncMock()  # type: ignore[method-assign]
        slack_msg = _msg(
            [
                {
                    "id": "F9",
                    "name": "weird",
                    "mimetype": None,
                    "size": "not-a-number",
                    "url_private_download": "https://files.slack.com/F9",
                }
            ]
        )

        result = await service.create_slack_message_from_api(slack_msg, "C1")

        # Falls back to octet-stream (unsupported) → not downloaded, no crash.
        assert len(result.files) == 1
        assert result.files[0].mimetype == "application/octet-stream"
        assert result.files[0].data is None
        service.download_file_content.assert_not_called()


class TestCoerceSize:
    def test_valid_int(self) -> None:
        assert SlackClientService._coerce_size(1234) == 1234

    def test_numeric_string(self) -> None:
        assert SlackClientService._coerce_size("1234") == 1234

    def test_none_and_garbage_fall_back_to_zero(self) -> None:
        assert SlackClientService._coerce_size(None) == 0
        assert SlackClientService._coerce_size("abc") == 0

    def test_negative_clamped_to_zero(self) -> None:
        assert SlackClientService._coerce_size(-5) == 0


class TestDownloadFileContent:
    _URL = "https://files.slack.com/files-pri/T1-F1/download/file.png"

    @pytest.mark.asyncio
    async def test_rejects_non_https(self, service: SlackClientService) -> None:
        assert await service.download_file_content("http://files.slack.com/F1") is None

    @pytest.mark.asyncio
    async def test_rejects_non_slack_host(self, service: SlackClientService) -> None:
        # The bearer bot token must never be sent to a non-Slack host.
        assert await service.download_file_content("https://evil.example/F1") is None
        assert (
            await service.download_file_content(
                "https://files.slack.com.evil.example/F1"
            )
            is None
        )

    @pytest.mark.asyncio
    async def test_returns_body_within_cap(
        self, service: SlackClientService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_session(monkeypatch, _FakeResponse([b"abc", b"def"]))
        assert await service.download_file_content(self._URL, 100) == b"abcdef"

    @pytest.mark.asyncio
    async def test_no_cap_reads_full_body(
        self, service: SlackClientService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_session(monkeypatch, _FakeResponse([b"a" * 100]))
        assert await service.download_file_content(self._URL) == b"a" * 100

    @pytest.mark.asyncio
    async def test_rejects_oversized_content_length(
        self, service: SlackClientService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_session(
            monkeypatch,
            _FakeResponse([b"x"], headers={"Content-Length": "999"}),
        )
        assert await service.download_file_content(self._URL, 10) is None

    @pytest.mark.asyncio
    async def test_aborts_when_streamed_body_exceeds_cap(
        self, service: SlackClientService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # No Content-Length header (under-reported metadata): the cap must still
        # be enforced while reading the body.
        _patch_session(monkeypatch, _FakeResponse([b"abc", b"defgh"]))
        assert await service.download_file_content(self._URL, 5) is None
