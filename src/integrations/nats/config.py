from typing import Any

from core.config import BaseConfig


class NatsConfig:
    """NATS specific configuration class that works with BaseConfig composition."""

    def __init__(self, base_config: BaseConfig):
        """Initialize with a BaseConfig instance.

        Args:
            base_config: BaseConfig instance for accessing configuration
        """
        self._base_config = base_config
        self._config_data = base_config.get_config_data()

    @classmethod
    def from_config_data(cls, config_data: dict[str, Any]) -> "NatsConfig":
        """Create instance from configuration dictionary subset.

        Args:
            config_data: NATS configuration dictionary

        Returns:
            NatsConfig instance
        """
        from core.config import BaseConfig

        base_config = BaseConfig()
        # Override the nats section with provided data
        base_config._config_data["nats"] = config_data
        return cls(base_config)

    def get_server_url(self) -> str | None:
        """Get the NATS server URL."""
        value = self._base_config.get_value("nats.server_url")
        return str(value) if value is not None else None

    def get_job_id(self) -> str | None:
        """Get the NATS job ID."""
        value = self._base_config.get_value("nats.job_id")
        return str(value) if value is not None else None

    def get_user(self) -> str | None:
        """Get the NATS username."""
        value = self._base_config.get_value("nats.user")
        return str(value) if value is not None else None

    def get_password(self) -> str | None:
        """Get the NATS password."""
        value = self._base_config.get_value("nats.password")
        return str(value) if value is not None else None

    def get_ca_cert_path(self) -> str | None:
        """Get the path to the NATS CA certificate."""
        value = self._base_config.get_value("nats.ca_cert_path")
        return str(value) if value is not None else None

    def get_subject_job_data(self) -> str:
        """Get the NATS subject for job data."""
        value = self._base_config.get_value("nats.subject_job_data", "jobdata")
        return str(value)

    def get_subject_job_updates(self) -> str:
        """Get the NATS subject for job updates."""
        value = self._base_config.get_value("nats.subject_job_updates", "jobupdates")
        return str(value)

    def is_configured(self) -> bool:
        """Check if all required NATS configuration is present.

        Returns:
            True if NATS_SERVER_URL and NATS_JOB_ID are configured
        """
        server_url = self.get_server_url()
        job_id = self.get_job_id()
        return (
            server_url is not None
            and server_url != ""
            and job_id is not None
            and job_id != ""
        )
