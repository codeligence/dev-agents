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

