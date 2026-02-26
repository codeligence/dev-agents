"""SkillContext facade — unified interface for skills to interact with the agent environment.

Wraps PydanticAI's RunContext and the framework's AgentExecutionContext behind a single,
type-safe API. Skills import SkillContext, construct it from their RunContext, and use it
for all communication, artifact management, project access, and configuration.

Usage:
    from core.skills.context import SkillContext

    async def my_skill_tool(ctx: RunContext[MyDeps], query: str) -> str:
        sc = SkillContext(ctx)
        await sc.send_toolcall_message("Working...")
        project_loader = sc.get_selected_project("default")
        artifact_id = sc.save_artifact(artifact_type="report", title="Report", content="...")
        return "Done"
"""

from typing import Generic, TypeVar

from pydantic_ai import RunContext
from pydantic_ai.messages import ModelMessage

from core.agents.context import get_current_agent_execution_context
from core.artifacts import Artifact, ArtifactMetadata
from core.config import BaseConfig
from core.exceptions import ConfigurationError
from core.integrations.context_integration_loader import ContextIntegrationLoader
from core.log import get_logger
from core.project_config import ProjectConfigFactory
from core.prompts import BasePrompts
from core.protocols.agent_protocols import AgentExecutionContext
from core.storage import BaseStorage

DepsT = TypeVar("DepsT")

logger = get_logger("SkillContext")


class SkillContext(Generic[DepsT]):
    """Unified interface for skills to interact with the agent environment.

    Wraps two mechanisms — PydanticAI's ``RunContext`` (conversation state, deps)
    and the framework's ``AgentExecutionContext`` (communication, storage, config) —
    behind a single facade.

    Generic over ``DepsT`` so that ``sc.deps`` returns the correct type
    (e.g. ``PersistentAgentDeps``).
    """

    def __init__(self, run_ctx: RunContext[DepsT]) -> None:
        self._run_ctx = run_ctx
        self._exec_ctx: AgentExecutionContext = get_current_agent_execution_context()

    # --- Dependencies ---

    @property
    def deps(self) -> DepsT:
        """Access the agent-specific dependencies (type-safe)."""
        return self._run_ctx.deps

    # --- Communication ---

    async def send_toolcall_message(self, fallback_message: str | None = None) -> None:
        """Extract the LLM's last text from messages and send it to the user.

        Some models provide a message for the user when calling tools.
        This forwards that message. If no text part is found, the optional
        *fallback_message* is sent as a status update.

        Args:
            fallback_message: Fallback text sent via ``send_status`` when no text part exists.
        """
        if not self._run_ctx.messages:
            return

        last_model_response = self._run_ctx.messages[-1]
        text_part = next(
            (part for part in last_model_response.parts if part.part_kind == "text"),
            None,
        )
        if text_part:
            await self._exec_ctx.send_response(text_part.content)
        elif fallback_message:
            await self._exec_ctx.send_status(fallback_message)

    async def send_response(self, response: str) -> None:
        """Send a response message to the user.

        Args:
            response: Response text to send.
        """
        await self._exec_ctx.send_response(response)

    async def send_status(self, message: str) -> None:
        """Send a status update to the user.

        Args:
            message: Status message to send.
        """
        await self._exec_ctx.send_status(message)

    async def send_attachment(
        self, name: str, content: str | bytes, is_binary: bool = False
    ) -> None:
        """Send an attachment to the user.

        Args:
            name: Title/name of the attachment.
            content: Content of the attachment (text/markdown or binary).
            is_binary: Whether the content is binary data.
        """
        await self._exec_ctx.send_attachment(name, content, is_binary)

    # --- Artifacts ---

    def save_artifact(
        self,
        artifact_type: str,
        title: str,
        content: str,
        execution_id: str,
        storage: BaseStorage,
        issue_id: str | None = None,
        pull_request_id: str | None = None,
        source_git_ref: str | None = None,
        target_git_ref: str | None = None,
    ) -> str:
        """Create and persist an artifact.

        Args:
            artifact_type: Type of artifact (e.g. "changelog", "test_plan").
            title: Human-readable title.
            content: Artifact content (markdown).
            execution_id: Execution ID for metadata.
            storage: Storage backend to persist the artifact.
            issue_id: Optional issue ID for metadata.
            pull_request_id: Optional PR ID for metadata.
            source_git_ref: Optional source git reference.
            target_git_ref: Optional target git reference.

        Returns:
            Generated artifact_id for later retrieval.
        """
        metadata = ArtifactMetadata(
            execution_id=execution_id,
            issue_id=issue_id,
            pull_request_id=pull_request_id,
            source_git_ref=source_git_ref,
            target_git_ref=target_git_ref,
        )

        artifact_id = metadata.generate_artifact_id(artifact_type)

        artifact = Artifact(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            title=title,
            content=content,
            metadata=metadata,
        )

        storage_key = f"artifact_{execution_id}_{artifact_id}"
        storage.set(storage_key, artifact.to_dict())

        logger.info(f"Saved artifact: {artifact_id}")
        return artifact_id

    def load_artifact(
        self,
        artifact_id: str,
        execution_id: str,
        storage: BaseStorage,
    ) -> Artifact | None:
        """Load a previously saved artifact by ID.

        Args:
            artifact_id: Artifact identifier to load.
            execution_id: Execution ID used when the artifact was saved.
            storage: Storage backend to load from.

        Returns:
            Artifact if found, None otherwise.
        """
        storage_key = f"artifact_{execution_id}_{artifact_id}"
        data = storage.get(storage_key)
        if not data:
            logger.info(f"Artifact not found: {artifact_id}")
            return None
        logger.info(f"Artifact loaded: {artifact_id}")
        return Artifact.from_dict(data)

    # --- Project ---

    def get_selected_project(
        self, project_name: str | None = None
    ) -> ContextIntegrationLoader:
        """Get project-specific ContextIntegrationLoader with validation.

        Args:
            project_name: Project name. Defaults to ``"default"`` if None.

        Returns:
            ContextIntegrationLoader configured for the selected project.

        Raises:
            ConfigurationError: If the project is not found, with a list of available projects.
        """
        project_name = project_name or "default"

        base_config = self._exec_ctx.get_config()
        project_factory = ProjectConfigFactory(base_config)

        try:
            project_factory.get_project_config(project_name)
            return self._exec_ctx.get_context_integration_loader(project_name)
        except ConfigurationError as e:
            available_projects = project_factory.get_available_projects()
            available_list = ", ".join(available_projects)
            raise ConfigurationError(
                f"Project '{project_name}' not found. "
                f"Please name an existing project first. "
                f"Available projects: {available_list}"
            ) from e

    # --- Config ---

    @property
    def config(self) -> BaseConfig:
        """Access the base configuration."""
        return self._exec_ctx.get_config()

    @property
    def prompts(self) -> BasePrompts:
        """Access the base prompts."""
        return self._exec_ctx.get_prompts()

    # --- Conversation ---

    @property
    def messages(self) -> list[ModelMessage]:
        """Access the conversation messages from RunContext."""
        return self._run_ctx.messages

    # --- Execution context ---

    @property
    def execution_context(self) -> AgentExecutionContext:
        """Access the underlying AgentExecutionContext directly."""
        return self._exec_ctx
