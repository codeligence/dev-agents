"""Code Research Agent for test plan generation.

This agent provides file search and content analysis capabilities
for both UI and API test plan agents.

Tool registration is extensible via the hook system:

- Action ``code_research.register_tools`` (signature: ``list[ToolRegistration]``)
  fires before agent construction so external code can append additional tools.
- Filter ``code_research.tool_registrations`` (signature:
  ``list[ToolRegistration] -> list[ToolRegistration]``) runs after the action,
  allowing callers to remove or reorder tools (including the built-in defaults).
"""

from pathlib import Path
from typing import Any

from pydantic_ai import Agent as PydanticAgent
from pydantic_ai import RunContext
from pydantic_ai.toolsets.function import FunctionToolset

from core.agents.context import get_current_agent_execution_context
from core.agents.models import ToolRegistration
from core.exceptions import GitFileNotFoundError, GitOperationError
from core.hooks import hooks
from core.log import get_logger
from integrations.git.utils import (
    git_glob_files,
    git_grep_search,
    git_list_directory,
    git_read_file,
)

from .models import CodeResearchDependencies

logger = get_logger(logger_name="CodeResearchAgent", level="DEBUG")


async def ai_grep_search(
    ctx: RunContext[CodeResearchDependencies],
    pattern: str,
    path: str | None = None,
    glob_filter: str | None = None,
    context_lines: int = 0,
) -> str:
    """
    Search file contents using regex pattern in the git branch.

    Pattern supports inline flags: (?i) case-insensitive, (?s) dotall, (?m) multiline. Combined: (?ims)pattern.
    Example: "(?i)TODO" for case-insensitive, "(?s)def.*return" for cross-line match.

    Args:
        pattern: Regex pattern with optional inline flags (e.g., "(?i)pattern")
        path: Optional exact directory or file to search in (relative to repo root)
        glob_filter: Optional glob pattern to filter files (e.g., "*.py", "*.ts")
        context_lines: Number of lines to show before/after each match (0-5)

    Returns:
        Matching lines with file paths and line numbers
    """
    if not pattern:
        logger.warning("ai_grep_search: No pattern provided")
        return "No pattern provided for search"

    try:
        await get_current_agent_execution_context().send_status(
            f"Searching for '{pattern}'..."
        )
        result = git_grep_search(
            repo_path=Path(ctx.deps.repo_path),
            git_ref=ctx.deps.git_ref,
            pattern=pattern,
            path=path,
            glob_filter=glob_filter,
            context_lines=context_lines,
        )

        if result.total_lines == 0:
            return f"No matches found for pattern '{pattern}'"

        formatted_results = [f"Found {result.total_lines} matches:\n\n"]
        formatted_results.extend(result.matches)
        if result.truncated:
            formatted_results.append(
                f"... (truncated, showing {len(result.matches)} of "
                f"{result.total_lines} lines)"
            )

        output = "\n".join(formatted_results)
        logger.debug(f"ai_grep_search result:\n{output}")
        return output

    except (GitOperationError, ValueError) as e:
        logger.error(f"ai_grep_search error: {type(e).__name__}: {e}")
        return f"Error searching files: {e}"


async def ai_glob_files(
    ctx: RunContext[CodeResearchDependencies],
    pattern: str,
    path: str | None = None,
) -> str:
    """
    Find files matching a glob pattern in the git branch.

    Args:
        pattern: Glob pattern (e.g., "**/*.py", "src/*.ts", "test_*.py")
        path: Optional directory to search in (relative to repo root)

    Returns:
        List of matching file paths, one per line
    """
    if not pattern:
        logger.warning("ai_glob_files: No pattern provided")
        return "No pattern provided for file search"

    try:
        await get_current_agent_execution_context().send_status(
            f"Finding files matching '{pattern}'..."
        )
        result = git_glob_files(
            repo_path=Path(ctx.deps.repo_path),
            git_ref=ctx.deps.git_ref,
            pattern=pattern,
            path=path,
        )

        if result.total_found == 0:
            return f"No files found matching pattern '{pattern}'"

        output_lines = result.files.copy()
        if result.truncated:
            output_lines.append(
                f"... (showing first {len(result.files)} of "
                f"{result.total_found} results)"
            )

        output = "\n".join(output_lines)
        logger.debug(f"ai_glob_files result:\n{output}")
        return output

    except (GitOperationError, ValueError) as e:
        logger.error(f"ai_glob_files error: {type(e).__name__}: {e}")
        return f"Error searching files: {e}"


async def ai_list_directory(
    ctx: RunContext[CodeResearchDependencies],
    path: str = "",
    ignore: list[str] | None = None,
) -> str:
    """
    List files and directories in a given path within the git branch.

    Args:
        path: Path to the directory to list (relative to repo root, empty for root)
        ignore: List of glob patterns to ignore (e.g., ["*.pyc", "__pycache__"])

    Returns:
        List of entries with type indicators (trailing / for directories)
    """
    logger.debug(f"ai_list_directory called with path={path!r}, ignore={ignore!r}")
    try:
        await get_current_agent_execution_context().send_status(
            f"Listing directory '{path or '.'}'..."
        )
        result = git_list_directory(
            repo_path=Path(ctx.deps.repo_path),
            git_ref=ctx.deps.git_ref,
            path=path,
            ignore=ignore,
        )

        if not result.directories and not result.files:
            return f"Directory '{path or '.'}' is empty or does not exist"

        max_entries = 25
        entries = result.directories + result.files
        total = len(entries)
        output_lines = entries[:max_entries]
        if total > max_entries:
            output_lines.append(f"[...truncated, showing {max_entries} / {total}]")

        output = "\n".join(output_lines)
        logger.debug(f"ai_list_directory result:\n{output}")
        return output

    except GitOperationError as e:
        logger.error(f"ai_list_directory error: {type(e).__name__}: {e}")
        return f"Error listing directory: {e}"


async def ai_read_file(
    ctx: RunContext[CodeResearchDependencies],
    file_path: str,
    offset: int | None = None,
    limit: int | None = None,
) -> str:
    """
    Read file contents with line numbers from the git branch.

    Args:
        file_path: Path to the file to read (relative to repo root)
        offset: Line number to start reading from (1-indexed)
        limit: Maximum number of lines to read

    Returns:
        File contents with line numbers in cat -n format
    """
    try:
        await get_current_agent_execution_context().send_status(
            f"Reading {file_path}..."
        )
        result = git_read_file(
            repo_path=Path(ctx.deps.repo_path),
            git_ref=ctx.deps.git_ref,
            file_path=file_path,
            offset=offset,
            limit=limit,
            max_lines=ctx.deps.max_lines,
        )

        output = result.content
        if result.truncated:
            remaining = result.total_lines - result.end_line
            output += f"\n... ({remaining} more lines)"

        lines = output.split("\n")
        log_preview = "\n".join(lines[:5]) + (
            f"\n... ({len(lines) - 5} more)" if len(lines) > 5 else ""
        )
        logger.debug(f"ai_read_file result:\n{log_preview}")
        return output

    except GitFileNotFoundError as e:
        logger.warning(f"ai_read_file: {e}")
        return f"Could not read file {file_path}: File not found"
    except GitOperationError as e:
        logger.error(f"ai_read_file error: {type(e).__name__}: {e}")
        return f"Error reading file {file_path}: {e}"


def _get_default_tool_registrations() -> list[ToolRegistration]:
    """Return the built-in tool registrations for the code research agent."""
    return [
        ToolRegistration(
            name="ai_grep_search",
            description="Search file contents using a regex pattern in the git branch.",
            function=ai_grep_search,
            priority=10,
        ),
        ToolRegistration(
            name="ai_glob_files",
            description="Find files matching a glob pattern in the git branch.",
            function=ai_glob_files,
            priority=20,
        ),
        ToolRegistration(
            name="ai_list_directory",
            description="List files and directories within the git branch.",
            function=ai_list_directory,
            priority=30,
        ),
        ToolRegistration(
            name="ai_read_file",
            description="Read file contents with line numbers from the git branch.",
            function=ai_read_file,
            priority=40,
        ),
    ]


def create_code_research_subagent(
    model: str, system_prompt: str, num_retries: int = 3, output_type: type[Any] = str
) -> PydanticAgent[CodeResearchDependencies, Any]:
    """Create a code research agent configured for file analysis tasks.

    Tool registration is extensible via two hooks:

    - Action ``code_research.register_tools`` receives the mutable list of
      ``ToolRegistration`` objects so external code can append additional tools.
    - Filter ``code_research.tool_registrations`` then runs on the resulting list,
      enabling callers to remove or reorder tools (including the built-in defaults).

    Args:
        model: LLM model to use (e.g., 'openai:gpt-4o-mini')
        system_prompt: System prompt for the agent
        num_retries: Number of retries for failed requests (default: 3)
        output_type: Return type for the agent (default: str)

    Returns:
        Configured PydanticAI agent for code research
    """
    registrations = _get_default_tool_registrations()

    hooks().do_action("code_research.register_tools", registrations)

    registrations = hooks().apply_filters(
        "code_research.tool_registrations", registrations
    )

    sorted_registrations = sorted(registrations, key=lambda r: r.priority)

    toolset = FunctionToolset[CodeResearchDependencies]()
    for reg in sorted_registrations:
        toolset.add_function(reg.function, name=reg.name)

    logger.info(
        f"Registered {len(sorted_registrations)} code research tools: "
        f"{[reg.name for reg in sorted_registrations]}"
    )

    return PydanticAgent(
        model=model,
        deps_type=CodeResearchDependencies,
        output_type=output_type,
        instructions=system_prompt,
        retries=num_retries,
        toolsets=[toolset],
    )
