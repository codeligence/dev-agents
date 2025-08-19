# Contributing to dev-agents

Thank you for your interest in contributing to dev-agents! This project implements AI-powered development team agents using PydanticAI for analyzing Azure DevOps file changes and creating testing notes with Slack integration.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Environment Setup](#development-environment-setup)
- [Code Standards](#code-standards)
- [Testing Guidelines](#testing-guidelines)
- [Pull Request Process](#pull-request-process)
- [Issue Reporting](#issue-reporting)
- [Development Workflow](#development-workflow)
- [Architecture Overview](#architecture-overview)

## Getting Started

dev-agents is built using enterprise-grade software architecture patterns while maintaining simplicity. The project follows protocol-based architecture with clean separation of concerns:

- **Framework Code**: Located in `src/core/` - reusable infrastructure components
- **Agent Use Cases**: Located in `src/agents/` - domain-specific agent implementations  
- **Integration Layer**: Located in `src/integrations/` - external service adapters

## Development Environment Setup

### Prerequisites

- **Python 3.11+** (required)
- **Git** for version control
- **Docker** (optional, for containerized development)

### Initial Setup

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd dev-agents
   ```

2. **Create and activate virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -e .
   ```

4. **Configure environment**:
   ```bash
   cp config/config.yaml.example config/config.yaml  # if available
   # Edit config/config.yaml with your settings
   ```

5. **Set up environment variables**:
   ```bash
   cp .env.example .env  # if available
   # Edit .env with your API keys and configuration
   ```

### Development Dependencies

For development work, you may need additional packages:
```bash
pip install pytest pytest-asyncio mypy black isort pre-commit
```

## Code Standards

### Type Safety

- **Full Typing**: All functions, methods, and variables must be properly typed
- **Generic Protocols**: Use `Protocol[T]` for type-safe generic interfaces
- **mypy Compliance**: Code must pass strict mypy type checking
- **Runtime Checks**: Use `isinstance()` checks with `@runtime_checkable` protocols

### Code Style

- **PEP 8 Compliance**: Follow Python style guidelines
- **Black Formatting**: Use Black for consistent code formatting
- **Import Sorting**: Use isort for organizing imports
- **Line Length**: Maximum 88 characters (Black default)

### Architecture Patterns

- **Protocol-Based Design**: All interfaces defined as Python Protocols
- **Composition over Inheritance**: Favor dependency injection
- **Single Responsibility**: Each class has one clear purpose
- **Clean Architecture**: Maintain separation between framework, agents, and integrations

### Documentation

- **Docstrings**: All public methods require comprehensive docstrings
- **Type Annotations**: Self-documenting code through proper typing
- **Code Examples**: Include usage examples in docstrings for complex interfaces
- **Comments**: Explain complex logic and business rules

### Configuration Management

When adding new services or features:

```python
class NewServiceConfig:
    def __init__(self, base_config: BaseConfig):
        self._base_config = base_config
        self._config_data = base_config.get_config_data()
    
    def get_service_setting(self) -> Optional[str]:
        return self._base_config.get_value('newservice.setting')
    
    def is_configured(self) -> bool:
        # Validation logic for required fields
        return self.get_service_setting() is not None
```

## Testing Guidelines

### Test Structure

- **Unit Tests**: Test individual components in isolation
- **Integration Tests**: Test real protocol implementations with actual services
- **Agent Tests**: Test agent logic with mocked dependencies
- **Protocol Compliance**: Test that implementations satisfy their protocols

### Test Requirements

- **Coverage**: Aim for 80%+ test coverage on new code
- **Test Naming**: Use descriptive test names that explain the scenario
- **Arrange-Act-Assert**: Structure tests clearly with setup, execution, and verification
- **Test Isolation**: Each test should be independent and repeatable

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test files
pytest tests/core/test_config.py

# Run tests with verbose output
pytest -v
```

### Writing Tests

```python
import pytest
from unittest.mock import Mock, AsyncMock
from src.core.protocols.agent_protocols import AgentExecutionContext

@pytest.mark.asyncio
async def test_agent_execution():
    # Arrange
    mock_context = Mock(spec=AgentExecutionContext)
    mock_context.get_config.return_value = {"key": "value"}
    
    # Act
    result = await my_agent.run(mock_context)
    
    # Assert
    assert result.success is True
    mock_context.get_config.assert_called_once()
```

## Pull Request Process

### Branch Strategy

1. **Create a feature branch** from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Use descriptive branch names**:
   - `feature/impact-analysis-enhancement`
   - `fix/slack-message-parsing`
   - `refactor/config-management`

### Commit Standards

- **Conventional Commits**: Use the format `type(scope): description`
- **Examples**:
  - `feat(agents): add code research agent`
  - `fix(slack): handle message parsing edge cases`
  - `docs(readme): update installation instructions`
  - `refactor(config): simplify environment variable handling`

### Pull Request Requirements

1. **Description**: Provide clear description of changes and motivation
2. **Testing**: Include tests for new functionality
3. **Documentation**: Update relevant documentation
4. **Type Safety**: Ensure mypy passes
5. **Code Style**: Ensure Black and isort formatting
6. **Breaking Changes**: Clearly document any breaking changes

### Review Process

1. **Self-Review**: Review your own changes before submitting
2. **Automated Checks**: Ensure all CI checks pass
3. **Peer Review**: Address feedback constructively
4. **Final Review**: Maintainer approval required for merge

## Issue Reporting

### Bug Reports

When reporting bugs, please include:

- **Environment**: Python version, OS, dependencies
- **Steps to Reproduce**: Clear steps to recreate the issue
- **Expected Behavior**: What should happen
- **Actual Behavior**: What actually happens
- **Error Messages**: Full error messages and stack traces
- **Configuration**: Relevant configuration (sanitized)

### Feature Requests

For new features, provide:

- **Use Case**: Why is this feature needed?
- **Proposed Solution**: How should it work?
- **Alternatives**: Other solutions considered
- **Implementation**: Any implementation ideas

### Security Issues

**DO NOT** report security vulnerabilities in public issues. Please follow our [Security Policy](SECURITY.md).

## Development Workflow

### Pre-commit Hooks

Set up pre-commit hooks for consistent code quality:

```bash
pre-commit install
```

This will run the following checks before each commit:
- Black code formatting
- isort import sorting
- mypy type checking
- Basic linting

### Code Quality Tools

```bash
# Format code with Black
black src tests

# Sort imports with isort
isort src tests

# Type checking with mypy
mypy src

# Run linting
flake8 src tests
```

### Agent Development Pattern

When creating new agents, follow this pattern:

```python
from src.core.protocols.agent_protocols import AgentExecutionContext, Agent

class MyAgent(Agent[MyResultType]):
    def __init__(self, context: AgentExecutionContext) -> None:
        super().__init__(context)
        self.context = context
        # Initialize agent with context
    
    async def run(self) -> MyResultType:
        # Agent implementation
        return result

# Register with factory
from src.core.agents.factory import SimpleAgentFactory
SimpleAgentFactory.register_agent("my-agent", MyAgent)
```

## Architecture Overview

### Core Principles

- **Protocol-Based Architecture**: Type-safe contracts with full typing support
- **Clean Architecture Separation**: Framework, agents, and integrations layers
- **SOLID Principles**: Single responsibility, dependency inversion, etc.
- **Configuration Management**: Type-safe config classes with environment resolution
- **Error Handling**: Domain exceptions with graceful degradation

### Key Components

- **`AgentExecutionContext`**: Protocol defining agent environment interface
- **`AgentService`**: Orchestrates agent execution with monitoring
- **`SimpleAgentFactory`**: Creates and configures agents using registry pattern
- **`BaseConfig`**: Core YAML configuration loader with environment variable resolution

## Code of Conduct

This project adheres to a code of conduct that ensures a welcoming environment for all contributors. Please be respectful, inclusive, and constructive in all interactions.

## Getting Help

- **Documentation**: Check the `docs/` directory and `CLAUDE.md`
- **Issues**: Search existing issues before creating new ones
- **Discussions**: Use GitHub Discussions for general questions
- **Contact**: Reach out to maintainers for complex questions

## License

By contributing to dev-agents, you agree that your contributions will be licensed under the same license as the project (see LICENSE.md).

Thank you for contributing to dev-agents!