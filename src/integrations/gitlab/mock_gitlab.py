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


import os
import json
from typing import Dict, Any, List
from .models import MergeRequest, Issue


def _load_mock_file(file_path: str) -> Dict[str, Any]:
    """Helper function to load mock data from a JSON file.
    
    Args:
        file_path: Path to the mock JSON file
        
    Returns:
        Loaded JSON data as dictionary
    """
    try:
        # Get the directory of this file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        full_path = os.path.join(current_dir, file_path)
        
        with open(full_path, 'r', encoding='utf-8') as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading mock file {file_path}: {e}")
        return {}


def mock_fetch_merge_request(merge_request_id: str) -> MergeRequest:
    """Fetch mock merge request data.
    
    Args:
        merge_request_id: Merge request ID to fetch
        
    Returns:
        MergeRequest object with mock data
    """
    # Load mock data from JSON files
    mr_data = _load_mock_file('mocks/gitlab_mr.json')
    commits_data = _load_mock_file('mocks/gitlab_commits.json')
    
    # Update the ID to match the requested ID
    if mr_data:
        mr_data['iid'] = int(merge_request_id)
    
    return MergeRequest(mr_data, commits_data)


def mock_fetch_issue(issue_id: str) -> Issue:
    """Fetch mock issue data.
    
    Args:
        issue_id: Issue ID to fetch
        
    Returns:
        Issue object with mock data
    """
    # Load mock data from JSON file
    issue_data = _load_mock_file('mocks/gitlab_issue.json')
    
    # Update the ID to match the requested ID
    if issue_data:
        issue_data['iid'] = int(issue_id)
    
    return Issue(issue_data)