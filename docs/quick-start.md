# Quick Start Guide

Get your first Dev Agent running in under 10 minutes! This guide will walk you through setting up a basic Slack bot that can analyze code changes and answer development questions.

## Prerequisites Checklist

Before you start, make sure you have:

- [ ] **Python 3.11+** installed
- [ ] **Git** available in your PATH
- [ ] **Virtual environment** support
- [ ] **Slack workspace** where you can install apps (admin access)
- [ ] **OpenAI API key** (or other LLM provider)

!!! tip "Don't have all prerequisites?"
    You can still follow along with mock integrations. Set `mock: true` in configurations to simulate external services.

## Step 1: Installation

Install Dev Agents with all integrations:

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install Dev Agents
pip install dev-agents[all]
```

## Step 2: Create Your First Project

Set up a new Dev Agents project:

```bash
# Create project directory
mkdir my-dev-agents
cd my-dev-agents

# Initialize project structure
mkdir -p config logs data/storage
```

## Step 3: Basic Configuration

Create your configuration file:

=== "config/config.yaml"
    ```yaml
    # Basic Dev Agents Configuration
    core:
      log:
        dir: "./logs"
      storage:
        file:
          dir: "./data/storage"
    
    # AI Model Configuration
    models:
      large: "openai:gpt-4"
      small: "openai:gpt-4-mini"
    
    # Git Repository Settings
    git:
      repository:
        path: "."  # Current directory
        defaultBranch: "main"
        autoPull: false
    
    # Slack Bot Configuration
    slack:
      bot:
        botToken: "${SLACK_BOT_TOKEN}"
        channelId: "${SLACK_CHANNEL_ID}"
        appToken: "${SLACK_APP_TOKEN}"
        processingTimeout: 6000
    
    # Agent Settings
    agents:
      gitchatbot:
        model: "openai:gpt-4-mini"
        maxTokens: 1000
        temperature: 0.7
        timeoutSeconds: 60
    
    # Subagent Configuration
    subagents:
      impactanalysis:
        maxFiles: 200
        retries: 3
        model: "openai:gpt-4"
      coderesearch:
        model: "openai:gpt-4-mini"
    ```

=== ".env"
    ```bash
    # Core Settings
    PYTHONPATH=src
    
    # OpenAI Configuration
    OPENAI_API_KEY=your-openai-api-key-here
    LLM_MODEL_LARGE=openai:gpt-4
    LLM_MODEL_SMALL=openai:gpt-4-mini
    
    # Slack Configuration (we'll set these up next)
    SLACK_BOT_TOKEN=xoxb-your-bot-token
    SLACK_APP_TOKEN=xapp-your-app-token
    SLACK_CHANNEL_ID=C1234567890
    
    # Git Repository Path (optional)
    GIT_REPO_PATH=.
    ```

## Step 4: Slack App Setup

### 4.1 Create Slack App

1. Go to [Slack API Apps](https://api.slack.com/apps)
2. Click **"Create New App"** → **"From an app manifest"**
3. Select your workspace
4. Use this manifest:

```json
{
  "display_information": {
    "name": "Dev Agents",
    "description": "AI-powered development team automation",
    "background_color": "#2c3e50"
  },
  "features": {
    "bot_user": {
      "display_name": "Dev Agents",
      "always_online": true
    }
  },
  "oauth_config": {
    "scopes": {
      "bot": [
        "app_mentions:read",
        "channels:history",
        "channels:read",
        "chat:write",
        "files:read",
        "groups:history",
        "groups:read",
        "im:history",
        "im:read",
        "mpim:history",
        "mpim:read",
        "users:read"
      ]
    }
  },
  "settings": {
    "event_subscriptions": {
      "bot_events": [
        "app_mention",
        "message.channels",
        "message.groups",
        "message.im",
        "message.mpim"
      ]
    },
    "socket_mode_enabled": true
  }
}
```

### 4.2 Configure Tokens

1. **Install App to Workspace**: Go to "Install App" and click "Install to Workspace"
2. **Copy Bot Token**: Found in "OAuth & Permissions" → starts with `xoxb-`
3. **Create App Token**: 
   - Go to "Basic Information" → "App-Level Tokens"
   - Click "Generate Token and Scopes"
   - Add `connections:write` scope
   - Token starts with `xapp-`
4. **Get Channel ID**:
   - Right-click your Slack channel → "Copy link"
   - Extract ID from URL: `https://yourworkspace.slack.com/archives/C1234567890`
   - Channel ID is `C1234567890`

### 4.3 Update Environment

Update your `.env` file with the actual tokens:

```bash
# Replace with your actual tokens
SLACK_BOT_TOKEN=xoxb-1234567890-1234567890-abcdefghijklmnopqrstuvwx
SLACK_APP_TOKEN=xapp-1-A1234567890-1234567890-abcdefghijklmnopqrstuvwxyz123456789012345678901234
SLACK_CHANNEL_ID=C1234567890
```

## Step 5: Test Your Setup

### 5.1 Verify Configuration

Create a test script to verify everything is set up correctly:

=== "test_setup.py"
    ```python
    #!/usr/bin/env python3
    """Test script to verify Dev Agents setup."""
    
    import os
    import sys
    from pathlib import Path
    
    # Add src to Python path
    sys.path.insert(0, str(Path(__file__).parent / "src"))
    
    def test_imports():
        """Test that all required modules can be imported."""
        try:
            from core.config import BaseConfig
            from core.agents.factory import SimpleAgentFactory
            from integrations.slack.slack_client_service import SlackClientService
            print("✅ All core modules imported successfully")
            return True
        except ImportError as e:
            print(f"❌ Import error: {e}")
            return False
    
    def test_configuration():
        """Test configuration loading."""
        try:
            from core.config import BaseConfig
            config = BaseConfig()
            
            # Test model configuration
            large_model = config.get_value('models.large')
            small_model = config.get_value('models.small')
            print(f"✅ Models configured: {large_model}, {small_model}")
            
            # Test Slack configuration
            bot_token = config.get_value('slack.bot.botToken')
            if bot_token and not bot_token.startswith('${'):
                print("✅ Slack configuration loaded")
            else:
                print("⚠️ Slack tokens not configured")
            
            return True
        except Exception as e:
            print(f"❌ Configuration error: {e}")
            return False
    
    def test_environment():
        """Test environment variables."""
        required_vars = ['OPENAI_API_KEY']
        optional_vars = ['SLACK_BOT_TOKEN', 'SLACK_APP_TOKEN', 'SLACK_CHANNEL_ID']
        
        for var in required_vars:
            if not os.getenv(var):
                print(f"❌ Missing required environment variable: {var}")
                return False
            print(f"✅ {var} configured")
        
        for var in optional_vars:
            if os.getenv(var):
                print(f"✅ {var} configured")
            else:
                print(f"⚠️ {var} not configured (optional)")
        
        return True
    
    if __name__ == "__main__":
        print("🧪 Testing Dev Agents Setup...\n")
        
        success = all([
            test_imports(),
            test_configuration(), 
            test_environment()
        ])
        
        if success:
            print("\n🎉 Setup verification complete! Ready to start your bot.")
        else:
            print("\n❌ Setup issues found. Please check configuration.")
            sys.exit(1)
    ```

Run the test:

```bash
python test_setup.py
```

### 5.2 Start Your Bot

If the test passes, start your Dev Agents bot:

```bash
# Start the Slack bot
dev-agents-slack-bot
```

You should see output like:

```
2024-01-15 10:30:00 INFO Starting Dev Agents Slack Bot
2024-01-15 10:30:01 INFO Slack client connected successfully
2024-01-15 10:30:01 INFO Bot is ready and listening for messages
```

## Step 6: Test in Slack

### 6.1 Basic Interaction

In your configured Slack channel, try:

```
@dev-agents hello
```

The bot should respond with a greeting and available commands.

### 6.2 Code Analysis

If you have a Git repository in your project directory, try:

```
@dev-agents analyze recent changes
```

### 6.3 Code Questions

Ask about your codebase:

```
@dev-agents help me understand the project structure
```

## Step 7: Explore Features

### Impact Analysis

Analyze code changes:

```
@dev-agents analyze the impact of my recent commits
```

### Code Research

Explore your codebase:

```
@dev-agents find all the authentication-related code
```

### Testing Guidance

Get testing recommendations:

```
@dev-agents what tests should I write for the user service?
```

## Common First-Time Issues

### Issue: Bot doesn't respond

**Symptoms**: Bot appears online but doesn't respond to mentions

**Solutions**:
1. Check channel ID is correct
2. Verify bot is in the channel: `/invite @dev-agents`
3. Check logs for error messages
4. Ensure Socket Mode is enabled in Slack app

### Issue: "Configuration not found"

**Symptoms**: Error about missing configuration files

**Solutions**:
```bash
# Ensure config directory exists
mkdir -p config

# Check if config files are in the right place
ls -la config/
```

### Issue: "OpenAI API key not found"

**Symptoms**: Error about missing OpenAI API key

**Solutions**:
1. Verify `.env` file exists and has `OPENAI_API_KEY`
2. Check the key is valid at [OpenAI API Keys](https://platform.openai.com/api-keys)
3. Ensure environment is loaded: `source .env`

## Next Steps

Congratulations! You now have a working Dev Agents setup. Here's what to explore next:

=== "Configuration"
    **Customize your agents**
    
    - [Slack Integration Setup](configuration/slack.md)
    - [AI Model Configuration](configuration/ai-models.md)
    - [Azure DevOps Integration](configuration/azure-devops.md)

=== "Advanced Usage"
    **Expand capabilities**
    
    - [Impact Analysis Deep Dive](user-guide/impact-analysis.md)
    - [Code Research Techniques](user-guide/code-research.md)
    - [Custom Agent Development](developer/agents.md)

=== "Examples"
    **Learn from working code**
    
    - [Basic Usage Examples](examples/basic-usage.md)
    - [Integration Patterns](examples/integrations.md)
    - [Custom Agent Examples](examples/custom-agents.md)

## Getting Help

If you run into issues:

1. **Check logs**: Look in `logs/main.log` for detailed error messages
2. **Verify configuration**: Run the test script again
3. **Search documentation**: Use the search feature to find specific topics
4. **Community support**: 
   - [GitHub Issues](https://github.com/codeligence/dev-agents/issues)
   - [GitHub Discussions](https://github.com/codeligence/dev-agents/discussions)

---

*Ready to build your own agents? Check out the [Developer Guide](developer/agents.md) to start creating custom AI agents!*
