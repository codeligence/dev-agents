"""Classification of Slack file attachments for multimodal agent input.

Slack supports uploading arbitrary file types, but a language model can only
consume a subset of them directly:

- **binary**: images and PDFs are forwarded as raw bytes via
  ``pydantic_ai.BinaryContent`` so the model can see them natively.
- **text**: text/code files are decoded and inlined into the prompt.
- **unsupported**: everything else (archives, office documents, audio, …) is
  represented by a short text marker instead of being downloaded.

Keeping this mapping in one place lets both the client service (which decides
whether to download bytes) and the message model (which builds the agent
content parts) agree on how a given mimetype is handled.
"""

from typing import Literal

AttachmentKind = Literal["binary", "text", "unsupported"]

# Mimetypes forwarded to the model as raw bytes (BinaryContent). Limited to the
# image and document formats the model accepts natively.
_BINARY_MIME_TYPES: frozenset[str] = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
        "application/pdf",
    }
)

# Non ``text/*`` mimetypes that still hold UTF-8 text and can be inlined.
_TEXT_MIME_TYPES: frozenset[str] = frozenset(
    {
        "application/json",
        "application/xml",
        "application/yaml",
        "application/x-yaml",
        "application/javascript",
        "application/typescript",
        "application/sql",
        "application/x-sh",
        "application/x-httpd-php",
        "application/graphql",
        "image/svg+xml",
    }
)


def classify_attachment(mimetype: str) -> AttachmentKind:
    """Return how an attachment with the given mimetype should be handled."""
    if mimetype in _BINARY_MIME_TYPES:
        return "binary"
    if mimetype.startswith("text/") or mimetype in _TEXT_MIME_TYPES:
        return "text"
    return "unsupported"
