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


"""Slack message consumer that uses the agent architecture."""
from agents.agents.gitchatbot.agent import GitChatbotAgent, AGENT_NAME
from core.agents.service import AgentService
from core.config import BaseConfig
from core.log import get_logger, set_context_token, reset_context_token
from core.message import MessageList
from core.prompts import get_default_prompts
from core.protocols.message_consumer_protocols import MessageConsumer
from entrypoints.slack_models.agent_context import SlackAgentContext
from integrations.slack.slack_client_service import SlackClientService

logger = get_logger("AgentMessageConsumer")


class AgentMessageConsumer(MessageConsumer):
    """Message consumer that processes messages using the agent architecture.

    Replaces DummyMessageConsumer with agent-based processing.
    Creates appropriate agent contexts and orchestrates agent execution.
    """

    def __init__(self, slack_client: SlackClientService, config: BaseConfig):
        self.slack_client = slack_client
        self.config = config
        self.agent_service = AgentService()

        # Register available agents
        self._register_agents()

        logger.info("Initialized AgentMessageConsumer with agent architecture")

    def _register_agents(self) -> None:
        """Register available agents with the service."""

        # Register chatbot agent factory function
        def create_chatbot_agent():
            return GitChatbotAgent

        self.agent_service.register_agent(AGENT_NAME, create_chatbot_agent)
        logger.info("Registered agents: " + AGENT_NAME)

    async def consume(self, messages: MessageList) -> None:
        """Process messages using the agent architecture.

        Args:
            messages: MessageList containing messages to process
        """
        logger.info(f"AgentMessageConsumer received {len(messages)} messages")

        if not messages:
            logger.info("No messages to process")
            return

        try:
            # Process messages directly (already filtered to single thread by service)
            if messages:
                first_message = messages.get_messages()[0]
                channel_id = first_message.channel_id
                thread_id = first_message.get_thread_id()

                # Set logging context for this thread
                context_token = set_context_token(thread_id)

                try:
                    logger.info(f"Processing thread: {thread_id} with {len(messages)} messages")

                    # Create Slack agent context
                    context = SlackAgentContext(
                        slack_client=self.slack_client,
                        channel_id=channel_id,
                        thread_ts=thread_id,
                        message_list=messages,  # Use messages directly, already loaded by service
                        config=self.config,
                        prompts=get_default_prompts()
                    )

                    # For now, always use the chatbot agent
                    # TODO: Add agent selection logic based on message content
                    agent_type = AGENT_NAME

                    # Execute agent using service - handles creation, execution, monitoring, and error handling
                    logger.info(f"Executing agent: {agent_type}")
                    await self.agent_service.execute_agent_by_type(agent_type, context)

                    logger.info(f"Agent execution completed: {agent_type} - {thread_id}")

                except Exception as e:
                    logger.error(f"Error processing thread {thread_id}: {str(e)}")

                    # Try to send error message to Slack if we have context
                    try:
                        if 'context' in locals():
                            await context.send_response(f"❌ Sorry, I encountered an error: {str(e)}")
                    except:
                        pass  # Best effort

                    raise
                finally:
                    # Always reset the logging context
                    reset_context_token(context_token)

        except Exception as e:
            logger.error(f"Error in AgentMessageConsumer: {str(e)}")
            raise