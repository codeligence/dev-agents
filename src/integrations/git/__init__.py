"""Git integration components."""

from .changed_file import ChangedFileSet
from .config import GitRepositoryConfig
from .git_repository import GitRepository
from .models import (
    DirectoryListingResult,
    FileContentResult,
    GitDiffContext,
    GlobFilesResult,
    GrepSearchResult,
)
from .utils import (
    git_glob_files,
    git_grep_search,
    git_list_directory,
    git_read_file,
)

__all__ = [
    "GitRepositoryConfig",
    "GitRepository",
    "GitDiffContext",
    "ChangedFileSet",
    # Utility functions
    "git_grep_search",
    "git_glob_files",
    "git_list_directory",
    "git_read_file",
    # Result models
    "GrepSearchResult",
    "GlobFilesResult",
    "DirectoryListingResult",
    "FileContentResult",
]
