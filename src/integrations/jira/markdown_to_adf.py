"""Markdown to ADF (Atlassian Document Format) converter.

Converts Markdown content to ADF JSON structure for use with Jira REST API v3.

Adapted from mcp_jira (https://github.com/codingthefuturewithai/mcp_jira)
Original code licensed under MIT License
"""

from typing import Any

from markdown_it import MarkdownIt
from markdown_it.token import Token


class MarkdownToADFConverter:
    """Converts Markdown content to Atlassian Document Format (ADF)."""

    def __init__(self) -> None:
        """Initialize the converter with markdown-it parser."""
        self.md = MarkdownIt(
            "commonmark",
            {
                "typographer": True,
                "linkify": True,
                "html": False,
            },
        )

    def convert(self, markdown_content: str) -> dict[str, Any]:
        """Convert Markdown content to ADF JSON structure.

        Args:
            markdown_content: Markdown text to convert

        Returns:
            ADF document as dictionary
        """
        tokens = self.md.parse(markdown_content)

        adf_doc: dict[str, Any] = {
            "version": 1,
            "type": "doc",
            "content": [],
        }

        adf_doc["content"] = self._process_tokens(tokens)

        return adf_doc

    def _process_tokens(self, tokens: list[Token]) -> list[dict[str, Any]]:
        """Process a list of markdown-it tokens into ADF nodes.

        Args:
            tokens: List of markdown-it tokens

        Returns:
            List of ADF content nodes
        """
        content: list[dict[str, Any]] = []
        i = 0

        while i < len(tokens):
            token = tokens[i]

            if token.type == "heading_open":
                heading_node, consumed = self._process_heading(tokens, i)
                content.append(heading_node)
                i += consumed
            elif token.type == "paragraph_open":
                paragraph_node, consumed = self._process_paragraph(tokens, i)
                content.append(paragraph_node)
                i += consumed
            elif token.type == "bullet_list_open":
                list_node, consumed = self._process_bullet_list(tokens, i)
                content.append(list_node)
                i += consumed
            elif token.type == "ordered_list_open":
                list_node, consumed = self._process_ordered_list(tokens, i)
                content.append(list_node)
                i += consumed
            elif token.type == "blockquote_open":
                quote_node, consumed = self._process_blockquote(tokens, i)
                content.append(quote_node)
                i += consumed
            elif token.type == "fence" or token.type == "code_block":
                code_node = self._process_code_block(token)
                content.append(code_node)
                i += 1
            elif token.type == "table_open":
                table_node, consumed = self._process_table(tokens, i)
                content.append(table_node)
                i += consumed
            elif token.type == "hr":
                content.append({"type": "rule"})
                i += 1
            else:
                i += 1

        return content

    def _process_heading(
        self, tokens: list[Token], start_idx: int
    ) -> tuple[dict[str, Any], int]:
        """Process heading tokens into ADF heading node.

        Args:
            tokens: List of all tokens
            start_idx: Starting index of the heading

        Returns:
            Tuple of (ADF heading node, number of tokens consumed)
        """
        open_token = tokens[start_idx]
        level = int(open_token.tag[1])

        inline_content: list[dict[str, Any]] = []
        consumed = 1

        for i in range(start_idx + 1, len(tokens)):
            token = tokens[i]
            if token.type == "heading_close":
                consumed = i - start_idx + 1
                break
            elif token.type == "inline":
                inline_content = self._process_inline_content(token)

        return {
            "type": "heading",
            "attrs": {"level": level},
            "content": inline_content,
        }, consumed

    def _process_paragraph(
        self, tokens: list[Token], start_idx: int
    ) -> tuple[dict[str, Any], int]:
        """Process paragraph tokens into ADF paragraph node.

        Args:
            tokens: List of all tokens
            start_idx: Starting index of the paragraph

        Returns:
            Tuple of (ADF paragraph node, number of tokens consumed)
        """
        inline_content: list[dict[str, Any]] = []
        consumed = 1

        for i in range(start_idx + 1, len(tokens)):
            token = tokens[i]
            if token.type == "paragraph_close":
                consumed = i - start_idx + 1
                break
            elif token.type == "inline":
                inline_content = self._process_inline_content(token)

        return {"type": "paragraph", "content": inline_content}, consumed

    def _process_bullet_list(
        self, tokens: list[Token], start_idx: int
    ) -> tuple[dict[str, Any], int]:
        """Process bullet list tokens into ADF bulletList node.

        Args:
            tokens: List of all tokens
            start_idx: Starting index of the list

        Returns:
            Tuple of (ADF bulletList node, number of tokens consumed)
        """
        list_items: list[dict[str, Any]] = []
        consumed = 1
        i = start_idx + 1

        while i < len(tokens):
            token = tokens[i]
            if token.type == "bullet_list_close":
                consumed = i - start_idx + 1
                break
            elif token.type == "list_item_open":
                list_item, item_consumed = self._process_list_item(tokens, i)
                list_items.append(list_item)
                i += item_consumed
            else:
                i += 1

        return {"type": "bulletList", "content": list_items}, consumed

    def _process_ordered_list(
        self, tokens: list[Token], start_idx: int
    ) -> tuple[dict[str, Any], int]:
        """Process ordered list tokens into ADF orderedList node.

        Args:
            tokens: List of all tokens
            start_idx: Starting index of the list

        Returns:
            Tuple of (ADF orderedList node, number of tokens consumed)
        """
        open_token = tokens[start_idx]
        list_items: list[dict[str, Any]] = []
        consumed = 1
        i = start_idx + 1

        attrs: dict[str, int] = {}
        if hasattr(open_token, "attrGet"):
            start_attr = open_token.attrGet("start")
            if start_attr is not None:
                attrs["order"] = int(start_attr)

        while i < len(tokens):
            token = tokens[i]
            if token.type == "ordered_list_close":
                consumed = i - start_idx + 1
                break
            elif token.type == "list_item_open":
                list_item, item_consumed = self._process_list_item(tokens, i)
                list_items.append(list_item)
                i += item_consumed
            else:
                i += 1

        node: dict[str, Any] = {"type": "orderedList", "content": list_items}
        if attrs:
            node["attrs"] = attrs

        return node, consumed

    def _process_list_item(
        self, tokens: list[Token], start_idx: int
    ) -> tuple[dict[str, Any], int]:
        """Process list item tokens into ADF listItem node.

        Args:
            tokens: List of all tokens
            start_idx: Starting index of the list item

        Returns:
            Tuple of (ADF listItem node, number of tokens consumed)
        """
        item_content: list[dict[str, Any]] = []
        consumed = 1
        i = start_idx + 1

        while i < len(tokens):
            token = tokens[i]
            if token.type == "list_item_close":
                consumed = i - start_idx + 1
                break
            elif token.type == "paragraph_open":
                paragraph, para_consumed = self._process_paragraph(tokens, i)
                item_content.append(paragraph)
                i += para_consumed
            elif token.type == "bullet_list_open":
                nested_list, nested_consumed = self._process_bullet_list(tokens, i)
                item_content.append(nested_list)
                i += nested_consumed
            elif token.type == "ordered_list_open":
                nested_list, nested_consumed = self._process_ordered_list(tokens, i)
                item_content.append(nested_list)
                i += nested_consumed
            else:
                i += 1

        return {"type": "listItem", "content": item_content}, consumed

    def _process_blockquote(
        self, tokens: list[Token], start_idx: int
    ) -> tuple[dict[str, Any], int]:
        """Process blockquote tokens into ADF blockquote node.

        Args:
            tokens: List of all tokens
            start_idx: Starting index of the blockquote

        Returns:
            Tuple of (ADF blockquote node, number of tokens consumed)
        """
        quote_content: list[dict[str, Any]] = []
        consumed = 1
        i = start_idx + 1

        while i < len(tokens):
            token = tokens[i]
            if token.type == "blockquote_close":
                consumed = i - start_idx + 1
                break
            elif token.type == "paragraph_open":
                paragraph, para_consumed = self._process_paragraph(tokens, i)
                quote_content.append(paragraph)
                i += para_consumed
            else:
                i += 1

        return {"type": "blockquote", "content": quote_content}, consumed

    def _process_code_block(self, token: Token) -> dict[str, Any]:
        """Process code block token into ADF codeBlock node.

        Args:
            token: Code block token

        Returns:
            ADF codeBlock node
        """
        language = None
        if hasattr(token, "info") and token.info:
            language = token.info.strip().split()[0]

        node: dict[str, Any] = {
            "type": "codeBlock",
            "content": [{"type": "text", "text": token.content.rstrip("\n")}],
        }

        if language:
            node["attrs"] = {"language": language}

        return node

    def _process_table(
        self, tokens: list[Token], start_idx: int
    ) -> tuple[dict[str, Any], int]:
        """Process table tokens into ADF table node.

        Args:
            tokens: List of all tokens
            start_idx: Starting index of the table

        Returns:
            Tuple of (ADF table node, number of tokens consumed)
        """
        table_rows: list[dict[str, Any]] = []
        consumed = 1
        i = start_idx + 1

        while i < len(tokens):
            token = tokens[i]
            if token.type == "table_close":
                consumed = i - start_idx + 1
                break
            elif token.type in ["thead_open", "tbody_open"] or token.type in [
                "thead_close",
                "tbody_close",
            ]:
                i += 1
                continue
            elif token.type == "tr_open":
                row, row_consumed = self._process_table_row(tokens, i)
                table_rows.append(row)
                i += row_consumed
            else:
                i += 1

        return {
            "type": "table",
            "attrs": {"isNumberColumnEnabled": False, "layout": "center"},
            "content": table_rows,
        }, consumed

    def _process_table_row(
        self, tokens: list[Token], start_idx: int
    ) -> tuple[dict[str, Any], int]:
        """Process table row tokens into ADF tableRow node.

        Args:
            tokens: List of all tokens
            start_idx: Starting index of the row

        Returns:
            Tuple of (ADF tableRow node, number of tokens consumed)
        """
        row_cells: list[dict[str, Any]] = []
        consumed = 1
        i = start_idx + 1

        while i < len(tokens):
            token = tokens[i]
            if token.type == "tr_close":
                consumed = i - start_idx + 1
                break
            elif token.type in ["th_open", "td_open"]:
                is_header = token.type == "th_open"
                cell, cell_consumed = self._process_table_cell(tokens, i, is_header)
                row_cells.append(cell)
                i += cell_consumed
            else:
                i += 1

        return {"type": "tableRow", "content": row_cells}, consumed

    def _process_table_cell(
        self, tokens: list[Token], start_idx: int, is_header: bool
    ) -> tuple[dict[str, Any], int]:
        """Process table cell tokens into ADF tableCell or tableHeader node.

        Args:
            tokens: List of all tokens
            start_idx: Starting index of the cell
            is_header: Whether this is a header cell

        Returns:
            Tuple of (ADF table cell node, number of tokens consumed)
        """
        consumed = 1
        i = start_idx + 1
        close_type = "th_close" if is_header else "td_close"

        inline_tokens: list[Token] = []
        while i < len(tokens):
            token = tokens[i]
            if token.type == close_type:
                consumed = i - start_idx + 1
                break
            elif token.type == "inline" and token.children:
                inline_tokens.extend(token.children)
            i += 1

        cell_content: list[dict[str, Any]] = []
        if inline_tokens:
            temp_token = Token("inline", "", 0)
            temp_token.children = inline_tokens
            temp_token.content = "".join(
                t.content for t in inline_tokens if hasattr(t, "content")
            )
            cell_content = self._process_inline_content(temp_token)

        if cell_content:
            paragraph_content = [{"type": "paragraph", "content": cell_content}]
        else:
            paragraph_content = [
                {"type": "paragraph", "content": [{"type": "text", "text": ""}]}
            ]

        cell_type = "tableHeader" if is_header else "tableCell"
        return {"type": cell_type, "attrs": {}, "content": paragraph_content}, consumed

    def _process_inline_content(self, token: Token) -> list[dict[str, Any]]:
        """Process inline token content into ADF inline nodes.

        Args:
            token: Inline token to process

        Returns:
            List of ADF inline content nodes
        """
        if not token.children:
            if token.content:
                return [{"type": "text", "text": token.content}]
            return []

        content: list[dict[str, Any]] = []
        i = 0

        while i < len(token.children):
            child = token.children[i]

            if child.type == "text":
                content.append({"type": "text", "text": child.content})
            elif child.type in ["strong_open", "em_open", "code_inline", "link_open"]:
                inline_node, consumed = self._process_inline_formatting(
                    token.children, i
                )
                content.append(inline_node)
                i += consumed - 1
            elif child.type == "softbreak":
                content.append({"type": "text", "text": " "})
            elif child.type == "hardbreak":
                content.append({"type": "hardBreak"})

            i += 1

        return content

    def _process_inline_formatting(
        self, children: list[Token], start_idx: int
    ) -> tuple[dict[str, Any], int]:
        """Process inline formatting tokens into ADF text nodes with marks.

        Args:
            children: List of inline token children
            start_idx: Starting index

        Returns:
            Tuple of (ADF text node with marks, number of tokens consumed)
        """
        start_token = children[start_idx]
        consumed = 1
        text_content = ""
        marks: list[dict[str, Any]] = []
        close_type = ""

        if start_token.type == "strong_open":
            marks.append({"type": "strong"})
            close_type = "strong_close"
        elif start_token.type == "em_open":
            marks.append({"type": "em"})
            close_type = "em_close"
        elif start_token.type == "code_inline":
            return {
                "type": "text",
                "text": start_token.content,
                "marks": [{"type": "code"}],
            }, 1
        elif start_token.type == "link_open":
            href = (
                start_token.attrGet("href") if hasattr(start_token, "attrGet") else "#"
            )
            marks.append({"type": "link", "attrs": {"href": href}})
            close_type = "link_close"
        else:
            return {"type": "text", "text": start_token.content}, 1

        for i in range(start_idx + 1, len(children)):
            token = children[i]
            if token.type == close_type:
                consumed = i - start_idx + 1
                break
            elif token.type == "text":
                text_content += token.content

        return {"type": "text", "text": text_content, "marks": marks}, consumed
