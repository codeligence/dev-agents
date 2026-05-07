from typing import Any


class LinearConfig:
    """Linear specific configuration class that works with project config subsets."""

    def __init__(self, config_data: dict[str, Any]):
        """Initialize with a configuration dictionary subset.

        Args:
            config_data: Linear configuration dictionary
        """
        self._config_data = config_data or {}

    def get_api_key(self) -> str | None:
        """Get the Linear API key."""
        return self._config_data.get("api_key")

    def get_use_mocks(self) -> bool:
        """Get the Linear mock mode setting."""
        mock_value = self._config_data.get("mock", "false")
        # Handle both boolean and string representations
        if isinstance(mock_value, bool):
            return mock_value
        return str(mock_value).lower() in ("true", "1", "yes", "on")

    def is_configured(self) -> bool:
        """Check if all required Linear configuration is present."""

        if self.get_use_mocks():
            return True

        required_fields = [self.get_api_key()]
        return all(field is not None and field != "" for field in required_fields)
