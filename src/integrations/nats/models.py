from pydantic import BaseModel, ConfigDict


class SubmitJobRequest(BaseModel):
    """Payload for ``jobs.{job_id}.submit``.

    Attributes:
        id: Unique identifier for the job
        project: Project name (case-sensitive, maps to directory)
        prompt: Multi-line prompt text to be written to prompts/{id}
    """

    model_config = ConfigDict(extra="ignore")

    id: str = ""
    project: str = ""
    prompt: str = ""


class ListSkillsRequest(BaseModel):
    """Payload for ``jobs.{job_id}.list-skills``. Currently no fields."""

    model_config = ConfigDict(extra="ignore")
