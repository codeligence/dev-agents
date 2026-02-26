from dataclasses import dataclass


@dataclass
class NatsJob:
    """Model for incoming NATS job messages.

    Attributes:
        id: Unique identifier for the job
        project: Project name (case-sensitive, maps to directory)
        prompt: Multi-line prompt text to be written to prompts/{id}
    """

    id: str
    project: str
    prompt: str
