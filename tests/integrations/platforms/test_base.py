"""Tests for shared helpers on BasePlatformService.

The warning tests install a real logging.Logger via monkeypatch and use
caplog so they don't depend on the conftest stub of ``core.log.get_logger``
— the assertions run against actual log records the way they would in
production.
"""

from unittest.mock import patch
import logging
import os

import pytest

from integrations.platforms import base
from integrations.platforms.base import BasePlatformService


class TestEnvFlag:
    @pytest.mark.parametrize(
        "raw",
        ["true", "True", "TRUE", "1", "yes", "YES", "on", "ON"],
    )
    def test_truthy_values(self, raw):
        with patch.dict(os.environ, {"X_FLAG": raw}, clear=True):
            assert BasePlatformService.env_flag("X_FLAG") is True

    @pytest.mark.parametrize(
        "raw",
        ["false", "False", "FALSE", "0", "no", "NO", "off", "OFF"],
    )
    def test_falsy_values(self, raw):
        with patch.dict(os.environ, {"X_FLAG": raw}, clear=True):
            assert BasePlatformService.env_flag("X_FLAG", default=True) is False

    def test_unset_returns_default(self):
        with patch.dict(os.environ, {}, clear=True):
            assert BasePlatformService.env_flag("X_FLAG") is False
            assert BasePlatformService.env_flag("X_FLAG", default=True) is True

    def test_empty_returns_default(self):
        with patch.dict(os.environ, {"X_FLAG": "   "}, clear=True):
            assert BasePlatformService.env_flag("X_FLAG") is False
            assert BasePlatformService.env_flag("X_FLAG", default=True) is True

    def test_whitespace_around_value_is_tolerated(self):
        with patch.dict(os.environ, {"X_FLAG": "  true  "}, clear=True):
            assert BasePlatformService.env_flag("X_FLAG") is True

    def test_unparseable_value_warns_and_falls_back(self, caplog, monkeypatch):
        """Unparseable values must log a warning so operators notice typos."""
        # Install a real logger for this test so we validate actual log
        # output, not interactions with the conftest's MagicMock stub.
        real_logger = logging.getLogger("test.integrations.platforms.base")
        real_logger.propagate = True
        monkeypatch.setattr(base, "logger", real_logger)

        caplog.set_level(logging.WARNING, logger=real_logger.name)
        with patch.dict(os.environ, {"X_FLAG": "yep"}, clear=True):
            assert BasePlatformService.env_flag("X_FLAG", default=True) is True

        warnings = [
            r
            for r in caplog.records
            if r.levelno == logging.WARNING and r.name == real_logger.name
        ]
        assert warnings, "expected a warning record to be captured"
        msg = warnings[-1].getMessage()
        assert "X_FLAG" in msg, "warning should name the env var"
        assert "yep" in msg, "warning should include the offending raw value"

    def test_parseable_values_do_not_warn(self, caplog, monkeypatch):
        """Valid values must not warn — only unparseable ones should."""
        real_logger = logging.getLogger("test.integrations.platforms.base")
        real_logger.propagate = True
        monkeypatch.setattr(base, "logger", real_logger)

        caplog.set_level(logging.WARNING, logger=real_logger.name)
        with patch.dict(os.environ, {"X_FLAG": "true"}, clear=True):
            BasePlatformService.env_flag("X_FLAG")
        with patch.dict(os.environ, {"X_FLAG": "false"}, clear=True):
            BasePlatformService.env_flag("X_FLAG")
        with patch.dict(os.environ, {}, clear=True):
            BasePlatformService.env_flag("X_FLAG")

        warnings = [
            r
            for r in caplog.records
            if r.levelno == logging.WARNING and r.name == real_logger.name
        ]
        assert warnings == [], "no warning should be emitted for parseable values"
