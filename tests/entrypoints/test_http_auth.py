"""Tests for the fail-closed Bearer-token policy shared by the HTTP entrypoints."""

from pathlib import Path
import textwrap

import pytest

from core.config import BaseConfig
from core.exceptions import ConfigurationError
from entrypoints.http_server.auth import ApiKeyAuth


def _config(tmp_path: Path, server_block: str) -> BaseConfig:
    """Write a minimal config with an ``agui.server`` block and load it."""
    config_file = tmp_path / "config.yaml"
    body = textwrap.indent(textwrap.dedent(server_block).strip("\n"), "    ")
    config_file.write_text("agui:\n  server:\n" + body + "\n")
    return BaseConfig(str(config_file))


class TestConstructor:
    def test_empty_keys_without_opt_in_is_rejected(self):
        with pytest.raises(ConfigurationError):
            ApiKeyAuth(api_keys=())

    def test_empty_keys_with_opt_in_is_open(self):
        auth = ApiKeyAuth(api_keys=(), allow_unauthenticated=True)
        assert auth.is_authorized("")

    def test_keys_with_opt_in_still_enforce_keys(self):
        """The opt-in only matters when there is nothing to check against."""
        auth = ApiKeyAuth(api_keys=("sk-a",), allow_unauthenticated=True)
        assert not auth.is_authorized("")
        assert auth.is_authorized("Bearer sk-a")


class TestFromConfig:
    def test_comma_separated_string(self, tmp_path):
        auth = ApiKeyAuth.from_config(_config(tmp_path, 'apiKeys: "a, b ,c"'), "agui")
        assert auth.api_keys == ("a", "b", "c")
        assert auth.allow_unauthenticated is False

    def test_list(self, tmp_path):
        auth = ApiKeyAuth.from_config(_config(tmp_path, "apiKeys: [a, b]"), "agui")
        assert auth.api_keys == ("a", "b")

    def test_blank_entries_dropped(self, tmp_path):
        auth = ApiKeyAuth.from_config(_config(tmp_path, 'apiKeys: "a,,  ,b"'), "agui")
        assert auth.api_keys == ("a", "b")

    def test_empty_string_without_opt_in_fails(self, tmp_path):
        """Regression: an empty apiKeys used to mean 'authentication disabled'."""
        with pytest.raises(ConfigurationError, match="AGUI_API_KEYS") as excinfo:
            ApiKeyAuth.from_config(_config(tmp_path, 'apiKeys: ""'), "agui")
        assert "AGUI_ALLOW_UNAUTHENTICATED" in str(excinfo.value)

    def test_missing_key_without_opt_in_fails(self, tmp_path):
        with pytest.raises(ConfigurationError):
            ApiKeyAuth.from_config(_config(tmp_path, "enabled: true"), "agui")

    def test_empty_with_opt_in_is_open(self, tmp_path):
        auth = ApiKeyAuth.from_config(
            _config(tmp_path, 'apiKeys: ""\nallowUnauthenticated: true'), "agui"
        )
        assert auth.api_keys == ()
        assert auth.allow_unauthenticated is True
        assert auth.is_authorized("")

    def test_string_false_opt_in_is_not_truthy(self, tmp_path):
        """Jinja-rendered booleans arrive as strings; "False" must stay false."""
        with pytest.raises(ConfigurationError):
            ApiKeyAuth.from_config(
                _config(tmp_path, 'apiKeys: ""\nallowUnauthenticated: "False"'),
                "agui",
            )

    @pytest.mark.parametrize(
        "server_block",
        [
            "apiKeys: 123",
            "apiKeys: {a: 1}",
            "apiKeys: [a, 2]",
            "apiKeys: true",
        ],
    )
    def test_malformed_type_is_a_configuration_error(self, tmp_path, server_block):
        """A wrong type must not degrade into 'no keys' plus the opt-in check."""
        with pytest.raises(ConfigurationError, match="agui.server.apiKeys"):
            ApiKeyAuth.from_config(
                _config(tmp_path, f"{server_block}\nallowUnauthenticated: true"),
                "agui",
            )


class TestIsAuthorized:
    AUTH = ApiKeyAuth(api_keys=("sk-correct", "sk-second"))

    def test_valid_key(self):
        assert self.AUTH.is_authorized("Bearer sk-correct")

    def test_second_valid_key(self):
        assert self.AUTH.is_authorized("Bearer sk-second")

    def test_wrong_key(self):
        assert not self.AUTH.is_authorized("Bearer sk-wrong")

    def test_missing_header(self):
        assert not self.AUTH.is_authorized("")

    def test_missing_bearer_prefix(self):
        assert not self.AUTH.is_authorized("sk-correct")

    def test_prefix_of_valid_key_rejected(self):
        assert not self.AUTH.is_authorized("Bearer sk-corre")

    def test_key_with_trailing_content_rejected(self):
        assert not self.AUTH.is_authorized("Bearer sk-correctX")

    def test_non_ascii_token_rejected(self):
        """Regression: non-ASCII str input made compare_digest raise TypeError."""
        assert not self.AUTH.is_authorized("Bearer é")

    def test_non_ascii_key_accepted(self):
        assert ApiKeyAuth(api_keys=("sk-ünïcode",)).is_authorized("Bearer sk-ünïcode")
