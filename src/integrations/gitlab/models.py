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


from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup


class Person:
    """Represents a GitLab user."""
    
    def __init__(self, data: Dict[str, Any]):
        """Initialize with GitLab API user data.
        
        Args:
            data: GitLab API user data dictionary
        """
        self.data = data
    
    def get_name(self) -> str:
        """Get user's full name."""
        return self.data.get('name', '')
    
    def get_username(self) -> str:
        """Get user's username."""
        return self.data.get('username', '')
    
    def get_id(self) -> int:
        """Get user's ID."""
        return self.data.get('id', 0)


class MergeRequest:
    """Represents a GitLab merge request."""
    
    def __init__(self, mr_data: Dict[str, Any], commits_data: List[Dict[str, Any]]):
        """Initialize with GitLab API merge request and commits data.
        
        Args:
            mr_data: GitLab API merge request data dictionary
            commits_data: GitLab API commits data list
        """
        self.mr_data = mr_data
        self.commits_data = commits_data
    
    def get_id(self) -> str:
        """Get merge request ID."""
        return str(self.mr_data.get('iid', ''))
    
    def get_title(self) -> str:
        """Get merge request title."""
        return self.mr_data.get('title', '')
    
    def get_description(self) -> str:
        """Get merge request description."""
        return self.mr_data.get('description', '')
    
    def get_state(self) -> str:
        """Get merge request state."""
        return self.mr_data.get('state', '')
    
    def get_source_branch(self) -> str:
        """Get source branch name."""
        return self.mr_data.get('source_branch', '')
    
    def get_target_branch(self) -> str:
        """Get target branch name."""
        return self.mr_data.get('target_branch', '')
    
    def get_author(self) -> Person:
        """Get the author of the merge request."""
        author_data = self.mr_data.get('author', {})
        return Person(author_data)
    
    def get_merge_commit_id(self) -> Optional[str]:
        """Get merge commit SHA."""
        return self.mr_data.get('merge_commit_sha')
    
    def get_source_commit_id(self) -> str:
        """Get source commit SHA."""
        return self.mr_data.get('sha', '')
    
    def get_target_commit_id(self) -> Optional[str]:
        """Get target commit SHA from diff_refs."""
        diff_refs = self.mr_data.get('diff_refs', {})
        return diff_refs.get('base_sha') if diff_refs else None
    
    def get_created_at(self) -> str:
        """Get creation date."""
        return self.mr_data.get('created_at', '')
    
    def get_updated_at(self) -> str:
        """Get last update date."""
        return self.mr_data.get('updated_at', '')
    
    def get_merged_at(self) -> Optional[str]:
        """Get merge date."""
        return self.mr_data.get('merged_at')
    
    def get_commits(self) -> List[Dict[str, Any]]:
        """Get commits associated with the merge request."""
        return self.commits_data
    
    def get_html_description(self) -> str:
        """Get HTML description."""
        # In a real implementation, this would convert markdown to HTML
        return self.get_description()
    
    def get_plain_description(self) -> str:
        """Get plain text description (remove any HTML)."""
        html_desc = self.get_html_description()
        if html_desc:
            # Use BeautifulSoup to strip HTML tags
            soup = BeautifulSoup(html_desc, 'html.parser')
            return soup.get_text()
        return ''
    
    def get_web_url(self) -> str:
        """Get web URL of the merge request."""
        return self.mr_data.get('web_url', '')
    
    def get_composed_MR_info(self) -> str:
        """Get composed merge request information for context."""
        author = self.get_author()
        author_name = f"{author.get_name()} (@{author.get_username()})" if author else "Unknown"
        
        composed_info = f"Merge Request #{self.get_id()}: {self.get_title()}\n"
        composed_info += f"Author: {author_name}\n"
        composed_info += f"State: {self.get_state()}\n"
        composed_info += f"Source Branch: {self.get_source_branch()}\n"
        composed_info += f"Target Branch: {self.get_target_branch()}\n"
        composed_info += f"Created: {self.get_created_at()}\n"
        composed_info += f"Updated: {self.get_updated_at()}\n"
        
        if self.get_merged_at():
            composed_info += f"Merged: {self.get_merged_at()}\n"
        
        composed_info += f"\nDescription:\n{self.get_plain_description()}\n"
        
        composed_info += "\nCommits:\n"
        for commit in self.get_commits():
            sha = commit.get('id', '')[:8]
            message = commit.get('title', '')
            author = commit.get('author_name', '')
            composed_info += f"- {sha} ({author}): {message}\n"
        
        return composed_info


class Issue:
    """Represents a GitLab issue."""
    
    def __init__(self, issue_data: Dict[str, Any]):
        """Initialize with GitLab API issue data.
        
        Args:
            issue_data: GitLab API issue data dictionary
        """
        self.issue_data = issue_data
    
    def get_id(self) -> str:
        """Get issue ID."""
        return str(self.issue_data.get('iid', ''))
    
    def get_title(self) -> str:
        """Get issue title."""
        return self.issue_data.get('title', '')
    
    def get_description(self) -> str:
        """Get issue description."""
        return self.issue_data.get('description', '')
    
    def get_state(self) -> str:
        """Get issue state."""
        return self.issue_data.get('state', '')
    
    def get_author(self) -> Person:
        """Get the author of the issue."""
        author_data = self.issue_data.get('author', {})
        return Person(author_data)
    
    def get_created_at(self) -> str:
        """Get creation date."""
        return self.issue_data.get('created_at', '')
    
    def get_updated_at(self) -> str:
        """Get last update date."""
        return self.issue_data.get('updated_at', '')
    
    def get_closed_at(self) -> Optional[str]:
        """Get close date."""
        return self.issue_data.get('closed_at')
    
    def get_html_description(self) -> str:
        """Get HTML description."""
        # In a real implementation, this would convert markdown to HTML
        return self.get_description()
    
    def get_plain_description(self) -> str:
        """Get plain text description (remove any HTML)."""
        html_desc = self.get_html_description()
        if html_desc:
            # Use BeautifulSoup to strip HTML tags
            soup = BeautifulSoup(html_desc, 'html.parser')
            return soup.get_text()
        return ''
    
    def get_web_url(self) -> str:
        """Get web URL of the issue."""
        return self.issue_data.get('web_url', '')
    
    def get_composed_issue_info(self) -> str:
        """Get composed issue information for context."""
        author = self.get_author()
        author_name = f"{author.get_name()} (@{author.get_username()})" if author else "Unknown"
        
        composed_info = f"Issue #{self.get_id()}: {self.get_title()}\n"
        composed_info += f"Author: {author_name}\n"
        composed_info += f"State: {self.get_state()}\n"
        composed_info += f"Created: {self.get_created_at()}\n"
        composed_info += f"Updated: {self.get_updated_at()}\n"
        
        if self.get_closed_at():
            composed_info += f"Closed: {self.get_closed_at()}\n"
        
        composed_info += f"\nDescription:\n{self.get_plain_description()}\n"
        
        return composed_info