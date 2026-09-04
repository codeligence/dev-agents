"""The AG-UI /agent endpoint must enforce API keys and refuse to start open.

`POST /agent` runs the agent, so it cannot be the one unauthenticated door on
the shared HTTP server while the sibling OpenAI entrypoint gates on keys.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch
import textwrap

import pytest

pytest.importorskip("ag_ui")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from core.config import BaseConfig  # noqa: E402
from core.exceptions import ConfigurationError  # noqa: E402
from entrypoints.agui_entrypoint.service import (  # noqa: E402
    AGUIConfig,
    register_if_configured,
    router,
)
from entrypoints.http_server.auth import ApiKeyAuth  # noqa: E402

RUN_PAYLOAD = {
    "thread_id": "t1",
    "run_id": "r1",
    "messages": [{"id": "m1", "role": "user", "content": "hello"}],
    "tools": [],
    "context": [],
    "state": {},
    "forwarded_props": {},
}


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _config_with_auth(auth: ApiKeyAuth):
    config = MagicMock(spec=AGUIConfig)
    config.get_auth.return_value = auth
    config.get_default_timeout.return_value = 300
    config.get_default_agent_type.return_value = "gitchatbot"
    config.get_max_message_length.return_value = 10000
    return config


def _patch_config(config):
    return patch("entrypoints.agui_entrypoint.service.AGUIConfig", return_value=config)


class TestAGUIAuth:
    SECRET = ApiKeyAuth(api_keys=("sk-secret",))

    def test_missing_key_rejected(self, client):
        with _patch_config(_config_with_auth(self.SECRET)):
            response = client.post("/agent", json=RUN_PAYLOAD)
        assert response.status_code == 401

    def test_wrong_key_rejected(self, client):
        with _patch_config(_config_with_auth(self.SECRET)):
            response = client.post(
                "/agent",
                json=RUN_PAYLOAD,
                headers={"Authorization": "Bearer sk-wrong"},
            )
        assert response.status_code == 401

    def test_non_ascii_token_rejected_not_500(self, client):
        """Servers decode raw header bytes as latin-1, so 0xE9 arrives as "é"."""
        with _patch_config(_config_with_auth(self.SECRET)):
            response = client.post(
                "/agent",
                json=RUN_PAYLOAD,
                headers={"Authorization": "Bearer é".encode("latin-1")},
            )
        assert response.status_code == 401

    def test_auth_precedes_input_validation(self, client):
        """An unauthenticated caller learns nothing about request validity."""
        with _patch_config(_config_with_auth(self.SECRET)):
            response = client.post("/agent", json={**RUN_PAYLOAD, "messages": []})
        assert response.status_code == 401

    def test_valid_key_passes_the_gate(self, client):
        """Past auth, the request reaches normal request validation."""
        with _patch_config(_config_with_auth(self.SECRET)):
            response = client.post(
                "/agent",
                json={**RUN_PAYLOAD, "messages": []},
                headers={"Authorization": "Bearer sk-secret"},
            )
        assert response.status_code == 400

    def test_explicit_unauthenticated_opt_in_is_open(self, client):
        open_auth = ApiKeyAuth(api_keys=(), allow_unauthenticated=True)
        with _patch_config(_config_with_auth(open_auth)):
            response = client.post("/agent", json={**RUN_PAYLOAD, "messages": []})
        assert response.status_code == 400


def _base_config(tmp_path: Path, server_block: str) -> BaseConfig:
    config_file = tmp_path / "config.yaml"
    body = textwrap.indent(textwrap.dedent(server_block).strip("\n"), "    ")
    config_file.write_text("agui:\n  server:\n    enabled: true\n" + body + "\n")
    return BaseConfig(str(config_file))


def _patch_startup(base_config: BaseConfig):
    return (
        patch(
            "entrypoints.agui_entrypoint.service.get_default_config",
            return_value=base_config,
        ),
        patch("entrypoints.http_server.server.register_router"),
    )


class TestAGUIStartup:
    """Registration must validate auth so a bad deployment fails to start."""

    def test_enabled_without_keys_refuses_to_register(self, tmp_path):
        config_patch, router_patch = _patch_startup(
            _base_config(tmp_path, 'apiKeys: ""')
        )
        with (
            config_patch,
            router_patch as register_router,
            pytest.raises(ConfigurationError, match="AGUI_API_KEYS"),
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

    def test_disabled_is_skipped_without_validation(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("agui:\n  server:\n    enabled: false\n")
        config_patch, router_patch = _patch_startup(BaseConfig(str(config_file)))
        with config_patch, router_patch as register_router:
            assert register_if_configured() is False
        register_router.assert_not_called()
