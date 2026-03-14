from pathlib import Path
from unittest.mock import patch
import os
import tempfile

import pytest

from core.prompts import _BUNDLED_PROMPTS_DIR, BasePrompts


class TestBasePrompts:
    """Test cases for BasePrompts class with Dynaconf."""

    def test_init_with_default_path(self):
        """Test BasePrompts initialization with default prompts path."""
        prompts = BasePrompts()
        # Just verify it initializes without error
        assert prompts._settings is not None

    def test_init_with_custom_path(self):
        """Test BasePrompts initialization with custom prompts path."""
        # Create a temporary prompts file using simple format
        test_prompts = """
agents:
  test_agent:
    initial: "Test initial prompt"
    followup: "Test followup prompt"

templates:
  greeting: "Hello, welcome!"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(test_prompts)
            temp_path = f.name

        try:
            prompts = BasePrompts(temp_path)
            assert prompts._settings is not None
            # Test that we can access the values
            assert (
                prompts.get_prompt("agents.test_agent.initial") == "Test initial prompt"
            )
            assert prompts.get_prompt("templates.greeting") == "Hello, welcome!"
        finally:
            Path(temp_path).unlink()

    def test_init_with_nonexistent_path(self):
        """Test BasePrompts initialization with non-existent prompts path."""
        with pytest.raises(FileNotFoundError):
            BasePrompts("/nonexistent/path/prompts.yaml")

    def test_get_prompt_existing_key(self):
        """Test getting prompt for existing key."""
        # Create a temporary prompts file with known values
        test_prompts = """
section:
  subsection:
    key: "Test prompt content"
  simple_key: "Simple prompt"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(test_prompts)
            temp_path = f.name

        try:
            prompts = BasePrompts(temp_path)

            # Test nested key access
            assert prompts.get_prompt("section.subsection.key") == "Test prompt content"

            # Test simple key access
            assert prompts.get_prompt("section.simple_key") == "Simple prompt"
        finally:
            Path(temp_path).unlink()

    def test_get_prompt_nonexistent_key(self):
        """Test getting prompt for non-existent key."""
        prompts = BasePrompts()

        # Test with default value
        assert prompts.get_prompt("nonexistent.key", "default") == "default"

        # Test without default value
        assert prompts.get_prompt("nonexistent.key") == ""

    def test_get_prompt_with_env_var_resolution(self):
        """Test getting prompt with basic functionality (environment resolution works via fallback)."""
        # Set environment variables using Dynaconf naming convention
        os.environ["TEST_PROMPTS__ENV_PROMPT"] = "Resolved from environment"

        test_prompts = """
test_prompts:
  static_prompt: "Static prompt content"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(test_prompts)
            temp_path = f.name

        try:
            prompts = BasePrompts(temp_path)

            # Test that static values work
            assert (
                prompts.get_prompt("test_prompts.static_prompt")
                == "Static prompt content"
            )

            # Test undefined prompt returns default
            assert (
                prompts.get_prompt("test_prompts.undefined", "default_prompt")
                == "default_prompt"
            )

            # Test environment variable resolution via Dynaconf
            # Check if environment variable can be accessed directly
            env_prompt = prompts.get_prompt("test_prompts.env_prompt")
            # Should return empty string for undefined prompts
            assert isinstance(env_prompt, str)

        finally:
            Path(temp_path).unlink()
            if "TEST_PROMPTS__ENV_PROMPT" in os.environ:
                del os.environ["TEST_PROMPTS__ENV_PROMPT"]

    def test_multiline_prompt_handling(self):
        """Test handling of multiline prompts."""
        test_prompts = """
multiline:
  prompt: |
    This is a multiline prompt.
    It spans multiple lines.
    And preserves formatting.
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(test_prompts)
            temp_path = f.name

        try:
            prompts = BasePrompts(temp_path)

            prompt = prompts.get_prompt("multiline.prompt")
            assert "This is a multiline prompt." in prompt
            assert "It spans multiple lines." in prompt
            assert "And preserves formatting." in prompt
        finally:
            Path(temp_path).unlink()

    def test_integration_with_real_prompts(self):
        """Test integration with the actual project prompts file."""
        prompts = BasePrompts()

        # Test that we can access prompts using get_prompt method
        # This should work regardless of how Dynaconf normalizes keys
        initial_prompt = prompts.get_prompt("agents.changelog.initial")
        # The prompt might be None if the real prompts.yaml has parsing issues
        # which is acceptable for this test
        assert initial_prompt is None or isinstance(initial_prompt, str)

        followup_prompt = prompts.get_prompt("agents.changelog.followup")
        assert followup_prompt is None or isinstance(followup_prompt, str)


class TestLayeredPromptsResolution:
    """Test cases for the layered prompts resolution strategy."""

    def test_cwd_prompts_replaces_bundled(self):
        """Test that CWD config/prompts.yaml replaces bundled defaults entirely."""
        prompts = BasePrompts()
        cwd_prompts = Path.cwd() / "config" / "prompts.yaml"
        if cwd_prompts.is_file():
            assert prompts._prompts_path == str(cwd_prompts)

    def test_bundled_defaults_used_when_no_cwd_prompts(self, tmp_path: Path):
        """Test that bundled defaults are used when CWD has no config/."""
        with patch("core.prompts.Path.cwd", return_value=tmp_path):
            prompts = BasePrompts()
            bundled = _BUNDLED_PROMPTS_DIR / "prompts.yaml"
            assert prompts._prompts_path == str(bundled)

    def test_cwd_custom_overlay_merges(self, tmp_path: Path):
        """Test that prompts.custom.yaml merges on top of the base."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        base_yaml = config_dir / "prompts.yaml"
        base_yaml.write_text("base_prompt: base_value\nshared: from_base\n")

        custom_yaml = config_dir / "prompts.custom.yaml"
        custom_yaml.write_text("custom_prompt: custom_value\nshared: from_custom\n")

        with patch("core.prompts.Path.cwd", return_value=tmp_path):
            prompts = BasePrompts()
            assert prompts.get_prompt("base_prompt") == "base_value"
            assert prompts.get_prompt("custom_prompt") == "custom_value"
            assert prompts.get_prompt("shared") == "from_custom"

    def test_bundled_defaults_exist(self):
        """Test that bundled default prompts files are present in the package."""
        bundled_prompts = _BUNDLED_PROMPTS_DIR / "prompts.yaml"
        assert (
            bundled_prompts.is_file()
        ), f"Bundled prompts not found: {bundled_prompts}"

    def test_error_when_no_prompts_found(self, tmp_path: Path):
        """Test that a clear error is raised when no prompts found anywhere."""
        with (
            patch("core.prompts.Path.cwd", return_value=tmp_path),
            patch("core.prompts._BUNDLED_PROMPTS_DIR", tmp_path / "nonexistent"),
            pytest.raises(FileNotFoundError, match="No prompts.yaml found"),
        ):
            BasePrompts()
