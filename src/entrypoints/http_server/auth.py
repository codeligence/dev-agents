"""Bearer-token authentication shared by the HTTP-hosted entrypoints.

Every entrypoint mounted on the shared server exposes the agent — repository
access, LLM spend, and whatever tools the deployment registered — so they all
gate on the same mechanism rather than each inventing one.

The policy is fail-closed. Keys are configured per entrypoint
(``<section>.server.apiKeys``, comma-separated string or YAML list). Running
without keys is not a silent default: it must be opted into explicitly with
``<section>.server.allowUnauthenticated: true``, which is only appropriate
when the port is reachable from a trusted network alone. Any other
combination — no keys and no opt-in, or a malformed ``apiKeys`` value — is a
:class:`~core.exceptions.ConfigurationError`, raised at startup so the
deployment refuses to start instead of starting open.
"""

from dataclasses import dataclass
from typing import Any
import hmac

from core.config import BaseConfig
from core.exceptions import ConfigurationError

__all__ = ["ApiKeyAuth"]

_BEARER_PREFIX = "Bearer "


@dataclass(frozen=True)
class ApiKeyAuth:
    """Validated Bearer-token policy for one HTTP entrypoint.

    Invariant: ``api_keys`` is non-empty or ``allow_unauthenticated`` is
    ``True``. The constructor enforces it, so holding an instance is proof
    the entrypoint is either gated or deliberately open.

    Example::

        auth = ApiKeyAuth.from_config(get_default_config(), "agui")
        if not auth.is_authorized(request.headers.get("authorization", "")):
            raise HTTPException(status_code=401)
    """

    api_keys: tuple[str, ...]
    allow_unauthenticated: bool = False

    def __post_init__(self) -> None:
        if not self.api_keys and not self.allow_unauthenticated:
            raise ConfigurationError(
                "HTTP entrypoint has no API keys configured and unauthenticated "
                "access is not enabled; refusing to start open."
            )

    @classmethod
    def from_config(cls, base_config: BaseConfig, section: str) -> "ApiKeyAuth":
        """Build the policy from ``<section>.server.apiKeys`` and
        ``<section>.server.allowUnauthenticated``.

        Args:
            base_config: Loaded application configuration.
            section: Top-level config section of the entrypoint (``"agui"`` or
                ``"openai"``); it also names the ``<SECTION>_API_KEYS`` /
                ``<SECTION>_ALLOW_UNAUTHENTICATED`` environment variables the
                bundled defaults wire in.

        Raises:
            ConfigurationError: If ``apiKeys`` has an unsupported type, or if
                no keys are configured without the explicit opt-in.
        """
        keys_path = f"{section}.server.apiKeys"
        allow_path = f"{section}.server.allowUnauthenticated"
        env_prefix = section.upper()

        api_keys = _parse_api_keys(base_config.get_value(keys_path, ""), keys_path)
        allow_unauthenticated = base_config.get_bool(allow_path, False)

        if not api_keys and not allow_unauthenticated:
            raise ConfigurationError(
                f"The '{section}' HTTP entrypoint is enabled but no API keys are "
                f"configured. Set {env_prefix}_API_KEYS ({keys_path}) to one or "
                "more comma-separated Bearer tokens, or set "
                f"{env_prefix}_ALLOW_UNAUTHENTICATED=true ({allow_path}) to run "
                "without authentication — unsafe outside a trusted network."
            )
        return cls(api_keys=api_keys, allow_unauthenticated=allow_unauthenticated)

    def is_authorized(self, auth_header: str) -> bool:
        """Whether *auth_header* carries one of the configured keys as a Bearer token.

        With no keys configured this is ``True`` only under the explicit
        ``allow_unauthenticated`` opt-in. Comparison uses
        :func:`hmac.compare_digest` so the result does not leak how many
        leading characters of a key were correct. Both sides are compared as
        UTF-8 bytes because ``compare_digest`` raises ``TypeError`` for
        non-ASCII ``str`` input, which would surface as a 500 instead of 401.
        """
        if not self.api_keys:
            return self.allow_unauthenticated
        if not auth_header.startswith(_BEARER_PREFIX):
            return False
        token = auth_header[len(_BEARER_PREFIX) :].encode()
        return any(hmac.compare_digest(token, key.encode()) for key in self.api_keys)


def _parse_api_keys(raw: Any, key_path: str) -> tuple[str, ...]:
    """Normalise a configured ``apiKeys`` value into a tuple of non-blank keys.

    Accepts a comma-separated string (the shape produced by a ``@jinja`` env
    template) or a list of strings. Anything else is a configuration error
    rather than "no keys", so a typo cannot silently disable authentication.
    """
    if isinstance(raw, str):
        entries = raw.split(",")
    elif isinstance(raw, list) and all(isinstance(entry, str) for entry in raw):
        entries = raw
    else:
        raise ConfigurationError(
            f"{key_path} must be a comma-separated string or a list of strings, "
            f"got {type(raw).__name__}."
        )
    return tuple(key.strip() for key in entries if key.strip())
