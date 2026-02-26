# Extending GitChatbot Tools

GitChatbot uses an extensible tool registration system that allows you to add custom tools without modifying the agent code.

## Overview

The GitChatbot agent dynamically registers tools at runtime using hooks:

1. **Default tools** are collected from the agent
2. **Action hook** fires to allow adding new tools
3. **Filter hook** fires to allow sorting/removing tools
4. **System prompt** is built with tool descriptions
5. **Tools** are registered with the PydanticAI agent

## Quick Start

Add a custom tool to GitChatbot:

```python
from core.hooks import hooks
from core.agents.models import ToolRegistration
from pydantic_ai import RunContext
from agents.agents.gitchatbot.models import PersistentAgentDeps

async def estimate_complexity(
    ctx: RunContext[PersistentAgentDeps],
    scope: str = "current_context",
) -> str:
    """
    Estimate the complexity of code changes.

    Args:
        scope: What to analyze - "current_context" uses PR/git refs from context

    Returns:
        Complexity estimation with metrics
    """
    # Access conversation context
    context = ctx.deps.load_context()

    # Your implementation here
    return f"Complexity analysis for PR #{context.pull_request_id}..."

def register_complexity_tool(registrations: list[ToolRegistration]) -> None:
    """Add complexity estimation tool to GitChatbot."""
    registrations.append(ToolRegistration(
        name="estimate_complexity",
        description="Code complexity estimation for change assessment",
        function=estimate_complexity,
        priority=50,
    ))

# Register during app startup
hooks().add_action("gitchatbot.register_tools", register_complexity_tool)
```

## ToolRegistration Model

```python
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

@dataclass
class ToolRegistration:
    name: str                           # Tool function name
    description: str                    # Shown in system prompt
    function: Callable[..., Awaitable[Any]]  # Async tool function
    priority: int = 10                  # Display order (lower = first)
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | str | Unique identifier used as the tool function name |
| `description` | str | Short description added to the system prompt |
| `function` | async callable | The tool implementation |
| `priority` | int | Controls ordering in system prompt (default: 10) |

## Writing Tool Functions

### Function Signature

Tools must be async and accept `RunContext` as the first parameter:

```python
from pydantic_ai import RunContext
from agents.agents.gitchatbot.models import PersistentAgentDeps

async def my_tool(
    ctx: RunContext[PersistentAgentDeps],
    required_param: str,
    optional_param: int = 10,
) -> str:
    """
    Tool documentation becomes the AI's understanding of the tool.

    Args:
        required_param: Description shown to the AI
        optional_param: Another parameter with default

    Returns:
        Result string returned to the AI
    """
    # Implementation
    return "Result"
```

### Accessing Context

The `ctx.deps` object provides access to:

```python
async def my_tool(ctx: RunContext[PersistentAgentDeps]) -> str:
    # Get execution context
    execution_id = ctx.deps.execution_id

    # Load conversation context (PR, issue, git refs)
    context = ctx.deps.load_context()

    if context.pull_request_id:
        # Work with PR
        pr_id = context.pull_request_id

    if context.source_git_ref and context.target_git_ref:
        # Work with git refs
        source = context.source_git_ref
        target = context.target_git_ref

    if context.issue_id:
        # Work with issue
        issue_id = context.issue_id

    # Access storage for artifacts
    storage = ctx.deps.storage

    return "Result"
```

### Sending Messages

Tools can send status updates to the user:

```python
from core.agents.context import get_current_agent_execution_context

async def my_tool(ctx: RunContext[PersistentAgentDeps]) -> str:
    # Send status message
    await get_current_agent_execution_context().send_status("Processing...")

    # Send response/attachment
    await get_current_agent_execution_context().send_attachment(
        title="Analysis Results",
        content="Detailed analysis content here..."
    )

    return "Analysis complete"
```

## Hook Reference

### `gitchatbot.register_tools` (Action)

Called with a mutable list of `ToolRegistration` objects. Add new tools by appending to this list.

```python
def add_my_tools(registrations: list[ToolRegistration]) -> None:
    registrations.append(ToolRegistration(...))
    registrations.append(ToolRegistration(...))

hooks().add_action("gitchatbot.register_tools", add_my_tools)
```

### `gitchatbot.tool_registrations` (Filter)

Called with the complete list after all additions. Use to sort, filter, or modify tools.

```python
def filter_tools(registrations: list[ToolRegistration]) -> list[ToolRegistration]:
    # Remove a specific tool
    return [r for r in registrations if r.name != "unwanted_tool"]

def reorder_tools(registrations: list[ToolRegistration]) -> list[ToolRegistration]:
    # Custom sorting
    return sorted(registrations, key=lambda r: r.name)

hooks().add_filter("gitchatbot.tool_registrations", filter_tools)
hooks().add_filter("gitchatbot.tool_registrations", reorder_tools, priority=20)
```

## Example: Complete Custom Tool

Here's a complete example of a custom code metrics tool:

```python
# my_extension/tools.py

from core.hooks import hooks
from core.agents.models import ToolRegistration
from core.agents.context import get_current_agent_execution_context
from pydantic_ai import RunContext
from agents.agents.gitchatbot.models import PersistentAgentDeps
from integrations.git.git_repository import GitRepository

async def analyze_code_metrics(
    ctx: RunContext[PersistentAgentDeps],
    metric_type: str = "all",
) -> str:
    """
    Analyze code metrics for the current context.

    Provides metrics like lines of code, complexity scores, and change statistics
    based on the current PR or git reference comparison.

    Args:
        metric_type: Type of metrics to analyze - "all", "complexity", "changes", "coverage"

    Returns:
        Formatted metrics report
    """
    # Notify user
    await get_current_agent_execution_context().send_status("Analyzing metrics...")

    # Get context
    context = ctx.deps.load_context()

    if not context.pull_request_id and not (context.source_git_ref and context.target_git_ref):
        return "No PR or git refs in context. Use update_context first."

    # Get git repository
    from core.agents.context import get_current_config
    config = get_current_config()
    project_config = config.get_default_project_config()
    git_repo = GitRepository(project_config=project_config)

    # Analyze based on metric type
    results = []

    if metric_type in ("all", "changes"):
        # Get changed files
        if context.source_git_ref and context.target_git_ref:
            diff_context = git_repo.get_diff_from_branches(
                context.source_git_ref,
                context.target_git_ref,
                "Metrics analysis"
            )
            results.append(f"Changed files: {len(diff_context.changed_files)}")

    if metric_type in ("all", "complexity"):
        results.append("Complexity: Medium (placeholder)")

    if metric_type in ("all", "coverage"):
        results.append("Coverage impact: Not available")

    return "## Code Metrics\n\n" + "\n".join(f"- {r}" for r in results)


def register_metrics_tools(registrations: list[ToolRegistration]) -> None:
    """Register code metrics tools with GitChatbot."""
    registrations.append(ToolRegistration(
        name="analyze_code_metrics",
        description="Code metrics analysis for quality assessment",
        function=analyze_code_metrics,
        priority=45,  # After changelog (20), tags (30), before research (40)
    ))


def setup_extension():
    """Initialize the extension during app startup."""
    hooks().add_action("gitchatbot.register_tools", register_metrics_tools)
```

Register in your app startup:

```python
# In your app initialization
from my_extension.tools import setup_extension

setup_extension()
```

## Default Tools

GitChatbot includes these default extensible tools:

| Tool | Priority | Description |
|------|----------|-------------|
| `create_test_plan_report` | 10 | Test plan generation |
| `create_changelog_report` | 20 | Changelog generation |
| `list_recent_tags` | 30 | Git tags listing |
| `research_codebase_subagent` | 40 | Code research with Claude |

## Tips and Best Practices

### 1. Use Appropriate Priority

Choose priority to position your tool logically:

```python
# Place after changelog but before research
priority=35

# Place at the end
priority=100
```

### 2. Write Clear Docstrings

The docstring becomes the AI's understanding of when to use the tool:

```python
async def my_tool(ctx: RunContext[PersistentAgentDeps], param: str) -> str:
    """
    Analyze security implications of code changes.

    Use this tool when the user asks about security, vulnerabilities,
    or potential risks in their code changes.

    Args:
        param: Specific area to focus on (e.g., "authentication", "input_validation")

    Returns:
        Security analysis report with recommendations
    """
```

### 3. Handle Errors Gracefully

Return helpful error messages instead of raising exceptions:

```python
async def my_tool(ctx: RunContext[PersistentAgentDeps]) -> str:
    try:
        result = await do_analysis()
        return f"Analysis complete: {result}"
    except SomeError as e:
        return f"Analysis failed: {str(e)}. Please check the configuration."
```

### 4. Validate Context Early

Check for required context before doing work:

```python
async def my_tool(ctx: RunContext[PersistentAgentDeps]) -> str:
    context = ctx.deps.load_context()

    if not context.pull_request_id:
        return "This tool requires a PR context. Use update_context with a PR ID first."

    # Continue with analysis...
```

## Next Steps

- [Hook System Overview](index.md)
- [Configuration Reference](../config-yaml.md)
- [Prompts Configuration](../prompts-yaml.md)
