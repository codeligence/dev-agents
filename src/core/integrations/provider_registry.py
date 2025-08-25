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


from typing import Dict, List, Optional, Type, Any, Callable, TypeVar
from core.protocols.provider_protocols import PullRequestProvider, IssueProvider
from core.project_config import ProjectConfig
from core.exceptions import ConfigurationError
from core.log import get_logger

logger = get_logger("ProviderRegistry")

T = TypeVar('T')


class ProviderRegistry:
    """Registry for managing provider implementations and resolving them from configuration."""

    def __init__(self):
        self._pullrequest_providers: Dict[str, Callable[[Dict[str, Any]], Optional[PullRequestProvider]]] = {}
        self._issue_providers: Dict[str, Callable[[Dict[str, Any]], Optional[IssueProvider]]] = {}

    def register_pullrequest_provider(
        self,
        name: str,
        factory: Callable[[Dict[str, Any]], Optional[PullRequestProvider]]
    ) -> None:
        """Register a pull request provider factory.

        Args:
            name: Provider name (e.g., 'devops', 'github')
            factory: Factory function that takes config dict and returns provider or None
        """
        self._pullrequest_providers[name] = factory
        logger.debug(f"Registered pull request provider: {name}")

    def register_issue_provider(
        self,
        name: str,
        factory: Callable[[Dict[str, Any]], Optional[IssueProvider]]
    ) -> None:
        """Register an issue provider factory.

        Args:
            name: Provider name (e.g., 'devops', 'jira')
            factory: Factory function that takes config dict and returns provider or None
        """
        self._issue_providers[name] = factory
        logger.debug(f"Registered issue provider: {name}")

    def resolve_pullrequest_provider(self, project_config: ProjectConfig) -> Optional[PullRequestProvider]:
        """Resolve a pull request provider from project configuration.

        Tries all registered providers in order until one matches the configuration.

        Args:
            project_config: Project configuration

        Returns:
            First matching provider or None if no provider matches
        """
        provider_configs = project_config.get_pullrequest_providers()
        return self._resolve_provider(
            self._pullrequest_providers,
            provider_configs,
            "pull request"
        )

    def resolve_issue_provider(self, project_config: ProjectConfig) -> Optional[IssueProvider]:
        """Resolve an issue provider from project configuration.

        Tries all registered providers in order until one matches the configuration.

        Args:
            project_config: Project configuration

        Returns:
            First matching provider or None if no provider matches
        """
        provider_configs = project_config.get_issue_providers()
        return self._resolve_provider(
            self._issue_providers,
            provider_configs,
            "issue"
        )

    def get_registered_pullrequest_providers(self) -> List[str]:
        """Get list of registered pull request provider names."""
        return list(self._pullrequest_providers.keys())

    def get_registered_issue_providers(self) -> List[str]:
        """Get list of registered issue provider names."""
        return list(self._issue_providers.keys())

    def _resolve_provider(
        self,
        providers_registry: Dict[str, Callable[[Dict[str, Any]], Optional[T]]],
        provider_configs: Dict[str, Dict[str, Any]],
        provider_type: str
    ) -> Optional[T]:
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
                        logger.info(f"Resolved {provider_type} provider: {provider_name}")
                        return provider
                except Exception as e:
                    logger.warning(f"Failed to create {provider_type} provider '{provider_name}': {e}")

        logger.warning(f"No {provider_type} provider could be resolved from configuration")
        return None


# Global registry instance
_global_registry = ProviderRegistry()


def get_provider_registry() -> ProviderRegistry:
    """Get the global provider registry instance."""
    return _global_registry