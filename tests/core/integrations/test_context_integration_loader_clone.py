from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from core.integrations.context_integration_loader import ContextIntegrationLoader
from integrations.git.config import GitRepositoryConfig


def _loader(repo_dir: Path) -> ContextIntegrationLoader:
    project_config = Mock()
    project_config.get_git_config.return_value = {"path": str(repo_dir)}
    return ContextIntegrationLoader(project_config)


class TestEnsureRepositoryAvailable:
    """Tests for ContextIntegrationLoader.ensure_repository_available."""

    async def test_skips_clone_when_checkout_present(self, tmp_path: Path):
        (tmp_path / ".git").mkdir()
        loader = _loader(tmp_path)
        provider = Mock()
        provider.clone = AsyncMock()
        loader.get_pullrequest_provider = Mock(return_value=provider)

        await loader.ensure_repository_available()

        provider.clone.assert_not_awaited()

    async def test_skips_clone_when_directory_populated_but_not_git(
        self, tmp_path: Path
    ):
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        (repo_dir / "existing_file.txt").write_text("content")
        loader = _loader(repo_dir)
        provider = Mock()
        provider.clone = AsyncMock()
        loader.get_pullrequest_provider = Mock(return_value=provider)

        await loader.ensure_repository_available()

        provider.clone.assert_not_awaited()

    async def test_skips_clone_when_dir_populated_during_lock_wait(
        self, tmp_path: Path
    ):
        # Simulate the directory being empty at the pre-lock check but populated
        # (non-git) by the time the lock is acquired: is_repo_dir_empty returns
        # True then False, has_git_repo stays False throughout.
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        loader = _loader(repo_dir)
        provider = Mock()
        provider.clone = AsyncMock()
        loader.get_pullrequest_provider = Mock(return_value=provider)

        with (
            patch.object(GitRepositoryConfig, "has_git_repo", return_value=False),
            patch.object(
                GitRepositoryConfig, "is_repo_dir_empty", side_effect=[True, False]
            ),
        ):
            await loader.ensure_repository_available()

        provider.clone.assert_not_awaited()

    async def test_clones_when_directory_empty(self, tmp_path: Path):
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        loader = _loader(repo_dir)
        provider = Mock()
        provider.clone = AsyncMock()
        loader.get_pullrequest_provider = Mock(return_value=provider)

        await loader.ensure_repository_available()

        provider.clone.assert_awaited_once_with(str(repo_dir.resolve()))

    async def test_is_idempotent_once_cloned(self, tmp_path: Path):
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        loader = _loader(repo_dir)

        async def fake_clone(target_dir: str) -> None:
            (Path(target_dir) / ".git").mkdir()

        provider = Mock()
        provider.clone = AsyncMock(side_effect=fake_clone)
        loader.get_pullrequest_provider = Mock(return_value=provider)

        await loader.ensure_repository_available()
        await loader.ensure_repository_available()

        provider.clone.assert_awaited_once()

    async def test_raises_when_no_provider(self, tmp_path: Path):
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        loader = _loader(repo_dir)
        loader.get_pullrequest_provider = Mock(return_value=None)

        with pytest.raises(ValueError, match="No pull request provider"):
            await loader.ensure_repository_available()
