"""Test fixtures and mock setup for platform tests.

Mocks the dev-agents framework imports (core.message, core.log, etc.)
so tests can run without the full dev-agents package installed.

We also replace the real ``integrations`` package init (which eagerly imports
all providers and their heavy dependencies) with a lightweight stub that only
contains the ``platforms`` sub-package.
"""

import sys
import types
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# 1. Stub out core.* framework modules
# ---------------------------------------------------------------------------

_core = types.ModuleType("core")
_core_message = types.ModuleType("core.message")
_core_log = types.ModuleType("core.log")
_core_hooks = types.ModuleType("core.hooks")
_core_hooks.hooks = MagicMock(return_value=MagicMock())
_core_agents = types.ModuleType("core.agents")
_core_agents_context = types.ModuleType("core.agents.context")


class _BaseMessage:
    """Minimal BaseMessage stub for testing."""
    pass


class _MessageList:
    """Minimal MessageList stub for testing."""
    def __init__(self, messages=None):
        self._messages = list(messages or [])

    def __len__(self):
        return len(self._messages)

    def __iter__(self):
        return iter(self._messages)


_core_message.BaseMessage = _BaseMessage
_core_message.MessageList = _MessageList

_logger = MagicMock()
_core_log.get_logger = MagicMock(return_value=_logger)
_core_log.setup_thread_logging = MagicMock()

_core_config = types.ModuleType("core.config")
_core_config.BaseConfig = MagicMock
_core_config.get_default_config = MagicMock(return_value=MagicMock())

_core_prompts = types.ModuleType("core.prompts")
_core_prompts.BasePrompts = MagicMock
_core_prompts.get_default_prompts = MagicMock(return_value=MagicMock())

_core_protocols = types.ModuleType("core.protocols")
_core_protocols_agent = types.ModuleType("core.protocols.agent_protocols")
_core_protocols_agent.AgentExecutionContext = type("AgentExecutionContext", (), {})

_core_agents_service = types.ModuleType("core.agents.service")
_core_agents_service.AgentService = MagicMock

_agents = types.ModuleType("agents")
_agents_agents = types.ModuleType("agents.agents")
_agents_gitchatbot = types.ModuleType("agents.agents.gitchatbot")
_agents_gitchatbot_agent = types.ModuleType("agents.agents.gitchatbot.agent")
_agents_gitchatbot_agent.AGENT_NAME = "gitchatbot"
_agents_gitchatbot_agent.GitChatbotAgent = MagicMock

sys.modules["core"] = _core
sys.modules["core.message"] = _core_message
sys.modules["core.log"] = _core_log
sys.modules["core.hooks"] = _core_hooks
sys.modules["core.config"] = _core_config
sys.modules["core.prompts"] = _core_prompts
sys.modules["core.protocols"] = _core_protocols
sys.modules["core.protocols.agent_protocols"] = _core_protocols_agent
sys.modules["core.agents"] = _core_agents
sys.modules["core.agents.context"] = _core_agents_context
sys.modules["core.agents.service"] = _core_agents_service
sys.modules["agents"] = _agents
sys.modules["agents.agents"] = _agents_agents
sys.modules["agents.agents.gitchatbot"] = _agents_gitchatbot
sys.modules["agents.agents.gitchatbot.agent"] = _agents_gitchatbot_agent

# ---------------------------------------------------------------------------
# 2. Replace the real integrations package with a lightweight version
#    so importing integrations.platforms doesn't pull in bitbucket/github/etc.
# ---------------------------------------------------------------------------

# Remove any cached real integrations module
for key in list(sys.modules.keys()):
    if key == "integrations" or key.startswith("integrations."):
        del sys.modules[key]

_integrations = types.ModuleType("integrations")
_integrations.__path__ = []  # make it a package
sys.modules["integrations"] = _integrations

# Now let Python discover integrations.platforms from the source tree
import importlib
import os

_src_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "src")
_platforms_path = os.path.join(_src_dir, "integrations", "platforms")

if os.path.isdir(_platforms_path):
    _integrations.__path__.append(os.path.join(_src_dir, "integrations"))
