# Hook System

Dev Agents includes a WordPress-style hook system for extensibility. Hooks allow you to extend functionality without modifying core code.

## Overview

The hook system provides two types of hooks:

| Type | Purpose | Exception Handling |
|------|---------|-------------------|
| **Actions** | Fire-and-forget events for side effects | Caught and logged |
| **Filters** | Transform data through a chain of callbacks | Propagate up |

## Quick Start

```python
from core.hooks import hooks

# Register an action
def on_agent_start(agent_name: str) -> None:
    print(f"Agent {agent_name} is starting")

hooks().add_action("agent.start", on_agent_start)

# Fire the action
hooks().do_action("agent.start", agent_name="gitchatbot")

# Register a filter
def uppercase_output(content: str) -> str:
    return content.upper()

hooks().add_filter("agent.output", uppercase_output)

# Apply filters
result = hooks().apply_filters("agent.output", "hello world")
# result: "HELLO WORLD"
```

## API Reference

### `hooks()`

Get the global hook registry singleton.

```python
from core.hooks import hooks

registry = hooks()
```

### Actions

#### `add_action(hook_name, callback, priority=10)`

Register a callback for an action hook.

```python
def my_callback(arg1: str, arg2: int) -> None:
    print(f"Received: {arg1}, {arg2}")

hooks().add_action("my_hook", my_callback, priority=5)
```

**Parameters:**
- `hook_name` (str): Unique identifier for the hook
- `callback` (Callable): Function to call when hook fires
- `priority` (int): Execution order; lower numbers run first. Default: 10

#### `do_action(hook_name, *args, **kwargs)`

Fire an action, calling all registered callbacks.

```python
hooks().do_action("my_hook", "hello", arg2=42)
```

**Note:** Exceptions in callbacks are caught and logged. Execution continues with remaining callbacks.

### Filters

#### `add_filter(hook_name, callback, priority=10)`

Register a callback for a filter hook.

```python
def add_prefix(value: str) -> str:
    return f"[PREFIX] {value}"

hooks().add_filter("format_output", add_prefix)
```

**Parameters:**
- `hook_name` (str): Unique identifier for the hook
- `callback` (Callable): Function that receives value as first arg, returns modified value
- `priority` (int): Execution order; lower numbers run first. Default: 10

#### `apply_filters(hook_name, value, *args, **kwargs)`

Apply filters to a value, chaining callbacks.

```python
result = hooks().apply_filters("format_output", "Hello", extra_arg="context")
```

**Note:** Exceptions in filter callbacks propagate up to the caller.

### Inspection

#### `has_action(hook_name)` / `has_filter(hook_name)`

Check if a hook has registered callbacks.

```python
if hooks().has_action("my_hook"):
    hooks().do_action("my_hook")
```

### Removal

#### `remove_action(hook_name, callback)` / `remove_filter(hook_name, callback)`

Remove a specific callback from a hook.

```python
hooks().remove_action("my_hook", my_callback)
```

**Returns:** `True` if callback was removed, `False` otherwise.

### Testing

#### `clear()`

Remove all registered hooks. Useful for test isolation.

```python
def teardown():
    hooks().clear()
```

## Priority System

Callbacks execute in priority order (lower numbers first):

```python
hooks().add_action("process", step_one, priority=10)
hooks().add_action("process", step_two, priority=20)
hooks().add_action("process", step_three, priority=5)

# Execution order: step_three (5) → step_one (10) → step_two (20)
hooks().do_action("process")
```

Callbacks with the same priority execute in registration order (FIFO).

## Available Hooks

### GitChatbot Agent

| Hook | Type | Purpose |
|------|------|---------|
| `gitchatbot.register_tools` | Action | Add custom tool registrations |
| `gitchatbot.tool_registrations` | Filter | Modify/filter tool list |

See [Extending GitChatbot](extending-gitchatbot.md) for detailed usage.

## Best Practices

### 1. Use Descriptive Hook Names

```python
# Good
hooks().add_action("agent.execution.started", callback)
hooks().add_filter("changelog.entries.format", callback)

# Avoid
hooks().add_action("start", callback)
hooks().add_filter("format", callback)
```

### 2. Document Your Hooks

When creating hooks in your code:

```python
# Fire hook: allows extensions to log agent events
# Args: agent_name (str), execution_id (str)
hooks().do_action("agent.started", agent_name, execution_id)
```

### 3. Handle Errors Gracefully

For actions, errors are caught automatically. For filters, consider error handling:

```python
def safe_filter(value: str) -> str:
    try:
        return transform(value)
    except Exception:
        return value  # Return unchanged on error
```

### 4. Use Appropriate Priority

| Priority | Use Case |
|----------|----------|
| 1-9 | Core functionality that must run first |
| 10 | Default priority for most callbacks |
| 11-99 | Normal extensions |
| 100+ | Cleanup or finalization callbacks |

## Next Steps

- [Extending GitChatbot Tools](extending-gitchatbot.md)
- [Configuration Overview](../config-yaml.md)
