"""Markdown renderer abstractions and concrete implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
import html
import re

import mistune

from calamus import MERMAID_VERSION


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
        #   "superscript" – ExtraMark superscript     (x^2^)
        #   "subscript"   – ExtraMark subscript       (H~2~O)
        # See: tests/test_extramark_compat.py and tests/test_gfm_compat.py
        self._renderer = mistune.create_markdown(
            renderer=mistune.HTMLRenderer(escape=False),
            plugins=["strikethrough", "table", "url"],
        )

    def render(self, text: str) -> str:
        from calamus.mermaid_support import (
            SubprocessMermaidRenderer,
            preprocess_markdown_for_static_export,
        )

        if SubprocessMermaidRenderer().is_available():
            # mmdc is installed: pre-render all diagrams to inline SVG data
            # URIs so config frontmatter (e.g. labelRotation) is applied
            # server-side, matching the behaviour of the md2html command.
            text = preprocess_markdown_for_static_export(text)
            return self._renderer(text)

        # Fallback: embed raw source in <pre class="mermaid"> and let the
        # browser-side mermaid.js handle rendering.
        prepared = self._prepare_mermaid_blocks(text)
        return self._renderer(prepared)

    def get_version(self) -> str:
        return getattr(mistune, "__version__", "unknown")

    def _prepare_mermaid_blocks(self, text: str) -> str:
        pattern = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL)

        def repl(match: re.Match[str]) -> str:
            diagram_source = html.escape(match.group(1).strip())
            return f'\n<pre class="mermaid">{diagram_source}</pre>\n'

        return pattern.sub(repl, text)
