# Environment Variables

Dev Agents is configured through [`config.yaml`](config-yaml.md), and almost every value there is
a Jinja template that reads an environment variable. In practice you only edit a `.env` file.

The `.env` file is loaded from the current working directory at startup
(`.env.example` in the repository is the annotated template). Only variables that a template
actually references have an effect — see [config.yaml](config-yaml.md) for how to add your own.

## Minimum setup

```bash
# One LLM provider
ANTHROPIC_API_KEY=sk-ant-...

# Models (Pydantic AI strings: provider:model-name)
LLM_MODEL_LARGE=anthropic:claude-sonnet-5
LLM_MODEL_SMALL=anthropic:claude-haiku-4-5

# Local checkout to analyze
GIT_REPO_PATH=/code
```

## LLM providers

Credentials are read by the Pydantic AI provider itself, not by Dev Agents.

| Variable | Used for |
|----------|----------|
| `OPENAI_API_KEY` | `openai:` models |
| `ANTHROPIC_API_KEY` | `anthropic:` models |
| `AWS_DEFAULT_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | `bedrock:` models |
| `LLM_MODEL_LARGE` | Main chat agent (default `openai:gpt-4.1`) |
| `LLM_MODEL_SMALL` | Code research subagent (default `openai:gpt-4.1-mini`) |

Any provider supported by [Pydantic AI](https://ai.pydantic.dev/models/) works; set that
provider's own credential variables.

## Core

| Variable | Default | Description |
|----------|---------|-------------|
| `CORE_LOG_DIR` | `/data/logs` | Log directory |
| `CORE_STORAGE_FILE_DIR` | `/data/storage` | File storage directory |
| `VERSION_CHECK_URL` | *(empty)* | Update check endpoint; empty disables it |
| `AVATAR_FULL_NAME` | `Kira Draft` | Agent name used in prompts |
| `AVATAR_SHORT_NAME` | `Kira` | Short name |
| `AVATAR_CHARACTER` | *(see [prompts.yaml](prompts-yaml.md))* | Personality paragraph |

Verbose console logging is enabled with the `-v` flag (which sets `DEV_AGENTS_CONSOLE_LOGGING=1`
for all services).

## Git repository

| Variable | Default | Description |
|----------|---------|-------------|
| `GIT_REPO_PATH` | `/code` | Path to the local checkout |
| `GIT_AUTOPULL` | `false` | Periodically pull the repository |
| `GIT_PULL_INTERVAL_SECONDS` | `120` | Pull interval when `GIT_AUTOPULL` is on |

See [Git integration](integrations/git.md).

## Providers

Every provider has a `*_MOCK` flag that returns canned data instead of calling the API.

| Provider | Variables |
|----------|-----------|
| **Azure DevOps** | `AZURE_URL`, `AZURE_DEVOPS_ORGANIZATION`, `AZURE_DEVOPS_PROJECT`, `AZURE_DEVOPS_PAT`, `AZURE_DEVOPS_REPOID`, `AZURE_DEVOPS_MOCK`, `DEVOPS_ALLOW_INSECURE_CLONE_URL` |
| **GitLab** | `GITLAB_API_URL`, `GITLAB_PROJECT_ID`, `GITLAB_TOKEN`, `GITLAB_MOCK`, `GITLAB_ALLOW_INSECURE_CLONE_URL` |
| **GitHub** | `GITHUB_API_URL`, `GITHUB_OWNER`, `GITHUB_REPO`, `GITHUB_TOKEN`, `GITHUB_MOCK`, `GITHUB_ALLOW_INSECURE_CLONE_URL` |
| **Bitbucket** | `BITBUCKET_API_URL`, `BITBUCKET_WORKSPACE`, `BITBUCKET_REPO_SLUG`, `BITBUCKET_EMAIL`, `BITBUCKET_TOKEN`, `BITBUCKET_MOCK`, `BITBUCKET_ALLOW_INSECURE_CLONE_URL` |
| **Jira** | `JIRA_DOMAIN`, `JIRA_EMAIL`, `JIRA_TOKEN`, `JIRA_MOCK`, `JIRA_IMAGE_MODEL` |

Clone URLs used with a provider token must be `https://` and point at the host of the
configured provider URL (`AZURE_URL`, `GITLAB_API_URL`, or the web host derived from
`GITHUB_API_URL` / `BITBUCKET_API_URL`). The `*_ALLOW_INSECURE_CLONE_URL` flags (default
`False`) are **development-only** and additionally permit `http://`; the host check still
applies. See [config.yaml](config-yaml.md#providers).

Linear has no environment templates in the bundled defaults — configure it in
`config/config.custom.yaml`, see [Linear](integrations/linear.md).

## Slack

| Variable | Default | Description |
|----------|---------|-------------|
| `SLACK_BOT_TOKEN` | *(empty)* | Bot token (`xoxb-…`) |
| `SLACK_APP_TOKEN` | *(empty)* | App-level token for Socket Mode (`xapp-…`) |
| `SLACK_PROCESSING_TIMEOUT` | `6000` | Per-thread processing timeout in seconds |
| `ALWAYS_RESPOND` | `false` | Respond without being mentioned |
| `SLACK_ATTACHMENTS_ENABLED` | `false` | Forward uploaded files into the LLM context |
| `SLACK_ATTACHMENT_MAX_SIZE_MB` | `25` | Max attachment size |
| `SLACK_ATTACHMENT_MAX_INLINE_TEXT_KB` | `50` | Max inlined text per attachment |
| `SLACK_INCLUDE_FEEDBACK_BUTTONS` | `false` | Append 👍/👎 buttons to final responses |

Both tokens must be set for the Slack entrypoint to start. See [Slack](integrations/slack.md).

## Platform services

Email, Mattermost and Telegram each start only when `<NAME>_ENABLED` is truthy **and** their
credentials are present. Without an allowlist, every user on that platform can drive the agent.
See [platform services](../testing-platforms.md).

| Platform | Variables |
|----------|-----------|
| **Telegram** | `TELEGRAM_ENABLED`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_USERS`, `TELEGRAM_REQUIRE_MENTION`, `TELEGRAM_FREE_RESPONSE_CHATS` |
| **Mattermost** | `MATTERMOST_ENABLED`, `MATTERMOST_URL`, `MATTERMOST_TOKEN`, `MATTERMOST_ALLOWED_USERS`, `MATTERMOST_REQUIRE_MENTION`, `MATTERMOST_FREE_RESPONSE_CHANNELS`, `MATTERMOST_REPLY_MODE`, `MATTERMOST_ALLOW_INSECURE` |
| **Email** | `EMAIL_ENABLED`, `EMAIL_ADDRESS`, `EMAIL_PASSWORD`, `EMAIL_IMAP_HOST`, `EMAIL_IMAP_PORT`, `EMAIL_SMTP_HOST`, `EMAIL_SMTP_PORT`, `EMAIL_POLL_INTERVAL`, `EMAIL_ALLOWED_USERS` |

## HTTP entrypoints

AG-UI and the OpenAI-compatible API share one server, which starts if either is enabled.

| Variable | Default | Description |
|----------|---------|-------------|
| `HTTP_HOST` | `0.0.0.0` | Bind address |
| `HTTP_PORT` | `8000` | Port |
| `HTTP_CORS_ORIGINS` | *(empty)* | Comma-separated origins or `*`; empty disables CORS |
| `AGUI_ENABLED` | `false` | Enable the AG-UI endpoint |
| `AGUI_API_KEYS` | *(empty)* | Comma-separated client keys; required unless unauthenticated access is opted into |
| `AGUI_ALLOW_UNAUTHENTICATED` | `false` | Opt in to running the AG-UI endpoint without keys (unsafe outside a trusted network) |
| `AGUI_DEFAULT_TIMEOUT` | `300` | Run timeout in seconds |
| `AGUI_DEFAULT_AGENT_TYPE` | `gitchatbot` | Agent to run |
| `AGUI_MAX_MESSAGE_LENGTH` | `10000` | Max inbound message length |
| `OPENAI_ENTRYPOINT_ENABLED` | `false` | Enable the OpenAI-compatible API |
| `OPENAI_API_KEYS` | *(empty)* | Comma-separated client keys; required unless unauthenticated access is opted into |
| `OPENAI_ALLOW_UNAUTHENTICATED` | `false` | Opt in to running the OpenAI-compatible API without keys (unsafe outside a trusted network) |
| `OPENAI_MODEL_NAME` | `dev-agents` | Model id advertised by `/v1/models` |
| `OPENAI_STREAMING_ENABLED` | `true` | Stream responses |
| `OPENAI_THINKING_ENABLED` | `true` | Emit reasoning/status chunks while streaming |
| `OPENAI_DEFAULT_TIMEOUT` | `300` | Run timeout in seconds |
| `OPENAI_DEFAULT_AGENT_TYPE` | `gitchatbot` | Agent to run |

`OPENAI_*` here configures the *inbound* API. The OpenAI models you call are set with
`LLM_MODEL_*` and `OPENAI_API_KEY`.

Both entrypoints run the agent, so authentication is fail-closed. An enabled entrypoint whose
`AGUI_API_KEYS` / `OPENAI_API_KEYS` is empty refuses to start with a configuration error naming
the variables to set. Running without authentication is an explicit opt-in via
`AGUI_ALLOW_UNAUTHENTICATED=true` / `OPENAI_ALLOW_UNAUTHENTICATED=true`, which is only appropriate
when the port is reachable from a trusted network alone; the server logs a warning at startup when
it is set. Clients authenticate with `Authorization: Bearer <key>`.

## CLI, NATS and subagents

| Variable | Default | Description |
|----------|---------|-------------|
| `CLI_DEFAULT_AGENT_TYPE` | `gitchatbot` | Agent used by the interactive CLI |
| `NATS_SERVER_URL` | *(empty)* | Enables the NATS entrypoint when set |
| `NATS_JOB_ID`, `NATS_USER`, `NATS_PASSWORD`, `NATS_CA_CERT_PATH` | *(empty)* | Connection details |
| `NATS_SUBJECT_JOB_DATA` | `jobs` | Job subject |
| `NATS_SUBJECT_JOB_UPDATES` | `jobupdates` | Job update subject |
| `CLAUDE_CODE_PATH` | *(empty)* | Path to the Claude Code CLI; enables the Claude Code research subagent |
| `CLAUDE_CODE_MODEL` | `claude-sonnet-5` | Model used by that subagent |

## Security

- Keep `.env` out of version control and restrict its permissions (`chmod 600 .env`).
- Use read-only tokens where the provider supports them.
- Prefer your platform's secret store (Docker secrets, Kubernetes secrets) over a plain `.env`
  in production.

## Next steps

- [config.yaml](config-yaml.md) — the structure behind these variables
- [prompts.yaml](prompts-yaml.md) — agent prompts and persona
