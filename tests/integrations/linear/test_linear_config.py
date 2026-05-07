from integrations.linear.config import LinearConfig


class TestLinearConfig:
    """Test cases for LinearConfig."""

    def test_direct_dict_constructor(self):
        """Test LinearConfig initialization with direct dictionary."""
        config_data = {
            "api_key": "lin_api_test123",
            "mock": False,
        }
        config = LinearConfig(config_data)

        assert config.get_api_key() == "lin_api_test123"
        assert not config.get_use_mocks()

    def test_empty_dict_constructor(self):
        """Test LinearConfig initialization with empty dictionary."""
        config = LinearConfig({})

        assert config.get_api_key() is None
        assert not config.get_use_mocks()

    def test_none_constructor(self):
        """Test LinearConfig initialization with None."""
        config = LinearConfig(None)

        assert config.get_api_key() is None
        assert not config.get_use_mocks()

    def test_mock_setting_variations(self):
        """Test different mock setting variations."""
        # Test boolean true
        config = LinearConfig({"mock": True})
        assert config.get_use_mocks()

        # Test string 'true'
        config = LinearConfig({"mock": "true"})
        assert config.get_use_mocks()

        # Test string 'false'
        config = LinearConfig({"mock": "false"})
        assert not config.get_use_mocks()

        # Test string '1'
        config = LinearConfig({"mock": "1"})
        assert config.get_use_mocks()

        # Test boolean false
        config = LinearConfig({"mock": False})
        assert not config.get_use_mocks()

    def test_is_configured_with_complete_config(self):
        """Test is_configured with all required fields."""
        config_data = {
            "api_key": "lin_api_test123",
        }
        config = LinearConfig(config_data)
        assert config.is_configured()

    def test_is_configured_with_missing_api_key(self):
        """Test is_configured with missing API key."""
        config = LinearConfig({})
        assert not config.is_configured()

    def test_is_configured_with_empty_api_key(self):
        """Test is_configured with empty string API key."""
        config = LinearConfig({"api_key": ""})
        assert not config.is_configured()

    def test_is_configured_with_mock_mode(self):
        """Test is_configured returns True when mock mode is enabled."""
        config = LinearConfig({"mock": True})
        assert config.is_configured()

    def test_is_configured_mock_mode_no_api_key(self):
        """Test is_configured returns True with mock mode even without API key."""
        config = LinearConfig({"mock": True})
        assert config.get_api_key() is None
        assert config.is_configured()

    def test_provider_usage_pattern(self):
        """Test the usage pattern expected by provider system."""
        provider_config = {
            "api_key": "lin_api_test123",
            "mock": True,
        }

        config = LinearConfig(provider_config)

        if config.is_configured() or config.get_use_mocks():
            assert True
        else:
            raise AssertionError("Provider should be createable with this config")
