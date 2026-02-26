"""Git utility functions for code research operations.

Pure functions for git operations that can be used independently of PydanticAI agents.
These utilities support searching, listing, and reading files from any git reference.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
import fnmatch
import re
import shlex
import subprocess

from git import (
    Blob,
    GitError,
    Tree,
)  # GitPython types, imported via PyDriller dependency
from git.exc import GitCommandError
from pydriller import Git  # type: ignore[import-untyped]

if TYPE_CHECKING:
    from collections.abc import Generator

    from pydriller.domain.commit import (  # type: ignore[import-untyped]
        Commit as PyDrillerCommit,
    )

from core.exceptions import GitFileNotFoundError, GitOperationError
from core.log import get_logger

from .models import (
    DirectoryListingResult,
    FileContentResult,
    GlobFilesResult,
    GrepSearchResult,
)

logger = get_logger(logger_name="GitUtils", level="DEBUG")

MAX_LINE_LENGTH = 180


def get_matching_blobs(
    tree: Tree, glob_filter: str | None = None, path: str | None = None
) -> Generator[tuple[str, Blob], None, None]:
    """Generator to yield file paths and blobs matching the criteria."""
    try:
        if path:
            sub_item = tree / path
            if sub_item.type == "blob":
                if not glob_filter or fnmatch.fnmatch(path, glob_filter):
                    yield path, sub_item
                return
            elif sub_item.type == "tree":
                start_tree = sub_item
            else:
                return
        else:
            start_tree = tree
    except KeyError:
        return

    for item in start_tree.traverse():
        if not isinstance(item, Blob):
            continue
        full_path = str(item.path)
        if not glob_filter or fnmatch.fnmatch(full_path, glob_filter):
            yield full_path, item


def git_grep_search(
    repo_path: Path,
    git_ref: str,
    pattern: str,
    path: str | None = None,
    glob_filter: str | None = None,
    context_lines: int = 0,
    max_results: int = 120,
) -> GrepSearchResult:
    """Search file contents using regex pattern in a git ref.

    Pattern supports inline flags for full control:
        (?i) - case insensitive
        (?m) - multiline (^ and $ match line boundaries)
        (?s) - dotall (. matches newlines for cross-line patterns)
        Combined: (?ims)pattern

    Examples:
        "(?i)TODO" - case insensitive search
        "(?s)def foo.*return" - match across multiple lines
        "(?im)^import" - multiline, case insensitive

    Args:
        repo_path: Path to the git repository
        git_ref: Git reference (branch, tag, or commit hash)
        pattern: Regular expression pattern with optional inline flags
        path: Optional directory or file to search in (relative to repo root)
        glob_filter: Optional glob pattern to filter files (e.g., "*.py", "*.ts")
        context_lines: Number of lines to show before/after each match (0-5)
        max_results: Maximum number of result lines to return

    Returns:
        GrepSearchResult with matches, total count, and truncation info

    Raises:
        GitOperationError: If operation fails
        ValueError: If pattern is empty or invalid regex
    """
    logger.info(
        f"git_grep_search called: pattern={pattern!r}, path={path!r}, "
        f"glob_filter={glob_filter!r}, context_lines={context_lines}"
    )

    if not pattern:
        raise ValueError("Pattern cannot be empty")

    repo_path = repo_path.resolve()

    # Clamp context lines to reasonable range
    context_lines = max(0, min(5, context_lines))

    logger.debug(
        f"git_grep_search: git_ref={git_ref}, repo_path={repo_path}, "
        f"clamped context_lines={context_lines}"
    )

    try:
        gr = Git(str(repo_path))
        commit: PyDrillerCommit = gr.get_commit(git_ref)
        gp_commit = commit._c_object  # GitPython Commit
        tree: Tree = gp_commit.tree
    except (ValueError, GitCommandError, GitError) as e:
        error_msg = f"Failed to access commit for ref '{git_ref}': {str(e)}"
        logger.warning(f"git_grep_search: {error_msg}")
        raise GitOperationError(error_msg)

    try:
        regex = re.compile(pattern)  # Pattern controls flags via inline syntax (?ims)
    except re.error as e:
        raise ValueError(f"Invalid regex pattern: {e}")

    output_lines: list[str] = []
    truncated = False
    for file_path, blob in get_matching_blobs(
        tree, glob_filter if not path or glob_filter else None, path
    ):
        # Early exit: stop searching if we already have enough results
        if len(output_lines) >= max_results:
            truncated = True
            break

        try:
            content_bytes = blob.data_stream.read()
            content = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            continue

        matches = list(regex.finditer(content))
        if not matches:
            continue

        lines = content.splitlines()
        num_lines = len(lines)
        if num_lines == 0:
            continue

        # Collect all matched line numbers (sets for uniqueness)
        matched_lines = set()
        hunk_ranges = []
        for m in matches:
            start_pos = m.start()
            end_pos = m.end()

            # Calculate start and end lines (1-indexed)
            start_line = content[:start_pos].count("\n") + 1
            end_line = content[:end_pos].count("\n") + 1

            for ln in range(start_line, end_line + 1):
                matched_lines.add(ln)

            from_line = max(1, start_line - context_lines)
            to_line = min(num_lines, end_line + context_lines)
            hunk_ranges.append((from_line, to_line))

        # Merge overlapping hunk ranges
        if hunk_ranges:
            hunk_ranges.sort()
            merged_ranges = []
            current_start, current_end = hunk_ranges[0]
            for start, end in hunk_ranges[1:]:
                if start <= current_end + 1:
                    current_end = max(current_end, end)
                else:
                    merged_ranges.append((current_start, current_end))
                    current_start, current_end = start, end
            merged_ranges.append((current_start, current_end))

            # Add file heading
            output_lines.append(file_path)

            # Add hunks
            for i, (start, end) in enumerate(merged_ranges):
                for ln in range(start, end + 1):
                    if ln > num_lines:
                        break
                    line_content = lines[ln - 1] if ln - 1 < len(lines) else ""
                    if len(line_content) > MAX_LINE_LENGTH:
                        line_content = (
                            line_content[:MAX_LINE_LENGTH] + "... (truncated)"
                        )
                    separator = ":" if ln in matched_lines else "-"
                    output_lines.append(f"{ln}{separator}{line_content}")

                # Add separator between hunks if more than one
                if i < len(merged_ranges) - 1:
                    output_lines.append("---")

            # Add break (blank line) after file
            output_lines.append("")

    # Remove trailing blank line if present
    if output_lines and output_lines[-1] == "":
        output_lines.pop()

    total_lines = len(output_lines)
    # Final truncation (in case last file pushed us over the limit)
    if total_lines > max_results:
        output_lines = output_lines[:max_results]
        truncated = True

    if total_lines == 0:
        logger.info(f"git_grep_search: No matches found for pattern '{pattern}'")
        return GrepSearchResult(
            matches=[],
            total_lines=0,
            truncated=False,
            pattern=pattern,
        )

    logger.info(f"git_grep_search: Found {total_lines} lines of matches")
    return GrepSearchResult(
        matches=output_lines,
        total_lines=total_lines,
        truncated=truncated,
        pattern=pattern,
    )


def git_glob_files(
    repo_path: Path,
    git_ref: str,
    pattern: str,
    path: str | None = None,
    max_results: int = 50,
) -> GlobFilesResult:
    """Find files matching a glob pattern in a git ref.

    Args:
        repo_path: Path to the git repository
        git_ref: Git reference (branch, tag, or commit hash)
        pattern: Glob pattern (e.g., "**/*.py", "src/*.ts", "test_*.py")
        path: Optional directory to search in (relative to repo root)
        max_results: Maximum number of files to return

    Returns:
        GlobFilesResult with matching files, total count, and truncation info

    Raises:
        GitOperationError: If git ls-tree fails with an error
        ValueError: If pattern is empty
    """
    logger.info(f"git_glob_files called: pattern={pattern!r}, path={path!r}")

    if not pattern:
        raise ValueError("Pattern cannot be empty")

    repo_path = repo_path.resolve()

    logger.debug(f"git_glob_files: git_ref={git_ref}, repo_path={repo_path}")

    # Use git ls-tree to list all files in the branch
    cmd = ["git", "ls-tree", "-r", "--name-only", git_ref]
    if path:
        cmd.append(path)

    logger.debug(f"git_glob_files: Executing git command: {shlex.join(cmd)}")

    result = subprocess.run(
        cmd,
        cwd=repo_path,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        error_msg = f"File listing failed: {result.stderr.strip()}"
        logger.warning(
            f"git_glob_files: git ls-tree failed with code {result.returncode}: "
            f"{result.stderr.strip()}"
        )
        raise GitOperationError(error_msg)

    all_files = result.stdout.strip().split("\n") if result.stdout.strip() else []
    logger.debug(f"git_glob_files: Found {len(all_files)} total files in tree")

    # Filter files using glob pattern with fnmatch
    matching_files = []
    for file_path in all_files:
        # Match against full path for ** patterns, or just filename for simple patterns
        if "**" in pattern or "/" in pattern:
            # For path patterns, match against full path
            if fnmatch.fnmatch(file_path, pattern):
                matching_files.append(file_path)
        else:
            # For simple patterns, match against filename only
            if fnmatch.fnmatch(Path(file_path).name, pattern):
                matching_files.append(file_path)

    # Limit results
    total_found = len(matching_files)
    truncated = False
    if len(matching_files) > max_results:
        matching_files = matching_files[:max_results]
        truncated = True

    logger.info(f"git_glob_files: Found {total_found} matching files")
    return GlobFilesResult(
        files=matching_files,
        total_found=total_found,
        truncated=truncated,
        pattern=pattern,
    )


def git_list_directory(
    repo_path: Path,
    git_ref: str,
    path: str = "",
    ignore: list[str] | None = None,
) -> DirectoryListingResult:
    """List files and directories in a given path within a git ref.

    Args:
        repo_path: Path to the git repository
        git_ref: Git reference (branch, tag, or commit hash)
        path: Path to the directory to list (relative to repo root, empty for root)
        ignore: List of glob patterns to ignore (e.g., ["*.pyc", "__pycache__"])

    Returns:
        DirectoryListingResult with sorted directories and files

    Raises:
        GitOperationError: If git ls-tree fails or directory doesn't exist
    """
    logger.info(f"git_list_directory called: path={path!r}, ignore={ignore!r}")

    repo_path = repo_path.resolve()
    ignore = ignore or []

    logger.debug(f"git_list_directory: git_ref={git_ref}, repo_path={repo_path}")

    # Use git ls-tree to list immediate children (not recursive)
    cmd = ["git", "ls-tree", git_ref]
    if path:
        # Ensure path ends with / for directory listing
        normalized_path = path.rstrip("/") + "/"
        cmd.append(normalized_path)
    else:
        cmd.append(".")

    logger.debug(f"git_list_directory: Executing git command: {shlex.join(cmd)}")

    result = subprocess.run(
        cmd,
        cwd=repo_path,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        error_msg = f"Directory listing failed: {result.stderr.strip()}"
        logger.warning(
            f"git_list_directory: git ls-tree failed with code {result.returncode}: "
            f"{result.stderr.strip()}"
        )
        raise GitOperationError(error_msg)

    if not result.stdout.strip():
        logger.info(
            f"git_list_directory: Directory '{path or '.'}' is empty or does not exist"
        )
        return DirectoryListingResult(
            directories=[],
            files=[],
            path=path or ".",
        )

    # Parse git ls-tree output: "<mode> <type> <hash>\t<name>"
    directories = []
    files = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        # Split on tab to get metadata and name
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        metadata, name = parts
        obj_type = metadata.split()[1]  # "blob" or "tree"

        # Extract just the filename (not full path)
        entry_name = Path(name).name

        # Check ignore patterns
        if any(fnmatch.fnmatch(entry_name, pat) for pat in ignore):
            logger.debug(f"git_list_directory: Ignoring {entry_name}")
            continue

        # Separate directories and files
        if obj_type == "tree":
            directories.append(f"{entry_name}/")
        else:
            files.append(entry_name)

    # Sort: directories and files alphabetically
    directories.sort()
    files.sort()

    logger.info(
        f"git_list_directory: Found {len(directories)} directories and {len(files)} files"
    )
    return DirectoryListingResult(
        directories=directories,
        files=files,
        path=path or ".",
    )


def git_read_file(
    repo_path: Path,
    git_ref: str,
    file_path: str,
    offset: int | None = None,
    limit: int | None = None,
    max_lines: int = 2000,
    max_line_length: int = 2000,
) -> FileContentResult:
    """Read file contents from a git ref with line numbers.

    Args:
        repo_path: Path to the git repository
        git_ref: Git reference (branch, tag, or commit hash)
        file_path: Path to the file to read (relative to repo root)
        offset: Line number to start reading from (1-indexed)
        limit: Maximum number of lines to read
        max_lines: Default maximum lines if limit not specified
        max_line_length: Maximum characters per line before truncation

    Returns:
        FileContentResult with content, line info, and truncation status

    Raises:
        GitFileNotFoundError: If the file doesn't exist in the git tree
        GitOperationError: If git show fails with an unexpected error
    """
    logger.info(
        f"git_read_file called: file_path={file_path!r}, offset={offset}, limit={limit}"
    )

    repo_path = repo_path.resolve()

    logger.debug(
        f"git_read_file: git_ref={git_ref}, repo_path={repo_path}, max_lines={max_lines}"
    )

    # Use git show to read file from specific branch
    cmd = ["git", "show", f"{git_ref}:{file_path}"]

    logger.debug(f"git_read_file: Executing git command: {shlex.join(cmd)}")

    result = subprocess.run(
        cmd,
        cwd=repo_path,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        stderr = result.stderr.strip()
        # Check if it's a "file not found" error (handle multiple languages)
        # English: "does not exist", German: "existiert nicht"
        file_not_found_patterns = [
            "does not exist",
            "existiert nicht",
            "fatal: path",
            "fatal: Pfad",
        ]
        if any(pattern in stderr for pattern in file_not_found_patterns):
            raise GitFileNotFoundError(f"File not found: {file_path}")
        error_msg = f"Could not read file {file_path}: {stderr}"
        logger.warning(
            f"git_read_file: git show failed with code {result.returncode}: {stderr}"
        )
        raise GitOperationError(error_msg)

    lines = result.stdout.splitlines()
    total_lines = len(lines)
    logger.debug(f"git_read_file: File has {total_lines} total lines")

    # Apply offset and limit
    start = (offset - 1) if offset else 0
    start = max(0, start)

    effective_limit = limit if limit else max_lines
    end = start + effective_limit

    selected_lines = lines[start:end]
    truncated = end < total_lines

    logger.debug(f"git_read_file: Reading lines {start + 1} to {min(end, total_lines)}")

    # Format with line numbers (cat -n style)
    width = len(str(end))
    output_lines = []
    for i, line in enumerate(selected_lines, start + 1):
        # Truncate long lines
        if len(line) > max_line_length:
            line = line[:max_line_length] + "... (truncated)"
        output_lines.append(f"{i:>{width}}\t{line}")

    content = "\n".join(output_lines)

    logger.info(
        f"git_read_file: Read {len(selected_lines)} lines from {file_path} "
        f"(lines {start + 1}-{min(end, total_lines)} of {total_lines})"
    )
    return FileContentResult(
        content=content,
        total_lines=total_lines,
        start_line=start + 1,
        end_line=min(end, total_lines),
        file_path=file_path,
        truncated=truncated,
    )
