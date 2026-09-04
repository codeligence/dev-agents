# config.yaml

`config.yaml` defines models, providers, projects, entrypoints and skills. Nearly every value is a
Jinja template reading an environment variable, so most deployments only edit `.env` and never
touch the YAML.

The authoritative copy of the defaults ships in the package at `src/core/defaults/config.yaml`.

## Resolution

`BaseConfig` (`src/core/config.py`) loads three layers:

1. **Bundled defaults** — `core/defaults/config.yaml`, always present.
2. **`<cwd>/config/config.yaml`** — if present, *replaces* the bundled defaults entirely.
3. **`<cwd>/config/config.custom.yaml`** — if present, deep-merged on top.

The recommended pattern is to leave the bundled defaults alone and write only the keys you change
into `config/config.custom.yaml`, so upgrades keep bringing you new defaults.

`projects` is an *entity* section: when your overlay defines it, projects that exist only in the
bundled defaults (i.e. `default`) are pruned rather than merged, so placeholders stay out of your
project list. All other sections merge normally.

The same layering applies to [`prompts.yaml`](prompts-yaml.md).

## Value syntax

```yaml
models:
  large: "@jinja {{env.LLM_MODEL_LARGE or 'openai:gpt-4.1'}}"

providers:
  github:
    token: "@jinja {{ env.get('GITHUB_TOKEN', '') }}"

projects:
  default:
    pullrequests:
      github:
        token: "@jinja {{ this.providers.github.token }}"   # cross-reference
```

- `@jinja` values are rendered by Dynaconf at load time; both `env.NAME` and `env.get('NAME', '')`
  forms are used.
- `this.<dotted.path>` references another value in the same file — this is how a provider is
  defined once and reused per project.
- Rendering produces **strings**, so booleans are read through `BaseConfig.get_bool()`
  (`true`, `1`, `yes`, `on`). Write plain `true` / `false` in your own YAML.
- Dynaconf environments are disabled — there is no `[development]` / `[production]` layering, and
  `DYNACONF_ENV` has no effect. Use separate `.env` files or overlays instead.

## Sections

### `core`

| Key | Environment variable | Default |
|-----|----------------------|---------|
| `core.log.dir` | `CORE_LOG_DIR` | `/data/logs` |
| `core.storage.file.dir` | `CORE_STORAGE_FILE_DIR` | `/data/storage` |
| `core.version_check_url` | `VERSION_CHECK_URL` | *(empty — disabled)* |

### `models`

Two named slots that agents reference via `this.models.*`. Values are
[Pydantic AI](https://ai.pydantic.dev/models/) model strings.

| Key | Environment variable | Default | Used for |
|-----|----------------------|---------|----------|
| `models.large` | `LLM_MODEL_LARGE` | `openai:gpt-4.1` | Main chat agent |
| `models.small` | `LLM_MODEL_SMALL` | `openai:gpt-4.1-mini` | Code research subagent |

```yaml
models:
  large: "anthropic:claude-sonnet-5"
  small: "anthropic:claude-haiku-4-5"
```

`openai:` targets the Responses API; use `openai-chat:` for Chat Completions semantics or a
gateway that only speaks that API. Temperature and token limits are per-agent, see
[`agents`](#agents).

### `providers`

Credentials defined once and referenced from `projects`. Every provider has a `mock` flag that
returns canned data instead of calling the API.

| Provider | Keys |
|----------|------|
| `devops` | `url`, `organization`, `project`, `pat`, `repoId`, `mock`, `allowInsecureCloneUrl` |
| `gitlab` | `api_url`, `project_id`, `token`, `mock`, `allowInsecureCloneUrl` |
| `github` | `api_url`, `owner`, `repo`, `token`, `mock`, `allowInsecureCloneUrl` |
| `bitbucket` | `api_url`, `workspace`, `repo_slug`, `username`, `token`, `mock`, `allowInsecureCloneUrl` |
| `jira` | `domain`, `email`, `token`, `mock`, `imageModel` |

The matching environment variables are listed in
[environment variables](environment-variables.md#providers). `bitbucket.api_url` defaults to
`https://api.bitbucket.org/2.0`; the other URLs default to empty.

When a pull request provider clones its repository, the clone URL is validated before the
token is used: it must be `https://` and its host (including any port) must match the
provider's configured host (`devops.url`, `gitlab.api_url`, or the web host derived from
`github.api_url` / `bitbucket.api_url`). URLs that embed credentials are always rejected.
`allowInsecureCloneUrl: true` is a **development-only** override that additionally permits
`http://`; the host check still applies.

### `projects`

A project ties one git checkout to the providers that serve its pull requests, issues and
pipelines. The bundled defaults ship a single project named `default`.

**`projects.<name>.git`**

| Key | Environment variable | Default | Description |
|-----|----------------------|---------|-------------|
| `path` | `GIT_REPO_PATH` | `/code` | Local checkout to analyze |
| `defaultBranch` | — | `main` | Comparison base branch |
| `autoPull` | `GIT_AUTOPULL` | `false` | Pull periodically |
| `pullIntervalSeconds` | `GIT_PULL_INTERVAL_SECONDS` | `120` | Interval when `autoPull` is on |

**Provider slots** — each maps a provider name to that provider's settings:

| Slot | Providers |
|------|-----------|
| `pullrequests` | `devops`, `gitlab`, `github`, `bitbucket` |
| `issues` | `devops`, `gitlab`, `github`, `jira`, `linear` |
| `pipelines` | `gitlab` |

Delete the slots you do not use — an unconfigured provider is simply not offered to the agent.
From code, access goes through `ProjectConfig` (`src/core/project_config.py`):

```python
from core.config import get_default_config

project = get_default_config().get_default_project_config()
project.get_git_config()
project.get_provider_config("pullrequests", "github")
```

### `slack`

| Key | Environment variable | Default |
|-----|----------------------|---------|
| `slack.bot.botToken` | `SLACK_BOT_TOKEN` | *(empty)* |
| `slack.bot.appToken` | `SLACK_APP_TOKEN` | *(empty)* |
| `slack.bot.processingTimeout` | `SLACK_PROCESSING_TIMEOUT` | `6000` |
| `slack.bot.alwaysRespond` | `ALWAYS_RESPOND` | `false` |
| `slack.attachments.enabled` | `SLACK_ATTACHMENTS_ENABLED` | `false` |
| `slack.attachments.maxFileSizeMb` | `SLACK_ATTACHMENT_MAX_SIZE_MB` | `25` |
| `slack.attachments.maxInlineTextKb` | `SLACK_ATTACHMENT_MAX_INLINE_TEXT_KB` | `50` |
| `slack.assistant.welcomeMessage` | — | greeting for new Assistant threads |
| `slack.assistant.includeFeedbackButtons` | `SLACK_INCLUDE_FEEDBACK_BUTTONS` | `false` |
| `slack.assistant.suggestedPrompts` | — | four `{title, message}` examples |

Attachment forwarding is opt-in on purpose: it sends private Slack files into the LLM context.
Overriding `suggestedPrompts` replaces the whole list.

### `http`, `agui`, `openai`, `nats`, `cli`

These mirror their environment variables one-to-one — see
[environment variables](environment-variables.md#http-entrypoints). `http.server.*` configures the
shared server used by the AG-UI and OpenAI-compatible entrypoints; `agui.server.enabled` and
`openai.server.enabled` decide whether it starts at all.

Both entrypoints run the agent, so authentication is fail-closed. An enabled entrypoint needs
`agui.server.apiKeys` / `openai.server.apiKeys` (`AGUI_API_KEYS` / `OPENAI_API_KEYS`, a
comma-separated string or a YAML list of Bearer tokens). If the value is empty, missing or has any
other type, startup aborts with a configuration error instead of serving the agent openly. To run
without authentication on purpose, set `agui.server.allowUnauthenticated` /
`openai.server.allowUnauthenticated` (`AGUI_ALLOW_UNAUTHENTICATED` / `OPENAI_ALLOW_UNAUTHENTICATED`)
to `true`. This is unsafe outside a trusted network: anyone who reaches the port gets repository
access, the registered tools and your LLM spend.

### `skills`

Skills are Python modules that register extra agent tools through the [hook
system](hooks/index.md). `load_skills()` imports them at startup.

```yaml
skills:
  enable:
    - skills.scheduler
    - mycompany_skills.deploy
  search_paths:
    - /opt/dev-agents/custom-skills
```

| Key | Default | Description |
|-----|---------|-------------|
| `skills.enable` | `[]` | Module paths to import, in order |
| `skills.search_paths` | `[]` | Extra import roots |

### `agents`

| Key | Default | Description |
|-----|---------|-------------|
| `agents.gitchatbot.model` | `this.models.large` | Model for the main chat agent |
| `agents.gitchatbot.maxTokens` | `2000` | Response token limit |
| `agents.gitchatbot.temperature` | `0.7` | Sampling temperature |
| `agents.gitchatbot.timeoutSeconds` | `60` | Per-run timeout |

### `subagents`

| Key | Environment variable | Default | Description |
|-----|----------------------|---------|-------------|
| `subagents.coderesearch.model` | — | `this.models.small` | Code research subagent model |
| `subagents.claude_code.cli_path` | `CLAUDE_CODE_PATH` | *(empty)* | Claude Code CLI binary |
| `subagents.claude_code.model` | `CLAUDE_CODE_MODEL` | `claude-sonnet-5` | Model for that subagent |

When the `claude` extra is installed *and* `subagents.claude_code.cli_path` is set, the chat agent
uses the Claude Code research tool; otherwise it falls back to the built-in code research
subagent.

## A minimal overlay

```yaml
# config/config.custom.yaml
models:
  large: "anthropic:claude-sonnet-5"
  small: "anthropic:claude-haiku-4-5"

projects:
  backend:
    git:
      path: "/code/backend"
      defaultBranch: "develop"
      autoPull: true
    pullrequests:
      github:
        api_url: "@jinja {{ this.providers.github.api_url }}"
        owner: "@jinja {{ this.providers.github.owner }}"
        repo: "@jinja {{ this.providers.github.repo }}"
        token: "@jinja {{ this.providers.github.token }}"
        mock: false

agents:
  gitchatbot:
    timeoutSeconds: 120
```

Because `projects` is an entity section, this leaves exactly one project — `backend`.

## Check what loaded

```bash
python -c "
from core.config import get_default_config
c = get_default_config()
print('models.large:', c.get_value('models.large'))
print('projects:', c.get_available_projects())
print('git path:', c.get_default_project_config().get_git_config().get('path'))
"
```

An empty value means the environment variable behind it is unset.

## Next steps

- [Environment variables](environment-variables.md)
- [prompts.yaml](prompts-yaml.md)
- [Integrations](integrations/git.md)
- [Hooks and skills](hooks/index.md)
