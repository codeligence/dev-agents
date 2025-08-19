import pytest
from unittest.mock import patch, AsyncMock, Mock, MagicMock
import httpx
from integrations.devops.provider import AzureDevOpsPullRequestProvider, AzureDevOpsIssueProvider
from integrations.devops.config import AzureDevOpsConfig
from core.protocols.provider_protocols import PullRequestModel, IssueModel


class TestAzureDevOpsPullRequestProvider:
    """Test cases for AzureDevOpsPullRequestProvider."""

    def test_from_config_with_valid_config(self):
        """Test provider creation with valid configuration."""
        config_data = {
            "url": "https://dev.azure.com",
            "organization": "test-org",
            "project": "test-project",
            "pat": "test-token",
            "repoId": "test-repo-id",
            "mock": False
        }

        provider = AzureDevOpsPullRequestProvider.from_config(config_data)
        assert provider is not None
        assert isinstance(provider, AzureDevOpsPullRequestProvider)
        assert isinstance(provider.config, AzureDevOpsConfig)

    def test_from_config_with_mock_enabled(self):
        """Test provider creation with mock mode enabled."""
        config_data = {
            "url": None,
            "organization": None,
            "project": None,
            "pat": None,
            "repoId": None,
            "mock": True
        }

        provider = AzureDevOpsPullRequestProvider.from_config(config_data)
        assert provider is not None
        assert isinstance(provider, AzureDevOpsPullRequestProvider)
        assert provider.config.get_use_mocks() == True

    def test_from_config_with_invalid_config(self):
        """Test provider creation with invalid configuration."""
        config_data = {
            "url": None,
            "organization": None,
            "project": None,
            "pat": None,
            "repoId": None,
            "mock": False  # Not configured and not mock mode
        }

        provider = AzureDevOpsPullRequestProvider.from_config(config_data)
        assert provider is None

    def test_from_config_with_empty_config(self):
        """Test provider creation with empty configuration."""
        provider = AzureDevOpsPullRequestProvider.from_config({})
        assert provider is None

    @pytest.mark.asyncio
    async def test_load_with_mock_mode(self):
        """Test loading pull request in mock mode."""
        config_data = {"mock": True}
        provider = AzureDevOpsPullRequestProvider.from_config(config_data)

        # Mock the mock functions
        with patch('integrations.devops.provider.mock_fetch_pull_request') as mock_fetch:
            mock_pr = Mock()
            mock_pr.get_composed_PR_info.return_value = "Mock PR Info"
            mock_pr.get_source_branch.return_value = "feature/test"
            mock_pr.get_target_branch.return_value = "main"
            mock_pr.get_source_commit_id.return_value = "abc123"
            mock_pr.get_target_commit_id.return_value = "def456"
            mock_pr.get_merge_commit_id.return_value = "ghi789"
            mock_fetch.return_value = mock_pr

            result = await provider.load("123")

            assert isinstance(result, PullRequestModel)
            assert result.id == "123"
            assert result.context == "Mock PR Info"
            assert result.source_branch == "feature/test"
            assert result.target_branch == "main"
            assert result.source_refs == ["feature/test", "abc123", "ghi789"]
            assert result.target_refs == ["main", "def456"]
            mock_fetch.assert_called_once_with("123")

    @pytest.mark.asyncio
    async def test_load_with_real_mode(self):
        """Test loading pull request in real mode."""
        config_data = {
            "url": "https://dev.azure.com",
            "organization": "test-org",
            "project": "test-project",
            "pat": "test-token",
            "repoId": "test-repo-id",
            "mock": False
        }
        provider = AzureDevOpsPullRequestProvider.from_config(config_data)

        # Mock the async fetch method
        with patch.object(provider, '_fetch_pull_request') as mock_fetch_async:
            mock_pr = Mock()
            mock_pr.get_composed_PR_info.return_value = "Real PR Info"
            mock_pr.get_source_branch.return_value = "feature/real"
            mock_pr.get_target_branch.return_value = "develop"
            mock_pr.get_source_commit_id.return_value = "real123"
            mock_pr.get_target_commit_id.return_value = "real456"
            mock_pr.get_merge_commit_id.return_value = "real789"
            mock_fetch_async.return_value = mock_pr

            result = await provider.load("456")

            assert isinstance(result, PullRequestModel)
            assert result.id == "456"
            assert result.context == "Real PR Info"
            assert result.source_branch == "feature/real"
            assert result.target_branch == "develop"
            assert result.source_refs == ["feature/real", "real123", "real789"]
            assert result.target_refs == ["develop", "real456"]
            mock_fetch_async.assert_called_once_with("456")

    @pytest.mark.asyncio
    async def test_fetch_pull_request_with_httpx(self):
        """Test _fetch_pull_request with mocked httpx client."""
        config_data = {
            "url": "https://dev.azure.com",
            "organization": "test-org",
            "project": "test-project",
            "pat": "test-token",
            "repoId": "test-repo-id",
            "mock": False
        }
        provider = AzureDevOpsPullRequestProvider.from_config(config_data)

        # Mock httpx responses
        mock_pr_response = Mock()
        mock_pr_response.status_code = 200
        mock_pr_response.raise_for_status = Mock()
        mock_pr_response.json.return_value = {
            "pullRequestId": 123,
            "title": "Test PR",
            "sourceRefName": "refs/heads/feature",
            "targetRefName": "refs/heads/main"
        }

        mock_commits_response = Mock()
        mock_commits_response.status_code = 200
        mock_commits_response.raise_for_status = Mock()
        mock_commits_response.json.return_value = {
            "value": [{"commitId": "commit123"}]
        }

        # Mock AsyncClient
        mock_client = AsyncMock()
        mock_client.get.side_effect = [mock_pr_response, mock_commits_response]
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch('httpx.AsyncClient', return_value=mock_client):
            result = await provider._fetch_pull_request("123")

            # Verify client was called with correct URLs
            expected_pr_url = "https://dev.azure.com/test-org/test-project/_apis/git/repositories/test-repo-id/pullRequests/123?api-version=7.1"
            expected_commits_url = "https://dev.azure.com/test-org/test-project/_apis/git/repositories/test-repo-id/pullRequests/123/commits?api-version=7.1"

            assert mock_client.get.call_count == 2
            mock_client.get.assert_any_call(expected_pr_url)
            mock_client.get.assert_any_call(expected_commits_url)

            # Verify result is PullRequest object
            assert result is not None
            assert hasattr(result, 'pr')
            assert hasattr(result, 'commit_data')

    @pytest.mark.asyncio
    async def test_fetch_pull_request_http_error(self):
        """Test _fetch_pull_request with HTTP error."""
        config_data = {
            "url": "https://dev.azure.com",
            "organization": "test-org",
            "project": "test-project",
            "pat": "test-token",
            "repoId": "test-repo-id",
            "mock": False
        }
        provider = AzureDevOpsPullRequestProvider.from_config(config_data)

        # Mock httpx client to raise HTTP error
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404 Not Found", request=Mock(), response=Mock()
        )
        mock_client.get.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch('httpx.AsyncClient', return_value=mock_client):
            with pytest.raises(httpx.HTTPStatusError):
                await provider._fetch_pull_request("999")

    @pytest.mark.asyncio
    async def test_download_image_as_base64_success(self):
        """Test download_image_as_base64 with successful response."""
        config_data = {
            "url": "https://dev.azure.com",
            "organization": "test-org",
            "project": "test-project",
            "pat": "test-token",
            "repoId": "test-repo-id",
            "mock": False
        }
        provider = AzureDevOpsPullRequestProvider.from_config(config_data)

        # Mock image content
        image_content = b"fake_image_data"
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = image_content

        # Mock AsyncClient
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch('httpx.AsyncClient', return_value=mock_client):
            result = await provider.download_image_as_base64("https://example.com/image.png")

            # Verify client was called with correct URL and auth
            mock_client.get.assert_called_once_with("https://example.com/image.png")

            # Verify result is base64 data URI
            assert result is not None
            assert result.startswith("data:image/png;base64,")

    @pytest.mark.asyncio
    async def test_download_image_as_base64_error(self):
        """Test download_image_as_base64 with HTTP error."""
        config_data = {
            "url": "https://dev.azure.com",
            "organization": "test-org",
            "project": "test-project",
            "pat": "test-token",
            "repoId": "test-repo-id",
            "mock": False
        }
        provider = AzureDevOpsPullRequestProvider.from_config(config_data)

        # Mock error response
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404 Not Found", request=Mock(), response=Mock()
        )

        # Mock AsyncClient
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch('httpx.AsyncClient', return_value=mock_client):
            with pytest.raises(httpx.HTTPStatusError):
                await provider.download_image_as_base64("https://example.com/notfound.png")

    @pytest.mark.asyncio
    async def test_refs_with_empty_values(self):
        """Test ref extraction with empty/None commit IDs."""
        config_data = {"mock": True}
        provider = AzureDevOpsPullRequestProvider.from_config(config_data)

        with patch('integrations.devops.provider.mock_fetch_pull_request') as mock_fetch:
            mock_pr = Mock()
            mock_pr.get_composed_PR_info.return_value = "Mock PR Info"
            mock_pr.get_source_branch.return_value = "feature/test"
            mock_pr.get_target_branch.return_value = "main"
            # Return empty/None commit IDs
            mock_pr.get_source_commit_id.return_value = ""
            mock_pr.get_target_commit_id.return_value = None
            mock_pr.get_merge_commit_id.return_value = ""
            mock_fetch.return_value = mock_pr

            result = await provider.load("123")

            # Should only include branches, not empty commit IDs
            assert result.source_refs == ["feature/test"]
            assert result.target_refs == ["main"]

    @pytest.mark.asyncio
    async def test_concurrent_requests_in_fetch_pull_request(self):
        """Test that PR and commits requests are made concurrently."""
        config_data = {
            "url": "https://dev.azure.com",
            "organization": "test-org",
            "project": "test-project",
            "pat": "test-token",
            "repoId": "test-repo-id",
            "mock": False
        }
        provider = AzureDevOpsPullRequestProvider.from_config(config_data)

        # Track call order to verify concurrency
        call_order = []

        async def mock_get(url):
            call_order.append(url)
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            if "pullRequests" in url and "commits" not in url:
                mock_response.json.return_value = {"pullRequestId": 123}
            else:
                mock_response.json.return_value = {"value": []}
            return mock_response

        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch('httpx.AsyncClient', return_value=mock_client):
            await provider._fetch_pull_request("123")

            # Both URLs should be called (verifies concurrent execution)
            assert len(call_order) == 2
            assert any("pullRequests/123?" in url for url in call_order)
            assert any("commits?" in url for url in call_order)



class TestAzureDevOpsIssueProvider:
    """Test cases for AzureDevOpsIssueProvider."""

    def test_from_config_with_valid_config(self):
        """Test provider creation with valid configuration."""
        config_data = {
            "url": "https://dev.azure.com",
            "organization": "test-org",
            "project": "test-project",
            "pat": "test-token",
            "repoId": "test-repo-id",
            "mock": False
        }

        provider = AzureDevOpsIssueProvider.from_config(config_data)
        assert provider is not None
        assert isinstance(provider, AzureDevOpsIssueProvider)
        assert isinstance(provider.config, AzureDevOpsConfig)

    def test_from_config_with_mock_enabled(self):
        """Test provider creation with mock mode enabled."""
        config_data = {
            "url": None,
            "organization": None,
            "project": None,
            "pat": None,
            "repoId": None,
            "mock": True
        }

        provider = AzureDevOpsIssueProvider.from_config(config_data)
        assert provider is not None
        assert isinstance(provider, AzureDevOpsIssueProvider)
        assert provider.config.get_use_mocks() == True

    def test_from_config_with_invalid_config(self):
        """Test provider creation with invalid configuration."""
        config_data = {
            "url": None,
            "organization": None,
            "project": None,
            "pat": None,
            "repoId": None,
            "mock": False  # Not configured and not mock mode
        }

        provider = AzureDevOpsIssueProvider.from_config(config_data)
        assert provider is None

    def test_from_config_with_empty_config(self):
        """Test provider creation with empty configuration."""
        provider = AzureDevOpsIssueProvider.from_config({})
        assert provider is None

    @pytest.mark.asyncio
    async def test_load_with_mock_mode(self):
        """Test loading work item in mock mode."""
        config_data = {"mock": True}
        provider = AzureDevOpsIssueProvider.from_config(config_data)

        # Mock the mock functions
        with patch('integrations.devops.provider.mock_fetch_work_item') as mock_fetch:
            mock_work_item = Mock()
            mock_work_item.get_composed_work_item_info.return_value = "Mock Work Item Info"
            mock_fetch.return_value = mock_work_item

            result = await provider.load("123")

            assert isinstance(result, IssueModel)
            assert result.id == "123"
            assert result.context == "Mock Work Item Info"
            mock_fetch.assert_called_once_with("123")

    @pytest.mark.asyncio
    async def test_load_with_real_mode(self):
        """Test loading work item in real mode."""
        config_data = {
            "url": "https://dev.azure.com",
            "organization": "test-org",
            "project": "test-project",
            "pat": "test-token",
            "repoId": "test-repo-id",
            "mock": False
        }
        provider = AzureDevOpsIssueProvider.from_config(config_data)

        # Mock the async fetch method
        with patch.object(provider, '_fetch_work_item') as mock_fetch_async:
            mock_work_item = Mock()
            mock_work_item.get_composed_work_item_info.return_value = "Real Work Item Info"
            mock_fetch_async.return_value = mock_work_item

            result = await provider.load("456")

            assert isinstance(result, IssueModel)
            assert result.id == "456"
            assert result.context == "Real Work Item Info"
            mock_fetch_async.assert_called_once_with("456")

    @pytest.mark.asyncio
    async def test_fetch_work_item_with_httpx(self):
        """Test _fetch_work_item with mocked httpx client."""
        config_data = {
            "url": "https://dev.azure.com",
            "organization": "test-org",
            "project": "test-project",
            "pat": "test-token",
            "repoId": "test-repo-id",
            "mock": False
        }
        provider = AzureDevOpsIssueProvider.from_config(config_data)

        # Mock httpx response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "id": 123,
            "fields": {
                "System.Title": "Test Work Item",
                "System.State": "Active"
            }
        }

        # Mock AsyncClient
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch('httpx.AsyncClient', return_value=mock_client):
            result = await provider._fetch_work_item("123")

            # Verify client was called with correct URL
            expected_url = "https://dev.azure.com/test-org/test-project/_apis/wit/workitems/123?$expand=Relations&api-version=7.1-preview.3"
            mock_client.get.assert_called_once_with(expected_url)

            # Verify result is WorkItem object
            assert result is not None
            assert hasattr(result, 'data')

    @pytest.mark.asyncio
    async def test_fetch_work_item_http_error(self):
        """Test _fetch_work_item with HTTP error."""
        config_data = {
            "url": "https://dev.azure.com",
            "organization": "test-org",
            "project": "test-project",
            "pat": "test-token",
            "repoId": "test-repo-id",
            "mock": False
        }
        provider = AzureDevOpsIssueProvider.from_config(config_data)

        # Mock httpx client to raise HTTP error
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "403 Forbidden", request=Mock(), response=Mock()
        )
        mock_client.get.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch('httpx.AsyncClient', return_value=mock_client):
            with pytest.raises(httpx.HTTPStatusError):
                await provider._fetch_work_item("999")



class TestProviderRegistration:
    """Test cases for provider registration behavior."""

    def test_providers_registered_on_import(self):
        """Test that Azure providers are registered when module is imported."""
        # Import the azure package to trigger registration
        import integrations.devops

        from core.integrations import get_provider_registry
        registry = get_provider_registry()

        # Check that devops providers are registered
        pr_providers = registry.get_registered_pullrequest_providers()
        issue_providers = registry.get_registered_issue_providers()

        assert "devops" in pr_providers
        assert "devops" in issue_providers

    def test_provider_factory_integration(self):
        """Test that registered providers work with the factory pattern."""
        import integrations.devops
        from core.integrations import get_provider_registry

        registry = get_provider_registry()

        # Test pull request provider factory
        pr_config = {
            "url": "https://dev.azure.com",
            "organization": "test-org",
            "project": "test-project",
            "pat": "test-token",
            "repoId": "test-repo-id",
            "mock": False
        }

        pr_factory = registry._pullrequest_providers["devops"]
        pr_provider = pr_factory(pr_config)
        assert pr_provider is not None
        assert isinstance(pr_provider, AzureDevOpsPullRequestProvider)

        # Test issue provider factory
        issue_config = {
            "url": "https://dev.azure.com",
            "organization": "test-org",
            "project": "test-project",
            "pat": "test-token",
            "repoId": "test-repo-id",
            "mock": False
        }

        issue_factory = registry._issue_providers["devops"]
        issue_provider = issue_factory(issue_config)
        assert issue_provider is not None
        assert isinstance(issue_provider, AzureDevOpsIssueProvider)

    def test_provider_factory_with_invalid_config(self):
        """Test that factory returns None for invalid configs."""
        import integrations.devops
        from core.integrations import get_provider_registry

        registry = get_provider_registry()

        # Test with empty config
        pr_factory = registry._pullrequest_providers["devops"]
        pr_provider = pr_factory({})
        assert pr_provider is None

        issue_factory = registry._issue_providers["devops"]
        issue_provider = issue_factory({})
        assert issue_provider is None
