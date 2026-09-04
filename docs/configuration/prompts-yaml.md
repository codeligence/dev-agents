# prompts.yaml

`prompts.yaml` holds the agent persona and system prompts. It is resolved in the same three layers
as [`config.yaml`](config-yaml.md#resolution):

1. Bundled defaults — `src/core/defaults/prompts.yaml`
2. `<cwd>/config/prompts.yaml` — replaces the bundled defaults entirely
3. `<cwd>/config/prompts.custom.yaml` — deep-merged on top

Put your changes in `config/prompts.custom.yaml` and override only the keys you care about.

## Structure

The shipped file is short — two top-level sections:

```yaml
avatar:
  fullName: "@jinja {{ env.AVATAR_FULL_NAME or 'Kira Draft' }}"
  shortName: "@jinja {{ env.AVATAR_SHORT_NAME or 'Kira' }}"
  character: "@jinja {{ env.AVATAR_CHARACTER or 'You are a helpful AI assistant. ...' }}"

agents:
  chatbot:
    initial: |
      @jinja You are {{ this.avatar.fullName }} a multilingual developer assistant.
      ...
      {{ this.agents.chatbot.custom }}
    custom: ""
    research_codebase_prompt: |
      ...
    code_research_prompt: |
      ...
  code_research_tools: |
    ## Code Research Tools (max 20 calls)
    ...
```

| Key | Used by |
|-----|---------|
| `avatar.fullName` / `shortName` | Referenced from prompts; also how the agent addresses itself |
| `avatar.character` | Personality paragraph interpolated into the chatbot prompt |
| `agents.chatbot.initial` | System prompt of the main chat agent |
| `agents.chatbot.custom` | Empty by default — your team-specific instructions, appended to `initial` |
| `agents.chatbot.research_codebase_prompt` | Task prompt sent to the Claude Code research subagent |
| `agents.chatbot.code_research_prompt` | System prompt of the built-in code research subagent |
| `agents.code_research_tools` | Tool cheat-sheet interpolated into `code_research_prompt` |

## Placeholders

Two mechanisms interpolate into these strings — do not mix them up:

- **`@jinja` / `{{ … }}`** — resolved by Dynaconf at load time. Use `env.NAME` for environment
  variables and `this.<dotted.path>` to reference another prompt value.
- **`{name}`** — Python `str.format()` placeholders filled in at runtime. These must survive
  into the final string:

| Placeholder | In | Filled with |
|-------------|-----|-------------|
| `{tool_descriptions}` | `agents.chatbot.initial` | Descriptions of the registered tools |
| `{instructions}` | `research_codebase_prompt` | The research task |
| `{context_description}` | `research_codebase_prompt` | Current PR / branch context |
| `{git_analysis_instructions}` | `research_codebase_prompt` | Git refs to compare |

Removing a placeholder from a prompt you override breaks that agent's formatting, so keep them.

## Customizing

The lowest-risk change is `agents.chatbot.custom`, which is appended to the stock prompt:

```yaml
# config/prompts.custom.yaml
agents:
  chatbot:
    custom: |
      Our services live under services/. Always mention the owning team when you
      describe a service, and prefer German when the user writes in German.
```

Persona changes need no YAML at all — set `AVATAR_FULL_NAME`, `AVATAR_SHORT_NAME` and
`AVATAR_CHARACTER` in `.env`.

To replace a full prompt, copy the key from the bundled file and edit it:

```yaml
agents:
  chatbot:
    initial: |
      You are a release engineer assistant.

      Available capabilities:
      {tool_descriptions}
```

## Check what loaded

```bash
python -c "
from core.prompts import get_default_prompts
p = get_default_prompts()
print(p.get_prompt('avatar.fullName'))
print(p.get_prompt('agents.chatbot.initial')[:400])
"
```

## Next steps

- [config.yaml](config-yaml.md) — models, agents, subagents
- [Extending the chat agent](hooks/extending-gitchatbot.md) — add tools that show up in
  `{tool_descriptions}`
