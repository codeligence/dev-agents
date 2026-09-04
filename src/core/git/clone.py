from pathlib import Path
from urllib.parse import urlsplit
import asyncio
import contextlib
import os
import shutil
import tempfile

from core.exceptions import GitOperationError
from core.log import get_logger

logger = get_logger(logger_name="GitClone", level="DEBUG")

_REDACTION = "***"

#: Hard ceiling for a single git subprocess; a stalled clone would otherwise
#: hold the per-repository clone lock forever and queue all later requests.
GIT_TIMEOUT_SECONDS = 300.0

#: Name prefix of the staging directory a clone is built in (see
#: :func:`clone_repository`). Hidden so a listing of the target directory
#: during a clone does not look like a checkout in progress went wrong.
_STAGING_PREFIX = ".clone-"

#: Credential settings applied to both the ``approve`` and ``clone`` commands.
#: The empty ``credential.helper`` resets the inherited helper list (a helper
#: configured at system or global scope, e.g. osxkeychain, would otherwise also
#: receive the token and could answer lookups with a stale one), so ``store``
#: is the only helper consulted. ``useHttpPath`` scopes each entry to its
#: repository path; git otherwise matches on host and username alone, so two
#: repositories on the same host would overwrite or reuse each other's token.
_CREDENTIAL_CONFIG = (
    "credential.helper=",
    "credential.helper=store",
    "credential.useHttpPath=true",
)


#: Checkout settings written into every clone's local config. With
#: ``core.symlinks=false`` git materialises a committed symlink as a plain
#: file holding the link target text instead of a real link, so nothing in
#: the working copy can point outside it. The read-only subagent that later
#: runs against the checkout resolves paths before reading them, but a link
#: that never exists cannot be followed by a tool that does not.
_CHECKOUT_CONFIG = ("core.symlinks=false",)


def _credential_flags(flag: str) -> list[str]:
    """Pair *flag* (``-c`` or ``--config``) with each credential setting."""
    return [arg for setting in _CREDENTIAL_CONFIG for arg in (flag, setting)]


def _checkout_flags() -> list[str]:
    """``--config`` pairs for :data:`_CHECKOUT_CONFIG`."""
    return [arg for setting in _CHECKOUT_CONFIG for arg in ("--config", setting)]


def web_host_from_api_url(api_url: str) -> str:
    """Derive the git web host from a provider API URL.

    Strips a leading ``api.`` sub-domain (e.g. ``api.github.com`` ->
    ``github.com``) and drops any API path and userinfo. A non-default port
    is preserved so self-hosted instances clone against the same endpoint
    they are queried on. Hosts without the ``api.`` prefix are returned
    unchanged.
    """
    host = urlsplit(api_url).netloc.rpartition("@")[2]
    api_prefix = "api."
    if host.startswith(api_prefix):
        host = host[len(api_prefix) :]
    return host


def _redact(text: str, secret: str | None) -> str:
    """Replace *secret* with a redaction marker so tokens never reach logs."""
    if secret:
        return text.replace(secret, _REDACTION)
    return text


async def _run_git(
    *args: str,
    action: str,
    input_data: bytes | None = None,
    secret: str | None = None,
) -> None:
    """Run a git subprocess with a timeout, raising GitOperationError on failure.

    The command runs without a shell and with ``GIT_TERMINAL_PROMPT=0`` so git
    fails fast instead of prompting. On timeout or cancellation the process is
    killed so it cannot keep writing after the caller has given up; a timeout
    raises GitOperationError with *secret* redacted from any error detail.
    """
    process = await asyncio.create_subprocess_exec(
        "git",
        *args,
        stdin=asyncio.subprocess.PIPE if input_data is not None else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )
    try:
        _, stderr = await asyncio.wait_for(
            process.communicate(input_data), timeout=GIT_TIMEOUT_SECONDS
        )
    except TimeoutError:
        process.kill()
        await process.wait()
        raise GitOperationError(
            f"{action} timed out after {GIT_TIMEOUT_SECONDS:.0f}s"
        ) from None
    except asyncio.CancelledError:
        process.kill()
        await process.wait()
        raise

    if process.returncode != 0:
        detail = _redact(stderr.decode("utf-8", errors="replace").strip(), secret)
        raise GitOperationError(f"{action} failed: {detail}")


async def _store_credential(url: str, user: str, password: str) -> None:
    """Persist a credential for *url* in git's ``store`` helper.

    Writes to the store helper's default file in the user's home directory
    (``~/.git-credentials``), outside any agent working copy. The credential
    is fed via stdin so it never appears in process arguments, and
    ``git credential approve`` replaces an existing entry for the same
    host/path/user, so token rotation does not accumulate stale lines.

    The entry is scoped to the repository path (see :data:`_CREDENTIAL_CONFIG`),
    which keeps per-repository tokens for the same host distinct.
    """
    parts = urlsplit(url)
    # Preserve host case and port, but drop any userinfo: git matches the host
    # exactly as it appears in the remote URL.
    host = parts.netloc.rpartition("@")[2]
    # git's credential path carries no leading slash.
    path = parts.path.lstrip("/")

    fields = [f"protocol={parts.scheme}", f"host={host}"]
    if path:
        fields.append(f"path={path}")
    fields += [f"username={user}", f"password={password}", "", ""]

    await _run_git(
        *_credential_flags("-c"),
        "credential",
        "approve",
        action=f"Storing git credential for {host}",
        input_data="\n".join(fields).encode(),
        secret=password,
    )


def _move_into_place(staging_dir: Path, target_dir: Path) -> None:
    """Move the clone built in *staging_dir* up into its parent *target_dir*.

    Refuses if *target_dir* holds anything besides the staging directory: the
    clone must not be merged into, or replace, data that appeared there while
    git was running. ``.git`` is moved last, so a failure part-way never
    leaves something that passes for a checkout.

    Raises:
        GitOperationError: If *target_dir* is no longer empty or a move fails
    """
    foreign = {entry.name for entry in target_dir.iterdir()} - {staging_dir.name}
    if foreign:
        raise GitOperationError(
            f"Cannot move clone into {target_dir}: directory is no longer empty "
            f"({', '.join(sorted(foreign))})"
        )
    entries = sorted(staging_dir.iterdir(), key=lambda entry: entry.name == ".git")
    try:
        for entry in entries:
            entry.rename(target_dir / entry.name)
        staging_dir.rmdir()
    except OSError as exc:
        raise GitOperationError(
            f"Moving clone into {target_dir} failed: {exc}"
        ) from exc


async def clone_repository(
    url: str, target_dir: str, *, user: str | None = None, password: str | None = None
) -> None:
    """Clone *url* into *target_dir* via ``git clone``.

    Runs git through ``asyncio.create_subprocess_exec`` (no shell) with a
    :data:`GIT_TIMEOUT_SECONDS` timeout. The credential is never embedded in the
    URL: it is stored in git's ``store`` credential helper (a file in the
    user's home directory) and the cloned repository's local config repeats
    :data:`_CREDENTIAL_CONFIG`, so ``origin`` stays credential-free while
    subsequent pulls look the token up the same way it was stored. Neither
    process arguments nor ``.git/config`` ever contain the secret.

    The clone is built in a fresh staging directory *inside* *target_dir*
    (created if absent) and moved up into place only after git succeeded and
    *target_dir* is verified to hold nothing else, with ``.git`` moved last.
    The staging directory lives inside the target rather than beside it
    because the target is commonly a mount point (``/code`` in the container
    image) whose parent is neither writable nor on the same filesystem. A
    failed or interrupted clone removes only that staging directory, plus
    *target_dir* itself if this call created it and it is still empty; data
    that already existed at *target_dir*, or appeared there while git ran, is
    never deleted or overwritten.

    Args:
        url: Credential-free clone URL
        target_dir: Filesystem path to clone into; must be absent or empty
        user: Username to authenticate with (used only when *password* is set)
        password: Token/PAT to authenticate with; omit for public/local remotes

    Raises:
        GitOperationError: If the git clone process fails or times out, or if
            *target_dir* is not empty once the clone is ready to move into it
    """
    logger.info("Cloning repository %s into %s", url, target_dir)

    clone_args = ["clone", *_checkout_flags()]
    if password is not None:
        await _store_credential(url, user or "", password)
        clone_args += _credential_flags("--config")

    target = Path(target_dir)
    created_target = not target.is_dir()
    target.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(tempfile.mkdtemp(prefix=_STAGING_PREFIX, dir=target))
    try:
        await _run_git(
            *clone_args,
            url,
            str(staging_dir),
            action=f"Cloning repository {url} into {target_dir}",
            secret=password,
        )
        _move_into_place(staging_dir, target)
    except BaseException:
        logger.warning("Removing clone staging directory %s", staging_dir)
        shutil.rmtree(staging_dir, ignore_errors=True)
        if created_target:
            # rmdir only succeeds on an empty directory, so this can never
            # delete data that arrived at target_dir in the meantime.
            with contextlib.suppress(OSError):
                target.rmdir()
        raise
    logger.info("Cloned repository into %s", target_dir)
