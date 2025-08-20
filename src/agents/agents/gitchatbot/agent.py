from typing import Union

from pydantic_ai import Agent as PydanticAgent, RunContext
from pydantic_ai.tools import ToolDefinition

from agents.agents.gitchatbot.config import GitChatbotAgentConfig
from agents.agents.gitchatbot.models import ChatbotContext, PersistentAgentDeps
from agents.agents.gitchatbot.prompts import GitChatbotAgentPrompts
from agents.subagents.impact_analysis.impact_analysis_subagent import ImpactAnalysisSubagent
from core.exceptions import AgentGracefulExit
from core.protocols.agent_protocols import AgentExecutionContext
from core.storage import get_storage

from core.agents.base import PydanticAIAgent
from entrypoints.slack_models.agent_context import SlackAgentContext
from integrations.git.git_repository import GitRepository

AGENT_NAME = "gitchatbot"

class GitChatbotAgent(PydanticAIAgent):
    """Chatbot agent that responds to user messages using AI and subagents.
    """

    def __init__(self, context: AgentExecutionContext) -> None:
        super().__init__(context)

        # Get configuration from context
        base_config = context.get_config()
        self.config = GitChatbotAgentConfig(base_config)

        # Get prompts
        base_prompts = context.get_prompts()
        self.prompts = GitChatbotAgentPrompts(base_prompts)

        # Set up the PydanticAI agent
        self.setup_agent()

    def get_dependencies(self) -> PersistentAgentDeps:
        """Get persistent dependencies for the chatbot agent.

        Creates a PersistentAgentDeps instance with storage and execution context.

        Returns:
            PersistentAgentDeps with storage and execution_id configured
        """
        # Get global storage instance
        storage = get_storage(self.context.get_config())

        # Get execution ID from context
        execution_id = self.context.get_execution_id()

        # Create persistent dependencies
        deps = PersistentAgentDeps(
            execution_id=execution_id,
            storage=storage
        )

        # Load existing context to make it available
        deps.context = deps.load_context()

        return deps

    def setup_agent(self) -> None:
        """Set up the PydanticAI agent instance."""
        self.agent = PydanticAgent(
            model=self.config.get_model(),
            deps_type=PersistentAgentDeps,
            output_type=str,
            instructions=self.prompts.get_chatbot_prompt()
        )

        async def bot_not_mentioned(ctx: RunContext[PersistentAgentDeps], tool_def: ToolDefinition) -> Union[
            ToolDefinition, None]:
            # Only enable skip_reply tool if bot is NOT mentioned in Slack contexts - this allows the bot to reply without mentions
            if isinstance(self.context, SlackAgentContext) and not self.context.is_bot_mentioned():
                return tool_def
            return None

        @self.agent.tool(prepare=bot_not_mentioned)
        async def skip_reply(ctx: RunContext[PersistentAgentDeps], reason: str) -> str:
            """
            Call this function if the message is not directed at the chatbot agent.

            This will gracefully exit the conversation processing.

            Returns:
                Instruction for further processing
            """
            self.logger.info(f"skip_reply tool called - raising AgentGracefulExit. Reason: {reason}")
            raise AgentGracefulExit("Conversation ended gracefully via skip_reply tool")

        @self.agent.tool
        async def update_context(ctx: RunContext[PersistentAgentDeps], context: ChatbotContext) -> str:
            """
            Update the conversation context with issue, PR, branch, or commit information. Set all available values at once

            Args:
                context: ChatbotContext instance with optional context fields

            Returns:
                Confirmation message about context update
            """
            self.logger.info(f"update_context tool called with: issue_id={context.issue_id}, "
                             f"pull_request_id={context.pull_request_id}, "
                             f"source_branch_name={context.source_branch_name}, "
                             f"target_branch_name={context.target_branch_name}, "
                             f"source_commit_hash={context.source_commit_hash}, "
                             f"target_commit_hash={context.target_commit_hash}")

            ctx.deps.save_context(context)

            # Log the updated context
            self.logger.info(f"Context updated and saved. Current context: "
                             f"issue_id={context.issue_id}, "
                             f"pull_request_id={context.pull_request_id}, "
                             f"source_branch_name={context.source_branch_name}, "
                             f"target_branch_name={context.target_branch_name}, "
                             f"source_commit_hash={context.source_commit_hash}, "
                             f"target_commit_hash={context.target_commit_hash}")

            # Create a summary of what was updated
            updated_fields = []
            if context.issue_id:
                updated_fields.append(f"issue_id: {context.issue_id}")
            if context.pull_request_id:
                updated_fields.append(f"pull_request_id: {context.pull_request_id}")
            if context.source_branch_name:
                updated_fields.append(f"source_branch_name: {context.source_branch_name}")
            if context.target_branch_name:
                updated_fields.append(f"target_branch_name: {context.target_branch_name}")
            if context.source_commit_hash:
                updated_fields.append(f"source_commit_hash: {context.source_commit_hash}")
            if context.target_commit_hash:
                updated_fields.append(f"target_commit_hash: {context.target_commit_hash}")

            if updated_fields:
                return f"Context updated successfully with: {', '.join(updated_fields)}. The context has been persisted and will be available for other tools."
            else:
                return "Context update called but no fields were provided. Current context remains unchanged."

        @self.agent.tool
        async def create_touched_files_summary(ctx: RunContext[PersistentAgentDeps]) -> str:
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

            if not any([current_context.pull_request_id, current_context.source_commit_hash,
                        current_context.target_commit_hash]):
                return "No pull request or commit information available in context. Please use update_context tool first to provide PR or commit details."

            context_info = []
            if current_context.pull_request_id:
                context_info.append(f"PR: {current_context.pull_request_id}")
            if current_context.source_commit_hash:
                context_info.append(f"Source commit: {current_context.source_commit_hash}")
            if current_context.target_commit_hash:
                context_info.append(f"Target commit: {current_context.target_commit_hash}")

            return f"Tool called successfully with context: {', '.join(context_info)}. File analysis implementation will follow."

        @self.agent.tool
        async def create_impact_analysis_report(ctx: RunContext[PersistentAgentDeps]) -> str:
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
                if not any([current_context.pull_request_id,
                            current_context.source_branch_name and current_context.target_branch_name]):
                    return "No pull request or branch information available in context. Please use update_context tool first to provide PR ID or branch names."

                # Create GitRepository instance
                git_repo = GitRepository(
                    base_config=self.context.get_config()
                )

                # Build GitDiffContext based on available information
                git_diff_context = None

                if current_context.pull_request_id:
                    # Use PR-based diff loading (most complete context)
                    self.logger.info(f"Loading diff for PR #{current_context.pull_request_id}")
                    git_diff_context = await git_repo.get_diff_from_pr(
                        current_context.pull_request_id,
                        current_context.issue_id  # Optional work item context
                    )
                elif current_context.source_branch_name and current_context.target_branch_name:
                    # Use branch comparison
                    context_description = f"Branch comparison: {current_context.source_branch_name} -> {current_context.target_branch_name}"
                    self.logger.info(f"Loading diff for {context_description}")
                    git_diff_context = git_repo.get_diff_from_branches(
                        current_context.source_branch_name,
                        current_context.target_branch_name,
                        context_description
                    )

                if not git_diff_context:
                    return "Unable to build diff context from available information."

                # Create ImpactAnalysisSubagent
                subagent = ImpactAnalysisSubagent(
                    context=self.context,
                    base_config=self.context.get_config(),
                    base_prompts=self.context.get_prompts(),
                )

                # Run impact analysis
                self.logger.info("Starting impact analysis...")
                result = await subagent.run(git_diff_context)

                # Log the results
                self.logger.info(f"Impact analysis completed:\n{result.summary()}")

                return "Impact analysis completed successfully. You can provide the requested impact analysis to the user now. Provide a compact summary of the impact and what should be retested. Result:\n" + result.summary()

            except Exception as e:
                self.logger.error(f"Error during impact analysis: {e}")
                return f"Impact analysis failed: {str(e)}"

