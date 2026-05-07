"""Split markdown text into Slack-message-sized chunks.

Slack rejects messages whose markdown content exceeds 12 000 characters
in a single block, and a message can hold at most one such block of
text. This module provides :func:`split_markdown_for_slack`, which
splits a long markdown string into chunks that each fit Slack's
per-message limit while preserving structure as much as possible.

Splitting strategy, in order of preference:

    1. ``# `` ... ``###### `` heading boundaries (H1 → H6)
    2. Paragraph break (``\\n\\n``)
    3. Line break (``\\n``)
    4. Hard character cut (last resort)

Code-fenced blocks (``` ``` ```) are kept atomic — heading, paragraph,
and line boundaries inside a fence are never used as splits. The single
exception is when a fenced block is itself larger than the limit, in
which case it is split inside its body at the latest paragraph break
that fits, falling back to a line break and then a hard char cut, with
the fence opener and closer re-emitted on both halves.

Line endings are normalized to ``\\n`` on input. ``\\r\\n`` becomes
``\\n``, any remaining ``\\r`` becomes ``\\n``, so ``\\r\\n\\r\\n`` and
``\\r\\r`` both reduce to ``\\n\\n`` (a paragraph break).
"""

from __future__ import annotations

import re

SLACK_MAX_BLOCK_CHARS = 12000

# Splitter levels in descending order of preference. Each entry is
# ``(needle, skip)`` where ``needle`` is searched for in the text and
# ``skip`` is the number of characters at the start of the match that
# belong to the *separator* — i.e. they stay attached to the previous
# chunk so that the next chunk begins with the heading marker (or with
# the first character after the paragraph/line break).
_LEVELS: list[tuple[str, int]] = [
    ("\n# ", 1),
    ("\n## ", 1),
    ("\n### ", 1),
    ("\n#### ", 1),
    ("\n##### ", 1),
    ("\n###### ", 1),
    ("\n\n", 2),
    ("\n", 1),
]

_FENCE_LINE_RE = re.compile(r"^\s*```(\S*)\s*$")


def split_markdown_for_slack(
    text: str, max_chars: int = SLACK_MAX_BLOCK_CHARS
) -> list[str]:
    """Split ``text`` into chunks that each fit one Slack markdown block.

    Returns a list of stripped chunks, each at most ``max_chars`` long.
    Empty or whitespace-only input returns an empty list. See the module
    docstring for the splitting strategy.
    """
    text = _normalize_line_endings(text)
    if not text.strip():
        return []
    if len(text) <= max_chars:
        return [text.strip()]
    chunks = _split_recursive(text, max_chars)
    return [c.strip() for c in chunks if c.strip()]


def _normalize_line_endings(text: str) -> str:
    """Normalize CRLF, CR, and runs of CR to LF.

    After this, ``\\r\\n``, ``\\r``, ``\\r\\r`` and ``\\r\\n\\r\\n`` all
    reduce to ``\\n`` or ``\\n\\n``, so the rest of the splitter only
    has to deal with ``\\n``.
    """
    if "\r" not in text:
        return text
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _split_recursive(text: str, max_chars: int) -> list[str]:
    """Split ``text`` using progressively finer splitters until each
    chunk fits ``max_chars`` or every level is exhausted.

    Fence ranges are computed once per ``text``; the level loop runs
    inline rather than recursing per level so the same input is never
    re-tokenized for fences.
    """
    if len(text) <= max_chars:
        return [text]

    fence_ranges = _find_fence_ranges(text)
    chunks: list[str] | None = None
    for needle, skip in _LEVELS:
        boundaries = _find_boundaries(text, needle, skip, fence_ranges)
        if not boundaries:
            continue
        candidate = _greedy_pack(text, boundaries, max_chars)
        # Only commit to a level if it actually divided the text;
        # boundaries at the very edges of ``text`` produce a single
        # chunk and we'd loop forever recursing on the same input.
        if len(candidate) > 1:
            chunks = candidate
            break
    if chunks is None:
        return _split_oversized(text, max_chars)

    out: list[str] = []
    for chunk in chunks:
        if len(chunk) > max_chars:
            out.extend(_split_recursive(chunk, max_chars))
        else:
            out.append(chunk)
    return out


def _find_fence_ranges(text: str) -> list[tuple[int, int]]:
    """Return ``(start, end)`` offsets for each fenced code block.

    Each range covers the open fence line through the close fence line,
    inclusive. If a fence is opened but never closed (malformed input),
    its range extends to the end of the text.
    """
    ranges: list[tuple[int, int]] = []
    in_fence = False
    fence_start = 0
    offset = 0
    lines = text.split("\n")
    for i, line in enumerate(lines):
        is_last = i == len(lines) - 1
        line_len = len(line) + (0 if is_last else 1)
        if _FENCE_LINE_RE.match(line):
            if not in_fence:
                in_fence = True
                fence_start = offset
            else:
                in_fence = False
                ranges.append((fence_start, offset + line_len))
        offset += line_len
    if in_fence:
        ranges.append((fence_start, len(text)))
    return ranges


def _is_strictly_inside(pos: int, ranges: list[tuple[int, int]]) -> bool:
    """True if ``pos`` lies strictly inside any range.

    Positions equal to a range's start or end are *not* strictly inside,
    so splitting right before a fence opener or right after a fence
    closer is allowed.
    """
    return any(start < pos < end for start, end in ranges)


def _find_boundaries(
    text: str,
    needle: str,
    skip: int,
    fence_ranges: list[tuple[int, int]],
) -> list[int]:
    """Return offsets at which ``text`` may be split.

    A boundary is the offset of the first content character of the next
    chunk (i.e. ``match_pos + skip``). Boundaries that fall strictly
    inside a fenced range are excluded so we never split mid-fence.
    """
    boundaries: list[int] = []
    start = 0
    while True:
        pos = text.find(needle, start)
        if pos == -1:
            break
        boundary = pos + skip
        if not _is_strictly_inside(boundary, fence_ranges):
            boundaries.append(boundary)
        start = pos + 1
    return boundaries


def _greedy_pack(text: str, boundaries: list[int], max_chars: int) -> list[str]:
    """Greedily pack ``text`` into chunks at the given boundary offsets.

    Emits the longest possible substrings of ``text`` such that each is
    ``<= max_chars`` whenever possible. A chunk may still exceed
    ``max_chars`` if a single segment between consecutive boundaries is
    itself oversized — the caller is responsible for recursing on those.
    """
    points = [0, *boundaries, len(text)]
    chunks: list[str] = []
    cur_start = points[0]
    cur_end = points[0]
    for next_end in points[1:]:
        if next_end == cur_end:
            continue
        if next_end - cur_start <= max_chars:
            cur_end = next_end
        else:
            if cur_end > cur_start:
                chunks.append(text[cur_start:cur_end])
            cur_start = cur_end
            cur_end = next_end
    if cur_end > cur_start:
        chunks.append(text[cur_start:cur_end])
    return chunks


def _split_oversized(text: str, max_chars: int) -> list[str]:
    """Last-resort split for chunks no splitter level could break.

    If the chunk is a single fenced code block, split it inside its
    body and re-emit the fence on both halves. Otherwise hard-cut at
    ``max_chars``.
    """
    if _is_fenced_block(text):
        return _split_oversized_fence(text, max_chars)
    return _hard_char_split(text, max_chars)


def _is_fenced_block(text: str) -> bool:
    """True if ``text`` is exactly one complete fenced code block."""
    stripped = text.strip()
    if not stripped:
        return False
    lines = stripped.split("\n")
    if len(lines) < 2:
        return False
    if not _FENCE_LINE_RE.match(lines[0]):
        return False
    if not _FENCE_LINE_RE.match(lines[-1]):
        return False
    return all(not _FENCE_LINE_RE.match(line) for line in lines[1:-1])


def _split_oversized_fence(chunk: str, max_chars: int) -> list[str]:
    """Split a single oversized fenced code block.

    Picks a paragraph break inside the body that fits the budget,
    falling back to a line break and then a hard char cut. The fence
    opener and closer are re-emitted on each output chunk so all
    pieces remain valid fenced blocks.
    """
    lines = chunk.strip().split("\n")
    fence_open = lines[0]
    fence_close = lines[-1]
    body = "\n".join(lines[1:-1])

    # Reassembled chunk shape: ``<open>\n<body>\n<close>``.
    overhead = len(fence_open) + len(fence_close) + 2
    body_budget = max_chars - overhead
    if body_budget <= 0 or len(body) <= body_budget:
        return [chunk]

    out: list[str] = []
    while len(body) > body_budget:
        split_at, sep_len = _find_fence_body_split(body, body_budget)
        out.append(f"{fence_open}\n{body[:split_at]}\n{fence_close}")
        body = body[split_at + sep_len :]
    out.append(f"{fence_open}\n{body}\n{fence_close}")
    return out


def _find_fence_body_split(body: str, budget: int) -> tuple[int, int]:
    """Pick a split point inside a fenced body within ``budget``.

    Returns ``(split_index, separator_length)``. Prefers ``\\n\\n``,
    then ``\\n``, then a hard char cut.
    """
    idx = body.rfind("\n\n", 0, budget + 1)
    if idx != -1:
        return idx, 2
    idx = body.rfind("\n", 0, budget + 1)
    if idx != -1:
        return idx, 1
    return budget, 0


def _hard_char_split(text: str, max_chars: int) -> list[str]:
    """Split ``text`` into fixed-size chunks of ``max_chars`` chars each."""
    return [text[i : i + max_chars] for i in range(0, len(text), max_chars)]
