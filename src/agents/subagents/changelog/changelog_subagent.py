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


"""Changelog Generation Subagent

This subagent generates changelog entries by analyzing file changes, commit history,
and related issue context to create meaningful, business-oriented changelog entries.
"""

from typing import cast

from pydantic_ai import Agent as PydanticAgent

from agents.subagents.code_research import (
    CodeResearchDependencies,
    create_code_research_subagent,
)
from core.agents.context import (
    get_current_agent_execution_context,
    get_current_config,
    get_current_prompts,
)
from core.config import BaseConfig
from core.log import get_logger
from core.prompts import BasePrompts
from integrations.git.git_repository import GitRepository
from integrations.git.models import Commit, GitDiffContext

from .models import (
    ChangelogConfig,
    ChangelogEntry,
    ChangelogPrompts,
    ChangelogReport,
    ChangelogResult,
)

logger = get_logger(logger_name="ChangelogSubagent", level="DEBUG")


class ChangelogSubagent:
    """Subagent for generating changelog entries from code changes.

    Analyzes all changed files equally (unlike impact analysis which categorizes
    frontend/backend) and generates meaningful changelog entries by combining:
    - File diffs
    - Commit history for each file
    - Issue context from referenced work items
    - AI-powered analysis for business-readable descriptions
    """

    def __init__(
        self,
        base_config: BaseConfig | None = None,
        base_prompts: BasePrompts | None = None,
    ):
        # Use context-local access or defaults
        base_config = base_config or get_current_config()
        base_prompts = base_prompts or get_current_prompts()

        # Create typed wrappers
        self.config = ChangelogConfig(base_config)
        self.prompts = ChangelogPrompts(base_prompts)

        # Initialize git repository with project config
        project_config = base_config.get_default_project_config()
        self.git_repo = GitRepository(project_config=project_config)

    def _extract_issue_ids(
        self, commit_messages: list[str]  # noqa: ARG002
    ) -> list[str]:
        """This is customer specific"""
        return []

    async def _load_issues_context(self, issue_ids: list[str]) -> str:
        """Load context for multiple issues and combine into a summary.

        Args:
            issue_ids: List of issue IDs to load

        Returns:
            Combined context string describing all issues
        """
        if not issue_ids:
            return "No related issues found."

        context_loader = (
            get_current_agent_execution_context().get_context_integration_loader()
        )
        issue_contexts = []

        for issue_id in issue_ids:
            try:
                logger.debug(f"Loading issue context for {issue_id}")
                issue_model = await context_loader.load_issue(issue_id)

                # Extract relevant information from the issue model
                # The exact format depends on the issue provider (JIRA, Azure DevOps, etc.)
                issue_summary = (
                    f"Issue {issue_id}: {getattr(issue_model, 'title', 'No title')}"
                )
                issue_description = getattr(issue_model, "description", "")
                if issue_description:
                    # Truncate long descriptions
                    if len(issue_description) > 200:
                        issue_description = issue_description[:200] + "..."
                    issue_summary += f" - {issue_description}"

                issue_contexts.append(issue_summary)

            except Exception as e:
                logger.warning(f"Could not load issue {issue_id}: {e}")
                issue_contexts.append(f"Issue {issue_id}: Could not load details")

        return "\n".join(issue_contexts)

    async def _generate_changelog_report(
        self,
        file_path: str,
        file_diff: str,
        git_diff_context: GitDiffContext,
        commits: list[Commit],
        issues_context: str,
        user_request: str | None = None,
    ) -> ChangelogReport:
        """Generate changelog report for a single file.

        Args:
            file_path: Path to the changed file
            file_diff: Diff content for the file
            git_diff_context: Git diff context containing repository info
            commits: List of commits that modified this file
            issues_context: Combined context from related issues
            user_request: Optional user-specific instructions for changelog generation

        Returns:
            ChangelogReport with generated changelog entries
        """
        try:
            # Get structured entries directly from AI
            entries = await self.execute_research_agent(
                file_path,
                file_diff,
                git_diff_context,
                commits,
                issues_context,
                user_request,
            )

            return ChangelogReport(
                file_path=file_path,
                entries=entries,  # Direct assignment, no parsing needed
            )

        except Exception as e:
            logger.error(f"Error generating changelog report for {file_path}: {e}")
            return ChangelogReport(
                file_path=file_path,
                entries=[],
            )

    async def execute_research_agent(
        self,
        file_path: str,
        file_diff: str,
        git_diff_context: GitDiffContext,
        commits: list[Commit],
        issues_context: str,
        user_request: str | None = None,
    ) -> list[ChangelogEntry]:
        """Execute research agent for changelog generation.

        Args:
            file_path: Path to the changed file
            file_diff: Diff content of the file
            git_diff_context: Git diff context containing repo path, branch info, etc.
            commits: List of commits that modified this file
            issues_context: Context from related issues
            user_request: Optional user-specific instructions for changelog generation

        Returns:
            List of ChangelogEntry objects
        """
        # Get configuration values
        model = self.config.get_analysis_model()
        num_retries = self.config.get_num_retries()

        # Get the changelog generation system prompt
        system_prompt = self.prompts.get_changelog_generation_prompt()

        # Create research agent with structured output
        agent = create_code_research_subagent(
            model=model,
            system_prompt=system_prompt,
            num_retries=num_retries,
            output_type=list[ChangelogEntry],
        )

        # Prepare dependencies
        deps = CodeResearchDependencies(
            git_ref=git_diff_context.source_branch, repo_path=git_diff_context.repo_path
        )

        # Format commit information for the prompt
        commits_info = (
            "\n".join(
                [
                    f"- {commit.commit_hash[:8]} ({commit.date.strftime('%Y-%m-%d')}): {commit.message}\n\n"
                    for commit in commits
                ]
            )
            if commits
            else "No commits found for this file."
        )

        # Create analysis prompt using template
        prompt_template = self.prompts.get_file_instruction_prompt()
        prompt = prompt_template.format(
            file_path=file_path,
            file_diff=file_diff,
            commits_info=commits_info,
            issues_context=issues_context,
            base_context=git_diff_context.context,
        )

        # Prepend user request if provided
        if user_request and user_request.strip():
            prompt = f"The user provided the following request that you need to honor: {user_request}\n\n{prompt}"

        # Run the analysis
        result = await agent.run(
            prompt,
            deps=deps,
        )

        # Track usage after agent execution
        get_current_agent_execution_context().track_usage(model, result.usage())

        return cast("list[ChangelogEntry]", result.output)

    async def _process_files_with_progress(
        self,
        files_to_process: list[str],
        git_diff_context: GitDiffContext,
        processed_files: list[str],
        total_files: int,
        changelog_reports: list[ChangelogReport],
        user_request: str | None = None,
    ) -> None:
        """Process files with progress updates in a DRY manner.

        Args:
            files_to_process: List of file paths to process
            git_diff_context: Git diff context containing file diffs
            processed_files: List to track processed files (modified in-place)
            total_files: Total number of files that will be processed for progress calculation
            changelog_reports: List to append results to (modified in-place)
            user_request: Optional user-specific instructions for changelog generation
        """

        # Set up progress tracker
        progress_tracker = get_current_agent_execution_context().get_progress_tracker()
        progress_tracker.reset(total_files)

        for file_path in files_to_process:
            if len(processed_files) >= self.config.get_max_files():
                break

            try:
                # Send progress update
                await progress_tracker.async_update()

                logger.debug(
                    f"Analyzing file {len(processed_files) + 1} / {total_files}: {file_path}"
                )
                file_diff = git_diff_context.file_diffs[file_path]

                # Get commits for this specific file
                commits = self.git_repo.get_commits(
                    source_ref=git_diff_context.source_branch,
                    target_ref=git_diff_context.target_branch,
                    file_path=file_path,
                )

                # Extract issue IDs and load issue context
                commit_messages = [commit.message for commit in commits]
                issue_ids = self._extract_issue_ids(commit_messages)
                issues_context = await self._load_issues_context(issue_ids)

                # Generate changelog report
                report = await self._generate_changelog_report(
                    file_path,
                    file_diff,
                    git_diff_context,
                    commits,
                    issues_context,
                    user_request,
                )

                # Debug log all report entries
                logger.debug(
                    f"Generated {len(report.entries)} changelog entries for {file_path}:"
                )
                for i, entry in enumerate(report.entries, 1):
                    entry_text = entry.description
                    if entry.issue_id:
                        entry_text += f" ({entry.issue_id})"
                    logger.debug(f"  {i}. {entry_text}")

                # Only add reports that have actual changelog entries
                if report.has_entries():
                    changelog_reports.append(report)

                processed_files.append(file_path)

                logger.debug(f"Successfully analyzed file: {file_path}")

            except Exception as e:
                logger.error(f"Error analyzing file {file_path}: {e}")

    async def generate_changelogs(
        self, git_diff_context: GitDiffContext, user_request: str | None = None
    ) -> ChangelogResult:
        """Run changelog generation on the provided git diff context.

        Args:
            git_diff_context: GitDiffContext containing file diffs and metadata
            user_request: Optional user-specific instructions for changelog generation

        Returns:
            ChangelogResult with generated changelog reports
        """
        logger.debug(
            f"Starting changelog generation for {len(git_diff_context.file_diffs)} files"
        )

        # Get all changed files (no filtering like impact analysis does)
        all_files = list(git_diff_context.file_diffs.keys())

        # Calculate total files that will be processed for accurate progress tracking
        max_files = self.config.get_max_files()
        total_files_to_process = min(len(all_files), max_files)

        logger.debug(
            f"Processing {len(all_files)} files. Analyzing max {max_files} files (total: {total_files_to_process})."
        )

        # Initialize results
        changelog_reports: list[ChangelogReport] = []
        processed_files: list[str] = []

        # Process all files with progress updates
        await self._process_files_with_progress(
            files_to_process=all_files,
            git_diff_context=git_diff_context,
            processed_files=processed_files,
            total_files=total_files_to_process,
            changelog_reports=changelog_reports,
            user_request=user_request,
        )

        # Create result
        result = ChangelogResult(reports=changelog_reports)

        logger.debug(
            f"Changelog generation complete: {len(changelog_reports)} reports generated"
        )
        return result

    async def summarize_changelog(
        self, changelog_result: ChangelogResult, user_request: str | None = None
    ) -> str:
        """Summarize changelog entries into a polished final changelog.

        Args:
            changelog_result: ChangelogResult containing individual changelog entries
            user_request: Optional user-specific instructions for changelog generation

        Returns:
            Summarized changelog as a formatted string
        """
        logger.debug("Starting changelog summarization")

        # Get the raw changelog content
        raw_changelog = changelog_result.format_changelog()
        logger.info("Summarizing changelog:\n\n" + raw_changelog)

        if (
            not raw_changelog
            or raw_changelog.strip() == "No significant changes detected."
        ):
            return "No significant changes detected."

        # Get configuration for summary model
        model = self.config.get_summary_model()
        num_retries = self.config.get_num_retries()

        # Get the summary system prompt
        system_prompt = self.prompts.get_changelog_summary_prompt()

        try:
            # Create summary agent with string output
            agent = PydanticAgent(
                model=model,
                output_type=str,
                instructions=system_prompt,
                retries=num_retries,
            )

            # Create the summarization prompt
            prompt = f"Transform the following raw changelog entries into a professional, well-organized changelog. Output your result only. Changelog:\n\n{raw_changelog}"

            # Prepend user request if provided
            if user_request and user_request.strip():
                prompt = f"The user provided the following request that you need to honor: {user_request}\n\n{prompt}"

            # Run the summarization
            result = await agent.run(prompt)

            # Track usage after agent execution
            get_current_agent_execution_context().track_usage(model, result.usage())

            summarized_changelog = result.output

            logger.debug("Changelog summarization complete")
            return summarized_changelog

        except Exception as e:
            logger.error(f"Error during changelog summarization: {e}")
            # Fallback to raw changelog if summarization fails
            return raw_changelog
