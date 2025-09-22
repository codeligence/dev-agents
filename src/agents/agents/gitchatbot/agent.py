# Copyright (C) 2025 Codeligence
#
# This file is part of Dev Agents.
#
# Dev Agents is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Dev Agents is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Dev Agents.  If not, see <https://www.gnu.org/licenses/>.


from pydantic_ai import Agent as PydanticAgent
from pydantic_ai import RunContext
from pydantic_ai.tools import ToolDefinition

from agents.agents.gitchatbot.config import GitChatbotAgentConfig
from agents.agents.gitchatbot.models import ChatbotContext, PersistentAgentDeps
from agents.agents.gitchatbot.prompts import GitChatbotAgentPrompts
from agents.subagents.changelog import ChangelogSubagent
from agents.subagents.impact_analysis.impact_analysis_subagent import (
    ImpactAnalysisSubagent,
)
from core.agents.base import PydanticAIAgent
from core.agents.context import (
    get_current_agent_execution_context,
    get_current_config,
    get_current_prompts,
)
from core.exceptions import AgentGracefulExit
from core.storage import get_storage
from entrypoints.slack_entrypoint.agent_context import SlackAgentContext
from integrations.git.git_repository import GitRepository

AGENT_NAME = "gitchatbot"


class GitChatbotAgent(PydanticAIAgent):
    """Chatbot agent that responds to user messages using AI and subagents."""

    def __init__(self) -> None:
        super().__init__()

        # Get configuration from context-local access
        base_config = get_current_config()
        self.config = GitChatbotAgentConfig(base_config)

        # Get prompts
        base_prompts = get_current_prompts()
        self.prompts = GitChatbotAgentPrompts(base_prompts)

        # Setup project loader for PR/Issue loading with caching
        self.project_config = base_config.get_default_project_config()
        self.project_loader = (
            get_current_agent_execution_context().get_context_integration_loader()
        )

        # Set up the PydanticAI agent
        self.setup_agent()

    def get_dependencies(self) -> PersistentAgentDeps:
        """Get persistent dependencies for the chatbot agent.

        Creates a PersistentAgentDeps instance with storage and execution context.

        Returns:
            PersistentAgentDeps with storage and execution_id configured
        """
        # Get global storage instance
        storage = get_storage(get_current_config())

        # Get execution ID from context
        execution_id = get_current_agent_execution_context().get_execution_id()

        # Create persistent dependencies
        deps = PersistentAgentDeps(execution_id=execution_id, storage=storage)

        # Load existing context to make it available
        deps.context = deps.load_context()

        return deps

    def setup_agent(self) -> None:
        """Set up the PydanticAI agent instance."""
        self.logger.info(f"Setting up agent with model {self.config.get_model()}")
        self.agent = PydanticAgent(
            model=self.config.get_model(),
            deps_type=PersistentAgentDeps,
            output_type=str,
            instructions=self.prompts.get_chatbot_prompt(),
        )

        async def bot_not_mentioned(
            _ctx: RunContext[PersistentAgentDeps], tool_def: ToolDefinition
        ) -> ToolDefinition | None:
            # Only enable skip_reply tool if bot is NOT mentioned in Slack contexts - this allows the bot to reply without mentions
            context = get_current_agent_execution_context()
            if (
                isinstance(context, SlackAgentContext)
                and not context.is_bot_mentioned()
            ):
                return tool_def
            return None

        @self.agent.tool(prepare=bot_not_mentioned)
        async def skip_reply(_ctx: RunContext[PersistentAgentDeps], reason: str) -> str:
            """
            Call this function if the message is not directed at the chatbot agent.

            This will gracefully exit the conversation processing.

            Returns:
                Instruction for further processing
            """
            self.logger.info(
                f"skip_reply tool called - raising AgentGracefulExit. Reason: {reason}"
            )
            raise AgentGracefulExit("Conversation ended gracefully via skip_reply tool")

        @self.agent.tool
        async def update_context(
            ctx: RunContext[PersistentAgentDeps], context: ChatbotContext
        ) -> str:
            """
            Update the conversation context with issue, PR, branch, or commit information. Set all available values at once

            When setting git refs:
            - source ref is the one with new changes, i.e. feature branch or a recent tag
            - target ref is the one that does not have the changes yet, i.e. main branch or old tagGene

            Args:
                context: ChatbotContext instance with optional context fields

            Returns:
                Confirmation message about context update
            """
            self.logger.info(
                f"update_context tool called with: issue_id={context.issue_id}, "
                f"pull_request_id={context.pull_request_id}, "
                f"source_git_ref={context.source_git_ref}, "
                f"target_git_ref={context.target_git_ref}"
            )

            ctx.deps.save_context(context)

            # Log the updated context
            self.logger.info(
                f"Context updated and saved. Current context: "
                f"issue_id={context.issue_id}, "
                f"pull_request_id={context.pull_request_id}, "
                f"source_git_ref={context.source_git_ref}, "
                f"target_git_ref={context.target_git_ref}"
            )

            # Create a summary of what was updated
            updated_fields = []
            if context.issue_id:
                updated_fields.append(f"issue_id: {context.issue_id}")
            if context.pull_request_id:
                updated_fields.append(f"pull_request_id: {context.pull_request_id}")
            if context.source_git_ref:
                updated_fields.append(f"source_git_ref: {context.source_git_ref}")
            if context.target_git_ref:
                updated_fields.append(f"target_git_ref: {context.target_git_ref}")

            # Fetch additional context from project loader
            additional_context_parts = []

            # Load pull request context if PR ID is provided
            if context.pull_request_id:
                try:
                    pr_model = await self.project_loader.load_pullrequest(
                        str(context.pull_request_id)
                    )
                    additional_context_parts.append(
                        f"Pull Request #{context.pull_request_id}: {pr_model.context}"
                    )
                except Exception as e:
                    self.logger.warning(
                        f"Could not load pull request #{context.pull_request_id}: {e}"
                    )

            # Load issue context if issue ID is provided
            if context.issue_id:
                try:
                    issue_model = await self.project_loader.load_issue(
                        str(context.issue_id)
                    )
                    additional_context_parts.append(
                        f"Issue #{context.issue_id}: {issue_model.context}"
                    )
                except Exception as e:
                    import traceback

                    self.logger.warning(
                        f"Could not load issue #{context.issue_id}: {e}\nFull traceback:\n{traceback.format_exc()}"
                    )

            # Build the response message
            if updated_fields:
                base_message = f"Context updated successfully with: {', '.join(updated_fields)}. The context has been persisted and will be available for other tools."
            else:
                base_message = "Context update called but no fields were provided. Current context remains unchanged."

            # Append additional context if any was loaded
            if additional_context_parts:
                base_message += "\n\nAdditional context loaded:\n" + "\n".join(
                    additional_context_parts
                )

            return base_message

        @self.agent.tool
        async def create_touched_files_summary(
            ctx: RunContext[PersistentAgentDeps],
        ) -> str:
            """
            Generate file change summaries for pull requests or commits.

            This tool analyzes changed files and creates summaries of their modifications.

            Returns:
                Summary information about touched files
            """
            await self.send_toolcall_message(ctx, "👋🚀")
            self.logger.info("create_touched_files_summary tool called")

            # Access current context from persistent storage
            current_context = ctx.deps.load_context()

            if not any(
                [
                    current_context.pull_request_id,
                    current_context.source_git_ref,
                    current_context.target_git_ref,
                ]
            ):
                return "No pull request or git reference information available in context. Please use update_context tool first to provide PR or git ref details."

            context_info = []
            if current_context.pull_request_id:
                context_info.append(f"PR: {current_context.pull_request_id}")
            if current_context.source_git_ref:
                context_info.append(f"Source ref: {current_context.source_git_ref}")
            if current_context.target_git_ref:
                context_info.append(f"Target ref: {current_context.target_git_ref}")

            return f"Tool called successfully with context: {', '.join(context_info)}. File analysis implementation will follow."

        @self.agent.tool
        async def create_impact_analysis_report(
            ctx: RunContext[PersistentAgentDeps],
        ) -> str:
            """
            Generate comprehensive impact analysis for code changes.

            This tool creates impact analysis based on file changes.

            Returns:
                Confirmation message that analysis was completed and logged
            """
            await self.send_toolcall_message(ctx, "👋🚀")
            self.logger.info("create_impact_analysis_report tool called")

            try:
                # Access current context from persistent storage
                current_context = ctx.deps.load_context()

                # Validate we have required context information
                if not any(
                    [
                        current_context.pull_request_id,
                        current_context.source_git_ref
                        and current_context.target_git_ref,
                    ]
                ):
                    return "No pull request or git reference information available in context. Please use update_context tool first to provide PR ID or git refs."

                # Create GitRepository instance
                git_repo = GitRepository(project_config=self.project_config)

                # Build GitDiffContext based on available information
                git_diff_context = None
                context_description = None

                if current_context.pull_request_id:
                    # Use PR-based diff loading via ContextIntegrationLoader (most complete context)
                    self.logger.info(
                        f"Loading diff for PR #{current_context.pull_request_id}"
                    )

                    # Get branch information from PR using ContextIntegrationLoader
                    (
                        source_branch,
                        target_branch,
                    ) = await self.project_loader.get_branches_from_pr(
                        current_context.pull_request_id
                    )

                    # Build context description
                    context_description = (
                        f"Pull Request #{current_context.pull_request_id}"
                    )

                    # Add issue context if available
                    if current_context.issue_id:
                        try:
                            issue_model = await self.project_loader.load_issue(
                                str(current_context.issue_id)
                            )
                            issue_title = f"Issue #{current_context.issue_id}"
                            context_description = (
                                f"Pull Request #{current_context.pull_request_id} - {issue_title}\n\n"
                                + issue_model.context
                            )
                        except Exception as e:
                            self.logger.warning(
                                f"Could not load issue #{current_context.issue_id}: {e}"
                            )

                    # Get git diff using branches
                    git_diff_context = git_repo.get_diff_from_branches(
                        source_branch,
                        target_branch,
                        context_description,
                        include_patch=True,
                    )

                elif current_context.source_git_ref and current_context.target_git_ref:
                    # Use direct git ref comparison
                    context_description = f"Git ref comparison: {current_context.source_git_ref} -> {current_context.target_git_ref}"
                    self.logger.info(f"Loading diff for {context_description}")
                    git_diff_context = git_repo.get_diff_from_branches(
                        current_context.source_git_ref,
                        current_context.target_git_ref,
                        context_description,
                        include_patch=True,
                    )

                if not git_diff_context:
                    return "Unable to build diff context from available information."

                # Create ImpactAnalysisSubagent
                subagent = ImpactAnalysisSubagent()

                # Run impact analysis
                self.logger.info("Starting impact analysis...")
                result = await subagent.run(git_diff_context)

                # Log the results
                self.logger.info(f"Impact analysis completed:\n{result.summary()}")

                return (
                    "Impact analysis completed successfully. You can provide the requested impact analysis to the user now. Provide a compact summary of the impact and what should be retested. Result:\n"
                    + result.summary()
                )

            except Exception as e:
                self.logger.error(f"Error during impact analysis: {e}", exc_info=True)
                return f"Impact analysis failed: {str(e)}"

        @self.agent.tool
        async def create_changelog_report(
            ctx: RunContext[PersistentAgentDeps],
            user_instructions: str = "",
        ) -> str:
            """
            Generate automated changelog from code changes.

            Creates a structured changelog with Fixed/Changed/Added/Removed sections
            based on file changes, commit history, and related issue context.

            Args:
                user_instructions: Optional user-specific instructions for changelog generation

            Returns:
                Formatted changelog ready for release notes
            """
            await self.send_toolcall_message(ctx, "📝🚀")
            self.logger.info("create_changelog_report tool called")

            try:
                # Access current context from persistent storage
                current_context = ctx.deps.load_context()

                # Validate we have required context information
                if not any(
                    [
                        current_context.pull_request_id,
                        current_context.source_git_ref
                        and current_context.target_git_ref,
                    ]
                ):
                    return "No pull request or git reference information available in context. Please use update_context tool first to provide PR ID or git refs."

                # Create GitRepository instance
                git_repo = GitRepository(project_config=self.project_config)

                # Build GitDiffContext based on available information
                git_diff_context = None
                context_description = None

                if current_context.pull_request_id:
                    # Use PR-based diff loading via ContextIntegrationLoader (most complete context)
                    self.logger.info(
                        f"Loading diff for PR #{current_context.pull_request_id}"
                    )

                    # Get branch information from PR using ContextIntegrationLoader
                    (
                        source_branch,
                        target_branch,
                    ) = await self.project_loader.get_branches_from_pr(
                        current_context.pull_request_id
                    )

                    # Build context description
                    context_description = (
                        f"Pull Request #{current_context.pull_request_id}"
                    )

                    # Add issue context if available
                    if current_context.issue_id:
                        try:
                            issue_model = await self.project_loader.load_issue(
                                str(current_context.issue_id)
                            )
                            issue_title = f"Issue #{current_context.issue_id}"
                            context_description = (
                                f"Pull Request #{current_context.pull_request_id} - {issue_title}\n\n"
                                + issue_model.context
                            )
                        except Exception as e:
                            self.logger.warning(
                                f"Could not load issue #{current_context.issue_id}: {e}"
                            )

                    # Get git diff using branches
                    git_diff_context = git_repo.get_diff_from_branches(
                        source_branch,
                        target_branch,
                        context_description,
                        include_patch=True,
                    )

                elif current_context.source_git_ref and current_context.target_git_ref:
                    # Use direct git ref comparison
                    context_description = f"Git ref comparison: {current_context.source_git_ref} -> {current_context.target_git_ref}"
                    self.logger.info(f"Loading diff for {context_description}")
                    git_diff_context = git_repo.get_diff_from_branches(
                        current_context.source_git_ref,
                        current_context.target_git_ref,
                        context_description,
                        include_patch=True,
                    )

                if not git_diff_context:
                    return "Unable to build diff context from available information."

                # Create ChangelogSubagent
                subagent = ChangelogSubagent()

                # Run changelog generation
                self.logger.info("Starting changelog generation...")
                result = await subagent.generate_changelogs(
                    git_diff_context, user_instructions
                )

                # Summarize the changelog
                changelog_output = await subagent.summarize_changelog(
                    result, user_instructions
                )

                # Log the results
                self.logger.info(f"Changelog generation completed:\n{changelog_output}")
                await get_current_agent_execution_context().send_response(
                    f"{git_diff_context.source_branch} -> {git_diff_context.target_branch}\n\n{changelog_output}",
                )

                return (
                    "Changelog generated successfully. User has successfully received the changelog. Here is a copy for you:\n\n"
                    + changelog_output
                )

            except Exception as e:
                self.logger.error(
                    f"Error during changelog generation: {type(e).__name__}: {str(e)}",
                    exc_info=True,
                )
                self.logger.error(
                    f"Context details: user_instructions='{user_instructions}', current_context={getattr(current_context, '__dict__', 'Unknown')}"
                )
                self.logger.error(
                    f"Agent context type: {type(get_current_agent_execution_context())}"
                )
                return f"Changelog generation failed: {type(e).__name__}: {str(e)}"

        @self.agent.tool
        async def list_recent_tags(
            ctx: RunContext[PersistentAgentDeps], limit: int = 20
        ) -> str:
            """
            List the most recent git tags from the repository.

            Git tags sorted by version in ascending order (oldest first)

            Args:
                limit: Maximum number of tags to retrieve (defaults to 20, max 50)

            Returns:
                Formatted list of recent git tags to be used in the response for the user in ascending order (oldest first).
            """
            await self.send_toolcall_message(ctx, "👋🚀")
            self.logger.info(f"list_recent_tags tool called with limit={limit}")

            try:
                # Validate limit parameter
                if limit <= 0:
                    return "Invalid limit: must be greater than 0"
                if limit > 50:
                    limit = 50  # Cap at reasonable maximum

                # Create GitRepository instance
                git_repo = GitRepository(project_config=self.project_config)

                # Get latest tags
                tags = git_repo.get_latest_tags(limit=limit)

                if not tags:
                    return "No git tags found in the repository."

                # Format the response
                tag_list = []
                for i, tag in enumerate(tags, 1):
                    tag_list.append(f"{i:2d}. {tag}")

                response = f"Recent git tags (showing {len(tags)} of up to {limit}) for further processing:\n\n"
                response += "\n".join(tag_list)

                self.logger.info(f"Retrieved {len(tags)} git tags successfully")
                return response

            except Exception as e:
                self.logger.error(f"Error retrieving git tags: {e}", exc_info=True)
                return f"Failed to retrieve git tags: {str(e)}"
