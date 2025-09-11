# Quick Start

Get your first Dev Agent running in minutes with these simple steps.

## Installation Options

### Option 1: **Docker**

   **I. Get and edit configuration:**
   * Run the Setup Wizard: [https://setup.dev-agents.ai](https://setup.dev-agents.ai) to create a configuration for your setup.
   * Alternatively, download example configuration:
     ```bash
     wget -O .env https://raw.githubusercontent.com/codeligence/dev-agents/refs/heads/main/.env.example
     ```
   * For LLM config, see also [https://ai.pydantic.dev/api/models/base/](https://ai.pydantic.dev/api/models/base/) for supported models.

   **II. Mount repository and start container:**
   * Your repository needs to be already cloned locally.
     ```bash
     # Mount cloned repository and configuration
     docker run --rm -it --env-file=.env -v your/local/repo/path:/code codeligence/dev-agents
     ```
     
     Add `-v` argument to see verbose logs.

### Option 2: **Clone and run** (requires Python 3.11+):

   **I. Clone Dev Agents:**
   * Clone the repository:
      ```bash
      git clone https://github.com/codeligence/dev-agents.git
      cd dev-agents
      ```

   **II. Get and edit configuration:**
   * Run the Setup Wizard: [https://setup.dev-agents.ai](https://setup.dev-agents.ai)
   * Or use example .env:
      ```bash
      cp .env.example .env
      ```
   * Fill in credentials for your version control provider (Gitlab/Github), LLM provider (Anthropic/OpenAI), and optional integrations (Jira/DevOps)
   * Choose LLM model (OpenAI/Anthropic) - see [https://ai.pydantic.dev/api/models/base/](https://ai.pydantic.dev/api/models/base/) for supported models

   **III. Install dependencies and run Dev Agents**

      ```bash
      pip install -e .[all]     
      python -m entrypoints.main
      ```

## First Interaction

Once running, interact with your agent in your tools (e.g. Slack):

`@DevAgents release notes for pull request 123 please`

## Next Steps

1. **Configure your integrations** - See the [Configuration](configuration/environment-variables.md) section
2. **Set up your team** - Add Dev Agents to Slack, Azure DevOps, or other tools
3. **Customize your agent** - Modify prompts and behavior for your workflow

## Need Help?

- Check the [Configuration](configuration/environment-variables.md) guide for detailed setup
- Visit our [GitHub Issues](https://github.com/codeligence/dev-agents/issues) for support
- Join [GitHub Discussions](https://github.com/codeligence/dev-agents/discussions) for community help