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


#!/usr/bin/env python3
"""AG-UI entrypoint for streaming agent events via HTTP."""

import asyncio
import traceback
from typing import AsyncGenerator

from ag_ui.core import (
    EventType,
    RunStartedEvent,
    RunFinishedEvent,
    RunErrorEvent,
    RunAgentInput
)
from ag_ui.encoder import EventEncoder
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

from agents.agents.gitchatbot.agent import AGENT_NAME
from core.agents.service import AgentService
from core.config import BaseConfig, get_default_config
from core.log import get_logger, setup_thread_logging, set_context_token, reset_context_token
from core.prompts import get_default_prompts
from entrypoints.ag_ui_models.agent_context import AGUIAgentContext
from entrypoints.ag_ui_models.message import convert_agui_messages_to_message_list

# Load environment variables
load_dotenv()

# Set up logging
base_config = get_default_config()
setup_thread_logging(base_config)
logger = get_logger("AGUIEntrypoint", level="INFO")

# Create FastAPI app
app = FastAPI(title="Agent AI API", description="Streaming agent execution API")

# Initialize agent service and register agents
agent_service = AgentService()

def _register_agents() -> None:
    """Register available agents with the service."""
    # Import and register the GitChatbot agent
    from agents.agents.gitchatbot.agent import GitChatbotAgent

    def create_chatbot_agent():
        return GitChatbotAgent

    agent_service.register_agent(AGENT_NAME, create_chatbot_agent)
    logger.info("Registered agents: " + AGENT_NAME)

# Register agents at startup
_register_agents()


class AGUIConfig:
    """Configuration for AG-UI service."""

    def __init__(self, base_config: BaseConfig):
        self._base_config = base_config
        self._config_data = base_config.get_config_data()

    def get_default_timeout(self) -> int:
        return int(self._base_config.get_value('agui.agent.defaultTimeout', 300))

    def get_default_agent_type(self) -> str:
        return self._base_config.get_value('agui.agent.defaultAgentType', AGENT_NAME)

    def get_max_message_length(self) -> int:
        return int(self._base_config.get_value('agui.agent.maxMessageLength', 10000))

    def get_server_host(self) -> str:
        return self._base_config.get_value('agui.server.host', '0.0.0.0')

    def get_server_port(self) -> int:
        return int(self._base_config.get_value('agui.server.port', 8000))

    def get_server_reload(self) -> bool:
        return bool(self._base_config.get_value('agui.server.reload', False))


@app.post("/agent")
async def run_agent(input_data: RunAgentInput, request: Request) -> StreamingResponse:
    """Run an agent and stream events back to client.

    Args:
        input_data: AG-UI RunAgentInput containing messages, tools, context, etc.
        request: FastAPI request object for header information

    Returns:
        StreamingResponse with Server-Sent Events containing agent execution progress
    """

    logger.info(f"Received agent run request: thread_id={input_data.thread_id}, run_id={input_data.run_id}")

    # Get configuration
    config_instance = AGUIConfig(base_config)

    if not input_data.thread_id or not input_data.run_id:
        logger.error("Missing required thread_id or run_id")
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Missing required thread_id or run_id")

    if not input_data.messages:
        logger.error("No messages provided in request")
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="At least one message is required")

    # Validate message length
    max_length = config_instance.get_max_message_length()
    for msg in input_data.messages:
        if hasattr(msg, 'content') and len(getattr(msg, 'content', '')) > max_length:
            logger.error(f"Message content exceeds maximum length: {len(msg.content)} > {max_length}")
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail=f"Message content exceeds maximum length of {max_length} characters")

    # Create event encoder based on client Accept header
    encoder = EventEncoder(accept=request.headers.get("accept"))

    async def event_generator() -> AsyncGenerator[str, None]:
        """Generator that yields AG-UI events as Server-Sent Events."""

        # Set logging context
        context_token = set_context_token(input_data.thread_id)

        try:
            # Start the run
            yield encoder.encode(RunStartedEvent(
                type=EventType.RUN_STARTED,
                thread_id=input_data.thread_id,
                run_id=input_data.run_id
            ))

            # Create event queue for agent context communication
            event_queue = asyncio.Queue()

            # Convert AG-UI messages to our internal format
            message_list = convert_agui_messages_to_message_list(
                input_data.messages,
                input_data.thread_id
            )

            # Create AG-UI agent context
            agui_context = AGUIAgentContext(
                message_list=message_list,
                config=base_config,
                prompts=get_default_prompts(),
                thread_id=input_data.thread_id,
                run_id=input_data.run_id,
                event_queue=event_queue
            )

            # Use existing config_instance
            agent_type = config_instance.get_default_agent_type()
            timeout = config_instance.get_default_timeout()

            logger.info(f"Executing agent: type={agent_type}, timeout={timeout}s")

            # Create task for agent execution
            agent_task = asyncio.create_task(
                agent_service.execute_agent_by_type(
                    agent_type=agent_type,
                    context=agui_context,
                    timeout_seconds=timeout
                )
            )

            # Stream events while agent is executing
            while not agent_task.done():
                try:
                    # Check for events with short timeout
                    event = await asyncio.wait_for(event_queue.get(), timeout=0.1)
                    yield encoder.encode(event)
                except asyncio.TimeoutError:
                    # No events, continue checking if agent is done
                    continue
                except Exception as e:
                    logger.error(f"Error consuming events: {str(e)}")
                    break

            # Agent execution finished, drain any remaining events
            while not event_queue.empty():
                try:
                    event = event_queue.get_nowait()
                    yield encoder.encode(event)
                except asyncio.QueueEmpty:
                    break

            # Check if agent task had an exception
            try:
                await agent_task  # This will raise if there was an exception
            except Exception as agent_error:
                logger.error(f"Agent execution failed: {str(agent_error)}")
                yield encoder.encode(RunErrorEvent(
                    type=EventType.RUN_ERROR,
                    message=f"Agent execution failed: {str(agent_error)}",
                    code="AGENT_EXECUTION_ERROR"
                ))
                return

            # Success - emit run finished event
            yield encoder.encode(RunFinishedEvent(
                type=EventType.RUN_FINISHED,
                thread_id=input_data.thread_id,
                run_id=input_data.run_id
            ))

            logger.info(f"Agent run completed successfully: {input_data.run_id}")

        except asyncio.TimeoutError:
            logger.error(f"Agent run timed out: {input_data.run_id}")
            yield encoder.encode(RunErrorEvent(
                type=EventType.RUN_ERROR,
                message="Agent execution timed out",
                code="TIMEOUT_ERROR"
            ))
        except asyncio.CancelledError:
            logger.info(f"Agent run cancelled: {input_data.run_id}")
            yield encoder.encode(RunErrorEvent(
                type=EventType.RUN_ERROR,
                message="Agent execution was cancelled",
                code="CANCELLED_ERROR"
            ))
        except ValueError as validation_error:
            logger.error(f"Invalid input data: {str(validation_error)}")
            yield encoder.encode(RunErrorEvent(
                type=EventType.RUN_ERROR,
                message=f"Invalid input: {str(validation_error)}",
                code="VALIDATION_ERROR"
            ))
        except Exception as unexpected_error:
            error_traceback = traceback.format_exc()
            logger.error(f"Unexpected error in agent run: {str(unexpected_error)}\\n{error_traceback}")
            yield encoder.encode(RunErrorEvent(
                type=EventType.RUN_ERROR,
                message=f"Unexpected error: {str(unexpected_error)}",
                code="INTERNAL_ERROR"
            ))

        finally:
            reset_context_token(context_token)

    return StreamingResponse(
        event_generator(),
        media_type=encoder.get_content_type()  # "text/event-stream"
    )




if __name__ == "__main__":
    import uvicorn

    logger.info("Starting AG-UI service")

    # Print release information if available
    try:
        with open("release.txt", "r") as f:
            release_info = f.read().strip()
            logger.info(f"Release information:\\n{release_info}")
    except FileNotFoundError:
        logger.info("No release information available")
    except Exception as release_error:
        logger.warning(f"Could not read release information: {release_error}")

    # Load configuration
    try:
        agui_config = AGUIConfig(base_config)
        host = agui_config.get_server_host()
        port = agui_config.get_server_port()
        reload = agui_config.get_server_reload()

        logger.info(f"AG-UI service starting on {host}:{port} (reload={reload})")
        logger.info("AG-UI service ready to accept requests")

        # Start the FastAPI server
        # Use import string when reload is enabled, direct app object otherwise
        uvicorn.run(
            "src.entrypoints.ag_ui_server:app" if reload else app,
            host=host,
            port=port,
            reload=reload,
            log_level="info"
        )
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
    except Exception as startup_error:
        logger.error(f"Failed to start AG-UI service: {str(startup_error)}")
        raise