from dataclasses import dataclass
from datetime import datetime

from .changed_file import ChangedFileSet


@dataclass
class Commit:
    """Represents a git commit with essential metadata."""

    commit_hash: str
    author: str
    date: datetime
    message: str


@dataclass
class DiffMetadata:
    """Metadata about the diff loading operation."""

    total_files_changed: int
    line_counts: dict[str, int]  # keys: 'insertions', 'deletions', 'total'


@dataclass
class GitDiffContext:
    """Unified context for git diff operations combining git data with business context.

    This replaces both ChangedFileSet and DiffLoadResult from the old system,
    providing a single comprehensive model for git diff operations.
    """

    # Git data (from ChangedFileSet)
    changed_files: ChangedFileSet
    file_diffs: dict[str, str]  # file_path -> diff content

    # Branch info
    source_branch: str
    target_branch: str

    # Repository info
    repo_path: str  # Path to the git repository

    # Business context (from DiffLoadResult)
    context: str  # Work item context or default message
    metadata: DiffMetadata  # Analysis metadata

    @property
    def has_changes(self) -> bool:
        """Whether any file changes were found."""
        return len(self.file_diffs) > 0


@dataclass
class GrepSearchResult:
    """Result from git grep search operation."""

    matches: list[str]
    total_lines: int
    truncated: bool
    pattern: str


@dataclass
class GlobFilesResult:
    """Result from git glob file search operation."""

    files: list[str]
    total_found: int
    truncated: bool
    pattern: str


@dataclass
class DirectoryListingResult:
    """Result from git directory listing operation."""

    directories: list[str]
    files: list[str]
    path: str


@dataclass
class FileContentResult:
    """Result from git file read operation."""

    content: str
    total_lines: int
    start_line: int
    end_line: int
    file_path: str
    truncated: bool
