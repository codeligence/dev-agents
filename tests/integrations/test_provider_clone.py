from unittest.mock import AsyncMock, Mock, patch

import pytest

from core.exceptions import GitOperationError
from core.protocols.provider_protocols import PullRequestModel, PullRequestProvider
from integrations.bitbucket.provider import BitBucketPullRequestProvider
from integrations.devops.provider import AzureDevOpsPullRequestProvider
from integrations.github.provider import GitHubPullRequestProvider
from integrations.gitlab.provider import GitLabMergeRequestProvider

_CLONE_REPOSITORY = "core.protocols.provider_protocols.clone_repository"


class TestGitHubClone:
    def _provider(self, **overrides) -> GitHubPullRequestProvider:
        config = Mock()
        config.get_use_mocks.return_value = overrides.get("mock", False)
        config.get_allow_insecure_clone_url.return_value = overrides.get(
            "allow_insecure", False
        )
        config.get_api_url.return_value = overrides.get(
            "api_url", "https://api.github.com"
        )
        config.get_owner.return_value = overrides.get("owner", "octocat")
        config.get_repo.return_value = overrides.get("repo", "hello")
        config.get_token.return_value = overrides.get("token", "ghtoken")
        return GitHubPullRequestProvider(config)

    async def test_clone_is_noop_in_mock_mode(self):
        provider = self._provider(mock=True)
        with patch(_CLONE_REPOSITORY, new=AsyncMock()) as mock_clone:
            await provider.clone("/tmp/target")
        mock_clone.assert_not_awaited()

    async def test_clone_passes_url_and_credentials(self):
        provider = self._provider()
        with patch(_CLONE_REPOSITORY, new=AsyncMock()) as mock_clone:
            await provider.clone("/tmp/target")
        mock_clone.assert_awaited_once_with(
            "https://github.com/octocat/hello.git",
            "/tmp/target",
            user="x-access-token",
            password="ghtoken",
        )

    async def test_clone_enterprise_host(self):
        provider = self._provider(api_url="https://ghe.corp.com/api/v3")
        with patch(_CLONE_REPOSITORY, new=AsyncMock()) as mock_clone:
            await provider.clone("/tmp/target")
        assert mock_clone.await_args.args[0] == (
            "https://ghe.corp.com/octocat/hello.git"
        )

    async def test_clone_unconfigured_raises(self):
        provider = self._provider(token="")
        with pytest.raises(GitOperationError):
            await provider.clone("/tmp/target")

    async def test_clone_url_is_https_even_for_http_api_url(self):
        provider = self._provider(api_url="http://ghe.corp.com/api/v3")
        with patch(_CLONE_REPOSITORY, new=AsyncMock()) as mock_clone:
            await provider.clone("/tmp/target")
        assert mock_clone.await_args.args[0] == (
            "https://ghe.corp.com/octocat/hello.git"
        )


class TestAzureDevOpsClone:
    def _provider(self, **overrides) -> AzureDevOpsPullRequestProvider:
        config = Mock()
        config.get_use_mocks.return_value = overrides.get("mock", False)
        config.get_allow_insecure_clone_url.return_value = overrides.get(
            "allow_insecure", False
        )
        config.get_url.return_value = overrides.get("url", "https://dev.azure.com")
        config.get_organization.return_value = overrides.get("organization", "org")
        config.get_project.return_value = overrides.get("project", "proj")
        config.get_repo_id.return_value = overrides.get("repo_id", "repo-guid")
        config.get_pat.return_value = overrides.get("pat", "azpat")
        return AzureDevOpsPullRequestProvider(config)

    async def test_clone_is_noop_in_mock_mode(self):
        provider = self._provider(mock=True)
        with patch(_CLONE_REPOSITORY, new=AsyncMock()) as mock_clone:
            await provider.clone("/tmp/target")
        mock_clone.assert_not_awaited()

    async def test_clone_passes_url_and_credentials(self):
        provider = self._provider()
        with patch(_CLONE_REPOSITORY, new=AsyncMock()) as mock_clone:
            await provider.clone("/tmp/target")
        mock_clone.assert_awaited_once_with(
            "https://dev.azure.com/org/proj/_git/repo-guid",
            "/tmp/target",
            user="",
            password="azpat",
        )

    async def test_clone_unconfigured_raises(self):
        provider = self._provider(repo_id=None)
        with pytest.raises(GitOperationError):
            await provider.clone("/tmp/target")

    async def test_clone_http_url_rejected(self):
        provider = self._provider(url="http://tfs.corp.local")
        with (
            patch(_CLONE_REPOSITORY, new=AsyncMock()) as mock_clone,
            pytest.raises(GitOperationError, match="must use https"),
        ):
            await provider.clone("/tmp/target")
        mock_clone.assert_not_awaited()

    async def test_clone_http_url_allowed_with_override(self):
        provider = self._provider(url="http://tfs.corp.local", allow_insecure=True)
        with patch(_CLONE_REPOSITORY, new=AsyncMock()) as mock_clone:
            await provider.clone("/tmp/target")
        assert mock_clone.await_args.args[0] == (
            "http://tfs.corp.local/org/proj/_git/repo-guid"
        )

    async def test_clone_self_hosted_with_port(self):
        provider = self._provider(url="https://tfs.corp.local:8443/tfs")
        with patch(_CLONE_REPOSITORY, new=AsyncMock()) as mock_clone:
            await provider.clone("/tmp/target")
        assert mock_clone.await_args.args[0] == (
            "https://tfs.corp.local:8443/tfs/org/proj/_git/repo-guid"
        )


class TestBitbucketClone:
    def _provider(self, **overrides) -> BitBucketPullRequestProvider:
        config = Mock()
        config.get_use_mocks.return_value = overrides.get("mock", False)
        config.get_allow_insecure_clone_url.return_value = overrides.get(
            "allow_insecure", False
        )
        config.get_api_url.return_value = overrides.get(
            "api_url", "https://api.bitbucket.org/2.0"
        )
        config.get_workspace.return_value = overrides.get("workspace", "ws")
        config.get_repo_slug.return_value = overrides.get("repo_slug", "slug")
        config.get_username.return_value = overrides.get("username", "me@corp.com")
        config.get_token.return_value = overrides.get("token", "bbtoken")
        return BitBucketPullRequestProvider(config)

    async def test_clone_is_noop_in_mock_mode(self):
        provider = self._provider(mock=True)
        with patch(_CLONE_REPOSITORY, new=AsyncMock()) as mock_clone:
            await provider.clone("/tmp/target")
        mock_clone.assert_not_awaited()

    async def test_clone_passes_url_and_credentials(self):
        provider = self._provider()
        with patch(_CLONE_REPOSITORY, new=AsyncMock()) as mock_clone:
            await provider.clone("/tmp/target")
        mock_clone.assert_awaited_once_with(
            "https://bitbucket.org/ws/slug.git",
            "/tmp/target",
            user="me@corp.com",
            password="bbtoken",
        )

    async def test_clone_unconfigured_raises(self):
        provider = self._provider(workspace="")
        with pytest.raises(GitOperationError):
            await provider.clone("/tmp/target")


class TestGitLabClone:
    def _provider(self, **overrides) -> GitLabMergeRequestProvider:
        config = Mock()
        config.get_use_mocks.return_value = overrides.get("mock", False)
        config.get_allow_insecure_clone_url.return_value = overrides.get(
            "allow_insecure", False
        )
        config.get_api_url.return_value = overrides.get(
            "api_url", "https://gitlab.example.com/api/v4"
        )
        config.get_project_id.return_value = overrides.get("project_id", "42")
        config.get_token.return_value = overrides.get("token", "gltoken")
        return GitLabMergeRequestProvider(config)

    async def test_clone_is_noop_in_mock_mode(self):
        provider = self._provider(mock=True)
        with (
            patch("integrations.gitlab.provider.httpx.AsyncClient") as mock_client_cls,
            patch(_CLONE_REPOSITORY, new=AsyncMock()) as mock_clone,
        ):
            await provider.clone("/tmp/target")
        mock_client_cls.assert_not_called()
        mock_clone.assert_not_awaited()

    async def test_clone_unconfigured_raises_without_api_call(self):
        provider = self._provider(token="")
        with (
            patch("integrations.gitlab.provider.httpx.AsyncClient") as mock_client_cls,
            pytest.raises(GitOperationError),
        ):
            await provider.clone("/tmp/target")
        mock_client_cls.assert_not_called()

    @staticmethod
    def _api_client(payload: dict) -> AsyncMock:
        response = Mock()
        response.raise_for_status = Mock()
        response.json.return_value = payload
        client = AsyncMock()
        client.get.return_value = response
        return client

    async def test_clone_fetches_clone_url_then_clones(self):
        provider = self._provider()
        client = self._api_client(
            {"http_url_to_repo": "https://gitlab.example.com/group/repo.git"}
        )

        with (
            patch("integrations.gitlab.provider.httpx.AsyncClient") as mock_client_cls,
            patch(_CLONE_REPOSITORY, new=AsyncMock()) as mock_clone,
        ):
            mock_client_cls.return_value.__aenter__.return_value = client
            await provider.clone("/tmp/target")

        client.get.assert_awaited_once_with(
            "https://gitlab.example.com/api/v4/projects/42",
            headers={"Authorization": "Bearer gltoken", "Accept": "application/json"},
        )
        mock_clone.assert_awaited_once_with(
            "https://gitlab.example.com/group/repo.git",
            "/tmp/target",
            user="oauth2",
            password="gltoken",
        )

    async def test_clone_rejects_http_url_from_api(self):
        provider = self._provider()
        client = self._api_client(
            {"http_url_to_repo": "http://gitlab.example.com/group/repo.git"}
        )

        with (
            patch("integrations.gitlab.provider.httpx.AsyncClient") as mock_client_cls,
            patch(_CLONE_REPOSITORY, new=AsyncMock()) as mock_clone,
            pytest.raises(GitOperationError, match="must use https"),
        ):
            mock_client_cls.return_value.__aenter__.return_value = client
            await provider.clone("/tmp/target")
        mock_clone.assert_not_awaited()

    async def test_clone_rejects_foreign_host_from_api(self):
        provider = self._provider()
        client = self._api_client(
            {"http_url_to_repo": "https://evil.example.com/group/repo.git"}
        )

        with (
            patch("integrations.gitlab.provider.httpx.AsyncClient") as mock_client_cls,
            patch(_CLONE_REPOSITORY, new=AsyncMock()) as mock_clone,
            pytest.raises(GitOperationError, match="does not match"),
        ):
            mock_client_cls.return_value.__aenter__.return_value = client
            await provider.clone("/tmp/target")
        mock_clone.assert_not_awaited()

    async def test_clone_rejects_url_with_embedded_credentials(self):
        provider = self._provider()
        client = self._api_client(
            {"http_url_to_repo": "https://oauth2:x@gitlab.example.com/group/repo.git"}
        )

        with (
            patch("integrations.gitlab.provider.httpx.AsyncClient") as mock_client_cls,
            patch(_CLONE_REPOSITORY, new=AsyncMock()) as mock_clone,
            pytest.raises(GitOperationError, match="embed credentials"),
        ):
            mock_client_cls.return_value.__aenter__.return_value = client
            await provider.clone("/tmp/target")
        mock_clone.assert_not_awaited()

    async def test_clone_http_url_allowed_with_override_on_same_host(self):
        provider = self._provider(allow_insecure=True)
        client = self._api_client(
            {"http_url_to_repo": "http://gitlab.example.com/group/repo.git"}
        )

        with (
            patch("integrations.gitlab.provider.httpx.AsyncClient") as mock_client_cls,
            patch(_CLONE_REPOSITORY, new=AsyncMock()) as mock_clone,
        ):
            mock_client_cls.return_value.__aenter__.return_value = client
            await provider.clone("/tmp/target")
        assert mock_clone.await_args.args[0] == (
            "http://gitlab.example.com/group/repo.git"
        )

    async def test_clone_override_still_rejects_foreign_host(self):
        provider = self._provider(allow_insecure=True)
        client = self._api_client(
            {"http_url_to_repo": "http://evil.example.com/group/repo.git"}
        )

        with (
            patch("integrations.gitlab.provider.httpx.AsyncClient") as mock_client_cls,
            patch(_CLONE_REPOSITORY, new=AsyncMock()) as mock_clone,
            pytest.raises(GitOperationError, match="does not match"),
        ):
            mock_client_cls.return_value.__aenter__.return_value = client
            await provider.clone("/tmp/target")
        mock_clone.assert_not_awaited()

    async def test_clone_expected_host_includes_port(self):
        provider = self._provider(api_url="https://gitlab.example.com:8443/api/v4")
        client = self._api_client(
            {"http_url_to_repo": "https://gitlab.example.com:8443/group/repo.git"}
        )

        with (
            patch("integrations.gitlab.provider.httpx.AsyncClient") as mock_client_cls,
            patch(_CLONE_REPOSITORY, new=AsyncMock()) as mock_clone,
        ):
            mock_client_cls.return_value.__aenter__.return_value = client
            await provider.clone("/tmp/target")
        mock_clone.assert_awaited_once()

    async def test_clone_missing_http_url_raises(self):
        provider = self._provider()
        client = self._api_client({})

        with patch("integrations.gitlab.provider.httpx.AsyncClient") as mock_client_cls:
            mock_client_cls.return_value.__aenter__.return_value = client
            with pytest.raises(GitOperationError):
                await provider.clone("/tmp/target")


class TestProtocolDefaultClone:
    async def test_default_clone_raises_not_implemented(self):
        class _BareProvider(PullRequestProvider):
            @staticmethod
            def from_config(config):  # noqa: ARG004
                return None

            async def load(self, pull_request_id: str) -> PullRequestModel:
                return PullRequestModel(id=pull_request_id, context="")

        with pytest.raises(NotImplementedError):
            await _BareProvider().clone("/tmp/target")
