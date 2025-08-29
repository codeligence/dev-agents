# config.yaml

The `config/config.yaml` file contains the main configuration for Dev Agents. This file provides default values that can be overridden by environment variables.

## File Structure

The configuration is organized into sections:

```yaml
# Agent Identity and Behavior
agent:
  name: "BettySharp"
  persona: "Senior Software Engineer"
  
# AI Model Configuration
ai:
  model:
    provider: "openai"  # openai, anthropic, azure
    name: "gpt-4"
    temperature: 0.7
    max_tokens: 2000
  
# Logging Configuration  
logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  
# Integration Settings
integrations:
  slack:
    enabled: true
    mock_mode: false
    
  azure_devops:
    enabled: true
    mock_mode: false
    
  git:
    repository:
      path: "/path/to/your/repo"
```

## Configuration Sections

### Agent Settings

```yaml
agent:
  name: "BettySharp"           # Agent display name
  persona: "Senior Software Engineer"  # Agent role/personality
```

### AI Model Configuration

```yaml
ai:
  model:
    provider: "openai"         # AI provider: openai, anthropic, azure
    name: "gpt-4"             # Model name
    temperature: 0.7          # Response creativity (0.0-1.0)
    max_tokens: 2000          # Maximum response length
```

### Slack Integration

```yaml
integrations:
  slack:
    enabled: true             # Enable/disable Slack integration
    mock_mode: false          # Use mock responses for testing
    channels:                 # Optional: restrict to specific channels
      - "#development"
      - "#devops"
```

### Azure DevOps Integration

```yaml
integrations:
  azure_devops:
    enabled: true
    mock_mode: false
    default_project: "YourProject"
    work_item_types:
      - "User Story"
      - "Task"
      - "Bug"
```

### Git Repository

```yaml
integrations:
  git:
    repository:
      path: "/path/to/your/repository"
    analysis:
      max_file_size: 1048576   # 1MB max file size for analysis
      exclude_patterns:
        - "*.log"
        - "node_modules/*"
        - ".git/*"
```

## Environment Variable Override

Any configuration value can be overridden by environment variables using dot notation:

```bash
# Override agent.name
AGENT_NAME=CustomBot

# Override ai.model.provider  
AI_MODEL_PROVIDER=anthropic

# Override integrations.slack.enabled
INTEGRATIONS_SLACK_ENABLED=false
```

Or using Dynaconf double underscore format:

```bash
# Same overrides using Dynaconf format
AGENT__NAME=CustomBot
AI__MODEL__PROVIDER=anthropic
INTEGRATIONS__SLACK__ENABLED=false
```

## Validation

The configuration is validated at startup. Check for issues:

```bash
python -c "
from src.core.config import BaseConfig
config = BaseConfig()
print('✓ Configuration valid')
"
```

## Development vs Production

You can have different configurations for different environments:

```yaml
# config/config.yaml (default/development)
logging:
  level: "DEBUG"
  
integrations:
  slack:
    mock_mode: true

# config/production.yaml
logging:
  level: "WARNING"
  
integrations:
  slack:
    mock_mode: false
```

Load specific environments:

```bash
ENV_FOR_DYNACONF=production python -m entrypoints.slack_bot
```

## Next Steps

- Configure [environment variables](environment-variables.md)
- Customize [prompts.yaml](prompts-yaml.md)  
- Set up [integrations](integrations/git.md)