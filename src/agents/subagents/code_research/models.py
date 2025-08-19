from dataclasses import dataclass
from typing import Optional


@dataclass 
class CodeResearchDependencies:
    """Dependencies for code research agent operations."""
    git_ref: str
    repo_path: Optional[str] = None
    
    def __post_init__(self):
        if self.repo_path is None:
            self.repo_path = "."