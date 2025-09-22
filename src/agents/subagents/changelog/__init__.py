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

This subagent generates changelog entries from code changes by analyzing file diffs,
commit history, and related issue context to create meaningful release notes.
"""

from .changelog_subagent import ChangelogSubagent
from .models import (
    ChangelogEntry,
    ChangelogReport,
    ChangelogResult,
)

__all__ = [
    "ChangelogEntry",
    "ChangelogReport",
    "ChangelogResult",
    "ChangelogSubagent",
]
