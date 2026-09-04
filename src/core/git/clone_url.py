"""Validation of authenticated clone URLs.

A clone URL is used together with a provider token, so it must only ever
point at the host the token was issued for and must only travel over TLS.
Providers derive the expected host from their configured API/base URL and
the template method in ``PullRequestProvider.clone`` validates the URL
before any git process is started.
"""

from urllib.parse import urlsplit

from core.exceptions import GitOperationError

_SECURE_SCHEME = "https"
_INSECURE_SCHEME = "http"


def host_from_url(url: str) -> str:
    """Return the host (with port, if any) of *url* without userinfo.

    Unlike ``urlsplit(url).hostname`` the port is preserved, so a self-hosted
    instance on a non-default port yields e.g. ``gitlab.corp.com:8443``.
    """
    return urlsplit(url).netloc.rpartition("@")[2]


def validate_clone_url(
    url: str, *, expected_host: str, allow_insecure: bool = False
) -> None:
    """Ensure *url* is safe to clone with a provider credential.

    The URL must not embed userinfo (credentials are stored in git's
    credential helper, never in the URL), must use ``https`` and must point at
    *expected_host*. Hosts are compared case-insensitively including the port.

    Args:
        url: Candidate clone URL, typically returned by a provider API or
            assembled from provider configuration
        expected_host: Host (optionally ``host:port``) the URL must match
        allow_insecure: Development-only switch that additionally permits the
            ``http`` scheme. The host check always applies.

    Raises:
        GitOperationError: If the URL embeds credentials, uses a disallowed
            scheme or points at a different host
    """
    if not expected_host:
        raise GitOperationError("Clone URL validation requires an expected host")

    parts = urlsplit(url)
    if "@" in parts.netloc:
        raise GitOperationError("Clone URL must not embed credentials")

    scheme = parts.scheme.lower()
    allowed_schemes = {_SECURE_SCHEME}
    if allow_insecure:
        allowed_schemes.add(_INSECURE_SCHEME)
    if scheme not in allowed_schemes:
        raise GitOperationError(
            f"Clone URL {url!r} must use https"
            + (" or http" if allow_insecure else "")
            + f", got scheme {parts.scheme!r}"
        )

    if parts.netloc.lower() != expected_host.lower():
        raise GitOperationError(
            f"Clone URL host {parts.netloc!r} does not match the configured "
            f"provider host {expected_host!r}"
        )
