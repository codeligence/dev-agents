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


from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict


class ChangedFile(BaseModel):
    """A single file changed in a feature branch."""
    path: str = Field(..., description="Repository‑relative path of the file (new path for renames)")
    status: str = Field(..., description="Single‑letter git status: A/M/D/R/C/T/B (binary)")
    insertions: Optional[int] = Field(None, description="Number of added lines – None for non‑text diffs")
    deletions: Optional[int] = Field(None, description="Number of deleted lines – None for non‑text diffs")
    binary: bool = Field(False, description="True if file is binary in this diff")
    patch: Optional[str] = Field(None, description="Full git diff patch text; heavy – populate only on demand")

    @field_validator("binary", mode="before")
    @classmethod
    def _auto_binary(cls, v, info):
        if v is not None:
            return v
        values = info.data
        if values.get("insertions") == "-":
            return True
        return False


class ChangedFileSet(BaseModel):
    """All changes unique to *source* since its divergence from *target*."""
    source_branch: str
    target_branch: str
    files: List[ChangedFile]

    def paths(self) -> List[str]:
        """Shortcut: return just the changed paths."""
        return [f.path for f in self.files]
    
    def get_file_diffs(self) -> Dict[str, str]:
        """Get file-by-file diff content for all changed files.
        
        Returns:
            Dictionary mapping file paths to their diff content (patch text)
        """
        file_diffs = {}
        for file in self.files:
            if file.patch is not None:
                file_diffs[file.path] = file.patch
            else:
                # If patch is None, provide a placeholder indicating no patch data
                file_diffs[file.path] = f"# No patch data available for {file.path}\n# Status: {file.status}"
        return file_diffs