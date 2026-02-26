from collections.abc import Callable
from typing import Any, TypeVar

from core.log import get_logger
from core.project_config import ProjectConfig
from core.protocols.provider_protocols import (
    IssueProvider,
    PipelineProvider,
    PullRequestProvider,
)

logger = get_logger("ProviderRegistry")

T = TypeVar("T")


class ProviderRegistry:
    """Registry for managing provider implementations and resolving them from configuration."""

    def __init__(self) -> None:
        self._pullrequest_providers: dict[
            str, Callable[[dict[str, Any]], PullRequestProvider | None]
        ] = {}
        self._issue_providers: dict[
            str, Callable[[dict[str, Any]], IssueProvider | None]
        ] = {}
        self._pipeline_providers: dict[
            str, Callable[[dict[str, Any]], PipelineProvider | None]
        ] = {}

    def register_pullrequest_provider(
        self,
        name: str,
        factory: Callable[[dict[str, Any]], PullRequestProvider | None],
    ) -> None:
        """Register a pull request provider factory.

        Args:
            name: Provider name (e.g., 'devops', 'github')
            factory: Factory function that takes config dict and returns provider or None
        """
        self._pullrequest_providers[name] = factory
        logger.debug(f"Registered pull request provider: {name}")

    def register_issue_provider(
        self, name: str, factory: Callable[[dict[str, Any]], IssueProvider | None]
    ) -> None:
        """Register an issue provider factory.

        Args:
            name: Provider name (e.g., 'devops', 'jira')
            factory: Factory function that takes config dict and returns provider or None
        """
        self._issue_providers[name] = factory
        logger.debug(f"Registered issue provider: {name}")

    def register_pipeline_provider(
        self, name: str, factory: Callable[[dict[str, Any]], PipelineProvider | None]
    ) -> None:
        """Register a pipeline provider factory.

        Args:
            name: Provider name (e.g., 'gitlab', 'github')
            factory: Factory function that takes config dict and returns provider or None
        """
        self._pipeline_providers[name] = factory
        logger.debug(f"Registered pipeline provider: {name}")

    def resolve_pullrequest_provider(
        self, project_config: ProjectConfig
    ) -> PullRequestProvider | None:
        """Resolve a pull request provider from project configuration.

        Tries all registered providers in order until one matches the configuration.

        Args:
            project_config: Project configuration

        Returns:
            First matching provider or None if no provider matches
        """
        provider_configs = project_config.get_pullrequest_providers()
        return self._resolve_provider(
            self._pullrequest_providers, provider_configs, "pull request"
        )

    def resolve_issue_provider(
        self, project_config: ProjectConfig
    ) -> IssueProvider | None:
        """Resolve an issue provider from project configuration.

        Tries all registered providers in order until one matches the configuration.

        Args:
            project_config: Project configuration

        Returns:
            First matching provider or None if no provider matches
        """
        provider_configs = project_config.get_issue_providers()
        return self._resolve_provider(self._issue_providers, provider_configs, "issue")

    def resolve_pipeline_provider(
        self, project_config: ProjectConfig
    ) -> PipelineProvider | None:
        """Resolve a pipeline provider from project configuration.

        Tries all registered providers in order until one matches the configuration.

        Args:
            project_config: Project configuration

        Returns:
            First matching provider or None if no provider matches
        """
        provider_configs = project_config.get_pipeline_providers()
        return self._resolve_provider(
            self._pipeline_providers, provider_configs, "pipeline"
        )

    def get_registered_pullrequest_providers(self) -> list[str]:
        """Get list of registered pull request provider names."""
        return list(self._pullrequest_providers.keys())

    def get_registered_issue_providers(self) -> list[str]:
        """Get list of registered issue provider names."""
        return list(self._issue_providers.keys())

    def get_registered_pipeline_providers(self) -> list[str]:
        """Get list of registered pipeline provider names."""
        return list(self._pipeline_providers.keys())

    def _resolve_provider(
        self,
        providers_registry: dict[str, Callable[[dict[str, Any]], T | None]],
        provider_configs: dict[str, dict[str, Any]],
        provider_type: str,
    ) -> T | None:
        """Generic provider resolution logic.

        Args:
            providers_registry: Registry of provider factories
            provider_configs: Configuration for providers
            provider_type: Type name for logging (e.g., 'pull request', 'issue')

        Returns:
            First matching provider or None if no provider matches
        """
        for provider_name, provider_config in provider_configs.items():
            if provider_name in providers_registry:
                factory = providers_registry[provider_name]
                try:
                    provider = factory(provider_config)
                    if provider is not None:
                        logger.info(
                            f"Resolved {provider_type} provider: {provider_name}"
                        )
                        return provider
                except Exception as e:
                    logger.warning(
                        f"Failed to create {provider_type} provider '{provider_name}': {e}"
                    )

        logger.warning(
            f"No {provider_type} provider could be resolved from configuration"
        )
        return None


# Global registry instance
_global_registry = ProviderRegistry()


def get_provider_registry() -> ProviderRegistry:
    """Get the global provider registry instance."""
    return _global_registry
