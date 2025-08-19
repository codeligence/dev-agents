import pytest
import tempfile
import os
from core.config import BaseConfig
from core.project_config import ProjectConfig, ProjectConfigFactory
from core.exceptions import ConfigurationError


class TestProjectConfig:
    """Test cases for ProjectConfig class."""

    def _create_test_config(self, config_content: str) -> BaseConfig:
        """Helper method to create a test config from string content."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write(config_content)
            temp_path = f.name

        # Store path for cleanup
        self._temp_files = getattr(self, '_temp_files', [])
        self._temp_files.append(temp_path)

        return BaseConfig(temp_path)

    def teardown_method(self):
        """Clean up temporary files after each test."""
        if hasattr(self, '_temp_files'):
            for temp_file in self._temp_files:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
            self._temp_files = []

    def test_project_config_initialization(self):
        """Test ProjectConfig initialization."""
        config_content = """
projects:
  test_project:
    git:
      path: "/test/repo"
      defaultBranch: "develop"
      autoPull: true
    pullrequests:
      devops:
        url: "https://dev.azure.com"
        organization: "test-org"
        project: "test-project"
    issues:
      devops:
        url: "https://dev.azure.com"
        organization: "test-org"
        project: "test-project"
"""
        base_config = self._create_test_config(config_content)
        project_config = ProjectConfig("test_project", base_config)

        assert project_config.project_name == "test_project"
        assert project_config._project_key == "projects.test_project"

    def test_get_git_config(self):
        """Test getting git configuration from project."""
        config_content = """
projects:
  test_project:
    git:
      path: "/test/repo"
      defaultBranch: "develop"
      autoPull: true
"""
        base_config = self._create_test_config(config_content)
        project_config = ProjectConfig("test_project", base_config)

        git_config = project_config.get_git_config()
        assert isinstance(git_config, dict)
        assert git_config["path"] == "/test/repo"
        assert git_config["defaultBranch"] == "develop"
        assert git_config["autoPull"] == True

    def test_get_git_config_missing(self):
        """Test getting git config when it's missing."""
        config_content = """
projects:
  test_project:
    pullrequests:
      devops:
        url: "https://dev.azure.com"
"""
        base_config = self._create_test_config(config_content)
        project_config = ProjectConfig("test_project", base_config)

        with pytest.raises(ConfigurationError, match="No git configuration found"):
            project_config.get_git_config()

    def test_get_pullrequest_providers(self):
        """Test getting pull request providers."""
        config_content = """
projects:
  test_project:
    pullrequests:
      devops:
        url: "https://dev.azure.com"
        organization: "test-org"
      github:
        url: "https://api.github.com"
        token: "ghp_token"
"""
        base_config = self._create_test_config(config_content)
        project_config = ProjectConfig("test_project", base_config)

        providers = project_config.get_pullrequest_providers()
        assert isinstance(providers, dict)
        assert "devops" in providers
        assert "github" in providers
        assert providers["devops"]["url"] == "https://dev.azure.com"
        assert providers["github"]["token"] == "ghp_token"

    def test_get_issue_providers(self):
        """Test getting issue providers."""
        config_content = """
projects:
  test_project:
    issues:
      devops:
        url: "https://dev.azure.com"
        organization: "test-org"
      jira:
        url: "https://company.atlassian.net"
        token: "jira_token"
"""
        base_config = self._create_test_config(config_content)
        project_config = ProjectConfig("test_project", base_config)

        providers = project_config.get_issue_providers()
        assert isinstance(providers, dict)
        assert "devops" in providers
        assert "jira" in providers
        assert providers["devops"]["url"] == "https://dev.azure.com"
        assert providers["jira"]["token"] == "jira_token"

    def test_get_provider_config(self):
        """Test getting specific provider configuration."""
        config_content = """
projects:
  test_project:
    pullrequests:
      devops:
        url: "https://dev.azure.com"
        organization: "test-org"
        project: "test-project"
    issues:
      jira:
        url: "https://company.atlassian.net"
        token: "jira_token"
"""
        base_config = self._create_test_config(config_content)
        project_config = ProjectConfig("test_project", base_config)

        # Test pull request provider
        devops_pr_config = project_config.get_provider_config("pullrequests", "devops")
        assert devops_pr_config is not None
        assert devops_pr_config["url"] == "https://dev.azure.com"
        assert devops_pr_config["organization"] == "test-org"

        # Test issue provider
        jira_config = project_config.get_provider_config("issues", "jira")
        assert jira_config is not None
        assert jira_config["url"] == "https://company.atlassian.net"
        assert jira_config["token"] == "jira_token"

        # Test non-existent provider
        missing_config = project_config.get_provider_config("pullrequests", "nonexistent")
        assert missing_config is None

    def test_is_configured(self):
        """Test project configuration validation."""
        # Test configured project
        config_content = """
projects:
  test_project:
    git:
      path: "/test/repo"
"""
        base_config = self._create_test_config(config_content)
        project_config = ProjectConfig("test_project", base_config)
        assert project_config.is_configured() == True

        # Test project without git config
        config_content = """
projects:
  test_project:
    pullrequests:
      devops:
        url: "https://dev.azure.com"
"""
        base_config = self._create_test_config(config_content)
        project_config = ProjectConfig("test_project", base_config)
        assert project_config.is_configured() == False

        # Test project with empty git path
        config_content = """
projects:
  test_project:
    git:
      path: ""
"""
        base_config = self._create_test_config(config_content)
        project_config = ProjectConfig("test_project", base_config)
        assert project_config.is_configured() == False


class TestProjectConfigFactory:
    """Test cases for ProjectConfigFactory class."""

    def _create_test_config(self, config_content: str) -> BaseConfig:
        """Helper method to create a test config from string content."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write(config_content)
            temp_path = f.name

        # Store path for cleanup
        self._temp_files = getattr(self, '_temp_files', [])
        self._temp_files.append(temp_path)

        return BaseConfig(temp_path)

    def teardown_method(self):
        """Clean up temporary files after each test."""
        if hasattr(self, '_temp_files'):
            for temp_file in self._temp_files:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
            self._temp_files = []

    def test_factory_initialization(self):
        """Test ProjectConfigFactory initialization."""
        config_content = """
projects:
  test_project:
    git:
      path: "/test/repo"
"""
        base_config = self._create_test_config(config_content)
        factory = ProjectConfigFactory(base_config)
        assert factory._base_config is base_config

    def test_get_available_projects(self):
        """Test getting available project names."""
        config_content = """
projects:
  default:
    git:
      path: "/default/repo"
  staging:
    git:
      path: "/staging/repo"
  production:
    git:
      path: "/prod/repo"
"""
        base_config = self._create_test_config(config_content)
        factory = ProjectConfigFactory(base_config)

        projects = factory.get_available_projects()
        assert isinstance(projects, list)
        assert len(projects) == 3
        assert "default" in projects
        assert "staging" in projects
        assert "production" in projects

    def test_get_available_projects_empty(self):
        """Test getting available projects when none exist."""
        config_content = """
other_section:
  value: "test"
"""
        base_config = self._create_test_config(config_content)
        factory = ProjectConfigFactory(base_config)

        projects = factory.get_available_projects()
        assert isinstance(projects, list)
        assert len(projects) == 0

    def test_get_project_config(self):
        """Test getting specific project configuration."""
        config_content = """
projects:
  test_project:
    git:
      path: "/test/repo"
      defaultBranch: "develop"
    pullrequests:
      devops:
        url: "https://dev.azure.com"
"""
        base_config = self._create_test_config(config_content)
        factory = ProjectConfigFactory(base_config)

        project_config = factory.get_project_config("test_project")
        assert isinstance(project_config, ProjectConfig)
        assert project_config.project_name == "test_project"

        # Verify we can access the config
        git_config = project_config.get_git_config()
        assert git_config["path"] == "/test/repo"
        assert git_config["defaultBranch"] == "develop"

    def test_get_project_config_nonexistent(self):
        """Test getting configuration for non-existent project."""
        config_content = """
projects:
  existing_project:
    git:
      path: "/test/repo"
"""
        base_config = self._create_test_config(config_content)
        factory = ProjectConfigFactory(base_config)

        with pytest.raises(ConfigurationError, match="Project 'nonexistent' not found"):
            factory.get_project_config("nonexistent")

    def test_get_default_project_config(self):
        """Test getting default project configuration."""
        config_content = """
projects:
  default:
    git:
      path: "/default/repo"
      defaultBranch: "main"
  other_project:
    git:
      path: "/other/repo"
"""
        base_config = self._create_test_config(config_content)
        factory = ProjectConfigFactory(base_config)

        default_config = factory.get_default_project_config()
        assert isinstance(default_config, ProjectConfig)
        assert default_config.project_name == "default"

        git_config = default_config.get_git_config()
        assert git_config["path"] == "/default/repo"
        assert git_config["defaultBranch"] == "main"

    def test_get_default_project_config_missing(self):
        """Test getting default project when it doesn't exist."""
        config_content = """
projects:
  other_project:
    git:
      path: "/other/repo"
"""
        base_config = self._create_test_config(config_content)
        factory = ProjectConfigFactory(base_config)

        with pytest.raises(ConfigurationError, match="Project 'default' not found"):
            factory.get_default_project_config()

    def test_real_config_integration(self):
        """Test integration with the actual project config file."""
        # This tests against the real config.yaml that should have projects.default
        base_config = BaseConfig()
        factory = ProjectConfigFactory(base_config)

        # Should be able to get available projects
        projects = factory.get_available_projects()
        assert isinstance(projects, list)
        assert "default" in projects

        # Should be able to get default project
        default_config = factory.get_default_project_config()
        assert isinstance(default_config, ProjectConfig)
        assert default_config.project_name == "default"

        # Should have git configuration
        git_config = default_config.get_git_config()
        assert isinstance(git_config, dict)
        assert "path" in git_config

        # Should have provider configurations
        pr_providers = default_config.get_pullrequest_providers()
        assert isinstance(pr_providers, dict)
        
        issue_providers = default_config.get_issue_providers()
        assert isinstance(issue_providers, dict)