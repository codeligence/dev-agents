"""Tests for git utility functions.

These tests use a "test" branch with a known state of the codebase
to ensure predictable test results.
"""

from pathlib import Path

import pytest

from core.exceptions import GitFileNotFoundError
from integrations.git.models import (
    DirectoryListingResult,
    FileContentResult,
    GlobFilesResult,
    GrepSearchResult,
)
from integrations.git.utils import (
    git_glob_files,
    git_grep_search,
    git_list_directory,
    git_read_file,
)


@pytest.fixture
def repo_path() -> Path:
    """Get the repository path (project root)."""
    return Path(__file__).parent.parent.parent.parent.resolve()


@pytest.fixture
def test_ref() -> str:
    """Git ref for test branch with known state."""
    return "test"


class TestGitGrepSearch:
    """Tests for git_grep_search utility function."""

    def test_basic_pattern_search(self, repo_path: Path, test_ref: str) -> None:
        """Test basic regex pattern search finds matches."""
        result = git_grep_search(
            repo_path=repo_path,
            git_ref=test_ref,
            pattern="def ",
        )
        assert isinstance(result, GrepSearchResult)
        assert result.total_lines > 0
        assert result.pattern == "def "

    def test_case_insensitive_flag(self, repo_path: Path, test_ref: str) -> None:
        """Test (?i) flag for case-insensitive search."""
        # Search for uppercase pattern that exists in lowercase
        result = git_grep_search(
            repo_path=repo_path,
            git_ref=test_ref,
            pattern="(?i)CLASS",
        )
        assert result.total_lines > 0
        # Verify the pattern stored is the original with flag
        assert result.pattern == "(?i)CLASS"

    def test_dotall_flag(self, repo_path: Path, test_ref: str) -> None:
        """Test (?s) flag for dotall - dot matches newlines."""
        # Pattern that spans multiple lines: class definition with docstring
        # This pattern matches 'class X:' followed by anything (including newlines) then '"""'
        result = git_grep_search(
            repo_path=repo_path,
            git_ref=test_ref,
            pattern=r'(?s)class \w+.*?""".*?"""',
            glob_filter="*.py",
        )
        assert result.total_lines > 0
        # Without (?s), .* wouldn't match across newlines

    def test_multiline_flag(self, repo_path: Path, test_ref: str) -> None:
        """Test (?m) flag for multiline - ^ and $ match line boundaries."""
        # Find lines that start with 'class '
        result = git_grep_search(
            repo_path=repo_path,
            git_ref=test_ref,
            pattern=r"(?m)^class \w+",
            glob_filter="*.py",
        )
        assert result.total_lines > 0

    def test_combined_flags(self, repo_path: Path, test_ref: str) -> None:
        """Test combined inline flags (?ims)."""
        # Case-insensitive, multiline: find lines starting with 'CLASS' (any case)
        result = git_grep_search(
            repo_path=repo_path,
            git_ref=test_ref,
            pattern=r"(?im)^class ",
            glob_filter="*.py",
        )
        assert result.total_lines > 0

    def test_no_flags_basic_behavior(self, repo_path: Path, test_ref: str) -> None:
        """Test that without flags, basic regex works (no implicit flags)."""
        # Case-sensitive search - should NOT match 'class' when searching for 'CLASS'
        result_upper = git_grep_search(
            repo_path=repo_path,
            git_ref=test_ref,
            pattern="CLASS",  # No (?i) flag
            glob_filter="*.py",
        )
        result_lower = git_grep_search(
            repo_path=repo_path,
            git_ref=test_ref,
            pattern="class",  # Lowercase
            glob_filter="*.py",
        )
        # 'class' (lowercase) should have more matches than 'CLASS' (uppercase)
        # since Python uses lowercase 'class' keyword
        assert result_lower.total_lines > result_upper.total_lines

    def test_glob_filter(self, repo_path: Path, test_ref: str) -> None:
        """Test glob pattern filtering limits to specific file types."""
        result = git_grep_search(
            repo_path=repo_path,
            git_ref=test_ref,
            pattern="import",
            glob_filter="*.py",
        )
        assert result.total_lines > 0
        # All matches should be from .py files
        for match in result.matches:
            # Skip non-file lines (line numbers, blank lines)
            if match and not match[0].isdigit() and match.strip():
                # This is a filename header
                assert ".py" in match or match.startswith("-") or match.startswith(" ")

    def test_path_filter(self, repo_path: Path, test_ref: str) -> None:
        """Test path filtering limits to specific directory."""
        result = git_grep_search(
            repo_path=repo_path,
            git_ref=test_ref,
            pattern="def ",
            path="src/integrations/git",
        )
        assert result.total_lines > 0

    def test_no_matches(self, repo_path: Path, test_ref: str) -> None:
        """Test when no matches are found."""
        result = git_grep_search(
            repo_path=repo_path,
            git_ref=test_ref,
            pattern="nonexistent_pattern_xyz_123_abc",
        )
        assert result.total_lines == 0
        assert len(result.matches) == 0
        assert not result.truncated

    def test_context_lines(self, repo_path: Path, test_ref: str) -> None:
        """Test context lines around matches."""
        result = git_grep_search(
            repo_path=repo_path,
            git_ref=test_ref,
            pattern="GitRepository",
            context_lines=2,
        )
        assert result.total_lines > 0

    def test_context_lines_clamped(self, repo_path: Path, test_ref: str) -> None:
        """Test context lines are clamped to valid range."""
        # Should not raise error even with out-of-range value
        result = git_grep_search(
            repo_path=repo_path,
            git_ref=test_ref,
            pattern="def ",
            context_lines=100,  # Will be clamped to 5
        )
        assert result.total_lines > 0

    def test_empty_pattern_raises(self, repo_path: Path, test_ref: str) -> None:
        """Test empty pattern raises ValueError."""
        with pytest.raises(ValueError, match="Pattern cannot be empty"):
            git_grep_search(
                repo_path=repo_path,
                git_ref=test_ref,
                pattern="",
            )

    def test_truncation(self, repo_path: Path, test_ref: str) -> None:
        """Test results are truncated when exceeding max_results."""
        result = git_grep_search(
            repo_path=repo_path,
            git_ref=test_ref,
            pattern=".",  # Match everything
            max_results=10,
        )
        if result.total_lines > 10:
            assert result.truncated
            assert len(result.matches) == 10


class TestGitGlobFiles:
    """Tests for git_glob_files utility function."""

    def test_find_python_files(self, repo_path: Path, test_ref: str) -> None:
        """Test finding Python files."""
        result = git_glob_files(
            repo_path=repo_path,
            git_ref=test_ref,
            pattern="*.py",
        )
        assert isinstance(result, GlobFilesResult)
        assert result.total_found > 0
        assert all(f.endswith(".py") for f in result.files)
        assert result.pattern == "*.py"

    def test_recursive_pattern(self, repo_path: Path, test_ref: str) -> None:
        """Test recursive glob pattern."""
        result = git_glob_files(
            repo_path=repo_path,
            git_ref=test_ref,
            pattern="**/*.py",
        )
        assert result.total_found > 0
        # Should include files in subdirectories
        assert any("/" in f for f in result.files)

    def test_path_filter(self, repo_path: Path, test_ref: str) -> None:
        """Test path filtering limits results to directory."""
        result = git_glob_files(
            repo_path=repo_path,
            git_ref=test_ref,
            pattern="*.py",
            path="src/integrations/git",
        )
        assert result.total_found > 0
        assert all("src/integrations/git" in f for f in result.files)

    def test_no_matches(self, repo_path: Path, test_ref: str) -> None:
        """Test when no files match."""
        result = git_glob_files(
            repo_path=repo_path,
            git_ref=test_ref,
            pattern="*.nonexistent_extension",
        )
        assert result.total_found == 0
        assert len(result.files) == 0

    def test_empty_pattern_raises(self, repo_path: Path, test_ref: str) -> None:
        """Test empty pattern raises ValueError."""
        with pytest.raises(ValueError, match="Pattern cannot be empty"):
            git_glob_files(
                repo_path=repo_path,
                git_ref=test_ref,
                pattern="",
            )

    def test_truncation(self, repo_path: Path, test_ref: str) -> None:
        """Test results are truncated when exceeding max_results."""
        result = git_glob_files(
            repo_path=repo_path,
            git_ref=test_ref,
            pattern="*.py",
            max_results=5,
        )
        if result.total_found > 5:
            assert result.truncated
            assert len(result.files) == 5


class TestGitListDirectory:
    """Tests for git_list_directory utility function."""

    def test_list_root(self, repo_path: Path, test_ref: str) -> None:
        """Test listing root directory."""
        result = git_list_directory(
            repo_path=repo_path,
            git_ref=test_ref,
            path="",
        )
        assert isinstance(result, DirectoryListingResult)
        assert len(result.directories) > 0 or len(result.files) > 0
        assert result.path == "."

    def test_list_src_directory(self, repo_path: Path, test_ref: str) -> None:
        """Test listing src directory."""
        result = git_list_directory(
            repo_path=repo_path,
            git_ref=test_ref,
            path="src",
        )
        assert "integrations/" in result.directories

    def test_directories_have_trailing_slash(
        self, repo_path: Path, test_ref: str
    ) -> None:
        """Test directories have trailing slash."""
        result = git_list_directory(
            repo_path=repo_path,
            git_ref=test_ref,
            path="src",
        )
        for dir_entry in result.directories:
            assert dir_entry.endswith("/")

    def test_files_no_trailing_slash(self, repo_path: Path, test_ref: str) -> None:
        """Test files do not have trailing slash."""
        result = git_list_directory(
            repo_path=repo_path,
            git_ref=test_ref,
            path="src/integrations/git",
        )
        for file_entry in result.files:
            assert not file_entry.endswith("/")

    def test_ignore_patterns(self, repo_path: Path, test_ref: str) -> None:
        """Test ignore patterns filter out entries."""
        result_all = git_list_directory(
            repo_path=repo_path,
            git_ref=test_ref,
            path="src/integrations/git",
        )
        result_filtered = git_list_directory(
            repo_path=repo_path,
            git_ref=test_ref,
            path="src/integrations/git",
            ignore=["__init__.py"],
        )
        # __init__.py should be in all but not in filtered
        assert "__init__.py" in result_all.files
        assert "__init__.py" not in result_filtered.files

    def test_empty_directory(self, repo_path: Path, test_ref: str) -> None:
        """Test listing non-existent path returns empty result."""
        result = git_list_directory(
            repo_path=repo_path,
            git_ref=test_ref,
            path="nonexistent_path_xyz",
        )
        assert len(result.directories) == 0
        assert len(result.files) == 0

    def test_sorted_output(self, repo_path: Path, test_ref: str) -> None:
        """Test directories and files are sorted alphabetically."""
        result = git_list_directory(
            repo_path=repo_path,
            git_ref=test_ref,
            path="src",
        )
        # Check directories are sorted
        assert result.directories == sorted(result.directories)
        # Check files are sorted
        assert result.files == sorted(result.files)


class TestGitReadFile:
    """Tests for git_read_file utility function."""

    def test_read_file(self, repo_path: Path, test_ref: str) -> None:
        """Test reading a file."""
        result = git_read_file(
            repo_path=repo_path,
            git_ref=test_ref,
            file_path="pyproject.toml",
        )
        assert isinstance(result, FileContentResult)
        assert result.total_lines > 0
        assert result.file_path == "pyproject.toml"
        assert result.start_line == 1
        # Content should have line numbers
        assert "\t" in result.content

    def test_read_with_offset(self, repo_path: Path, test_ref: str) -> None:
        """Test reading with line offset."""
        result = git_read_file(
            repo_path=repo_path,
            git_ref=test_ref,
            file_path="pyproject.toml",
            offset=5,
        )
        assert result.start_line == 5

    def test_read_with_limit(self, repo_path: Path, test_ref: str) -> None:
        """Test reading with line limit."""
        result = git_read_file(
            repo_path=repo_path,
            git_ref=test_ref,
            file_path="pyproject.toml",
            limit=10,
        )
        # Content should have at most 10 lines
        lines = result.content.strip().split("\n")
        assert len(lines) <= 10

    def test_read_with_offset_and_limit(self, repo_path: Path, test_ref: str) -> None:
        """Test reading with both offset and limit."""
        result = git_read_file(
            repo_path=repo_path,
            git_ref=test_ref,
            file_path="pyproject.toml",
            offset=3,
            limit=5,
        )
        assert result.start_line == 3
        assert result.end_line <= result.start_line + 5

    def test_file_not_found(self, repo_path: Path, test_ref: str) -> None:
        """Test reading non-existent file raises GitFileNotFoundError."""
        with pytest.raises(GitFileNotFoundError):
            git_read_file(
                repo_path=repo_path,
                git_ref=test_ref,
                file_path="nonexistent_file_xyz.py",
            )

    def test_truncation_indicator(self, repo_path: Path, test_ref: str) -> None:
        """Test truncated flag when file has more lines."""
        result = git_read_file(
            repo_path=repo_path,
            git_ref=test_ref,
            file_path="pyproject.toml",
            limit=5,
        )
        if result.total_lines > 5:
            assert result.truncated
        else:
            assert not result.truncated

    def test_line_numbers_in_content(self, repo_path: Path, test_ref: str) -> None:
        """Test content includes line numbers."""
        result = git_read_file(
            repo_path=repo_path,
            git_ref=test_ref,
            file_path="pyproject.toml",
            limit=5,
        )
        lines = result.content.strip().split("\n")
        for line in lines:
            # Each line should start with a number followed by tab
            parts = line.split("\t", 1)
            assert len(parts) == 2
            assert parts[0].strip().isdigit()
