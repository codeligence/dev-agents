from pathlib import Path
from unittest.mock import AsyncMock, patch
import asyncio
import subprocess

import pytest

from core.exceptions import GitOperationError
from core.git.clone import (
    _credential_flags,
    _store_credential,
    clone_repository,
    web_host_from_api_url,
)


class TestWebHostFromApiUrl:
    """Tests for deriving a git web host from a provider API URL."""

    def test_strips_api_subdomain(self):
        assert web_host_from_api_url("https://api.github.com") == "github.com"

    def test_strips_api_subdomain_for_bitbucket(self):
        assert web_host_from_api_url("https://api.bitbucket.org/2.0") == "bitbucket.org"

    def test_self_hosted_host_with_api_path_unchanged(self):
        assert web_host_from_api_url("https://ghe.example.com/api/v3") == (
            "ghe.example.com"
        )

    def test_preserves_non_default_port(self):
        assert web_host_from_api_url("https://ghe.example.com:8443/api/v3") == (
            "ghe.example.com:8443"
        )

    def test_drops_userinfo(self):
        assert web_host_from_api_url("https://user:pw@api.github.com") == "github.com"


def _git(*args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        env={"GIT_TERMINAL_PROMPT": "0", "PATH": _path()},
    )
    return result.stdout.strip()


def _path() -> str:
    import os

    return os.environ.get("PATH", "")


@pytest.fixture
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect HOME so credential writes never touch the real ~.

    ``_run_git`` inherits ``os.environ``, so this also covers the git
    subprocesses started by the code under test.
    """
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    return home


def _git_env(home: Path) -> dict[str, str]:
    return {
        "PATH": _path(),
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "GIT_TERMINAL_PROMPT": "0",
    }


def _credential_fill(url: str, home: Path) -> str:
    """Return the password git resolves for *url*, or "" if none matches.

    Uses the same credential settings the production code configures, so a
    mismatch between how a credential is stored and looked up shows up here.
    """
    result = subprocess.run(
        ["git", *_credential_flags("-c"), "credential", "fill"],
        input=f"url={url}\n\n",
        capture_output=True,
        text=True,
        # An unmatched lookup falls through to prompting; fail fast instead.
        env={**_git_env(home), "GIT_ASKPASS": "/usr/bin/false"},
        timeout=30,
    )
    for line in result.stdout.splitlines():
        if line.startswith("password="):
            return line.removeprefix("password=")
    return ""


def _git_config(repo: Path, *args: str) -> list[str]:
    result = subprocess.run(
        ["git", "config", "--local", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        env={"GIT_TERMINAL_PROMPT": "0", "PATH": _path()},
    )
    return result.stdout.rstrip("\n").split("\n")


@pytest.fixture
def local_remote(tmp_path: Path) -> str:
    """Create a seeded local bare repository usable as a clone source."""
    remote = tmp_path / "remote.git"
    seed = tmp_path / "seed"
    _git("init", "--bare", str(remote))
    # Seed whatever branch the bare repo's HEAD points at (git's built-in
    # default when no init.defaultBranch is configured), so the clone checks
    # out the seeded content on any machine regardless of git configuration.
    default_branch = _git("symbolic-ref", "--short", "HEAD", cwd=remote)
    _git("clone", str(remote), str(seed))
    (seed / "README").write_text("hi")
    _git("add", ".", cwd=seed)
    _git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "init", cwd=seed)
    _git("push", "origin", f"HEAD:{default_branch}", cwd=seed)
    return f"file://{remote}"


class _FakeProcess:
    """Stand-in for an asyncio subprocess with scriptable behaviour."""

    def __init__(self, *, hang: bool = False):
        self.hang = hang
        self.killed = False
        self.stdin_data: bytes | None = None
        self.returncode: int | None = 0

    async def communicate(self, input: bytes | None = None) -> tuple[bytes, bytes]:
        self.stdin_data = input
        if self.hang:
            await asyncio.sleep(3600)
        return b"", b""

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9

    async def wait(self) -> int:
        return -9


class TestCloneRepository:
    """Tests for the clone_repository helper."""

    async def test_clone_success(self, local_remote: str, tmp_path: Path):
        target = tmp_path / "clone"
        await clone_repository(local_remote, str(target))
        assert (target / ".git").is_dir()
        assert (target / "README").read_text() == "hi"

    async def test_clone_failure_raises_git_operation_error(self, tmp_path: Path):
        target = tmp_path / "clone"
        with pytest.raises(GitOperationError):
            await clone_repository("file:///no/such/repo.git", str(target))
        assert not target.exists()

    async def test_clone_timeout_removes_partial_clone(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """A killed clone must not leave a directory that looks like a repo.

        The timeout kills git with SIGKILL, so a partially written ``.git/``
        survives unless clone_repository cleans up. ``has_git_repo`` only
        checks for ``.git``, so a leftover would permanently short-circuit
        every later clone attempt.
        """
        import core.git.clone as clone_module

        monkeypatch.setattr(clone_module, "GIT_TIMEOUT_SECONDS", 0.05)
        target = tmp_path / "clone"

        async def fake_exec(*argv: str, **_kwargs: object) -> _FakeProcess:
            # Stand in for the partial checkout git leaves behind when killed.
            staging = Path(argv[-1])
            (staging / ".git").mkdir()
            (staging / ".git" / "config").write_text("[core]\n")
            return _FakeProcess(hang=True)

        with (
            patch(
                "core.git.clone.asyncio.create_subprocess_exec",
                side_effect=fake_exec,
            ),
            pytest.raises(GitOperationError, match="timed out"),
        ):
            await clone_repository("https://git.example.com/repo.git", str(target))
        assert not target.exists()

    async def test_clone_timeout_kills_process_and_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        import core.git.clone as clone_module

        monkeypatch.setattr(clone_module, "GIT_TIMEOUT_SECONDS", 0.05)
        process = _FakeProcess(hang=True)
        with (
            patch(
                "core.git.clone.asyncio.create_subprocess_exec",
                new=AsyncMock(return_value=process),
            ),
            pytest.raises(GitOperationError, match="timed out"),
        ):
            await clone_repository(
                "https://git.example.com/repo.git", str(tmp_path / "clone")
            )
        assert process.killed

    async def test_cancellation_kills_process_and_removes_staging(self, tmp_path: Path):
        """Cancelling the clone must not leave git writing into the target."""
        process = _FakeProcess(hang=True)
        target = tmp_path / "clone"
        with patch(
            "core.git.clone.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=process),
        ):
            task = asyncio.create_task(
                clone_repository("https://git.example.com/repo.git", str(target))
            )
            await asyncio.sleep(0.01)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        assert process.killed
        assert not target.exists()


def _staging_dirs(directory: Path) -> list[Path]:
    return [p for p in directory.iterdir() if p.name.startswith(".clone-")]


class TestCloneStaging:
    """The clone is built in a staging dir; target_dir data is never deleted.

    ``_run_git`` is replaced so no clone runs; the fake receives the staging
    path git would clone into as its last positional argument.
    """

    @pytest.fixture
    def fake_run_git(self, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
        """Patch ``_run_git`` with a fake that records where git was told to clone.

        The fake writes a partial checkout there (like a clone that died
        part-way) and then fails, unless ``seen["succeed"]`` is set.
        """
        seen: dict[str, Path] = {}

        async def _fake(*args: str, **_kwargs: object) -> None:
            staging = Path(args[-1])
            seen["staging"] = staging
            (staging / ".git").mkdir()
            (staging / ".git" / "config").write_text("[core]\n")
            (staging / "README").write_text("cloned")
            if "succeed" not in seen:
                raise GitOperationError("Cloning repository failed: boom")

        monkeypatch.setattr("core.git.clone._run_git", _fake)
        return seen

    async def test_failure_keeps_pre_existing_target_contents(
        self, tmp_path: Path, fake_run_git: dict[str, Path]
    ):
        target = tmp_path / "clone"
        target.mkdir()
        sentinel = target / "precious.txt"
        sentinel.write_text("keep me")

        with pytest.raises(GitOperationError, match="boom"):
            await clone_repository("https://git.example.com/repo.git", str(target))

        assert sentinel.read_text() == "keep me"
        assert sorted(p.name for p in target.iterdir()) == ["precious.txt"]
        assert not fake_run_git["staging"].exists()

    async def test_refuses_pre_existing_target_contents_after_successful_git(
        self, tmp_path: Path, fake_run_git: dict[str, Path]
    ):
        fake_run_git["succeed"] = Path()
        target = tmp_path / "clone"
        target.mkdir()
        sentinel = target / "precious.txt"
        sentinel.write_text("keep me")

        with pytest.raises(GitOperationError, match="no longer empty"):
            await clone_repository("https://git.example.com/repo.git", str(target))

        assert sentinel.read_text() == "keep me"
        assert sorted(p.name for p in target.iterdir()) == ["precious.txt"]
        assert not fake_run_git["staging"].exists()

    async def test_failure_removes_staging_dir_and_created_target(
        self, tmp_path: Path, fake_run_git: dict[str, Path]
    ):
        target = tmp_path / "clone"

        with pytest.raises(GitOperationError, match="boom"):
            await clone_repository("https://git.example.com/repo.git", str(target))

        assert fake_run_git["staging"].parent == target
        assert not fake_run_git["staging"].exists()
        # An empty target this call created is removed again; nothing else is.
        assert not target.exists()
        assert sorted(p.name for p in tmp_path.iterdir()) == []

    @pytest.mark.usefixtures("fake_run_git")
    async def test_failure_keeps_pre_existing_empty_target(self, tmp_path: Path):
        target = tmp_path / "clone"
        target.mkdir()

        with pytest.raises(GitOperationError, match="boom"):
            await clone_repository("https://git.example.com/repo.git", str(target))

        assert target.is_dir()
        assert list(target.iterdir()) == []

    async def test_success_moves_clone_into_place(
        self, tmp_path: Path, fake_run_git: dict[str, Path]
    ):
        fake_run_git["succeed"] = Path()
        target = tmp_path / "clone"

        await clone_repository("https://git.example.com/repo.git", str(target))

        assert (target / ".git" / "config").read_text() == "[core]\n"
        assert (target / "README").read_text() == "cloned"
        assert sorted(p.name for p in target.iterdir()) == [".git", "README"]
        assert not fake_run_git["staging"].exists()

    async def test_refuses_to_move_over_data_that_appeared_during_clone(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        target = tmp_path / "clone"
        sentinel = target / "precious.txt"

        async def _fake(*args: str, **_kwargs: object) -> None:
            (Path(args[-1]) / ".git").mkdir()
            # Another writer populates target_dir while git is running.
            sentinel.write_text("keep me")

        monkeypatch.setattr("core.git.clone._run_git", _fake)

        with pytest.raises(GitOperationError, match="no longer empty"):
            await clone_repository("https://git.example.com/repo.git", str(target))

        assert sentinel.read_text() == "keep me"
        assert not (target / ".git").exists()
        assert _staging_dirs(target) == []

    async def test_real_clone_leaves_no_staging_dir(
        self, local_remote: str, tmp_path: Path
    ):
        target = tmp_path / "clone"
        await clone_repository(local_remote, str(target))
        assert (target / ".git").is_dir()
        assert _staging_dirs(target) == []
        assert _staging_dirs(tmp_path) == []


class TestCloneCredentialHandling:
    """The token must never appear in argv or the cloned repo's config."""

    async def _clone_with_credentials(self, target: Path) -> list[_FakeProcess]:
        processes: list[_FakeProcess] = []

        async def fake_exec(*argv: str, **_kwargs: object) -> _FakeProcess:
            process = _FakeProcess()
            process.argv = argv  # type: ignore[attr-defined]
            processes.append(process)
            return process

        with patch(
            "core.git.clone.asyncio.create_subprocess_exec",
            side_effect=fake_exec,
        ):
            await clone_repository(
                "https://git.example.com:8443/group/repo.git",
                str(target),
                user="oauth2",
                password="SUPERSECRET123",
            )
        return processes

    async def test_credential_is_stored_via_stdin(self, tmp_path: Path):
        approve, _ = await self._clone_with_credentials(tmp_path / "clone")
        assert approve.argv == (
            "git",
            "-c",
            "credential.helper=",
            "-c",
            "credential.helper=store",
            "-c",
            "credential.useHttpPath=true",
            "credential",
            "approve",
        )
        assert approve.stdin_data == (
            b"protocol=https\n"
            b"host=git.example.com:8443\n"
            b"path=group/repo.git\n"
            b"username=oauth2\n"
            b"password=SUPERSECRET123\n\n"
        )

    async def test_clone_argv_has_helper_config_but_no_secret(self, tmp_path: Path):
        _, clone = await self._clone_with_credentials(tmp_path / "clone")
        assert clone.argv == (
            "git",
            "clone",
            "--config",
            "core.symlinks=false",
            "--config",
            "credential.helper=",
            "--config",
            "credential.helper=store",
            "--config",
            "credential.useHttpPath=true",
            "https://git.example.com:8443/group/repo.git",
            clone.argv[-1],
        )
        assert Path(clone.argv[-1]).parent == tmp_path / "clone"
        assert Path(clone.argv[-1]).name.startswith(".clone-")
        assert all("SUPERSECRET123" not in arg for arg in clone.argv)

    async def test_clone_materialises_symlinks_as_files(
        self, local_remote: str, tmp_path: Path
    ):
        """A committed symlink must not become a real link in the checkout.

        Regression: the read-only subagent reads paths from the working copy,
        and a link committed by a contributor would otherwise point it
        wherever they chose.
        """
        work = tmp_path / "work"
        _git("clone", local_remote, str(work))
        (work / "creds").symlink_to("/etc/hostname")
        _git("add", "creds", cwd=work)
        _git(
            "-c",
            "user.email=t@t",
            "-c",
            "user.name=t",
            "commit",
            "-m",
            "link",
            cwd=work,
        )
        _git("push", "origin", "HEAD", cwd=work)

        target = tmp_path / "clone"
        await clone_repository(local_remote, str(target))
        link = target / "creds"
        assert not link.is_symlink()
        assert link.read_text() == "/etc/hostname"
        assert _git_config(target, "core.symlinks") == ["false"]

    async def test_clone_without_password_skips_credential_store(
        self, local_remote: str, tmp_path: Path
    ):
        target = tmp_path / "clone"
        await clone_repository(local_remote, str(target))
        helper = subprocess.run(
            ["git", "config", "--local", "credential.helper"],
            cwd=target,
            capture_output=True,
            text=True,
            env={"GIT_TERMINAL_PROMPT": "0", "PATH": _path()},
        )
        assert helper.returncode != 0  # no helper configured, nothing stored

    async def test_clone_failure_redacts_secret(self, tmp_path: Path):
        secret = "SUPERSECRET123"
        process = _FakeProcess()
        process.returncode = 128

        async def failing_communicate(_input: bytes | None = None):
            return b"", f"fatal: auth failed for token {secret}".encode()

        process.communicate = failing_communicate  # type: ignore[method-assign]
        with (
            patch(
                "core.git.clone.asyncio.create_subprocess_exec",
                new=AsyncMock(return_value=process),
            ),
            pytest.raises(GitOperationError) as exc_info,
        ):
            await clone_repository(
                "https://git.example.com/repo.git",
                str(tmp_path / "clone"),
                user="u",
                password=secret,
            )
        message = str(exc_info.value)
        assert secret not in message
        assert "***" in message


class TestCredentialStoreRoundTrip:
    """End-to-end checks against real git, in an isolated HOME.

    These assert the behaviour git actually exhibits with the settings we
    ship, rather than the arguments we pass.
    """

    async def test_inherited_helper_is_not_consulted(
        self, isolated_home: Path, tmp_path: Path
    ):
        # A helper configured at global scope must neither receive the token
        # nor be able to answer lookups with a stale one.
        marker = tmp_path / "inherited-helper-ran.txt"
        (isolated_home / ".gitconfig").write_text(
            "[credential]\n" f'\thelper = "!f() {{ echo ran >> {marker}; }}; f"\n'
        )

        await _store_credential(
            "https://git.example.com/group/repo.git", "oauth2", "TOKEN_A"
        )

        assert not marker.exists()
        stored = (isolated_home / ".git-credentials").read_text()
        assert stored.strip() == (
            "https://oauth2:TOKEN_A@git.example.com/group/repo.git"
        )

    async def test_credentials_are_scoped_per_repository(self, isolated_home: Path):
        # Same host and username, different repositories: each must keep its
        # own token instead of overwriting or reusing the other's.
        host = "https://git.example.com"
        await _store_credential(f"{host}/group/repo-a.git", "oauth2", "TOKEN_A")
        await _store_credential(f"{host}/group/repo-b.git", "oauth2", "TOKEN_B")

        stored = (isolated_home / ".git-credentials").read_text().strip().splitlines()
        assert len(stored) == 2

        assert _credential_fill(f"{host}/group/repo-a.git", isolated_home) == "TOKEN_A"
        assert _credential_fill(f"{host}/group/repo-b.git", isolated_home) == "TOKEN_B"

    async def test_rotated_token_replaces_entry(self, isolated_home: Path):
        url = "https://git.example.com/group/repo.git"
        await _store_credential(url, "oauth2", "OLD_TOKEN")
        await _store_credential(url, "oauth2", "NEW_TOKEN")

        stored = (isolated_home / ".git-credentials").read_text().strip().splitlines()
        assert len(stored) == 1
        assert _credential_fill(url, isolated_home) == "NEW_TOKEN"

    @pytest.mark.usefixtures("isolated_home")
    async def test_clone_persists_credential_config_in_repo(
        self, local_remote: str, tmp_path: Path
    ):
        # The cloned repo must look credentials up exactly as they were
        # stored, so the existing auto-pull stays authenticated.
        target = tmp_path / "clone"
        await clone_repository(
            local_remote, str(target), user="oauth2", password="TOKEN_A"
        )

        assert _git_config(target, "--get-all", "credential.helper") == ["", "store"]
        assert _git_config(target, "credential.useHttpPath") == ["true"]
        assert "TOKEN_A" not in (target / ".git" / "config").read_text()
        assert _git_config(target, "remote.origin.url") == [local_remote]
