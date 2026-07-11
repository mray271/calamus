"""Markdown renderer abstractions and concrete implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
import html
import re
import unicodedata

import mistune

from calamus import MERMAID_VERSION


def _slugify(text: str) -> str:
    """Convert heading text to a GitHub-style anchor id."""
    text = text.lower()
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text.strip())
    return text


_HEADING_RE = re.compile(r"(<h([1-6])>)(.*?)(</h[1-6]>)", re.DOTALL)


def _add_heading_ids(html_text: str) -> str:
    """Post-process rendered HTML to add id attributes to headings."""
    if not isinstance(html_text, str):
        return html_text
    def _repl(m: re.Match) -> str:
        open_tag, level, inner, close_tag = m.group(1), m.group(2), m.group(3), m.group(4)
        plain = re.sub(r"<[^>]+>", "", inner)
        slug = _slugify(plain)
        if slug:
            return f'<h{level} id="{slug}">{inner}{close_tag}'
        return m.group(0)
    return _HEADING_RE.sub(_repl, html_text)


class AbstractMarkdownRenderer(ABC):
    """Defines the Markdown-to-HTML rendering interface."""

    @abstractmethod
    def render(self, text: str) -> str:
        """Render Markdown text to HTML."""

    @abstractmethod
    def get_version(self) -> str:
        """Return the underlying renderer version."""


class MistuneRenderer(AbstractMarkdownRenderer):
    """Render Markdown to HTML with Mermaid fence support."""

    MERMAID_VERSION = MERMAID_VERSION

    def __init__(self) -> None:
        # TODO: Enable additional mistune 3 plugins for full ExtraMark support.
        # The following plugins ship with mistune 3 and only need to be added
        # to the list below — no extra dependencies required:
        #   "task_lists"  – GFM task-list checkboxes  (- [x] / - [ ])
        #   "def_list"    – ExtraMark definition lists (Term\n:   Definition)
        #   "footnotes"   – ExtraMark/GFM footnotes   ([^1] / [^1]: text)
        #   "abbr"        – ExtraMark abbreviations   (*[HTML]: expansion)
        # See: tests/test_extramark_compat.py and tests/test_gfm_compat.py
        # "superscript" and "subscript" are already enabled (x^2^, H~2~O,
        # and scientific notation such as M~🜨~ for Earth mass).
        self._renderer = mistune.create_markdown(
            renderer=mistune.HTMLRenderer(escape=False),
            plugins=["strikethrough", "table", "url", "subscript", "superscript"],
        )

    def render_preprocessed(self, text: str) -> str:
        """Run mistune on *text* without any Mermaid preprocessing."""
        return _add_heading_ids(self._renderer(text))

    def render(self, text: str) -> str:
        from calamus.mermaid_support import (
            SubprocessMermaidRenderer,
            preprocess_markdown_for_static_export,
        )

        if SubprocessMermaidRenderer().is_available():
            text = preprocess_markdown_for_static_export(text)
            return _add_heading_ids(self._renderer(text))

        prepared = self._prepare_mermaid_blocks(text)
        return _add_heading_ids(self._renderer(prepared))

    def get_version(self) -> str:
        return getattr(mistune, "__version__", "unknown")

    def _prepare_mermaid_blocks(self, text: str) -> str:
        pattern = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL)

        def repl(match: re.Match[str]) -> str:
            diagram_source = html.escape(match.group(1).strip())
            return f'\n<pre class="mermaid">{diagram_source}</pre>\n'

        return pattern.sub(repl, text)
