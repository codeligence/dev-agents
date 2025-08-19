"""Core domain exceptions for the agent framework."""


class AgentException(Exception):
    """Base exception for all agent-related errors."""
    
    def __init__(self, message: str, agent_type: str = None):
        super().__init__(message)
        self.agent_type = agent_type


class AgentExecutionError(AgentException):
    """Raised when an agent fails during execution."""
    pass


class AgentConfigurationError(AgentException):
    """Raised when agent configuration is invalid or missing."""
    pass


class AgentNotFoundError(AgentException):
    """Raised when requested agent type is not found."""
    pass


class AgentContextError(AgentException):
    """Raised when there are issues with the execution context."""
    pass


class AgentTimeoutError(AgentException):
    """Raised when agent execution exceeds timeout limits."""
    pass


class AgentGracefulExit(AgentException):
    """Raised by agents to gracefully terminate processing without error."""
    pass


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing."""
    pass