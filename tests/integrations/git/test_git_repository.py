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


from datetime import datetime
from unittest.mock import Mock, patch
import subprocess

import pytest

from core.project_config import ProjectConfig
from integrations.git.git_repository import GitRepository


class TestGitRepositoryGetCommits:
    """Test cases for GitRepository get_commits method."""

    def setup_method(self):
        """Setup test fixtures."""
        # Create a mock project config
        self.mock_project_config = Mock(spec=ProjectConfig)

        # Mock the git config to return a valid path
        with patch(
            "integrations.git.git_repository.GitRepositoryConfig"
        ) as mock_git_config_class:
            mock_git_config = Mock()
            mock_git_config.get_repo_dir.return_value = "/fake/repo/path"
            mock_git_config.get_auto_pull.return_value = (
                False  # Disable auto-pull for tests
            )
            mock_git_config_class.from_project_config.return_value = mock_git_config

            self.git_repo = GitRepository(self.mock_project_config)

    def test_get_commits_success(self):
        """Test get_commits with successful git output."""
        # Mock git output - format: hash|author|iso_date|full_message|||COMMIT_END|||
        mock_output = """abc123|John Doe|2025-01-15T10:30:00Z|Fix authentication bug

This fixes the login issue that was causing users to be unable to access their accounts.

- Updated password validation
- Fixed session handling|||COMMIT_END|||def456|Jane Smith|2025-01-14T15:45:00Z|Add user validation|||COMMIT_END|||789ghi|Bob Johnson|2025-01-13T09:15:00Z|Update documentation

Added comprehensive documentation for the new authentication system.|||COMMIT_END|||"""

        with (
            patch.object(self.git_repo, "_resolve_branch") as mock_resolve,
            patch.object(self.git_repo, "_git_output") as mock_git_output,
        ):

            # Setup mocks
            mock_resolve.side_effect = lambda x: f"resolved_{x}"
            mock_git_output.return_value = mock_output

            # Execute
            commits = self.git_repo.get_commits(
                "release/v1.0", "release/v2.0", "src/auth.py"
            )

            # Verify
            assert len(commits) == 3

            # Check first commit (should be newest due to sorting)
            assert commits[0].commit_hash == "abc123"
            assert commits[0].author == "John Doe"
            assert commits[0].date == datetime(
                2025,
                1,
                15,
                10,
                30,
                0,
                tzinfo=datetime.fromisoformat("2025-01-15T10:30:00+00:00").tzinfo,
            )
            expected_message = """Fix authentication bug

This fixes the login issue that was causing users to be unable to access their accounts.

- Updated password validation
- Fixed session handling"""
            assert commits[0].message == expected_message

            # Check sorting (newest first)
            assert commits[0].date > commits[1].date > commits[2].date

            # Verify git command was called correctly
            expected_cmd = "git log --format='format:%H|%an|%aI|%B|||COMMIT_END|||' --full-history resolved_release/v1.0...resolved_release/v2.0 -- src/auth.py"
            mock_git_output.assert_called_once_with(expected_cmd)

            # Verify branch resolution calls
            assert mock_resolve.call_count == 2
            mock_resolve.assert_any_call("release/v1.0")
            mock_resolve.assert_any_call("release/v2.0")

    def test_get_commits_empty_output(self):
        """Test get_commits when no commits are found."""
        with (
            patch.object(self.git_repo, "_resolve_branch") as mock_resolve,
            patch.object(self.git_repo, "_git_output") as mock_git_output,
        ):

            mock_resolve.side_effect = lambda x: f"resolved_{x}"
            mock_git_output.return_value = ""

            commits = self.git_repo.get_commits("branch1", "branch2", "nonexistent.py")

            assert commits == []

    def test_get_commits_whitespace_only_output(self):
        """Test get_commits with whitespace-only output."""
        with (
            patch.object(self.git_repo, "_resolve_branch") as mock_resolve,
            patch.object(self.git_repo, "_git_output") as mock_git_output,
        ):

            mock_resolve.side_effect = lambda x: f"resolved_{x}"
            mock_git_output.return_value = "   \n  \n   "

            commits = self.git_repo.get_commits("branch1", "branch2", "file.py")

            assert commits == []

    def test_get_commits_malformed_line_skipped(self):
        """Test get_commits skips malformed entries."""
        mock_output = """abc123|John Doe|2025-01-15T10:30:00Z|Valid commit|||COMMIT_END|||invalid_entry_without_pipes|||COMMIT_END|||def456|Jane Smith|2025-01-14T15:45:00Z|Another valid commit|||COMMIT_END|||only|two|parts|||COMMIT_END|||"""

        with (
            patch.object(self.git_repo, "_resolve_branch") as mock_resolve,
            patch.object(self.git_repo, "_git_output") as mock_git_output,
        ):

            mock_resolve.side_effect = lambda x: f"resolved_{x}"
            mock_git_output.return_value = mock_output

            commits = self.git_repo.get_commits("branch1", "branch2", "file.py")

            # Should only get the 2 valid commits
            assert len(commits) == 2
            assert commits[0].commit_hash == "abc123"
            assert commits[1].commit_hash == "def456"

    def test_get_commits_invalid_date_skipped(self):
        """Test get_commits skips commits with invalid dates."""
        mock_output = """abc123|John Doe|2025-01-15T10:30:00Z|Valid commit|||COMMIT_END|||def456|Jane Smith|invalid-date|Invalid date commit|||COMMIT_END|||789ghi|Bob Johnson|2025-01-13T09:15:00Z|Another valid commit|||COMMIT_END|||"""

        with (
            patch.object(self.git_repo, "_resolve_branch") as mock_resolve,
            patch.object(self.git_repo, "_git_output") as mock_git_output,
        ):

            mock_resolve.side_effect = lambda x: f"resolved_{x}"
            mock_git_output.return_value = mock_output

            commits = self.git_repo.get_commits("branch1", "branch2", "file.py")

            # Should only get the 2 valid commits
            assert len(commits) == 2
            assert commits[0].commit_hash == "abc123"
            assert commits[1].commit_hash == "789ghi"

    def test_get_commits_subprocess_error(self):
        """Test get_commits handles subprocess errors gracefully."""
        with (
            patch.object(self.git_repo, "_resolve_branch") as mock_resolve,
            patch.object(self.git_repo, "_git_output") as mock_git_output,
        ):

            mock_resolve.side_effect = lambda x: f"resolved_{x}"
            mock_git_output.side_effect = subprocess.CalledProcessError(1, "git log")

            commits = self.git_repo.get_commits("branch1", "branch2", "file.py")

            assert commits == []

    def test_get_commits_branch_resolution_error(self):
        """Test get_commits handles branch resolution errors."""
        with patch.object(self.git_repo, "_resolve_branch") as mock_resolve:
            mock_resolve.side_effect = ValueError("Branch not found")

            with pytest.raises(ValueError, match="Branch not found"):
                self.git_repo.get_commits("nonexistent_branch", "branch2", "file.py")

    def test_get_commits_message_with_pipes(self):
        """Test get_commits handles commit messages containing pipe characters."""
        # Commit message contains pipes which could break parsing if not handled correctly
        mock_output = "abc123|John Doe|2025-01-15T10:30:00Z|Fix bug in pipeline | update tests|||COMMIT_END|||"

        with (
            patch.object(self.git_repo, "_resolve_branch") as mock_resolve,
            patch.object(self.git_repo, "_git_output") as mock_git_output,
        ):

            mock_resolve.side_effect = lambda x: f"resolved_{x}"
            mock_git_output.return_value = mock_output

            commits = self.git_repo.get_commits("branch1", "branch2", "file.py")

            assert len(commits) == 1
            assert commits[0].message == "Fix bug in pipeline | update tests"

    def test_get_commits_date_formats(self):
        """Test get_commits handles different ISO date formats."""
        mock_output = """abc123|John Doe|2025-01-15T10:30:00+00:00|UTC timezone|||COMMIT_END|||def456|Jane Smith|2025-01-14T15:45:00-05:00|Negative timezone|||COMMIT_END|||789ghi|Bob Johnson|2025-01-13T09:15:00Z|Zulu timezone|||COMMIT_END|||"""

        with (
            patch.object(self.git_repo, "_resolve_branch") as mock_resolve,
            patch.object(self.git_repo, "_git_output") as mock_git_output,
        ):

            mock_resolve.side_effect = lambda x: f"resolved_{x}"
            mock_git_output.return_value = mock_output

            commits = self.git_repo.get_commits("branch1", "branch2", "file.py")

            assert len(commits) == 3
            # All dates should parse successfully
            for commit in commits:
                assert isinstance(commit.date, datetime)
                assert commit.date.tzinfo is not None

    def test_get_commits_file_path_quoting(self):
        """Test get_commits properly quotes file paths with special characters."""
        file_path = "src/special file with spaces.py"

        with (
            patch.object(self.git_repo, "_resolve_branch") as mock_resolve,
            patch.object(self.git_repo, "_git_output") as mock_git_output,
        ):

            mock_resolve.side_effect = lambda x: f"resolved_{x}"
            mock_git_output.return_value = ""

            self.git_repo.get_commits("branch1", "branch2", file_path)

            # Verify the file path was properly quoted in the git command
            called_cmd = mock_git_output.call_args[0][0]
            assert "'src/special file with spaces.py'" in called_cmd

    def test_get_commits_sorting(self):
        """Test get_commits returns commits sorted by date (newest first)."""
        # Mix up the dates to ensure sorting is working
        mock_output = """middle|Author 2|2025-01-15T12:00:00Z|Middle commit|||COMMIT_END|||oldest|Author 3|2025-01-14T10:00:00Z|Oldest commit|||COMMIT_END|||newest|Author 1|2025-01-16T14:00:00Z|Newest commit|||COMMIT_END|||"""

        with (
            patch.object(self.git_repo, "_resolve_branch") as mock_resolve,
            patch.object(self.git_repo, "_git_output") as mock_git_output,
        ):

            mock_resolve.side_effect = lambda x: f"resolved_{x}"
            mock_git_output.return_value = mock_output

            commits = self.git_repo.get_commits("branch1", "branch2", "file.py")

            assert len(commits) == 3
            # Should be sorted newest first
            assert commits[0].commit_hash == "newest"
            assert commits[1].commit_hash == "middle"
            assert commits[2].commit_hash == "oldest"

            # Verify actual date ordering
            for i in range(len(commits) - 1):
                assert commits[i].date >= commits[i + 1].date
