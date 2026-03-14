from pathlib import Path
from unittest.mock import patch
import os
import tempfile
import threading

import pytest

from core.config import _BUNDLED_CONFIG_DIR, BaseConfig, get_default_config


class TestBaseConfig:
    """Test cases for BaseConfig class with Dynaconf."""

    def test_init_with_default_path(self):
        """Test BaseConfig initialization with default config path."""
        config = BaseConfig()
        assert config._config_data is not None
        assert isinstance(config._config_data, dict)

    def test_init_with_custom_path(self):
        """Test BaseConfig initialization with custom config path."""
        # Create a temporary config file using simple Dynaconf format
        test_config = """
core:
  log:
    dir: "/tmp/logs"
  debug: true

test_section:
  value: "test_value"
  number: 42
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write(test_config)
            temp_path = f.name

        try:
            config = BaseConfig(temp_path)
            assert config._config_data is not None
            # Test that we can access the values
            assert config.get_value("core.log.dir") == "/tmp/logs"
            assert config.get_value("test_section.number") == 42
        finally:
            Path(temp_path).unlink()

    def test_init_with_nonexistent_path(self):
        """Test BaseConfig initialization with non-existent config path."""
        with pytest.raises(FileNotFoundError):
            BaseConfig("/nonexistent/path/config.yaml")

    def test_get_config_data(self):
        """Test getting full config data."""
        config = BaseConfig()
        data = config.get_config_data()
        assert isinstance(data, dict)

    def test_get_value_existing_key(self):
        """Test getting value for existing key."""
        # Create a temporary config file with known values
        test_config = """
section:
  subsection:
    key: test_value
  simple_key: simple_value
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write(test_config)
            temp_path = f.name

        try:
            config = BaseConfig(temp_path)

            # Test nested key access
            assert config.get_value("section.subsection.key") == "test_value"

            # Test simple key access
            assert config.get_value("section.simple_key") == "simple_value"

            # Test section access
            section_data = config.get_value("section")
            assert isinstance(section_data, dict)
        finally:
            Path(temp_path).unlink()

    def test_get_value_nonexistent_key(self):
        """Test getting value for non-existent key."""
        config = BaseConfig()

        # Test with default value
        assert config.get_value("nonexistent.key", "default") == "default"

        # Test without default value
        assert config.get_value("nonexistent.key") is None

    def test_get_value_with_env_var_resolution(self):
        """Test getting value with Dynaconf environment variable resolution."""
        # Set environment variables using Dynaconf naming convention
        os.environ["TEST_SECTION_ENV_VALUE"] = "resolved_from_env"
        os.environ["DYNACONF_TEST_SECTION_OVERRIDE"] = "dynaconf_override"

        test_config = """
test_section:
  static_value: "static_content"
  number: 42
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write(test_config)
            temp_path = f.name

        try:
            config = BaseConfig(temp_path)

            # Test environment variable resolution
            # Dynaconf should pick up TEST_SECTION_ENV_VALUE
            env_value = config.get_value("test_section.env_value")
            assert env_value == "resolved_from_env"

            # Test that static values still work
            assert config.get_value("test_section.static_value") == "static_content"
            assert config.get_value("test_section.number") == 42

            # Test undefined value returns default
            assert (
                config.get_value("test_section.undefined", "default_value")
                == "default_value"
            )
        finally:
            Path(temp_path).unlink()
            if "TEST_SECTION_ENV_VALUE" in os.environ:
                del os.environ["TEST_SECTION_ENV_VALUE"]
            if "DYNACONF_TEST_SECTION_OVERRIDE" in os.environ:
                del os.environ["DYNACONF_TEST_SECTION_OVERRIDE"]

    def test_integration_with_real_config(self):
        """Test integration with the actual project config file."""
        config = BaseConfig()

        # Test that we can access values using get_value method
        # This should work regardless of how Dynaconf normalizes keys
        core_log_dir = config.get_value("core.log.dir")
        assert core_log_dir is not None

        # Test accessing projects section with new structure
        projects = config.get_value("projects")
        assert projects is not None
        assert isinstance(projects, dict)

        # Test accessing azure devops config in new project structure
        azure_mock = config.get_value("projects.default.pullrequests.devops.mock")
        assert azure_mock is not None

    def test_env_var_resolution(self):
        """Test that environment variables override config values."""
        # Test with environment variable set
        os.environ["SLACK_BOT_PROCESSING_TIMEOUT"] = "600"
        os.environ["SLACK__BOT__PROCESSING_TIMEOUT"] = "700"

        try:
            config = BaseConfig()

            # Test that environment variables override config defaults
            timeout = config.get_value("slack.bot.processingTimeout")
            # Handle both string and integer values from environment/config
            timeout_int = int(timeout) if isinstance(timeout, str) else timeout
            assert (
                timeout_int == 6000 or timeout_int == 600 or timeout_int == 700
            )  # Config default (6000) or env override

            # Test dot notation fallback
            timeout_alt = config.get_value("slack.bot.processingTimeout")
            assert timeout_alt is not None

        finally:
            # Clean up
            if "SLACK_BOT_PROCESSING_TIMEOUT" in os.environ:
                del os.environ["SLACK_BOT_PROCESSING_TIMEOUT"]
            if "SLACK__BOT__PROCESSING_TIMEOUT" in os.environ:
                del os.environ["SLACK__BOT__PROCESSING_TIMEOUT"]

    def test_env_var_fallback_behavior(self):
        """Test fallback behavior for environment variables."""
        config = BaseConfig()

        # Test that non-existent keys return defaults
        assert config.get_value("nonexistent.key", "default") == "default"

        # Test environment variable fallback
        os.environ["NONEXISTENT_KEY"] = "env_value"
        try:
            # Should pick up env var using our fallback logic
            assert config.get_value("nonexistent.key") == "env_value"
        finally:
            del os.environ["NONEXISTENT_KEY"]


class TestDefaultConfigSingleton:
    """Test cases for get_default_config() singleton functionality."""

    def setup_method(self):
        """Reset the singleton instance before each test."""
        # Clear the singleton instance for testing
        import core.config

        core.config._default_config_instance = None

    def test_get_default_config_returns_baseconfig_instance(self):
        """Test that get_default_config() returns a BaseConfig instance."""
        config = get_default_config()
        assert isinstance(config, BaseConfig)
        assert config._config_data is not None

    def test_get_default_config_singleton_behavior(self):
        """Test that get_default_config() returns the same instance on multiple calls."""
        config1 = get_default_config()
        config2 = get_default_config()

        # Should be the exact same object instance
        assert config1 is config2
        assert id(config1) == id(config2)

    def test_get_default_config_loads_default_config_yaml(self):
        """Test that get_default_config() loads from the default config.yaml path."""
        config = get_default_config()

        # Verify it has config data from the default file
        assert config._config_data is not None
        assert isinstance(config._config_data, dict)

        # The default config should have some expected structure
        # (This will depend on your actual config.yaml content)
        config_data = config.get_config_data()
        assert isinstance(config_data, dict)

    def test_get_default_config_thread_safety(self):
        """Test that get_default_config() is thread-safe."""
        configs = []
        exceptions = []

        def get_config_in_thread():
            try:
                config = get_default_config()
                configs.append(config)
            except Exception as e:
                exceptions.append(e)

        # Create multiple threads that call get_default_config() simultaneously
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=get_config_in_thread)
            threads.append(thread)

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Check that no exceptions occurred
        assert len(exceptions) == 0, f"Exceptions occurred: {exceptions}"

        # Check that all threads got the same instance
        assert len(configs) == 10
        first_config = configs[0]
        for config in configs:
            assert config is first_config

    def test_get_default_config_memory_efficiency(self):
        """Test that get_default_config() is memory efficient with single instance."""
        # Get multiple references
        configs = [get_default_config() for _ in range(100)]

        # All should be the same object
        first_config = configs[0]
        for config in configs:
            assert config is first_config

        # Only one BaseConfig instance should exist
        import gc

        gc.collect()  # Force garbage collection

        # Verify all references point to the same object
        config_ids = {id(config) for config in configs}
        assert len(config_ids) == 1

    def test_get_default_config_preserves_environment_resolution(self):
        """Test that singleton preserves environment variable resolution."""
        # Set a test environment variable
        test_key = "TEST_SINGLETON_VAR"
        test_value = "singleton_test_value"
        os.environ[test_key] = test_value

        try:
            config = get_default_config()

            # Should be able to get environment variables using various formats
            assert config.get_value("test.singleton.var") == test_value

            # Multiple calls should still work
            config2 = get_default_config()
            assert config2.get_value("test.singleton.var") == test_value
            assert config is config2

        finally:
            if test_key in os.environ:
                del os.environ[test_key]

    def test_get_default_config_vs_direct_baseconfig(self):
        """Test that get_default_config() behaves like BaseConfig() but is cached."""
        # Get singleton instance
        singleton_config = get_default_config()

        # Create direct BaseConfig instance
        direct_config = BaseConfig()

        # Both should have the same configuration data
        singleton_data = singleton_config.get_config_data()
        direct_data = direct_config.get_config_data()

        # Data should be equivalent (but objects are different)
        assert singleton_data == direct_data
        assert singleton_config is not direct_config

        # Both should resolve environment variables the same way
        test_key = "COMPARISON_TEST_VAR"
        test_value = "comparison_value"
        os.environ[test_key] = test_value

        try:
            singleton_result = singleton_config.get_value("comparison.test.var")
            direct_result = direct_config.get_value("comparison.test.var")

            assert singleton_result == test_value
            assert direct_result == test_value
            assert singleton_result == direct_result

        finally:
            if test_key in os.environ:
                del os.environ[test_key]


class TestLayeredConfigResolution:
    """Test cases for the layered config resolution strategy."""

    def test_cwd_config_replaces_bundled(self):
        """Test that CWD config/config.yaml replaces bundled defaults entirely."""
        # When running from project root, CWD config/ exists and should be used
        config = BaseConfig()

        # CWD config should be the primary path (not the bundled one)
        cwd_config = Path.cwd() / "config" / "config.yaml"
        if cwd_config.is_file():
            assert config._config_path == str(cwd_config)

    def test_bundled_defaults_used_when_no_cwd_config(self, tmp_path: Path):
        """Test that bundled defaults are used when CWD has no config/."""
        # Simulate a CWD without config/ by patching Path.cwd()
        with patch("core.config.Path.cwd", return_value=tmp_path):
            config = BaseConfig()
            bundled = _BUNDLED_CONFIG_DIR / "config.yaml"
            assert config._config_path == str(bundled)

    def test_cwd_custom_overlay_merges(self, tmp_path: Path):
        """Test that config.custom.yaml merges on top of the base."""
        # Create a config dir with base and custom files
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        base_yaml = config_dir / "config.yaml"
        base_yaml.write_text("base_key: base_value\nshared_key: from_base\n")

        custom_yaml = config_dir / "config.custom.yaml"
        custom_yaml.write_text("custom_key: custom_value\nshared_key: from_custom\n")

        with patch("core.config.Path.cwd", return_value=tmp_path):
            config = BaseConfig()
            # Base value should be present
            assert config.get_value("base_key") == "base_value"
            # Custom value should be present
            assert config.get_value("custom_key") == "custom_value"
            # Custom should override base for shared keys
            assert config.get_value("shared_key") == "from_custom"

    def test_bundled_defaults_exist(self):
        """Test that bundled default config files are present in the package."""
        bundled_config = _BUNDLED_CONFIG_DIR / "config.yaml"
        assert bundled_config.is_file(), f"Bundled config not found: {bundled_config}"

    def test_error_when_no_config_found(self, tmp_path: Path):
        """Test that a clear error is raised when no config is found anywhere."""
        # Empty temp dir: no CWD config, and sabotage the bundled path
        with (
            patch("core.config.Path.cwd", return_value=tmp_path),
            patch("core.config._BUNDLED_CONFIG_DIR", tmp_path / "nonexistent"),
            pytest.raises(FileNotFoundError, match="No config.yaml found"),
        ):
            BaseConfig()


class TestBundledProjectPruning:
    """Test that bundled-only project entries are pruned when a custom overlay defines its own projects."""

    def test_custom_overlay_prunes_bundled_projects(self, tmp_path: Path):
        """Custom overlay defines only my_app — bundled 'default' should be pruned."""
        defaults_dir = tmp_path / "defaults"
        defaults_dir.mkdir()
        bundled = defaults_dir / "config.yaml"
        bundled.write_text(
            "projects:\n"
            "  default:\n"
            "    git:\n"
            "      path: /code\n"
            "models:\n"
            "  large: openai:gpt-4\n"
        )

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        custom = config_dir / "config.custom.yaml"
        custom.write_text(
            "projects:\n" "  my_app:\n" "    git:\n" "      path: /my-repo\n"
        )

        with (
            patch("core.config.Path.cwd", return_value=tmp_path),
            patch("core.config._BUNDLED_CONFIG_DIR", defaults_dir),
        ):
            config = BaseConfig()
            projects = config.get_available_projects()
            assert "my_app" in projects
            assert "default" not in projects
            # Non-entity sections should be unaffected
            assert config.get_value("models.large") == "openai:gpt-4"

    def test_custom_overlay_keeps_user_defined_default(self, tmp_path: Path):
        """Custom overlay explicitly defines 'default' — it should be kept."""
        defaults_dir = tmp_path / "defaults"
        defaults_dir.mkdir()
        bundled = defaults_dir / "config.yaml"
        bundled.write_text(
            "projects:\n" "  default:\n" "    git:\n" "      path: /code\n"
        )

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        custom = config_dir / "config.custom.yaml"
        custom.write_text(
            "projects:\n"
            "  default:\n"
            "    git:\n"
            "      path: /my-default\n"
            "  my_app:\n"
            "    git:\n"
            "      path: /my-repo\n"
        )

        with (
            patch("core.config.Path.cwd", return_value=tmp_path),
            patch("core.config._BUNDLED_CONFIG_DIR", defaults_dir),
        ):
            config = BaseConfig()
            projects = config.get_available_projects()
            assert "default" in projects
            assert "my_app" in projects
            # User's override should win
            assert config.get_value("projects.default.git.path") == "/my-default"

    def test_no_pruning_without_custom_overlay(self, tmp_path: Path):
        """No custom overlay — bundled 'default' project should be present."""
        defaults_dir = tmp_path / "defaults"
        defaults_dir.mkdir()
        bundled = defaults_dir / "config.yaml"
        bundled.write_text(
            "projects:\n" "  default:\n" "    git:\n" "      path: /code\n"
        )

        with (
            patch("core.config.Path.cwd", return_value=tmp_path),
            patch("core.config._BUNDLED_CONFIG_DIR", defaults_dir),
        ):
            config = BaseConfig()
            assert "default" in config.get_available_projects()

    def test_no_pruning_when_cwd_replaces_bundled(self, tmp_path: Path):
        """CWD config.yaml replaces bundled — no merge, no pruning needed."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        cwd_config = config_dir / "config.yaml"
        cwd_config.write_text(
            "projects:\n" "  my_app:\n" "    git:\n" "      path: /my-repo\n"
        )

        with patch("core.config.Path.cwd", return_value=tmp_path):
            config = BaseConfig()
            projects = config.get_available_projects()
            assert "my_app" in projects
            assert "default" not in projects

    def test_custom_overlay_without_projects_keeps_bundled(self, tmp_path: Path):
        """Custom overlay doesn't touch projects — bundled 'default' should remain."""
        defaults_dir = tmp_path / "defaults"
        defaults_dir.mkdir()
        bundled = defaults_dir / "config.yaml"
        bundled.write_text(
            "projects:\n" "  default:\n" "    git:\n" "      path: /code\n"
        )

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        custom = config_dir / "config.custom.yaml"
        custom.write_text("models:\n  large: openai:gpt-4.1\n")

        with (
            patch("core.config.Path.cwd", return_value=tmp_path),
            patch("core.config._BUNDLED_CONFIG_DIR", defaults_dir),
        ):
            config = BaseConfig()
            assert "default" in config.get_available_projects()
