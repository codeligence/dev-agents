# Quick Start

Dev Agents needs three things: an **LLM API key**, a **local git checkout** to analyze, and at
least one **entrypoint** to talk to it through. Everything else is optional.

## 1. Configuration

Generate a `.env` with the [Setup Wizard](https://setup.dev-agents.ai), or start from the example:

```bash
wget -O .env https://raw.githubusercontent.com/codeligence/dev-agents/main/.env.example
```

The minimum:

```bash
ANTHROPIC_API_KEY=sk-ant-...              # or OPENAI_API_KEY / AWS credentials
LLM_MODEL_LARGE=anthropic:claude-sonnet-5
LLM_MODEL_SMALL=anthropic:claude-haiku-4-5
GIT_REPO_PATH=/code                       # path to the checkout to analyze
```

Model strings follow [Pydantic AI](https://ai.pydantic.dev/models/) (`provider:model-name`).
Add Slack tokens and provider credentials as needed — see
[environment variables](configuration/environment-variables.md).

## 2. Run

=== "Docker"

    ```bash
    docker run --rm -it --env-file=.env \
      -v /path/to/your/repo:/code \
      codeligence/dev-agents
    ```

    Add `-v` (after the image name) for verbose logs.

=== "From source"

    Requires Python 3.11+.

    ```bash
    git clone https://github.com/codeligence/dev-agents.git
    cd dev-agents
    cp .env.example .env      # then edit
    pip install -e ".[prod]"  # or ".[all]" for dev tooling
    dev-agents
    ```

## 3. Talk to it

On startup, Dev Agents detects which services are configured and starts them all in parallel:
Slack, [platform services](testing-platforms.md), NATS, the HTTP entrypoints (AG-UI and the
OpenAI-compatible API), and — when stdin is a terminal — an interactive CLI chat.

```bash
dev-agents                      # interactive chat + every configured service
dev-agents --prompt "How does the auth flow work?"   # single prompt, then exit
dev-agents -v                   # verbose logging
```

In Slack:

```
@DevAgents how does the authentication flow work?
```

## Next steps

- [Environment variables](configuration/environment-variables.md) — the full reference
- [config.yaml](configuration/config-yaml.md) — projects, providers, agents
- [Slack](configuration/integrations/slack.md) — app manifest and scopes
- [Hooks](configuration/hooks/index.md) — extend the agent with your own tools
