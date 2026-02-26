from typing import Any

from pydantic import BaseModel, Field, field_validator


class ChangedFile(BaseModel):
    """A single file changed in a feature branch."""

    path: str = Field(
        ..., description="Repository‑relative path of the file (new path for renames)"
    )
    status: str = Field(
        ..., description="Single‑letter git status: A/M/D/R/C/T/B (binary)"
    )
    insertions: int | None = Field(
        None, description="Number of added lines – None for non‑text diffs"
    )
    deletions: int | None = Field(
        None, description="Number of deleted lines – None for non‑text diffs"
    )
    binary: bool = Field(False, description="True if file is binary in this diff")
    patch: str | None = Field(
        None, description="Full git diff patch text; heavy – populate only on demand"
    )

    @field_validator("binary", mode="before")
    @classmethod
    def _auto_binary(cls, v: bool, info: Any) -> bool:
        if v is not None:
            return v
        values = info.data
        return values.get("insertions") == "-"


class ChangedFileSet(BaseModel):
    """All changes unique to *source* since its divergence from *target*."""

    source_branch: str
    target_branch: str
    files: list[ChangedFile]

    def paths(self) -> list[str]:
        """Shortcut: return just the changed paths."""
        return [f.path for f in self.files]

    def get_file_diffs(self) -> dict[str, str]:
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
                file_diffs[file.path] = (
                    f"# No patch data available for {file.path}\n# Status: {file.status}"
                )
        return file_diffs
