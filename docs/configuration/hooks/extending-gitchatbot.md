# Extending the Chat Agent

The chat agent (`gitchatbot`) builds its toolset at run time from a list of `ToolRegistration`
objects. Two [hooks](index.md) let you change that list, so you can add company-specific tools
without forking the agent:

- `gitchatbot.register_tools` (action) — append your registrations
- `gitchatbot.tool_registrations` (filter) — reorder or drop registrations, defaults included

The same pair exists for the code research subagent: `code_research.register_tools` and
`code_research.tool_registrations`.

## ToolRegistration

```python
from core.agents.models import ToolRegistration
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Function name the model calls |
| `description` | `str` | One-liner listed under the agent's capabilities in the system prompt |
| `function` | async callable | Tool implementation; first parameter is `RunContext` |
| `priority` | `int` | Ordering in the prompt, ascending. Default `10` |

The descriptions are joined into `{tool_descriptions}` in
[`agents.chatbot.initial`](../prompts-yaml.md), so write them for the model: what the tool does,
what arguments it takes, what it returns.

Built-in priorities to slot around: `list_recent_tags` (30), the code research tool (40),
`get_token_usage` (70).

## A tool

```python
from pydantic_ai import RunContext

from core.skills.context import SkillContext


async def deployment_status(ctx: RunContext, environment: str) -> str:
    """Get the current deployment status for an environment.

    Args:
        environment: Environment name, e.g. "staging" or "production".

    Returns:
        Markdown summary of the running version and its health.
    """
    sc = SkillContext(ctx)
    await sc.send_toolcall_message(f"Checking {environment}...")

    try:
        status = await fetch_status(environment)
    except Exception as exc:
        return f"Could not read the deployment status: {exc}"

    return f"**{environment}**: version {status.version}, healthy={status.healthy}"
```

Rules that matter:

- The function must be `async` and take `RunContext` first. Every other parameter needs a type
  annotation — Pydantic AI derives the tool schema from them.
- Return a string. Return a readable error message instead of raising: an exception ends the run,
  a message lets the model recover.
- The docstring is part of the schema the model sees.

`SkillContext` (`src/core/skills/context.py`) is the facade onto the run:

| Member | Purpose |
|--------|---------|
| `sc.deps` | Agent dependencies (context, conversation state) |
| `await sc.send_toolcall_message(fallback)` | Forward the model's tool-call text as a status update |
| `await sc.send_status(msg)` / `send_response(msg)` | Post a status / a full response |
| `await sc.send_attachment(...)` / `download_attachment(id)` | Attachments (a Slack canvas, for example) |
| `sc.save_artifact(...)` / `load_artifact(...)` | Persist and reload generated artifacts |
| `sc.get_selected_project(default)` | The project the user is currently working in |
| `sc.config` / `sc.prompts` | Configuration and prompts |

## Registering it

Put the wiring in a skill module — one `setup()` that registers the hooks:

```python
# mycompany_skills/deploy.py
from core.agents.models import ToolRegistration
from core.hooks import hooks


def register_tools(registrations: list[ToolRegistration]) -> None:
    registrations.append(
        ToolRegistration(
            name="deployment_status",
            description=(
                "Get the current deployment status of an environment. "
                "Args: environment (e.g. 'staging', 'production'). "
                "Returns: running version and health as markdown."
            ),
            function=deployment_status,
            priority=50,
        )
    )


def setup() -> None:
    hooks().add_action("gitchatbot.register_tools", register_tools)
```

Enable it in `config/config.custom.yaml`:

```yaml
skills:
  enable:
    - mycompany_skills.deploy
  search_paths:
    - /opt/dev-agents/custom-skills   # only if the module is not importable already
```

`load_skills()` imports each listed module at startup and calls its `setup()`. A module without
`setup()` is skipped with a warning, and an error inside `setup()` is logged without taking the
process down.

## Removing or reordering tools

The filter receives the full list, defaults included:

```python
def drop_token_usage(registrations: list[ToolRegistration]) -> list[ToolRegistration]:
    return [r for r in registrations if r.name != "get_token_usage"]


hooks().add_filter("gitchatbot.tool_registrations", drop_token_usage)
```

Filters must return the list, and exceptions propagate — a raise here fails the run.

## Next steps

- [Hook system](index.md) — the full hook list
- [prompts.yaml](../prompts-yaml.md) — where `{tool_descriptions}` is rendered
