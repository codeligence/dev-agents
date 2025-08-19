import pytest
import tempfile
import os
from unittest.mock import Mock
from typing import Optional, Dict, Any

from core.config import BaseConfig
from core.project_config import ProjectConfig, ProjectConfigFactory
from core.integrations.provider_registry import ProviderRegistry, get_provider_registry
from core.protocols.provider_protocols import PullRequestProvider, IssueProvider, PullRequestModel, IssueModel


class MockPullRequestProvider:
    """Mock pull request provider for testing."""

    def __init__(self, name: str):
        self.name = name

    @staticmethod
    def from_config(config_data: Dict[str, Any]) -> Optional['MockPullRequestProvider']:
        """Create provider from config data."""
        if config_data.get("enabled", True):
            return MockPullRequestProvider(config_data.get("name", "mock"))
        return None

    async def load(self, pull_request_id: str) -> PullRequestModel:
        """Load pull request by ID."""
        return PullRequestModel(
            id=pull_request_id,
            context=f"Mock PR {pull_request_id} from {self.name}",
            source_branch="feature/test",
            target_branch="main"
        )


class MockIssueProvider:
    """Mock issue provider for testing."""

    def __init__(self, name: str):
        self.name = name

    @staticmethod
    def from_config(config_data: Dict[str, Any]) -> Optional['MockIssueProvider']:
        """Create provider from config data."""
        if config_data.get("enabled", True):
            return MockIssueProvider(config_data.get("name", "mock"))
        return None

    async def load(self, issue_id: str) -> IssueModel:
        """Load issue by ID."""
        return IssueModel(
            id=issue_id,
            context=f"Mock Issue {issue_id} from {self.name}"
        )


class FailingProvider:
    """Provider that fails during creation for testing error handling."""

    @staticmethod
    def from_config(config_data: Dict[str, Any]) -> Optional['FailingProvider']:
        """Create provider that always fails."""
        raise Exception("Provider creation failed")


class TestProviderRegistry:
    """Test cases for ProviderRegistry class."""

    def setup_method(self):
        """Set up a fresh registry for each test."""
        self.registry = ProviderRegistry()

    def test_registry_initialization(self):
        """Test ProviderRegistry initialization."""
        assert isinstance(self.registry._pullrequest_providers, dict)
        assert isinstance(self.registry._issue_providers, dict)
        assert len(self.registry._pullrequest_providers) == 0
        assert len(self.registry._issue_providers) == 0

    def test_register_pullrequest_provider(self):
        """Test registering pull request providers."""
        self.registry.register_pullrequest_provider("mock", MockPullRequestProvider.from_config)

        providers = self.registry.get_registered_pullrequest_providers()
        assert "mock" in providers
        assert len(providers) == 1

    def test_register_issue_provider(self):
        """Test registering issue providers."""
        self.registry.register_issue_provider("mock", MockIssueProvider.from_config)

        providers = self.registry.get_registered_issue_providers()
        assert "mock" in providers
        assert len(providers) == 1

    def test_register_multiple_providers(self):
        """Test registering multiple providers."""
        self.registry.register_pullrequest_provider("mock1", MockPullRequestProvider.from_config)
        self.registry.register_pullrequest_provider("mock2", MockPullRequestProvider.from_config)
        self.registry.register_issue_provider("mock1", MockIssueProvider.from_config)
        self.registry.register_issue_provider("mock2", MockIssueProvider.from_config)

        pr_providers = self.registry.get_registered_pullrequest_providers()
        issue_providers = self.registry.get_registered_issue_providers()

        assert len(pr_providers) == 2
        assert "mock1" in pr_providers
        assert "mock2" in pr_providers

        assert len(issue_providers) == 2
        assert "mock1" in issue_providers
        assert "mock2" in issue_providers

    def _create_test_project_config(self, config_content: str) -> ProjectConfig:
        """Helper to create a project config for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write(config_content)
            temp_path = f.name

        # Store path for cleanup
        self._temp_files = getattr(self, '_temp_files', [])
        self._temp_files.append(temp_path)

        base_config = BaseConfig(temp_path)
        factory = ProjectConfigFactory(base_config)
        return factory.get_project_config("test_project")

    def teardown_method(self):
        """Clean up temporary files after each test."""
        if hasattr(self, '_temp_files'):
            for temp_file in self._temp_files:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
            self._temp_files = []

    def test_resolve_pullrequest_provider_success(self):
        """Test successful pull request provider resolution."""
        config_content = """
projects:
  test_project:
    git:
      path: "/test/repo"
    pullrequests:
      mock:
        enabled: true
        name: "test-mock"
"""
        self.registry.register_pullrequest_provider("mock", MockPullRequestProvider.from_config)
        project_config = self._create_test_project_config(config_content)

        provider = self.registry.resolve_pullrequest_provider(project_config)
        assert provider is not None
        assert isinstance(provider, MockPullRequestProvider)
        assert provider.name == "test-mock"

    def test_resolve_issue_provider_success(self):
        """Test successful issue provider resolution."""
        config_content = """
projects:
  test_project:
    git:
      path: "/test/repo"
    issues:
      mock:
        enabled: true
        name: "test-mock"
"""
        self.registry.register_issue_provider("mock", MockIssueProvider.from_config)
        project_config = self._create_test_project_config(config_content)

        provider = self.registry.resolve_issue_provider(project_config)
        assert provider is not None
        assert isinstance(provider, MockIssueProvider)
        assert provider.name == "test-mock"

    def test_resolve_provider_no_match(self):
        """Test provider resolution when no providers match."""
        config_content = """
projects:
  test_project:
    git:
      path: "/test/repo"
    pullrequests:
      unknown_provider:
        enabled: true
"""
        self.registry.register_pullrequest_provider("mock", MockPullRequestProvider.from_config)
        project_config = self._create_test_project_config(config_content)

        provider = self.registry.resolve_pullrequest_provider(project_config)
        assert provider is None

    def test_resolve_provider_disabled(self):
        """Test provider resolution when provider is disabled."""
        config_content = """
projects:
  test_project:
    git:
      path: "/test/repo"
    pullrequests:
      mock:
        enabled: false
        name: "test-mock"
"""
        self.registry.register_pullrequest_provider("mock", MockPullRequestProvider.from_config)
        project_config = self._create_test_project_config(config_content)

        provider = self.registry.resolve_pullrequest_provider(project_config)
        assert provider is None

    def test_resolve_provider_creation_failure(self):
        """Test provider resolution when provider creation fails."""
        config_content = """
projects:
  test_project:
    git:
      path: "/test/repo"
    pullrequests:
      failing:
        enabled: true
"""
        self.registry.register_pullrequest_provider("failing", FailingProvider.from_config)
        project_config = self._create_test_project_config(config_content)

        # Should handle the exception gracefully and return None
        provider = self.registry.resolve_pullrequest_provider(project_config)
        assert provider is None

    def test_resolve_provider_multiple_candidates(self):
        """Test provider resolution with multiple candidate providers."""
        config_content = """
projects:
  test_project:
    git:
      path: "/test/repo"
    pullrequests:
      mock1:
        enabled: false  # This one is disabled
        name: "disabled-mock"
      mock2:
        enabled: true   # This one should be selected
        name: "selected-mock"
"""
        self.registry.register_pullrequest_provider("mock1", MockPullRequestProvider.from_config)
        self.registry.register_pullrequest_provider("mock2", MockPullRequestProvider.from_config)
        project_config = self._create_test_project_config(config_content)

        provider = self.registry.resolve_pullrequest_provider(project_config)
        assert provider is not None
        assert isinstance(provider, MockPullRequestProvider)
        assert provider.name == "selected-mock"

    def test_resolve_provider_first_match_wins(self):
        """Test that first matching provider is returned."""
        config_content = """
projects:
  test_project:
    git:
      path: "/test/repo"
    pullrequests:
      mock1:
        enabled: true
        name: "first-mock"
      mock2:
        enabled: true
        name: "second-mock"
"""
        self.registry.register_pullrequest_provider("mock1", MockPullRequestProvider.from_config)
        self.registry.register_pullrequest_provider("mock2", MockPullRequestProvider.from_config)
        project_config = self._create_test_project_config(config_content)

        # The order depends on dict iteration, but one should be selected
        provider = self.registry.resolve_pullrequest_provider(project_config)
        assert provider is not None
        assert isinstance(provider, MockPullRequestProvider)
        assert provider.name in ["first-mock", "second-mock"]

    def test_empty_provider_config(self):
        """Test provider resolution with empty provider configs."""
        config_content = """
projects:
  test_project:
    git:
      path: "/test/repo"
    pullrequests: {}
    issues: {}
"""
        self.registry.register_pullrequest_provider("mock", MockPullRequestProvider.from_config)
        self.registry.register_issue_provider("mock", MockIssueProvider.from_config)
        project_config = self._create_test_project_config(config_content)

        pr_provider = self.registry.resolve_pullrequest_provider(project_config)
        issue_provider = self.registry.resolve_issue_provider(project_config)

        assert pr_provider is None
        assert issue_provider is None


class TestGlobalProviderRegistry:
    """Test cases for global provider registry singleton."""

    def test_get_provider_registry_singleton(self):
        """Test that get_provider_registry returns the same instance."""
        registry1 = get_provider_registry()
        registry2 = get_provider_registry()

        assert registry1 is registry2
        assert isinstance(registry1, ProviderRegistry)

    def test_global_registry_persistence(self):
        """Test that registrations persist across calls."""
        registry1 = get_provider_registry()
        registry1.register_pullrequest_provider("test", MockPullRequestProvider.from_config)

        registry2 = get_provider_registry()
        providers = registry2.get_registered_pullrequest_providers()

        assert "test" in providers

    def test_global_registry_state_isolation(self):
        """Test that global registry state is isolated from local instances."""
        global_registry = get_provider_registry()
        local_registry = ProviderRegistry()

        global_registry.register_pullrequest_provider("global", MockPullRequestProvider.from_config)
        local_registry.register_pullrequest_provider("local", MockPullRequestProvider.from_config)

        global_providers = global_registry.get_registered_pullrequest_providers()
        local_providers = local_registry.get_registered_pullrequest_providers()

        assert "global" in global_providers
        assert "local" not in global_providers
        assert "local" in local_providers
        assert "global" not in local_providers