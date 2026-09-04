"""The OpenAI-compatible routes must enforce API keys and refuse to start open."""

from pathlib import Path
from unittest.mock import MagicMock, patch
import textwrap

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from core.config import BaseConfig
from core.exceptions import ConfigurationError
from entrypoints.http_server.auth import ApiKeyAuth
from entrypoints.openai_entrypoint.service import (
    OpenAIConfig,
    register_if_configured,
    router,
)

CHAT_PAYLOAD = {
    "model": "dev-agents",
    "messages": [{"role": "user", "content": "hello"}],
}


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _config_with_auth(auth: ApiKeyAuth):
    config = MagicMock(spec=OpenAIConfig)
    config.get_auth.return_value = auth
    config.get_model_name.return_value = "dev-agents"
    config.get_default_timeout.return_value = 300
    config.get_default_agent_type.return_value = "gitchatbot"
    config.is_streaming_enabled.return_value = False
    config.is_thinking_enabled.return_value = False
    return config


def _patch_config(config):
    return patch(
        "entrypoints.openai_entrypoint.service.OpenAIConfig", return_value=config
    )


class TestOpenAIAuth:
    SECRET = ApiKeyAuth(api_keys=("sk-secret",))

    def test_models_missing_key_rejected(self, client):
        with _patch_config(_config_with_auth(self.SECRET)):
            response = client.get("/v1/models")
        assert response.status_code == 401

    def test_models_wrong_key_rejected(self, client):
        with _patch_config(_config_with_auth(self.SECRET)):
            response = client.get(
                "/v1/models", headers={"Authorization": "Bearer sk-wrong"}
            )
        assert response.status_code == 401

    def test_models_non_ascii_token_rejected_not_500(self, client):
        """Servers decode raw header bytes as latin-1, so 0xE9 arrives as "é"."""
        with _patch_config(_config_with_auth(self.SECRET)):
            response = client.get(
                "/v1/models",
                headers={"Authorization": "Bearer é".encode("latin-1")},
            )
        assert response.status_code == 401

    def test_models_valid_key_accepted(self, client):
        with _patch_config(_config_with_auth(self.SECRET)):
            response = client.get(
                "/v1/models", headers={"Authorization": "Bearer sk-secret"}
            )
        assert response.status_code == 200
        assert response.json()["data"][0]["id"] == "dev-agents"

    def test_chat_auth_precedes_input_validation(self, client):
        """An unauthenticated caller learns nothing about request validity."""
        with _patch_config(_config_with_auth(self.SECRET)):
            response = client.post(
                "/v1/chat/completions", json={**CHAT_PAYLOAD, "messages": []}
            )
        assert response.status_code == 401

    def test_chat_valid_key_passes_the_gate(self, client):
        """Past auth, the request reaches normal request validation."""
        with _patch_config(_config_with_auth(self.SECRET)):
            response = client.post(
                "/v1/chat/completions",
                json={**CHAT_PAYLOAD, "messages": []},
                headers={"Authorization": "Bearer sk-secret"},
            )
        assert response.status_code == 400

    def test_explicit_unauthenticated_opt_in_is_open(self, client):
        open_auth = ApiKeyAuth(api_keys=(), allow_unauthenticated=True)
        with _patch_config(_config_with_auth(open_auth)):
            response = client.get("/v1/models")
        assert response.status_code == 200


def _base_config(tmp_path: Path, server_block: str) -> BaseConfig:
    config_file = tmp_path / "config.yaml"
    body = textwrap.indent(textwrap.dedent(server_block).strip("\n"), "    ")
    config_file.write_text("openai:\n  server:\n    enabled: true\n" + body + "\n")
    return BaseConfig(str(config_file))


def _patch_startup(base_config: BaseConfig):
    return (
        patch(
            "entrypoints.openai_entrypoint.service.get_default_config",
            return_value=base_config,
        ),
        patch("entrypoints.http_server.server.register_router"),
    )


class TestOpenAIStartup:
    """Registration must validate auth so a bad deployment fails to start."""

    def test_enabled_without_keys_refuses_to_register(self, tmp_path):
        config_patch, router_patch = _patch_startup(
            _base_config(tmp_path, 'apiKeys: ""')
        )
        with (
            config_patch,
            router_patch as register_router,
            pytest.raises(ConfigurationError, match="OPENAI_API_KEYS"),
        ):
            register_if_configured()
        register_router.assert_not_called()

    def test_enabled_with_malformed_keys_refuses_to_register(self, tmp_path):
        config_patch, router_patch = _patch_startup(
            _base_config(tmp_path, "apiKeys: 123\nallowUnauthenticated: true")
        )
        with (
            config_patch,
            router_patch as register_router,
            pytest.raises(ConfigurationError, match="openai.server.apiKeys"),
        ):
            register_if_configured()
        register_router.assert_not_called()

    def test_enabled_with_keys_registers(self, tmp_path):
        config_patch, router_patch = _patch_startup(
            _base_config(tmp_path, "apiKeys: sk-secret")
        )
        with config_patch, router_patch as register_router:
            assert register_if_configured() is True
        register_router.assert_called_once_with(router)

    def test_enabled_with_opt_in_registers(self, tmp_path):
        config_patch, router_patch = _patch_startup(
            _base_config(tmp_path, 'apiKeys: ""\nallowUnauthenticated: true')
        )
        with config_patch, router_patch as register_router:
            assert register_if_configured() is True
        register_router.assert_called_once_with(router)
