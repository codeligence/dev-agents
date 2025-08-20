from dataclasses import dataclass
from typing import Dict

from .changed_file import ChangedFileSet


@dataclass
class DiffMetadata:
    """Metadata about the diff loading operation."""
    total_files_changed: int
    line_counts: Dict[str, int]  # keys: 'insertions', 'deletions', 'total'


@dataclass
class GitDiffContext:
    """Unified context for git diff operations combining git data with business context.

    This replaces both ChangedFileSet and DiffLoadResult from the old system,
    providing a single comprehensive model for git diff operations.
    """
    # Git data (from ChangedFileSet)
    changed_files: ChangedFileSet
    file_diffs: Dict[str, str]  # file_path -> diff content

    # Branch info
    source_branch: str
    target_branch: str

    # Repository info
    repo_path: str                      # Path to the git repository

    # Business context (from DiffLoadResult)
    context: str                         # Work item context or default message
    metadata: DiffMetadata              # Analysis metadata

    @property
    def has_changes(self) -> bool:
        """Whether any file changes were found."""
        return len(self.file_diffs) > 0
