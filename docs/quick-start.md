# Quick Start

Get your first Dev Agent running in minutes with these simple steps.

## Installation Options

### Option 1: Setup Wizard (Recommended)

Run the **Setup Wizard** at [https://setup.dev-agents.ai](https://setup.dev-agents.ai)

The wizard generates your configuration and start instructions for local or server deployment.

### Option 2: Manual Setup

Clone and configure the repository manually:

```bash
# 1) Clone the repository
git clone https://github.com/codeligence/dev-agents.git
cd dev-agents

# 2) Copy example environment file and edit
cp .env.example .env

# 3) Install dependencies
pip install -e .[all]

# 4) Start with command line interface
python -m entrypoints.cli_chat

# or use docker (coming soon)
```

## First Interaction

Once running, interact with your agent in your tools (e.g. Slack):

```
@BettySharp release notes for sprint 42
```

## Next Steps

1. **Configure your integrations** - See the [Configuration](configuration/environment-variables.md) section
2. **Set up your team** - Add Dev Agents to Slack, Azure DevOps, or other tools
3. **Customize your agent** - Modify prompts and behavior for your workflow

## Need Help?

- Check the [Configuration](configuration/environment-variables.md) guide for detailed setup
- Visit our [GitHub Issues](https://github.com/codeligence/dev-agents/issues) for support
- Join [GitHub Discussions](https://github.com/codeligence/dev-agents/discussions) for community help