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


"""Dev Agents - AI Agents for Agile Dev Teams.

This package provides AI agents for common development workflow automation including:
- Release notes generation from PRs
- PR review and guideline checking
- UI impact analysis and test note generation
- Code research and analysis
- and more

The agents are designed to integrate with Slack, Azure DevOps, GitLab, and other
development tools to provide consistent AI assistance across your development workflow.
"""

__version__ = "0.9.3"
__author__ = "Dev Agents Team"
__email__ = "dev@codeligence.com"

from core.config import BaseConfig
from core.prompts import BasePrompts

__all__ = [
    "BaseConfig",
    "BasePrompts",
]
