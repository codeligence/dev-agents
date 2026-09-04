# Hook System

`HookRegistry` (`src/core/hooks.py`) is a WordPress-style extension point: **actions** for side
effects, **filters** for transforming a value. It is how skills add tools, register agents, and
customize behaviour without touching framework code.

```python
from core.hooks import hooks

# Action — fire and forget
hooks().add_action("user_login", lambda user_id: print(f"{user_id} logged in"))
hooks().do_action("user_login", user_id=123)

# Filter — transform a value
hooks().add_filter("post_content", lambda content: content.upper())
hooks().apply_filters("post_content", "hello world")   # "HELLO WORLD"
```

`hooks()` returns the process-wide singleton registry; call it from anywhere.

## API

| Method | Purpose |
|--------|---------|
| `add_action(name, callback, priority=10)` | Register a side-effect callback |
| `do_action(name, *args, **kwargs)` | Fire all callbacks for `name` |
| `add_filter(name, callback, priority=10)` | Register a transform; it receives the value first and must return it |
| `apply_filters(name, value, *args, **kwargs)` | Chain callbacks over `value` and return the result |
| `has_action(name)` / `has_filter(name)` | Check whether anything is registered |
| `remove_action(name, callback)` / `remove_filter(name, callback)` | Unregister; returns `True` if removed |
| `clear()` | Drop everything — for test isolation |

Two behavioural differences that matter:

- **Actions swallow exceptions.** A failing callback is logged and the remaining callbacks still
  run.
- **Filters do not.** An exception in a filter propagates to the caller, so validate your input.

Callbacks run in ascending `priority` (default `10`), and registration order breaks ties:

```python
hooks().add_action("startup", third, priority=20)
hooks().add_action("startup", first, priority=5)
hooks().add_action("startup", second)          # priority 10
# runs: first → second → third
```

## Available hooks

| Hook | Type | Payload | Purpose |
|------|------|---------|---------|
| `agent_service.created` | Action | `AgentService` | Register agent types at startup |
| `agent_service.execute_agent_name` | Filter | `str` | Override which agent runs |
| `gitchatbot.register_tools` | Action | `list[ToolRegistration]` | Append tools for the chat agent |
| `gitchatbot.tool_registrations` | Filter | `list[ToolRegistration]` | Reorder or drop those tools |
| `code_research.register_tools` | Action | `list[ToolRegistration]` | Append tools for the code research subagent |
| `code_research.tool_registrations` | Filter | `list[ToolRegistration]` | Reorder or drop them, defaults included |
| `claude_code_subagent.collect_tools` | Filter | `list[tuple[str, list]]` | Add `(server_name, tools)` MCP servers to the Claude Code subagent |
| `slack.feedback` | Action | `event=FeedbackEvent` | React to a 👍/👎 click |
| `slack.feedback.blocks` | Filter | `list[dict]` | Customize the feedback Block Kit blocks |

## Registering an agent

```python
from core.hooks import hooks
from core.agents.service import AgentService

def register_my_agents(service: AgentService) -> None:
    service.register_agent("my_custom_agent", lambda: MyCustomAgent)

hooks().add_action("agent_service.created", register_my_agents)
```

## Where to register

Registration must happen before the agent runs. The supported place is a **skill**: a module with
a top-level `setup()` that wires up its hooks, listed under `skills.enable` in
[config.yaml](../config-yaml.md#skills) and imported once at startup by `load_skills()`.

```yaml
skills:
  enable:
    - mycompany_skills.deploy
  search_paths:
    - /opt/dev-agents/custom-skills
```

## Testing

`clear()` gives each test a clean registry:

```python
import pytest
from core.hooks import hooks

@pytest.fixture(autouse=True)
def clean_hooks():
    hooks().clear()
    yield
    hooks().clear()
```

## Next steps

- [Extending the chat agent](extending-gitchatbot.md) — add your own tools
- [config.yaml](../config-yaml.md#skills) — enable skill modules
