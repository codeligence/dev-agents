# Copyright (C) 2025 Codeligence
#
# This file is part of Dev Agents.
#
# Dev Agents is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Dev Agents is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Dev Agents.  If not, see <https://www.gnu.org/licenses/>.


import pytest
import tempfile
import os
from core.config import BaseConfig
from integrations.devops.config import AzureDevOpsConfig


class TestAzureDevOpsConfigNew:
    """Test cases for new AzureDevOpsConfig API with project-based configuration."""

    def test_direct_dict_constructor(self):
        """Test AzureDevOpsConfig initialization with direct dictionary."""
        config_data = {
            "url": "https://dev.azure.com",
            "organization": "test-org",
            "project": "test-project",
            "pat": "test-token",
            "repoId": "test-repo-id",
            "mock": False
        }
        azure_config = AzureDevOpsConfig(config_data)

        assert azure_config.get_url() == "https://dev.azure.com"
        assert azure_config.get_organization() == "test-org"
        assert azure_config.get_project() == "test-project"
        assert azure_config.get_pat() == "test-token"
        assert azure_config.get_repo_id() == "test-repo-id"
        assert azure_config.get_use_mocks() == False

    def test_empty_dict_constructor(self):
        """Test AzureDevOpsConfig initialization with empty dictionary."""
        azure_config = AzureDevOpsConfig({})

        assert azure_config.get_url() is None
        assert azure_config.get_organization() is None
        assert azure_config.get_project() is None
        assert azure_config.get_pat() is None
        assert azure_config.get_repo_id() is None
        assert azure_config.get_use_mocks() == False  # Should default to False

    def test_none_constructor(self):
        """Test AzureDevOpsConfig initialization with None."""
        azure_config = AzureDevOpsConfig(None)

        assert azure_config.get_url() is None
        assert azure_config.get_organization() is None
        assert azure_config.get_project() is None
        assert azure_config.get_pat() is None
        assert azure_config.get_repo_id() is None
        assert azure_config.get_use_mocks() == False

    def test_mock_setting_variations(self):
        """Test different mock setting variations."""
        # Test boolean true
        config = AzureDevOpsConfig({"mock": True})
        assert config.get_use_mocks() == True

        # Test string 'true'
        config = AzureDevOpsConfig({"mock": "true"})
        assert config.get_use_mocks() == True

        # Test string 'false'
        config = AzureDevOpsConfig({"mock": "false"})
        assert config.get_use_mocks() == False

        # Test integer 1
        config = AzureDevOpsConfig({"mock": 1})
        assert config.get_use_mocks() == True

        # Test integer 0
        config = AzureDevOpsConfig({"mock": 0})
        assert config.get_use_mocks() == False

    def test_is_configured_with_complete_config(self):
        """Test is_configured with all required fields."""
        config_data = {
            "url": "https://dev.azure.com",
            "organization": "test-org",
            "project": "test-project",
            "pat": "test-token",
            "repoId": "test-repo-id"
        }
        azure_config = AzureDevOpsConfig(config_data)
        assert azure_config.is_configured() == True

    def test_is_configured_with_missing_fields(self):
        """Test is_configured with missing required fields."""
        config_data = {
            "url": "https://dev.azure.com",
            "organization": "test-org"
            # Missing project, pat, repoId
        }
        azure_config = AzureDevOpsConfig(config_data)
        assert azure_config.is_configured() == False

    def test_is_configured_with_empty_fields(self):
        """Test is_configured with empty string fields."""
        config_data = {
            "url": "",  # Empty string should be considered missing
            "organization": "test-org",
            "project": "test-project",
            "pat": "test-token",
            "repoId": "test-repo-id"
        }
        azure_config = AzureDevOpsConfig(config_data)
        assert azure_config.is_configured() == False

    def test_legacy_format_extraction(self):
        """Test extracting config from old azure.devops.* format."""
        config_content = """
azure:
  devops:
    url: "https://dev.azure.com"
    organization: "test-org"
    project: "test-project"
    pat: "test-token"
    repoId: "test-repo-id"
    mock: false
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write(config_content)
            temp_path = f.name

        try:
            base_config = BaseConfig(temp_path)
            config_data = base_config.get_value('azure.devops', {})
            azure_config = AzureDevOpsConfig(config_data)

            assert azure_config.get_url() == "https://dev.azure.com"
            assert azure_config.get_organization() == "test-org"
            assert azure_config.get_project() == "test-project"
            assert azure_config.get_pat() == "test-token"
            assert azure_config.get_repo_id() == "test-repo-id"
            assert azure_config.get_use_mocks() == False
        finally:
            os.unlink(temp_path)

    def test_with_env_vars(self):
        """Test configuration with environment variable resolution."""
        os.environ['TEST_AZURE_URL'] = 'https://env.azure.com'
        os.environ['TEST_AZURE_ORG'] = 'env-org'

        config_content = """
azure:
  devops:
    url: "@jinja {{env.TEST_AZURE_URL}}"
    organization: "@jinja {{env.TEST_AZURE_ORG}}"
    project: "config-project"
    pat: "config-token"
    repoId: "config-repo"
    mock: false
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write(config_content)
            temp_path = f.name

        try:
            base_config = BaseConfig(temp_path)
            config_data = base_config.get_value('azure.devops', {})
            azure_config = AzureDevOpsConfig(config_data)

            # These should come from environment variables via Jinja templates
            assert azure_config.get_url() == 'https://env.azure.com'
            assert azure_config.get_organization() == 'env-org'

            # These should come from config file
            assert azure_config.get_project() == 'config-project'
            assert azure_config.get_pat() == 'config-token'
            assert azure_config.get_repo_id() == 'config-repo'

        finally:
            os.unlink(temp_path)
            # Clean up environment variables
            if 'TEST_AZURE_URL' in os.environ:
                del os.environ['TEST_AZURE_URL']
            if 'TEST_AZURE_ORG' in os.environ:
                del os.environ['TEST_AZURE_ORG']

    def test_missing_section(self):
        """Test when azure.devops section is missing."""
        config_content = """
other_section:
  some_value: "test"
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write(config_content)
            temp_path = f.name

        try:
            base_config = BaseConfig(temp_path)
            config_data = base_config.get_value('azure.devops', {})
            azure_config = AzureDevOpsConfig(config_data)

            # Should handle missing section gracefully
            assert azure_config.get_url() is None
            assert azure_config.get_organization() is None
            assert azure_config.get_project() is None
            assert azure_config.get_pat() is None
            assert azure_config.get_repo_id() is None
            assert azure_config.get_use_mocks() == False
            assert azure_config.is_configured() == False
        finally:
            os.unlink(temp_path)

    def test_provider_usage_pattern(self):
        """Test the usage pattern expected by provider system."""
        # This simulates how the provider system would use AzureDevOpsConfig
        provider_config = {
            "url": "https://dev.azure.com",
            "organization": "test-org",
            "project": "test-project",
            "pat": "test-token",
            "repoId": "test-repo-id",
            "mock": True
        }

        # Provider factory would call this
        azure_config = AzureDevOpsConfig(provider_config)

        # Provider would check if configured
        if azure_config.is_configured() or azure_config.get_use_mocks():
            # Provider would be created
            assert True  # This is the expected path
        else:
            assert False, "Provider should be createable with this config"