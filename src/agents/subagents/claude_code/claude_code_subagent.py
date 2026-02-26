from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
    create_sdk_mcp_server,
    tool,
)
from claude_agent_sdk.types import SystemPromptPreset
from pydantic_ai.usage import RunUsage

from core.agents.context import get_current_agent_execution_context
from core.integrations.context_integration_loader import ContextIntegrationLoader
from core.log import get_logger

from .models import ClaudeCodeConfig

logger = get_logger(__name__)


class ClaudeCodeSubagent:
    """Subagent for interacting with Claude SDK to perform codebase research and analysis.

    This subagent provides a wrapper around the Claude Agent SDK, configured with
    read-only tools for safe codebase exploration and analysis.
    """

    def __init__(
        self,
        cli_path: str | None = None,
        context_loader: ContextIntegrationLoader | None = None,
    ):
        """Initialize Claude Code subagent.

        Args:
            cli_path: Optional path to Claude Code CLI. If not provided, uses config default.
            context_loader: Optional ContextIntegrationLoader for accessing project issues and PRs.
        """
        if cli_path is None:
            # Load from config
            from core.config import get_default_config

            base_config = get_default_config()
            claude_config = ClaudeCodeConfig(base_config)
            cli_path = claude_config.get_cli_path()

        self._cli_path = cli_path
        self._context_loader = context_loader

    def _create_project_tools(
        self, context_loader: ContextIntegrationLoader
    ) -> tuple[list[Any], list[str]]:
        """Create project-specific tools for Claude SDK based on available providers.

        Args:
            context_loader: ContextIntegrationLoader instance to access providers

        Returns:
            Tuple of (tools_list, tool_names_list) for MCP server creation
        """
        project_tools = []
        tool_names = []

        # Check if issue provider is available before creating tool
        if context_loader.get_issue_provider() is not None:

            @tool(
                "get_issue_info",
                "Get detailed information about an issue/work item",
                {"id": str},
            )
            async def get_issue_info(args: dict[str, Any]) -> dict[str, Any]:
                """Fetch issue information from the project management system."""
                try:
                    issue_id = args["id"]
                    logger.debug(f"Fetching issue #{issue_id}")
                    issue_model = await context_loader.load_issue(issue_id)
                    return {
                        "content": [
                            {
                                "type": "text",
                                "text": f"Issue #{issue_model.id}:\n\n{issue_model.context}",
                            }
                        ]
                    }
                except Exception as e:
                    logger.error(f"Error fetching issue #{args.get('id')}: {e}")
                    return {
                        "content": [
                            {
                                "type": "text",
                                "text": f"Error fetching issue: {str(e)}",
                            }
                        ]
                    }

            project_tools.append(get_issue_info)
            tool_names.append("mcp__project_tools__get_issue_info")
            logger.debug("Added get_issue_info tool (issue provider available)")

        # Check if PR provider is available before creating tool
        if context_loader.get_pullrequest_provider() is not None:

            @tool(
                "get_pullrequest_info",
                "Get detailed information about a pull request",
                {"id": str},
            )
            async def get_pullrequest_info(args: dict[str, Any]) -> dict[str, Any]:
                """Fetch pull request information from the project management system."""
                try:
                    pr_id = args["id"]
                    logger.debug(f"Fetching PR #{pr_id}")
                    pr_model = await context_loader.load_pullrequest(pr_id)

                    # Build PR info text
                    pr_info = [
                        f"Pull Request #{pr_model.id}:",
                        f"\nSource Branch: {pr_model.source_branch or 'N/A'}",
                        f"Target Branch: {pr_model.target_branch or 'N/A'}",
                        f"\n{pr_model.context}",
                    ]

                    return {"content": [{"type": "text", "text": "\n".join(pr_info)}]}
                except Exception as e:
                    logger.error(f"Error fetching PR #{args.get('id')}: {e}")
                    return {
                        "content": [
                            {
                                "type": "text",
                                "text": f"Error fetching pull request: {str(e)}",
                            }
                        ]
                    }

            project_tools.append(get_pullrequest_info)
            tool_names.append("mcp__project_tools__get_pullrequest_info")
            logger.debug("Added get_pullrequest_info tool (PR provider available)")

        return project_tools, tool_names

    async def query(
        self,
        formatted_query: str,
        repo_path: str,
    ) -> str:
        """Query Claude SDK to perform codebase research or analysis.

        Args:
            formatted_query: The formatted prompt/query to send to Claude SDK
            repo_path: The path to the repository to analyze

        Returns:
            The final summary report from Claude SDK
        """
        logger.debug(f"Querying Claude SDK for repository: {repo_path}")

        # Create custom tools if context_loader is available
        mcp_servers = {}
        allowed_tools = [
            # Git read-only tools
            "Bash(git log:*)",
            "Bash(git diff:*)",
            "Bash(git show:*)",
            # File reading and search tools
            "Read",
            "Grep",
            "Glob",
        ]
        # Configure Claude SDK with repository working directory and full read toolset
        disallowed_tools = [
            # Git mutation commands
            "Bash(git add:*)",
            "Bash(git rm:*)",
            "Bash(git mv:*)",
            "Bash(git commit:*)",
            "Bash(git push:*)",
            "Bash(git pull:*)",
            "Bash(git merge:*)",
            "Bash(git rebase:*)",
            "Bash(git reset:*)",
            "Bash(git checkout:*)",
            "Bash(git stash:*)",
            "Bash(git tag:*)",
            "Bash(git branch:*)",
            "Bash(git clean:*)",
            "Bash(git worktree:*)",
            "Bash(git gc:*)",
            # File modification tools
            "Write",
            "Edit",
        ]

        if self._context_loader is not None:
            # Create project-specific tools based on available providers
            project_tools, tool_names = self._create_project_tools(self._context_loader)

            # Only create MCP server if we have tools to add
            if project_tools:
                project_tools_server = create_sdk_mcp_server(
                    name="project-tools",
                    version="1.0.0",
                    tools=project_tools,
                )

                mcp_servers["project_tools"] = project_tools_server
                allowed_tools.extend(tool_names)
                logger.debug(
                    f"Added {len(project_tools)} project tool(s) to Claude SDK"
                )

        if mcp_servers:
            options = ClaudeAgentOptions(
                cwd=repo_path,
                cli_path=self._cli_path,
                system_prompt=SystemPromptPreset(type="preset", preset="claude_code"),
                mcp_servers=mcp_servers,  # type: ignore[arg-type]
                allowed_tools=allowed_tools,
                disallowed_tools=disallowed_tools,
            )
        else:
            options = ClaudeAgentOptions(
                cwd=repo_path,
                cli_path=self._cli_path,
                system_prompt=SystemPromptPreset(type="preset", preset="claude_code"),
                allowed_tools=allowed_tools,
                disallowed_tools=disallowed_tools,
            )

        # Use Claude SDK to perform the analysis
        summary_report = ""
        async with ClaudeSDKClient(options=options) as client:
            await client.query(formatted_query)

            last_result = ""
            step_num = 1

            # Stream the response and capture steps
            async for msg in client.receive_response():
                if isinstance(msg, AssistantMessage):
                    for block in msg.content:
                        if isinstance(block, TextBlock):
                            step_text = block.text.strip()
                            # Log intermediate steps at debug level
                            if step_text:
                                logger.debug(
                                    f"Claude SDK step {step_num}: {step_text[:200]}..."
                                )
                                # Send status update to agent context
                                await get_current_agent_execution_context().send_status(
                                    step_text[:200]
                                )
                                last_result = step_text
                                step_num += 1
                elif isinstance(msg, ResultMessage):
                    logger.info("Claude SDK Usage Statistics:")
                    logger.info(f"  Duration (ms): {msg.duration_ms}")
                    logger.info(f"  API Duration (ms): {msg.duration_api_ms}")
                    logger.info(f"  Number of Turns: {msg.num_turns}")
                    if msg.total_cost_usd is not None:
                        logger.info(f"  Total Cost (USD): ${msg.total_cost_usd:.6f}")
                    if msg.usage is not None:
                        logger.info("  Token Usage:")
                        for key, value in msg.usage.items():
                            logger.info(f"    {key}: {value}")

                        # Track usage with agent execution context
                        run_usage = RunUsage(
                            input_tokens=msg.usage.get("input_tokens", 0),
                            output_tokens=msg.usage.get("output_tokens", 0),
                            cache_write_tokens=msg.usage.get(
                                "cache_creation_input_tokens", 0
                            ),
                            cache_read_tokens=msg.usage.get(
                                "cache_read_input_tokens", 0
                            ),
                            requests=msg.num_turns,
                        )
                        get_current_agent_execution_context().track_usage(
                            "claude", run_usage
                        )

            summary_report = last_result

        logger.debug("Claude SDK analysis completed")

        return summary_report
