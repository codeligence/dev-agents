"""Tests for the platform registry (detect, start, stop)."""

import os
from unittest.mock import AsyncMock, patch

import pytest

from integrations.platforms import detect_platforms, _create_service


class TestDetectPlatforms:
    def test_none_detected(self):
        with patch.dict(os.environ, {}, clear=True):
            assert detect_platforms() == []

    def test_email_detected(self):
        with patch.dict(os.environ, {
            "EMAIL_ADDRESS": "a@b.com",
            "EMAIL_PASSWORD": "x",
            "EMAIL_IMAP_HOST": "imap.example.com",
            "EMAIL_SMTP_HOST": "smtp.example.com",
        }, clear=True):
            assert "email" in detect_platforms()

    def test_email_needs_all_four(self):
        base = {
            "EMAIL_ADDRESS": "a@b.com",
            "EMAIL_PASSWORD": "x",
            "EMAIL_IMAP_HOST": "imap.example.com",
            "EMAIL_SMTP_HOST": "smtp.example.com",
        }
        for missing in base:
            env = {k: v for k, v in base.items() if k != missing}
            with patch.dict(os.environ, env, clear=True):
                assert "email" not in detect_platforms(), (
                    f"email should not be detected when {missing} is missing"
                )

    def test_mattermost_detected(self):
        with patch.dict(os.environ, {
            "MATTERMOST_URL": "https://mm.example.com",
            "MATTERMOST_TOKEN": "tok",
        }, clear=True):
            assert "mattermost" in detect_platforms()

    def test_mattermost_needs_both(self):
        with patch.dict(os.environ, {"MATTERMOST_URL": "https://mm"}, clear=True):
            assert "mattermost" not in detect_platforms()

    def test_telegram_detected(self):
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "123:ABC"}, clear=True):
            assert "telegram" in detect_platforms()

    def test_all_detected(self):
        with patch.dict(os.environ, {
            "EMAIL_ADDRESS": "a@b.com",
            "EMAIL_PASSWORD": "x",
            "EMAIL_IMAP_HOST": "imap.example.com",
            "EMAIL_SMTP_HOST": "smtp.example.com",
            "MATTERMOST_URL": "https://mm",
            "MATTERMOST_TOKEN": "tok",
            "TELEGRAM_BOT_TOKEN": "123:ABC",
        }, clear=True):
            result = detect_platforms()
            assert result == ["email", "mattermost", "telegram"]


class TestCreateService:
    def test_create_email(self):
        with patch.dict(os.environ, {
            "EMAIL_ADDRESS": "a@b.com",
            "EMAIL_PASSWORD": "x",
            "EMAIL_IMAP_HOST": "imap",
            "EMAIL_SMTP_HOST": "smtp",
        }):
            svc = _create_service("email")
            assert svc.name == "email"

    def test_create_mattermost(self):
        with patch.dict(os.environ, {
            "MATTERMOST_URL": "https://mm",
            "MATTERMOST_TOKEN": "tok",
        }):
            svc = _create_service("mattermost")
            assert svc.name == "mattermost"

    def test_create_telegram(self):
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "123:ABC"}):
            svc = _create_service("telegram")
            assert svc.name == "telegram"

    def test_create_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown platform"):
            _create_service("discord")
