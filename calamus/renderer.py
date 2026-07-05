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
        self._renderer = mistune.create_markdown(
            renderer=mistune.HTMLRenderer(escape=False),
            plugins=["strikethrough", "table", "url"],
        )

    def render(self, text: str) -> str:
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
