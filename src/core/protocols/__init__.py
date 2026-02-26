"""Protocol definitions for type-safe interfaces."""

from .agent_protocols import Agent, AgentExecutionContext
from .message_consumer_protocols import MessageConsumer
from .provider_protocols import (
    IssueModel,
    IssueProvider,
    PipelineListFilter,
    PipelineModel,
    PipelineProvider,
    PipelineSummaryModel,
    PullRequestModel,
    PullRequestProvider,
)

__all__ = [
    "Agent",
    "AgentExecutionContext",
    "MessageConsumer",
    "PullRequestProvider",
    "IssueProvider",
    "PipelineProvider",
    "PullRequestModel",
    "IssueModel",
    "PipelineModel",
    "PipelineListFilter",
    "PipelineSummaryModel",
]
