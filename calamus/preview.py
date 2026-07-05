"""Markdown preview abstractions and implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk

from calamus.mermaid_support import get_mermaid_init_script, get_mermaid_script_tag
from calamus.renderer import AbstractMarkdownRenderer, MistuneRenderer

try:
    gi.require_version("WebKit", "6.0")
    from gi.repository import WebKit as _WebKitModule

    _WEBKIT_AVAILABLE = True
except (ImportError, ValueError):
    try:
        gi.require_version("WebKit2", "4.1")
        from gi.repository import WebKit2 as _WebKitModule

        _WEBKIT_AVAILABLE = True
    except (ImportError, ValueError):
        _WebKitModule = None
        _WEBKIT_AVAILABLE = False


_HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
{mermaid_script}
<script>
  document.addEventListener('DOMContentLoaded', function() {{
    mermaid.initialize({{ startOnLoad: true, theme: 'default' }});
  }});
</script>
<style>
  body {{ font-family: sans-serif; max-width: 800px; margin: 2em auto; padding: 0 1em; line-height: 1.6; }}
  code {{ background: #f4f4f4; padding: 2px 4px; border-radius: 3px; font-family: monospace; }}
  pre {{ background: #f4f4f4; padding: 1em; border-radius: 4px; overflow-x: auto; }}
  pre.mermaid {{ background: transparent; padding: 0; }}
  blockquote {{ border-left: 4px solid #ccc; margin: 0; padding-left: 1em; color: #666; }}
  img {{ max-width: 100%; }}
</style>
</head>
<body>
{body}
{mermaid_init_script}
</body>
</html>
"""


class AbstractPreview(ABC):
    """Defines preview behavior."""

    @abstractmethod
    def update(self, markdown_text: str) -> None:
        """Update the preview with Markdown text."""

    @abstractmethod
    def get_widget(self) -> Gtk.Widget:
        """Return the widget used to render the preview."""


class WebKitPreview(AbstractPreview):
    """Preview implementation backed by WebKit (6.0) or WebKit2 (4.1)."""

    def __init__(self, renderer: AbstractMarkdownRenderer | None = None) -> None:
        self._renderer = renderer or MistuneRenderer()
        self._view = _WebKitModule.WebView()
        self._view.set_hexpand(True)
        self._view.set_vexpand(True)

    def update(self, markdown_text: str) -> None:
        html_body = self._renderer.render(markdown_text)
        html_text = _HTML_TEMPLATE.format(
            body=html_body,
            mermaid_script=get_mermaid_script_tag(),
            mermaid_init_script=get_mermaid_init_script(),
        )
        self._view.load_html(html_text, "file:///")

    def get_widget(self) -> Gtk.Widget:
        return self._view


class TextViewPreview(AbstractPreview):
    """Fallback preview that shows raw Markdown text."""

    def __init__(self) -> None:
        self._view = Gtk.TextView()
        self._view.set_editable(False)
        self._view.set_wrap_mode(Gtk.WrapMode.WORD)
        self._view.set_hexpand(True)
        self._view.set_vexpand(True)

    def update(self, markdown_text: str) -> None:
        self._view.get_buffer().set_text(markdown_text)

    def get_widget(self) -> Gtk.Widget:
        return self._view


def create_preview() -> AbstractPreview:
    """Create the best preview implementation for the current system."""
    if _WEBKIT_AVAILABLE:
        return WebKitPreview()
    return TextViewPreview()
