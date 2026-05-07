import pytest

from integrations.linear.provider import LinearIssueProvider


class TestLinearIssueProvider:
    """Test cases for LinearIssueProvider."""

    def test_from_config_valid(self):
        """Test creating provider with valid config."""
        config_data = {"api_key": "lin_api_test123"}
        provider = LinearIssueProvider.from_config(config_data)
        assert provider is not None
        assert isinstance(provider, LinearIssueProvider)

    def test_from_config_missing_api_key(self):
        """Test creating provider with missing API key returns None."""
        provider = LinearIssueProvider.from_config({})
        assert provider is None

    def test_from_config_empty_api_key(self):
        """Test creating provider with empty API key returns None."""
        provider = LinearIssueProvider.from_config({"api_key": ""})
        assert provider is None

    def test_from_config_mock_mode(self):
        """Test creating provider in mock mode without API key."""
        provider = LinearIssueProvider.from_config({"mock": True})
        assert provider is not None

    @pytest.mark.asyncio
    async def test_load_mock_issue(self):
        """Test loading an issue in mock mode."""
        provider = LinearIssueProvider.from_config({"mock": True})
        assert provider is not None

        issue = await provider.load("ENG-123")
        assert issue.id == "ENG-123"
        assert "ENG-123" in issue.context
        assert "Implement Linear integration" in issue.context

    @pytest.mark.asyncio
    async def test_load_mock_issue_updates_identifier(self):
        """Test that mock load updates the identifier to match the request."""
        provider = LinearIssueProvider.from_config({"mock": True})
        assert provider is not None

        issue = await provider.load("TEAM-456")
        assert issue.id == "TEAM-456"
        assert "TEAM-456" in issue.context

    def test_extract_issue_ids_basic(self):
        """Test extracting Linear issue IDs from text."""
        provider = LinearIssueProvider.from_config({"mock": True})
        assert provider is not None

        ids = provider.extract_issue_ids("Fix bug in ENG-123 and TEAM-456")
        assert "ENG-123" in ids
        assert "TEAM-456" in ids

    def test_extract_issue_ids_case_insensitive(self):
        """Test that issue ID extraction is case insensitive."""
        provider = LinearIssueProvider.from_config({"mock": True})
        assert provider is not None

        ids = provider.extract_issue_ids("See eng-123 for details")
        assert "ENG-123" in ids

    def test_extract_issue_ids_no_matches(self):
        """Test extracting issue IDs when no matches exist."""
        provider = LinearIssueProvider.from_config({"mock": True})
        assert provider is not None

        ids = provider.extract_issue_ids("No issue references here")
        assert ids == []

    def test_extract_issue_ids_deduplication(self):
        """Test that duplicate issue IDs are deduplicated."""
        provider = LinearIssueProvider.from_config({"mock": True})
        assert provider is not None

        ids = provider.extract_issue_ids("ENG-123 is related to ENG-123")
        assert len(ids) == 1
        assert "ENG-123" in ids

    def test_extract_issue_ids_ignores_short_keys(self):
        """Test that single-letter team keys are ignored."""
        provider = LinearIssueProvider.from_config({"mock": True})
        assert provider is not None

        ids = provider.extract_issue_ids("See X-123 for details")
        assert ids == []

    def test_extract_issue_ids_multiple_teams(self):
        """Test extracting IDs from multiple teams."""
        provider = LinearIssueProvider.from_config({"mock": True})
        assert provider is not None

        ids = provider.extract_issue_ids(
            "Blocked by ENG-100, related to DESIGN-50 and QA-200"
        )
        assert len(ids) == 3
        assert "ENG-100" in ids
        assert "DESIGN-50" in ids
        assert "QA-200" in ids
