"""Tests for the markdown splitter used by Slack integration."""

import pytest

from integrations.slack.markdown_splitter import (
    SLACK_MAX_BLOCK_CHARS,
    split_markdown_for_slack,
)


class TestShortInputs:
    """Inputs at or under the limit are returned unchanged."""

    def test_short_text_returns_single_chunk(self) -> None:
        text = "# Hello\n\nA short paragraph."
        assert split_markdown_for_slack(text) == [text]

    def test_text_at_exact_limit_returns_single_chunk(self) -> None:
        text = "x" * SLACK_MAX_BLOCK_CHARS
        assert split_markdown_for_slack(text) == [text]

    @pytest.mark.parametrize("text", ["", "   ", "\n\n", "\n\n  \r\n\r\n"])
    def test_empty_input_returns_empty_list(self, text: str) -> None:
        assert split_markdown_for_slack(text) == []


class TestLineEndingNormalization:
    """All CR/LF variants reduce to LF before splitting."""

    def test_crlf_normalized_to_lf(self) -> None:
        a = "# H1\r\n\r\ncontent\r\n# H2\r\n\r\nmore"
        b = "# H1\n\ncontent\n# H2\n\nmore"
        assert split_markdown_for_slack(a) == split_markdown_for_slack(b)

    def test_cr_normalized_to_lf(self) -> None:
        a = "# H1\r\rcontent\r# H2\r\rmore"
        b = "# H1\n\ncontent\n# H2\n\nmore"
        assert split_markdown_for_slack(a) == split_markdown_for_slack(b)

    def test_crlf_split_at_h1_with_small_limit(self) -> None:
        text = "# First\r\nlots of body content here\r\n# Second\r\nmore body"
        chunks = split_markdown_for_slack(text, max_chars=40)
        assert len(chunks) == 2
        assert chunks[0].startswith("# First")
        assert chunks[1].startswith("# Second")


class TestHeadingSplits:
    """Heading boundaries are preferred from H1 down to H6."""

    def _two_section_text(self, marker: str) -> str:
        return f"{marker} First\nbody one\n{marker} Second\nbody two"

    @pytest.mark.parametrize("marker", ["#", "##", "###", "####", "#####", "######"])
    def test_split_at_each_heading_level(self, marker: str) -> None:
        text = self._two_section_text(marker)
        chunks = split_markdown_for_slack(text, max_chars=25)
        assert len(chunks) == 2
        assert chunks[0].startswith(f"{marker} First")
        assert chunks[1].startswith(f"{marker} Second")

    def test_h1_preferred_over_h2(self) -> None:
        text = (
            "# Top\n\n## Sub A\nbody a\n## Sub B\nbody b\n\n"
            "# Other\n\n## Sub C\nbody c"
        )
        chunks = split_markdown_for_slack(text, max_chars=60)
        # Should split at the second '# Other', not at any '## Sub'
        assert len(chunks) == 2
        assert chunks[0].startswith("# Top")
        assert chunks[1].startswith("# Other")

    def test_recursive_h1_too_big_descends_to_h2(self) -> None:
        big_a = "filler line\n" * 10
        big_b = "filler line\n" * 10
        text = f"# Only H1\n\n## Sub A\n{big_a}\n## Sub B\n{big_b}"
        chunks = split_markdown_for_slack(text, max_chars=80)
        # H1-only level produces one oversized chunk → recurses to H2
        assert len(chunks) >= 2
        assert any("## Sub A" in c for c in chunks)
        assert any("## Sub B" in c for c in chunks)


class TestParagraphAndLineSplits:
    """Falls back to paragraph and then line breaks when no headings exist."""

    def test_split_at_paragraph_when_no_headings(self) -> None:
        text = "para one is here.\n\npara two follows.\n\npara three closes."
        chunks = split_markdown_for_slack(text, max_chars=25)
        assert len(chunks) == 3
        assert chunks[0] == "para one is here."
        assert chunks[1] == "para two follows."
        assert chunks[2] == "para three closes."

    def test_split_at_line_when_no_paragraphs(self) -> None:
        text = "line one\nline two\nline three\nline four"
        chunks = split_markdown_for_slack(text, max_chars=18)
        assert all(len(c) <= 18 for c in chunks)
        # All lines must be present in document order
        assert "\n".join(chunks).count("line") == 4

    def test_hard_cut_when_one_giant_line(self) -> None:
        text = "x" * (SLACK_MAX_BLOCK_CHARS * 2 + 17)
        chunks = split_markdown_for_slack(text)
        assert len(chunks) == 3
        assert all(len(c) <= SLACK_MAX_BLOCK_CHARS for c in chunks)
        assert "".join(chunks) == text


class TestFenceSafety:
    """Boundaries inside code fences are never used."""

    def test_heading_inside_fence_is_not_a_split_point(self) -> None:
        text = (
            "intro paragraph here\n\n"
            "```bash\n"
            "# this is a comment, not a heading\n"
            "echo hello\n"
            "```\n\n"
            "# Real heading\n\n"
            "tail paragraph"
        )
        chunks = split_markdown_for_slack(text, max_chars=80)
        # The fenced '# this is a comment' must not start a chunk
        for chunk in chunks:
            assert not chunk.startswith("# this is a comment")
        # The real heading should start its own chunk
        assert any(c.startswith("# Real heading") for c in chunks)

    def test_fence_with_language_tag_atomic(self) -> None:
        # Short body so the whole fence fits in one chunk;
        # surrounding paragraphs force a paragraph-level split.
        body = "\n".join(f"l{i}" for i in range(8))
        text = (
            "a long intro paragraph that needs its own space\n\n"
            f"```python\n{body}\n```\n\n"
            "a long outro paragraph that needs its own space"
        )
        chunks = split_markdown_for_slack(text, max_chars=60)
        fence_chunk = next((c for c in chunks if "```python" in c), None)
        assert fence_chunk is not None
        assert "l5" in fence_chunk
        assert fence_chunk.rstrip().endswith("```")

    def test_split_right_before_fence_is_allowed(self) -> None:
        body = "x" * 200
        text = f"intro paragraph\n\n```\n{body}\n```"
        chunks = split_markdown_for_slack(text, max_chars=80)
        # We expect intro to be one chunk and the fence its own chunk
        assert any(c.startswith("```") and c.rstrip().endswith("```") for c in chunks)


class TestOversizedFence:
    """Fences larger than the limit are split into valid sub-fences."""

    def test_oversized_fence_splits_at_paragraph_break(self) -> None:
        # Body has clear paragraph breaks; the fence as a whole exceeds 100.
        para_a = "line a1\nline a2\nline a3"
        para_b = "line b1\nline b2\nline b3"
        para_c = "line c1\nline c2\nline c3"
        body = f"{para_a}\n\n{para_b}\n\n{para_c}"
        text = f"```python\n{body}\n```"
        chunks = split_markdown_for_slack(text, max_chars=60)

        assert len(chunks) >= 2
        for chunk in chunks:
            assert len(chunk) <= 60
            # Each chunk is itself a valid fenced block
            assert chunk.startswith("```python")
            assert chunk.rstrip().endswith("```")

    def test_oversized_fence_preserves_language_tag(self) -> None:
        body = "\n\n".join("paragraph " + ("z" * 30) for _ in range(5))
        text = f"```rust\n{body}\n```"
        chunks = split_markdown_for_slack(text, max_chars=80)
        assert len(chunks) >= 2
        for chunk in chunks:
            assert chunk.startswith("```rust")

    def test_oversized_fence_recursive_split(self) -> None:
        # Force three sub-fences from one giant fence
        body = "\n\n".join("p" + ("y" * 30) for _ in range(8))
        text = f"```\n{body}\n```"
        chunks = split_markdown_for_slack(text, max_chars=70)
        assert len(chunks) >= 3
        for chunk in chunks:
            assert len(chunk) <= 70
            assert chunk.startswith("```")
            assert chunk.rstrip().endswith("```")

    def test_oversized_fence_no_paragraph_falls_to_line(self) -> None:
        body = "\n".join(f"line{i:03d}" for i in range(50))
        text = f"```\n{body}\n```"
        chunks = split_markdown_for_slack(text, max_chars=80)
        assert len(chunks) >= 2
        for chunk in chunks:
            assert len(chunk) <= 80
            assert chunk.startswith("```")
            assert chunk.rstrip().endswith("```")

    def test_oversized_fence_handles_crlf_paragraph(self) -> None:
        a = "first\r\nblock"
        b = "second\r\nblock"
        c = "third\r\nblock"
        text = f"```\r\n{a}\r\n\r\n{b}\r\n\r\n{c}\r\n```"
        chunks = split_markdown_for_slack(text, max_chars=40)
        assert len(chunks) >= 2
        for chunk in chunks:
            assert chunk.startswith("```")
            assert chunk.rstrip().endswith("```")


class TestDocumentOrder:
    """Chunks are returned in document order."""

    def test_chunks_preserve_heading_order(self) -> None:
        text = "# A\nbody a\n# B\nbody b\n# C\nbody c\n# D\nbody d"
        chunks = split_markdown_for_slack(text, max_chars=12)
        markers = ("# A", "# B", "# C", "# D")
        positions = []
        for marker in markers:
            for i, chunk in enumerate(chunks):
                if marker in chunk:
                    positions.append(i)
                    break
        assert len(positions) == len(markers)
        assert positions == sorted(positions)

    def test_all_chunks_within_limit(self) -> None:
        text = (
            "# First\n"
            + ("body line\n" * 200)
            + "# Second\n"
            + ("body line\n" * 200)
            + "# Third\n"
            + ("body line\n" * 200)
        )
        chunks = split_markdown_for_slack(text, max_chars=500)
        assert all(len(c) <= 500 for c in chunks)
        assert len(chunks) >= 3
