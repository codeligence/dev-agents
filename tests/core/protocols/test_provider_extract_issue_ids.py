from integrations.devops.config import AzureDevOpsConfig
from integrations.devops.provider import AzureDevOpsIssueProvider
from integrations.github.config import GitHubConfig
from integrations.github.provider import GitHubIssueProvider
from integrations.gitlab.config import GitLabConfig
from integrations.gitlab.provider import GitLabIssueProvider
from integrations.jira.config import JiraConfig
from integrations.jira.provider import JiraIssueProvider


class TestJiraIssueProviderExtractIssueIds:
    """Test cases for JiraIssueProvider.extract_issue_ids method."""

    def test_extract_standard_jira_format(self):
        """Test extraction of standard Jira format (ABC-1234)."""
        config = JiraConfig({})
        provider = JiraIssueProvider(config)

        text = "Please check ABC-1234 and XYZ-567 for details"
        result = provider.extract_issue_ids(text)

        assert set(result) == {"ABC-1234", "XYZ-567"}

    def test_extract_space_separated_format(self):
        """Test extraction of space-separated format (SES 3456)."""
        config = JiraConfig({})
        provider = JiraIssueProvider(config)

        text = "Issues: SES 3456, MNO 789, DEF 111"
        result = provider.extract_issue_ids(text)

        assert set(result) == {"SES-3456", "MNO-789", "DEF-111"}

    def test_extract_mixed_formats(self):
        """Test extraction of mixed dash and space formats."""
        config = JiraConfig({})
        provider = JiraIssueProvider(config)

        text = "Mixed format: DEF-999 and GHI 111, also ABC-123"
        result = provider.extract_issue_ids(text)

        assert set(result) == {"DEF-999", "GHI-111", "ABC-123"}

    def test_extract_case_insensitive_matching(self):
        """Test case-insensitive matching with uppercase output."""
        config = JiraConfig({})
        provider = JiraIssueProvider(config)

        text = "case test: abc-123, XYZ 456, def-789, pqr 999"
        result = provider.extract_issue_ids(text)

        assert set(result) == {"ABC-123", "XYZ-456", "DEF-789", "PQR-999"}

    def test_extract_empty_text(self):
        """Test with empty text."""
        config = JiraConfig({})
        provider = JiraIssueProvider(config)

        result = provider.extract_issue_ids("")

        assert result == []

    def test_extract_multiple_spaces_normalization(self):
        """Test normalization of multiple spaces to single dash."""
        config = JiraConfig({})
        provider = JiraIssueProvider(config)

        text = "Issues with multiple spaces: ABC   123, DEF    456"
        result = provider.extract_issue_ids(text)

        assert set(result) == {"ABC-123", "DEF-456"}

    def test_extract_minimum_project_code_length(self):
        """Test that project codes must be at least 2 characters."""
        config = JiraConfig({})
        provider = JiraIssueProvider(config)

        text = "Valid: AB-123, ABC-456. Invalid: A-789 (too short)"
        result = provider.extract_issue_ids(text)

        assert set(result) == {"AB-123", "ABC-456"}

    def test_extract_duplicate_removal(self):
        """Test that duplicate issue IDs are deduplicated."""
        config = JiraConfig({})
        provider = JiraIssueProvider(config)

        text = "Same issue mentioned twice: ABC-123 and ABC-123 again, also DEF-456"
        result = provider.extract_issue_ids(text)

        # Should only contain unique IDs, order doesn't matter for set comparison
        assert set(result) == {"ABC-123", "DEF-456"}
        assert len(result) == 2

    def test_extract_long_project_codes(self):
        """Test extraction with longer project codes."""
        config = JiraConfig({})
        provider = JiraIssueProvider(config)

        text = "Long codes: PROJECTNAME-1234, VERYLONGPROJECTNAME 5678"
        result = provider.extract_issue_ids(text)

        assert set(result) == {"PROJECTNAME-1234", "VERYLONGPROJECTNAME-5678"}

    def test_extract_with_special_characters_around(self):
        """Test extraction with special characters surrounding issue IDs."""
        config = JiraConfig({})
        provider = JiraIssueProvider(config)

        text = "Issues: [ABC-123], (DEF 456), {GHI-789}, and <JKL 999>."
        result = provider.extract_issue_ids(text)

        assert set(result) == {"ABC-123", "DEF-456", "GHI-789", "JKL-999"}


class TestDefaultIssueProviderExtractIssueIds:
    """Test cases for default extract_issue_ids implementation in other providers."""

    def test_azure_devops_default_implementation(self):
        """Test that Azure DevOps provider uses default empty list implementation."""
        config = AzureDevOpsConfig({})
        provider = AzureDevOpsIssueProvider(config)

        text = "Check ABC-1234 and SES 3456 for details"
        result = provider.extract_issue_ids(text)

        assert result == []

    def test_github_default_implementation(self):
        """Test that GitHub provider uses default empty list implementation."""
        config_data = {}
        config = GitHubConfig.from_config_data(config_data)
        provider = GitHubIssueProvider(config)

        text = "Check ABC-1234 and SES 3456 for details"
        result = provider.extract_issue_ids(text)

        assert result == []

    def test_gitlab_default_implementation(self):
        """Test that GitLab provider uses default empty list implementation."""
        config = GitLabConfig({})
        provider = GitLabIssueProvider(config)

        text = "Check ABC-1234 and SES 3456 for details"
        result = provider.extract_issue_ids(text)

        assert result == []

    def test_all_providers_have_extract_method(self):
        """Test that all provider classes have the extract_issue_ids method."""
        providers = [
            AzureDevOpsIssueProvider(AzureDevOpsConfig({})),
            GitHubIssueProvider(GitHubConfig.from_config_data({})),
            GitLabIssueProvider(GitLabConfig({})),
            JiraIssueProvider(JiraConfig({})),
        ]

        for provider in providers:
            assert hasattr(provider, "extract_issue_ids")
            assert callable(provider.extract_issue_ids)

    def test_method_signature_consistency(self):
        """Test that all providers have consistent method signature."""
        providers = [
            AzureDevOpsIssueProvider(AzureDevOpsConfig({})),
            GitHubIssueProvider(GitHubConfig.from_config_data({})),
            GitLabIssueProvider(GitLabConfig({})),
            JiraIssueProvider(JiraConfig({})),
        ]

        test_text = "Test text with ABC-123"

        for provider in providers:
            # Should not raise any exceptions
            result = provider.extract_issue_ids(test_text)
            assert isinstance(result, list)
            assert all(isinstance(issue_id, str) for issue_id in result)


class TestProtocolComplianceExtractIssueIds:
    """Test protocol compliance for extract_issue_ids method."""

    def test_protocol_method_exists(self):
        """Test that the protocol defines the extract_issue_ids method."""
        from core.protocols.provider_protocols import IssueProvider

        # Check that the method exists in the protocol
        assert hasattr(IssueProvider, "extract_issue_ids")

    def test_jira_provider_overrides_default(self):
        """Test that Jira provider properly overrides the default implementation."""
        config = JiraConfig({})
        provider = JiraIssueProvider(config)

        # Jira should extract issue IDs
        result = provider.extract_issue_ids("Check ABC-123")
        assert result == ["ABC-123"]

        # Verify it's not using default empty implementation
        assert result != []

    def test_other_providers_use_default(self):
        """Test that non-Jira providers use the default implementation."""
        providers = [
            AzureDevOpsIssueProvider(AzureDevOpsConfig({})),
            GitHubIssueProvider(GitHubConfig.from_config_data({})),
            GitLabIssueProvider(GitLabConfig({})),
        ]

        for provider in providers:
            result = provider.extract_issue_ids("Check ABC-123")
            assert result == []  # Default implementation returns empty list
