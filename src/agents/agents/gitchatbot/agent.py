from typing import cast

from pydantic_ai import Agent as PydanticAgent
from pydantic_ai import RunContext
from pydantic_ai.tools import ToolDefinition
from pydantic_ai.toolsets.function import FunctionToolset

from agents.agents.gitchatbot.config import GitChatbotAgentConfig
from agents.agents.gitchatbot.models import ChatbotContext, PersistentAgentDeps
from agents.agents.gitchatbot.prompts import GitChatbotAgentPrompts
from core.agents.base import PydanticAIAgent
from core.agents.context import (
    get_current_agent_execution_context,
    get_current_config,
    get_current_prompts,
)
from core.agents.models import ToolRegistration
from core.exceptions import AgentGracefulExit, ConfigurationError
from core.hooks import hooks
from core.skills.context import SkillContext
from core.storage import get_storage
from core.usage import get_usage_storage
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
            Update the conversation context with issue, PR, branch, project, or commit information. Set all available values at once

            When setting git refs:
            - source ref is the one with new changes, i.e. feature branch or a recent tag
            - target ref is the one that does not have the changes yet, i.e. main branch or old tagGene

            Args:
                context: ChatbotContext instance with optional context fields including project selection

            Returns:
                Confirmation message about context update
            """
            self.logger.info(
                f"update_context tool called with: issue_id={context.issue_id}, "
                f"pull_request_id={context.pull_request_id}, "
                f"source_git_ref={context.source_git_ref}, "
                f"target_git_ref={context.target_git_ref}, "
                f"project={context.project}"
            )

            ctx.deps.save_context(context)

            # Log the updated context
            self.logger.info(
                f"Context updated and saved. Current context: "
                f"issue_id={context.issue_id}, "
                f"pull_request_id={context.pull_request_id}, "
                f"source_git_ref={context.source_git_ref}, "
                f"target_git_ref={context.target_git_ref}, "
                f"project={context.project}"
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
            if context.project:
                updated_fields.append(f"project: {context.project}")

            # Fetch additional context from project loader
            additional_context_parts: list[str] = []

            # Get project-specific loader - fail fast if project invalid
            sc = SkillContext(ctx)
            try:
                project_loader = sc.get_selected_project(context.project)
            except ConfigurationError as e:
                return str(e)

            # Load pull request context if PR ID is provided
            if context.pull_request_id:
                try:
                    pr_model = await project_loader.load_pullrequest(
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
                    issue_model = await project_loader.load_issue(str(context.issue_id))
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
                base_message += (
                    "\n\nAdditional context loaded for further use (no message has been sent to the user):\n"
                    + "\n".join(additional_context_parts)
                )

            return base_message

        @self.agent.tool
        async def load_artefact(
            ctx: RunContext[PersistentAgentDeps], artefact_id: str
        ) -> str:
            """
            Load a previously generated artifact by its ID.

            Retrieves artifacts (changelogs, test plans) that were generated earlier
            in this conversation. Artifact IDs are provided when artifacts are created.

            Args:
                artefact_id: Artifact identifier in format: type_issue_pr_source_target_timestamp
                             Example: changelog_1243_bugfix_1243_main_20251119130338

            Returns:
                The artifact content if found, error message otherwise
            """
            sc = SkillContext(ctx)
            await sc.send_toolcall_message("Loading artifact...")
            self.logger.info(
                f"load_artefact tool called with artifact_id={artefact_id}"
            )

            try:
                artifact = sc.load_artifact(
                    artifact_id=artefact_id,
                    execution_id=ctx.deps.execution_id,
                    storage=ctx.deps.storage,
                )

                if not artifact:
                    return f"Artifact '{artefact_id}' not found in this conversation."

                return f"# {artifact.title}\n\n{artifact.content}"

            except Exception as e:
                self.logger.error(
                    f"Error loading artifact {artefact_id}: {e}", exc_info=True
                )
                return f"Failed to load artifact: {str(e)}"

        @self.agent.tool
        async def list_artifacts(
            ctx: RunContext[PersistentAgentDeps],
        ) -> str:
            """
            List all artifact IDs available in this conversation.

            Returns:
                List of artifact IDs that can be loaded with load_artefact
            """
            sc = SkillContext(ctx)
            await sc.send_toolcall_message("Listing artifacts...")
            self.logger.info("list_artifacts tool called")

            try:
                current_context = ctx.deps.load_context()

                if not current_context.artifact_ids:
                    return "No artifacts available."

                return "\n".join(current_context.artifact_ids)

            except Exception as e:
                self.logger.error(f"Error listing artifacts: {e}", exc_info=True)
                return f"Failed to list artifacts: {str(e)}"

    def _is_claude_code_available(self) -> bool:
        """Check if Claude Code is available and configured.

        Returns True if both:
        1. The claude_agent_sdk package is installed
        2. The CLI path is configured (via config or CLAUDE_CODE_PATH env var)
        """
        try:
            # Check if SDK is installed
            import claude_agent_sdk  # noqa: F401

            # Check if configured
            from agents.subagents.claude_code import ClaudeCodeConfig

            claude_config = ClaudeCodeConfig(get_current_config())
            return claude_config.is_configured()
        except ImportError:
            return False

    def _get_default_tool_registrations(self) -> list[ToolRegistration]:
        """Get the default extensible tool registrations.

        These tools are registered dynamically via hooks and can be extended
        or filtered by external code. Skills register their tools via hooks
        (see ``core.skills`` and ``src/skills/``).

        Note: Only one code research tool is included based on Claude Code availability:
        - If Claude Code is configured: research_codebase_subagent (uses Claude Code)
        - Otherwise: code_research (uses internal analysis tools)

        Returns:
            List of ToolRegistration objects for the default extensible tools.
        """
        registrations: list[ToolRegistration] = [
            ToolRegistration(
                name="list_recent_tags",
                description=(
                    "List the most recent git tags from the repository. "
                    "Git tags sorted by version in ascending order (oldest first). "
                    "Args: limit (maximum number of tags to retrieve, defaults to 20, max 50). "
                    "Returns: Formatted list of recent git tags in ascending order (oldest first)."
                ),
                function=self._tool_list_recent_tags,
                priority=30,
            ),
        ]

        # Add code research tool based on Claude Code availability
        if self._is_claude_code_available():
            self.logger.info(
                "Claude Code is available - using research_codebase_subagent"
            )
            registrations.append(
                ToolRegistration(
                    name="research_codebase_subagent",
                    description=(
                        "Research the codebase using Claude Code subagent to answer specific questions or perform analysis. "
                        "Important: this tool does not have access to the conversation. "
                        "This tool executes an AI agent that has full access to the code repository. "
                        "You need to provide full context for this task. "
                        "Uses Claude Code with full read toolset (git tools, Read, Grep, Glob) to "
                        "investigate code changes, analyze patterns, or answer questions about the codebase. "
                        "The tool operates on the current context (PR or git refs from update_context). So call update_context first, even if you just set target=HEAD."
                        "Args: instructions (user-specific instructions describing what to research, can be extensive markdown). "
                        "Returns: Research results and analysis from Claude Code."
                    ),
                    function=self._tool_research_codebase_subagent,
                    priority=40,
                )
            )
        else:
            self.logger.info("Using internal code_research tool")
            registrations.append(
                ToolRegistration(
                    name="code_research",
                    description=(
                        "Research the codebase using internal code analysis tools to answer questions. "
                        "Uses git-aware search and file reading tools to investigate the codebase "
                        "and answer specific questions about the implementation. "
                        "The tool operates on the current context (PR or git refs from update_context). "
                        "If no context is set, it defaults to analyzing the current HEAD. "
                        "Args: instructions (full context and question to research, provide all details "
                        "needed as this tool does not have access to the conversation). "
                        "Returns: Research results and analysis from the code research agent."
                    ),
                    function=self._tool_code_research,
                    priority=40,
                )
            )

        # Add remaining inline tools
        registrations.append(
            ToolRegistration(
                name="get_token_usage",
                description=(
                    "Get token usage statistics for the specified number of days. "
                    "Args: days (number of days to retrieve, any positive number). "
                    "Returns: Formatted markdown report of token usage."
                ),
                function=self._tool_get_token_usage,
                priority=70,
            ),
        )

        return registrations

    async def _tool_list_recent_tags(
        self,
        ctx: RunContext[PersistentAgentDeps],
        limit: int = 20,
    ) -> str:
        """List the most recent git tags from the repository.

        Git tags sorted by version in ascending order (oldest first)

        Args:
            limit: Maximum number of tags to retrieve (defaults to 20, max 50)

        Returns:
            Formatted list of recent git tags in ascending order (oldest first).
        """
        sc = SkillContext(ctx)
        await sc.send_toolcall_message("Fetching tags...")
        self.logger.info(f"list_recent_tags tool called with limit={limit}")

        try:
            current_context = sc.deps.load_context()

            # Get project-specific loader
            try:
                project_loader = sc.get_selected_project(current_context.project)
            except ConfigurationError as e:
                return str(e)

            project_config = project_loader.get_project_config()

            # Validate limit parameter
            if limit <= 0:
                return "Invalid limit: must be greater than 0"
            if limit > 50:
                limit = 50  # Cap at reasonable maximum

            git_repo = GitRepository(project_config=project_config)
            tags = git_repo.get_latest_tags(limit=limit)

            if not tags:
                return "No git tags found in the repository."

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

    async def _tool_research_codebase_subagent(
        self,
        ctx: RunContext[PersistentAgentDeps],
        instructions: str,
    ) -> str:
        """Research the codebase using Claude Code subagent.

        Args:
            instructions: User-specific instructions describing what to research.

        Returns:
            Research results and analysis from Claude Code
        """
        sc = SkillContext(ctx)
        await sc.send_toolcall_message("Researching codebase...")
        self.logger.info("research_codebase tool called")

        try:
            current_context = sc.deps.load_context()

            try:
                project_loader = sc.get_selected_project(current_context.project)
            except ConfigurationError as e:
                self.logger.warning(f"Configuration error in research_codebase: {e}")
                return str(e)

            project_config = project_loader.get_project_config()
            git_repo = GitRepository(project_config=project_config)

            context_description = None
            source_branch = None
            target_branch = None

            if current_context.pull_request_id:
                self.logger.info(
                    f"Researching codebase for PR #{current_context.pull_request_id}"
                )

                (
                    source_branch,
                    target_branch,
                ) = await project_loader.get_branches_from_pr(
                    current_context.pull_request_id
                )

                context_description = f"Pull Request #{current_context.pull_request_id}"

                if current_context.issue_id:
                    try:
                        issue_model = await project_loader.load_issue(
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

            elif current_context.source_git_ref and current_context.target_git_ref:
                source_branch = current_context.source_git_ref
                target_branch = current_context.target_git_ref
                context_description = (
                    f"Git ref comparison: {source_branch} -> {target_branch}"
                )
                self.logger.info(f"Researching codebase for {context_description}")

            else:
                target_branch = current_context.target_git_ref or "HEAD"
                context_description = "General codebase exploration"
                self.logger.info("Researching codebase (general exploration)")

            git_analysis_instructions = ""
            if source_branch and target_branch:
                git_analysis_instructions = f'Analyze the code changes between git ref "{source_branch}" and "{target_branch}".'

            formatted_query = self.prompts.get_research_codebase_prompt().format(
                instructions=instructions,
                context_description=context_description,
                git_analysis_instructions=git_analysis_instructions,
            )

            from agents.subagents.claude_code import ClaudeCodeSubagent

            claude_subagent = ClaudeCodeSubagent(context_loader=project_loader)
            research_results = await claude_subagent.query(
                formatted_query=formatted_query,
                repo_path=str(git_repo.repo_path),
            )

            self.logger.info("Codebase research completed")

            return (
                "Codebase research completed successfully. Here are the results:\n\n"
                + research_results
            )

        except Exception as e:
            self.logger.error(
                f"Error during codebase research: {type(e).__name__}: {str(e)}",
                exc_info=True,
            )
            return f"Codebase research failed: {type(e).__name__}: {str(e)}"

    async def _tool_code_research(
        self,
        ctx: RunContext[PersistentAgentDeps],
        instructions: str,
    ) -> str:
        """Research the codebase using internal code analysis tools.

        Args:
            instructions: Full context and question to research.

        Returns:
            Research results and analysis from the code research agent
        """
        sc = SkillContext(ctx)
        await sc.send_toolcall_message("Checking code...")
        self.logger.info("code_research tool called")

        try:
            current_context = sc.deps.load_context()

            try:
                project_loader = sc.get_selected_project(current_context.project)
            except ConfigurationError as e:
                self.logger.warning(f"Configuration error in code_research: {e}")
                return str(e)

            project_config = project_loader.get_project_config()
            git_repo = GitRepository(project_config=project_config)

            # Determine git ref and context description
            if current_context.pull_request_id:
                source_branch, _ = await project_loader.get_branches_from_pr(
                    current_context.pull_request_id
                )
                context_description = f"Pull Request #{current_context.pull_request_id}"
            elif current_context.source_git_ref:
                source_branch = current_context.source_git_ref
                context_description = f"Git ref: {current_context.source_git_ref}"
            else:
                source_branch = "HEAD"
                context_description = "Current HEAD"

            from agents.subagents.code_research import (
                CodeResearchConfig,
                CodeResearchDependencies,
                create_code_research_subagent,
            )
            from core.agents import run_agent_safely

            code_research_config = CodeResearchConfig(get_current_config())
            model = code_research_config.get_model()
            num_retries = code_research_config.get_num_retries()
            system_prompt = self.prompts.get_code_research_prompt()

            agent = create_code_research_subagent(
                model=model,
                system_prompt=system_prompt,
                num_retries=num_retries,
            )

            deps = CodeResearchDependencies(
                git_ref=source_branch,
                repo_path=str(git_repo.repo_path),
            )

            prompt = f"""Context: {context_description}

User Instructions:
{instructions}"""

            result = await run_agent_safely(agent, prompt, deps=deps)

            get_current_agent_execution_context().track_usage(model, result.usage())

            self.logger.info("Code research completed")
            return f"Code research completed. Results:\n\n{result.output}"

        except Exception as e:
            self.logger.error(
                f"Error during code research: {type(e).__name__}: {str(e)}",
                exc_info=True,
            )
            return f"Code research failed: {type(e).__name__}: {str(e)}"

    async def _tool_get_token_usage(
        self,
        _ctx: RunContext[PersistentAgentDeps],
        days: int,
    ) -> str:
        """Get token usage statistics for the specified number of days.

        Args:
            days: Number of days to retrieve (any positive number)

        Returns:
            Formatted markdown report of token usage
        """
        self.logger.info(f"get_token_usage tool called with days={days}")

        if days < 1:
            return "Days must be a positive number."

        storage = get_storage(get_current_config())
        usage_storage = get_usage_storage(storage)
        usages = usage_storage.load_usage(days)
        return usage_storage.format_usage(usages)

    async def run(self) -> str:
        """Execute the agent with hook-based extensible tools.

        Overrides the base class run() to:
        1. Collect tool registrations via hooks
        2. Build dynamic system prompt with tool descriptions
        3. Create FunctionToolset with registered tools
        4. Run agent with dynamic toolset

        Returns:
            AI-generated response string
        """
        # Ensure agent is set up
        if self.agent is None:
            self.setup_agent()

        if self.agent is None:
            raise RuntimeError(
                "setup_agent() must set self.agent to a PydanticAgent instance"
            )

        self.logger.info(f"Starting {self.__class__.__name__} execution")

        # 1. Collect default tool registrations
        tool_registrations = self._get_default_tool_registrations()

        # 2. Action hook: allow adding more tools
        hooks().do_action("gitchatbot.register_tools", tool_registrations)

        # 3. Filter hook: allow sorting/removing tools
        tool_registrations = hooks().apply_filters(
            "gitchatbot.tool_registrations", tool_registrations
        )

        # 4. Build dynamic system prompt with tool descriptions
        sorted_registrations = sorted(tool_registrations, key=lambda r: r.priority)
        tool_descriptions = "\n".join(
            f"- {reg.description}" for reg in sorted_registrations
        )
        system_prompt = self.prompts.get_chatbot_prompt().format(
            tool_descriptions=tool_descriptions
        )

        # 5. Create FunctionToolset with registered tools
        toolset = FunctionToolset[PersistentAgentDeps]()
        for reg in sorted_registrations:
            toolset.add_function(reg.function, name=reg.name)

        self.logger.info(
            f"Registered {len(sorted_registrations)} extensible tools: "
            f"{[reg.name for reg in sorted_registrations]}"
        )

        try:
            # Get messages from context
            message_list = get_current_agent_execution_context().get_message_list()

            if not message_list:
                self.logger.warning("No messages to respond to")
                response = (
                    "I don't see any messages to respond to. Please send me a message!"
                )
                await get_current_agent_execution_context().send_response(response)
                return response

            # Get chat history for processing
            chat_history = message_list.to_pydantic_chat_history()
            self.logger.info(
                f"Processing conversation with {len(chat_history)} message groups"
            )

            # Get dependencies
            deps = self.get_dependencies()

            # Run agent with dynamic toolset and overridden instructions
            self.logger.info(
                "Calling PydanticAI agent with chat history and dynamic tools..."
            )
            result = await self.agent.run(
                message_history=chat_history,
                deps=deps,
                toolsets=[toolset],
                instructions=system_prompt,
            )

            # Track usage after agent execution
            context = get_current_agent_execution_context()
            model_name = (
                self.agent.model if self.agent and self.agent.model else "unknown"
            )
            context.track_usage(model_name, result.usage())

            response = result.output

            self.logger.info(
                f"Generated response: {response[:100]}..."
                if len(response) > 100
                else f"Generated response: {response}"
            )
            await get_current_agent_execution_context().send_response(response)

            self.result = response
            return cast("str", response)

        except AgentGracefulExit:
            # Re-raise without interception - let it propagate up naturally
            raise

        except Exception as e:
            error_msg = f"Error in {self.__class__.__name__}: {str(e)}"
            self.logger.error(error_msg)
            await get_current_agent_execution_context().send_response(
                f"Sorry, I encountered an error: {str(e)}"
            )
            raise
