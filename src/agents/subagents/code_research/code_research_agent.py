"""Code Research Agent for impact analysis.

This agent provides file search and content analysis capabilities
for both UI and API impact analysis agents.
"""

import os
import shlex
import subprocess
from pathlib import Path
from typing import List, Optional, Type, Any

from pydantic_ai import Agent as PydanticAgent, RunContext

from core.log import get_logger
from .models import CodeResearchDependencies

logger = get_logger(logger_name="CodeResearchAgent", level="DEBUG")


def create_code_research_agent(
    model: str,
    system_prompt: str,
    num_retries: int = 3,
    output_type: type[Any] = str
) -> PydanticAgent[CodeResearchDependencies, Any]:
    """Create a code research agent configured for file analysis tasks.

    Args:
        model: LLM model to use (e.g., 'openai:gpt-4o-mini')
        system_prompt: System prompt for the agent
        num_retries: Number of retries for failed requests (default: 3)
        output_type: Return type for the agent (default: str)

    Returns:
        Configured PydanticAI agent for code research
    """
    agent = PydanticAgent(
        model=model,
        deps_type=CodeResearchDependencies,
        output_type=output_type,
        instructions=system_prompt,
        retries=num_retries
    )

    @agent.tool
    async def ai_grep_files(ctx: RunContext[CodeResearchDependencies], keywords: List[str], search_path: Optional[str] = None) -> str:
        """
        Search for files containing ALL the given keywords, always using the source branch from dependencies.

        Args:
            keywords: List of keywords to search for, INCLUSIVE. Files that contain all keywords
            search_path: Optional path to search in (relative to repo root)

        Returns:
            List of file paths as a formatted string
        """
        if not keywords:
            return "No keywords provided for search"

        git_ref = ctx.deps.git_ref
        repo_path = Path(ctx.deps.repo_path).resolve()

        logger.debug(f"Searching for keywords {keywords} in git ref {git_ref}")

        try:
            # Use git grep to search within the specified branch
            base_cmd = ["git", "grep", "-l"]
            for kw in keywords:
                base_cmd += ["-e", kw]
            base_cmd += [git_ref, "--", "."]

            if search_path:
                base_cmd = base_cmd[:-2] + [search_path]  # Replace "." with search_path

            logger.debug(f"Running command: {' '.join(base_cmd)}")

            result = subprocess.run(
                base_cmd,
                cwd=repo_path,
                capture_output=True,
                text=True,
            )

            if result.returncode not in (0, 1):
                logger.warning(f"git grep failed: {result.stderr.strip()}")
                return f"Search failed: {result.stderr.strip()}"

            files = result.stdout.strip().split('\n') if result.stdout.strip() else []

            # Limit results to avoid overwhelming the agent
            max_results = 30
            if len(files) > max_results:
                files = files[:max_results]
                files.append(f"... (showing first {max_results} of {len(files)} results)")

            if not files:
                return "No files found containing all keywords"

            # Format results with numbering
            formatted_results = []
            for i, file_path in enumerate(files, 1):
                # Remove branch prefix if present
                clean_path = file_path.replace(f"{git_ref}:", "")
                formatted_results.append(f"{i}. {clean_path}")

            return "\n".join(formatted_results)

        except Exception as e:
            logger.error(f"Error in ai_grep_files: {e}")
            return f"Error searching files: {e}"

    @agent.tool
    async def ai_list_files(ctx: RunContext[CodeResearchDependencies], keywords: List[str], search_path: Optional[str] = None) -> str:
        """
        Search for files by name (case-insensitive) containing ALL the given keywords, always using the source branch from dependencies.

        Args:
            keywords: List of keywords to search for in filenames (case-insensitive)
            search_path: Optional path to search in (relative to repo root)

        Returns:
            List of files whose names contain the keywords, one per line
        """
        if not keywords:
            return "No keywords provided for file name search"

        git_ref = ctx.deps.git_ref
        repo_path = Path(ctx.deps.repo_path).resolve()

        logger.debug(f"Searching for file names containing {keywords} in git ref {git_ref}")

        try:
            # Use git ls-tree to list files in the branch
            cmd = ["git", "ls-tree", "-r", "--name-only", git_ref]
            if search_path:
                cmd.append(search_path)

            logger.debug(f"Running command: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                cwd=repo_path,
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                logger.warning(f"git ls-tree failed: {result.stderr.strip()}")
                return f"File listing failed: {result.stderr.strip()}"

            all_files = result.stdout.strip().split('\n') if result.stdout.strip() else []

            # Filter files that contain all keywords (case-insensitive)
            matching_files = []
            for file_path in all_files:
                file_name = os.path.basename(file_path).lower()
                if all(keyword.lower() in file_name for keyword in keywords):
                    matching_files.append(file_path)

            # Limit results
            max_results = 30
            if len(matching_files) > max_results:
                matching_files = matching_files[:max_results]
                matching_files.append(f"... (showing first {max_results} results)")

            if not matching_files:
                return "No files found with names matching all keywords"

            return "\n".join(matching_files)

        except Exception as e:
            logger.error(f"Error in ai_list_files: {e}")
            return f"Error listing files: {e}"

    @agent.tool
    async def ai_read_file(ctx: RunContext[CodeResearchDependencies], file_path: str) -> str:
        """
        Read the contents of a file, always using the source branch from dependencies.

        Args:
            file_path: Path to the file to read (relative to repo root)

        Returns:
            The contents of the file, or an error message if the file could not be read
        """
        git_ref = ctx.deps.git_ref
        repo_path = Path(ctx.deps.repo_path).resolve()

        logger.debug(f"Reading file {file_path} from git ref {git_ref}")

        try:
            # Use git show to read file from specific branch
            cmd = ["git", "show", f"{git_ref}:{file_path}"]

            logger.debug(f"Running command: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                cwd=repo_path,
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                logger.warning(f"git show failed: {result.stderr.strip()}")
                return f"Could not read file {file_path}: {result.stderr.strip()}"

            content = result.stdout

            # Limit content size to avoid overwhelming the agent
            max_chars = 10000
            if len(content) > max_chars:
                content = content[:max_chars] + f"\n... (file truncated at {max_chars} characters)"

            return content

        except Exception as e:
            logger.error(f"Error in ai_read_file: {e}")
            return f"Error reading file {file_path}: {e}"

    return agent
