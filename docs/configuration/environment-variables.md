# Environment Variables

Dev Agents uses environment variables for flexible configuration across different deployment scenarios. This guide covers all available variables with examples and best practices.

## Quick Start

**Minimum required variables to get started:**

```bash
# Choose one AI provider
OPENAI_API_KEY=your_openai_key
# OR
ANTHROPIC_API_KEY=your_anthropic_key
# OR
AWS_DEFAULT_REGION=your-region
AWS_ACCESS_KEY_ID=ABCDEFGHIJKLMNOPQRST
AWS_SECRET_ACCESS_KEY=abcdefghijklmnopqrstuvwxyz1234567890ABCD

# Models to use, like openai:gpt-4o, anthropic:claude-3-5-sonnet-latest, use any model listed here: https://ai.pydantic.dev/models/ 
LLM_MODEL_SMALL=bedrock:anthropic.claude-3-haiku-20240307-v1:0
LLM_MODEL_LARGE=bedrock:anthropic.claude-3-5-sonnet-20240620-v1:0

# Agent identity
AVATAR_FULL_NAME="BettySharp"
AVATAR_SHORT_NAME="Betty"

# Git repository path
GIT_REPO_PATH=/path/to/your/repository
```

## Quick Reference

| Variable | Category | Status | Description |
|----------|----------|--------|-------------|
| [`OPENAI_API_KEY`](#ai-providers) | AI | ⚠️ Required* | OpenAI API key for GPT models |
| [`ANTHROPIC_API_KEY`](#ai-providers) | AI | ⚠️ Required* | Anthropic API key for Claude models |
| [`AVATAR_FULL_NAME`](#agent-identity) | Identity | ⚠️ Required | Full display name for your agent |
| [`AVATAR_SHORT_NAME`](#agent-identity) | Identity | ⚠️ Required | Short name for your agent |
| [`GIT_REPO_PATH`](#git-integration) | Git | ⚠️ Required | Path to your git repository |
| [`SLACK_BOT_TOKEN`](#slack-integration) | Slack | ✅ Optional | Slack bot token (if using Slack) |
| [`AZURE_DEVOPS_PAT`](#azure-devops) | DevOps | ✅ Optional | Azure DevOps personal access token |
| [`LLM_MODEL_LARGE`](#ai-models) | AI | 🔧 Advanced | Large model for complex tasks |

*One AI provider is required

## Configuration Categories

### Agent Identity

Define your agent's personality and appearance across all integrations.

```bash
# Agent display names
AVATAR_FULL_NAME="BettySharp"        # Full name shown in Slack, etc.
AVATAR_SHORT_NAME="Betty"            # Short name for casual references
```

**Examples:**
- `AVATAR_FULL_NAME="DevBot Pro"` / `AVATAR_SHORT_NAME="DevBot"`
- `AVATAR_FULL_NAME="Code Assistant"` / `AVATAR_SHORT_NAME="CodeBot"`
- `AVATAR_FULL_NAME="TeamAI Helper"` / `AVATAR_SHORT_NAME="TeamAI"`

### AI Providers

Configure your preferred AI model provider. **Choose one:**

=== "OpenAI"
    ```bash
    OPENAI_API_KEY=sk-your-openai-api-key-here
    
    # Optional: Specify models (defaults shown)
    LLM_MODEL_LARGE=openai:gpt-4
    LLM_MODEL_SMALL=openai:gpt-4-mini
    ```
    
    **Best for:** Balanced performance, wide model selection
    
=== "Anthropic"
    ```bash
    ANTHROPIC_API_KEY=sk-ant-your-anthropic-key-here
    
    # Optional: Specify models (defaults shown)  
    LLM_MODEL_LARGE=anthropic:claude-sonnet-4-20250514
    LLM_MODEL_SMALL=anthropic:claude-3-5-haiku-latest
    ```
    
    **Best for:** Code analysis, detailed reasoning
    
=== "AWS Bedrock"
    ```bash
    AWS_DEFAULT_REGION=us-east-1
    AWS_ACCESS_KEY_ID=your-access-key
    AWS_SECRET_ACCESS_KEY=your-secret-key
    
    # Use Bedrock models
    LLM_MODEL_LARGE=aws:anthropic.claude-3-sonnet
    LLM_MODEL_SMALL=aws:anthropic.claude-3-haiku
    ```
    
    **Best for:** Enterprise AWS environments

### AI Models

Fine-tune model selection for different use cases:

```bash
# Large model: complex analysis, code review, detailed responses
LLM_MODEL_LARGE=anthropic:claude-sonnet-4-20250514

# Small model: quick responses, simple tasks, cost optimization  
LLM_MODEL_SMALL=anthropic:claude-3-5-haiku-latest
```

**Available Model Formats:**
- OpenAI: `openai:gpt-4`, `openai:gpt-4-mini`, `openai:gpt-3.5-turbo`
- Anthropic: `anthropic:claude-sonnet-4-20250514`, `anthropic:claude-3-5-haiku-latest`
- AWS Bedrock: `aws:anthropic.claude-3-sonnet`, `aws:amazon.titan-text-express`

And any model supported by [Pydantic AI](https://ai.pydantic.dev/models/). Use according ENV variables and the model naming.

### Git Integration

Configure access to your source code repository:

```bash
# Required: Path to your git repository
GIT_REPO_PATH=/home/user/projects/my-app

# Optional: Auto-pull latest changes before analysis
GIT_AUTOPULL=false                    # true to enable auto-pull
GIT_PULL_INTERVAL_SECONDS=120         # How often to pull (seconds)
```

**Path Examples:**
- Absolute: `GIT_REPO_PATH=/home/user/projects/my-app`
- Windows: `GIT_REPO_PATH=C:\Projects\my-app`
- Relative: `GIT_REPO_PATH=.` (current directory)

### Slack Integration

Connect your agent to Slack for team collaboration:

```bash
# Required for Slack integration
SLACK_BOT_TOKEN=xoxb-your-bot-user-oauth-token
SLACK_APP_TOKEN=xapp-your-app-level-token

# Optional: Default channel for notifications  
SLACK_CHANNEL_ID=C1234567890
```

**Setup Steps:**
1. Create Slack app at [api.slack.com](https://api.slack.com/apps)
2. Enable Socket Mode and generate App-Level Token (`SLACK_APP_TOKEN`)
3. Install app and copy Bot User OAuth Token (`SLACK_BOT_TOKEN`)
4. Find channel ID in Slack URL or app settings (`SLACK_CHANNEL_ID`)

### Azure DevOps

Integrate with Azure DevOps for work item and pull request analysis:

```bash
# Azure DevOps connection
AZURE_URL=https://dev.azure.com           # Base Azure DevOps URL
AZURE_DEVOPS_ORGANIZATION=mycompany       # Your organization name
AZURE_DEVOPS_PROJECT=MyProject            # Project name  
AZURE_DEVOPS_PAT=your-personal-access-token
AZURE_DEVOPS_REPOID=repo-guid-here        # Repository GUID

# Optional: Mock mode for testing
AZURE_DEVOPS_MOCK=false                   # true for mock responses
```

**Personal Access Token Setup:**
1. Go to Azure DevOps → User Settings → Personal Access Tokens
2. Create new token with these scopes:
   - `Code (read)` - Read repositories and commits
   - `Work Items (read)` - Read work items and queries
   - `Project and Team (read)` - Read project information

### GitLab Integration

Connect to GitLab for merge request and issue analysis:

```bash
# GitLab connection
GITLAB_API_URL=https://gitlab.com/api/v4  # GitLab API URL
GITLAB_PROJECT_ID=12345                   # Numeric project ID
GITLAB_TOKEN=glpat-your-gitlab-token      # GitLab personal access token

# Optional: Mock mode for testing
GITLAB_MOCK=false                         # true for mock responses
```

**Token Setup:**
1. GitLab → User Settings → Access Tokens
2. Create token with scopes: `api`, `read_user`, `read_repository`
3. Find Project ID in Project Settings → General

### Core System

Configure system-level settings:

```bash
# Logging configuration
CORE_LOG_DIR=./logs                       # Log file directory

# Storage configuration  
CORE_STORAGE_FILE_DIR=./storage           # Data storage directory
```

### Interface Configuration

#### AGUI (Web Interface)

```bash
# Server settings
AGUI_HOST=0.0.0.0                        # Server bind address
AGUI_PORT=8000                           # Server port
AGUI_RELOAD=false                        # Auto-reload on code changes

# Agent settings
AGUI_DEFAULT_TIMEOUT=300                 # Request timeout (seconds)
AGUI_DEFAULT_AGENT_TYPE=chatbot          # Default agent type
AGUI_MAX_MESSAGE_LENGTH=10000            # Max message length
```

#### CLI (Command Line Interface)

```bash
# CLI default settings
CLI_DEFAULT_AGENT_TYPE=gitchatbot        # Default agent for CLI
```

### Advanced Agent Configuration

#### Impact Analysis

Fine-tune impact analysis behavior:

```bash
# Impact analysis limits
IMPACT_ANALYSIS_MAX_FILES=200            # Max files to analyze per request
```

**Performance Notes:**
- Higher values = more thorough analysis, slower processing
- Lower values = faster processing, might miss some impacts
- Recommended range: 50-500 depending on repository size

## Environment File Setup

### Creating Your .env File

```bash
# Copy the example file
cp .env.example .env

# Edit with your values
nano .env
```

### Complete .env Template

```bash
# ================================================================
# Dev Agents Environment Configuration
# ================================================================

# Agent Identity
AVATAR_FULL_NAME="BettySharp"
AVATAR_SHORT_NAME="Betty"

# AI Provider (choose one)
ANTHROPIC_API_KEY=sk-ant-your-key-here
# OPENAI_API_KEY=sk-your-key-here
# AWS_DEFAULT_REGION=us-east-1
# AWS_ACCESS_KEY_ID=your-key
# AWS_SECRET_ACCESS_KEY=your-secret

# Git Repository
GIT_REPO_PATH=/path/to/your/repository
GIT_AUTOPULL=false

# Slack Integration (optional)
# SLACK_BOT_TOKEN=xoxb-your-token
# SLACK_APP_TOKEN=xapp-your-token
# SLACK_CHANNEL_ID=C1234567890

# Azure DevOps (optional)
# AZURE_URL=https://dev.azure.com
# AZURE_DEVOPS_ORGANIZATION=myorg
# AZURE_DEVOPS_PROJECT=myproject
# AZURE_DEVOPS_PAT=your-pat

# GitLab (optional)
# GITLAB_API_URL=https://gitlab.com/api/v4
# GITLAB_PROJECT_ID=12345
# GITLAB_TOKEN=glpat-your-token

# Advanced Configuration
# LLM_MODEL_LARGE=anthropic:claude-sonnet-4-20250514
# LLM_MODEL_SMALL=anthropic:claude-3-5-haiku-latest
# CORE_LOG_DIR=./logs
# IMPACT_ANALYSIS_MAX_FILES=200
```

## Environment-Specific Examples

### Development Environment

```bash
# .env.development
AVATAR_FULL_NAME="DevBot (Dev)"
AZURE_DEVOPS_MOCK=true
GITLAB_MOCK=true
AGUI_RELOAD=true
CORE_LOG_DIR=./logs/dev
```

### Staging Environment

```bash
# .env.staging  
AVATAR_FULL_NAME="DevBot (Staging)"
AZURE_DEVOPS_MOCK=false
LLM_MODEL_LARGE=anthropic:claude-3-5-haiku-latest  # Use smaller model
IMPACT_ANALYSIS_MAX_FILES=100                      # Limit analysis
```

### Production Environment

```bash
# .env.production
AVATAR_FULL_NAME="BettySharp"
AGUI_HOST=127.0.0.1                               # Secure binding
CORE_LOG_DIR=/var/log/dev-agents                  # System logs
CORE_STORAGE_FILE_DIR=/var/lib/dev-agents/storage # System storage
```

## Validation & Testing

### Validate Configuration

Test your environment setup:

```bash
# Basic configuration test
python -c "
from src.core.config import BaseConfig
config = BaseConfig()
print('✅ Configuration loaded successfully')
"

# Test AI provider connection
python -c "
from pydantic_ai import Agent
agent = Agent('anthropic:claude-3-5-haiku-latest')
print('✅ AI provider connection successful')
"

# Test specific integrations
python -c "
from src.integrations.slack.config import SlackConfig
from src.integrations.azure.config import AzureDevOpsConfig
from src.core.config import BaseConfig

base = BaseConfig()
slack = SlackConfig(base)
azure = AzureDevOpsConfig(base)

print(f'Slack configured: {slack.is_configured()}')  
print(f'Azure DevOps configured: {azure.is_configured()}')
"
```

### Debug Missing Variables

```bash
# Check which variables are missing
python -c "
import os
required = ['AVATAR_FULL_NAME', 'AVATAR_SHORT_NAME', 'GIT_REPO_PATH']
optional = ['OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'SLACK_BOT_TOKEN']

print('Required variables:')
for var in required:
    status = '✅' if os.getenv(var) else '❌'
    print(f'  {status} {var}')

print('\nOptional variables:') 
for var in optional:
    status = '✅' if os.getenv(var) else '⚪'
    print(f'  {status} {var}')
"
```

## Security Best Practices

### Token Security

- **Never commit** `.env` files to version control
- **Use strong tokens** with appropriate scopes only
- **Rotate tokens** regularly (quarterly recommended)
- **Monitor usage** in provider dashboards for unusual activity

### File Permissions

```bash
# Secure your .env file
chmod 600 .env                    # Owner read/write only
chown $USER:$USER .env           # Ensure correct ownership
```

### Environment Isolation

```bash
# Use different .env files per environment
cp .env.example .env.development
cp .env.example .env.staging  
cp .env.example .env.production

# Load specific environment
ENV_FILE=.env.staging python -m src.entrypoints.slack_bot
```

## Troubleshooting

### Common Issues

#### "Configuration not found" Error

```bash
# Check if .env file exists and is readable
ls -la .env
cat .env | head -5

# Verify file is in correct location (project root)
pwd
ls -la | grep .env
```

#### "AI Provider Authentication Failed"

```bash
# Test API key validity
# For OpenAI:
curl -H "Authorization: Bearer $OPENAI_API_KEY" \
  https://api.openai.com/v1/models

# For Anthropic:
curl -H "x-api-key: $ANTHROPIC_API_KEY" \
  https://api.anthropic.com/v1/messages
```

#### "Git repository not found"

```bash
# Verify git repository path
ls -la "$GIT_REPO_PATH/.git"

# Test git operations
cd "$GIT_REPO_PATH" && git status
```

#### "Slack connection failed"

```bash
# Test Slack tokens
curl -X POST https://slack.com/api/auth.test \
  -H "Authorization: Bearer $SLACK_BOT_TOKEN"
```

### Debug Mode

Enable detailed logging for troubleshooting:

```bash
# Set debug logging level
export CORE_LOG_LEVEL=DEBUG

# Run with verbose output
python -m src.entrypoints.slack_bot --verbose
```

## Next Steps

- Configure [config.yaml](config-yaml.md) for advanced settings
- Set up [integrations](integrations/git.md) for your development workflow  
- Customize [prompts.yaml](prompts-yaml.md) for your team's needs

---

💡 **Tip:** Start with the Quick Start variables, then add integrations as needed. Most variables have sensible defaults and can be configured later.
