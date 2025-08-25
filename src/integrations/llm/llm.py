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


from pydantic_ai import Agent

from core.log import get_logger

logger = get_logger(logger_name="LLM", level="DEBUG")


def _create_agent(model_full_name):
    return Agent(
        model=model_full_name,
        output_type=str,
    )


def invoke_llm(prompt_text, model_full_name):
    logger.info(f"Invoking LLM with model={model_full_name}, prompt_text[:200]={prompt_text[:200]!r}")
    agent = _create_agent(model_full_name)
    result = agent.run_sync(prompt_text)
    return result.output


async def invoke_llm_async(prompt_text, model_full_name):
    logger.info(f"Invoking LLM async with model={model_full_name}, prompt_text[:200]={prompt_text[:200]!r}")
    agent = _create_agent(model_full_name)
    result = await agent.run(prompt_text)
    return result.output