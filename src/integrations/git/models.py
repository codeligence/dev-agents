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