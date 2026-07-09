"""Markdown preview abstractions and implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk

from calamus.mermaid_support import get_mermaid_init_script, get_mermaid_script_tag
from calamus.renderer import AbstractMarkdownRenderer, MistuneRenderer
from calamus.highlight_support import get_highlight_css_tag, get_highlight_script_tag

try:
    gi.require_version("WebKit", "6.0")
    from gi.repository import WebKit as _WebKitModule

    _WEBKIT_AVAILABLE = True
except (ImportError, ValueError):
    # WebKit2 4.1 uses GTK3 internally and cannot be loaded alongside GTK4.
    # Install webkitgtk6.0 for the live preview to work.
    _WebKitModule = None
    _WEBKIT_AVAILABLE = False


_HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="color-scheme" content="{color_scheme}">
{mermaid_script}
{highlight_css}
{highlight_script}
<style>
  /* Explicit fallback chain for Unicode symbol ranges.
     "Noto Sans Symbols 2" covers partial alchemical symbols; "Unifont Upper"
     covers the full SMP including Alchemical Symbols (U+1F700-U+1F77F) such
     as 🜨 (U+1F728, Earth).  "Noto Sans Symbols" covers Mathematical Operators
     (U+2200-U+22FF) including ⊕ (U+2295, Earth radius).
     Listed after prose fonts so they activate only for uncovered glyphs. */
  @font-face {{
    font-family: "NotoSymbols2";
    src: local("Noto Sans Symbols 2"), local("NotoSansSymbols2"),
         local("Unifont Upper"), local("Unifont CSUR");
    unicode-range: U+1F700-U+1F77F, U+1F780-U+1F7FF, U+1F800-U+1F8FF,
                   U+2300-U+23FF, U+2600-U+26FF, U+2700-U+27BF;
  }}
  @font-face {{
    font-family: "NotoSymbols";
    src: local("Noto Sans Symbols"), local("NotoSansSymbols");
    unicode-range: U+2100-U+214F, U+2190-U+21FF, U+2200-U+22FF,
                   U+2300-U+23FF, U+25A0-U+25FF, U+2600-U+26FF;
  }}
  :root {{
    --bg: #ffffff;
    --fg: #1c1c1c;
    --code-bg: #f4f4f4;
    --blockquote-color: #666666;
    --blockquote-border: #cccccc;
    --link-color: #0066cc;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #1e1e1e;
      --fg: #eeeeee;
      --code-bg: #2d2d2d;
      --blockquote-color: #aaaaaa;
      --blockquote-border: #555555;
      --link-color: #6699cc;
    }}
  }}
  body {{ font-family: "Noto Sans", "DejaVu Sans", "NotoSymbols2", "NotoSymbols", sans-serif; max-width: 800px; margin: 2em auto; padding: 0 1em; line-height: 1.6; background: var(--bg); color: var(--fg); }}
  a {{ color: var(--link-color); }}
  code {{ background: var(--code-bg); padding: 2px 4px; border-radius: 3px; font-family: monospace; }}
  pre {{ background: var(--code-bg); padding: 1em; border-radius: 4px; overflow-x: auto; }}
  pre.mermaid {{ background: transparent; padding: 0; }}
  blockquote {{ border-left: 4px solid var(--blockquote-border); margin: 0; padding-left: 1em; color: var(--blockquote-color); }}
  img {{ max-width: 100%; }}
  /* Explicit sub/sup sizing — WebKit's UA default (font-size: smaller ≈ 83%)
     is not visually distinct enough, especially for symbol glyphs.
     position:relative + vertical-align:baseline prevents sub/sup from
     expanding the line-height of the surrounding text. */
  sub, sup {{
    font-size: 0.70em;
    line-height: 0;
    position: relative;
    vertical-align: baseline;
  }}
  sub {{ bottom: -0.3em; }}
  sup {{ top: -0.5em; }}
</style>
</head>
<body>
{body}
<script>
  mermaid.initialize({{ startOnLoad: false, theme: '{mermaid_theme}' }});
  mermaid.run({{ querySelector: '.mermaid' }});
  hljs.highlightAll();
</script>
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
        # Disable the bwrap/dbus-proxy sandbox — required when running inside
        # Docker where bubblewrap cannot create user namespaces.
        context = _WebKitModule.WebContext.get_default()
        if hasattr(context, "set_sandbox_enabled"):
            context.set_sandbox_enabled(False)
        self._view = _WebKitModule.WebView()
        self._view.set_hexpand(True)
        self._view.set_vexpand(True)
        self._last_markdown: str = ""
        self._style_manager = Adw.StyleManager.get_default()
        self._style_manager.connect("notify::dark", self._on_dark_changed)

    def _on_dark_changed(
        self, _style_manager: Adw.StyleManager, _param: object
    ) -> None:
        if self._last_markdown:
            self.update(self._last_markdown)

    def update(self, markdown_text: str) -> None:
        from calamus.mermaid_support import SubprocessMermaidRenderer

        self._last_markdown = markdown_text
        dark = self._style_manager.get_dark()
        color_scheme = "dark" if dark else "light"
        mermaid_theme = "dark" if dark else "default"

        html_body = self._renderer.render(markdown_text)
        mermaid_script = (
            ""
            if SubprocessMermaidRenderer().is_available()
            else get_mermaid_script_tag()
        )
        html_text = _HTML_TEMPLATE.format(
            body=html_body,
            mermaid_script=mermaid_script,
            color_scheme=color_scheme,
            mermaid_theme=mermaid_theme,
            highlight_css=get_highlight_css_tag(dark=dark),
            highlight_script=get_highlight_script_tag(),
        )
        # Use load_bytes with an explicit encoding declaration rather than
        # load_html, which can fall back to Latin-1 charset sniffing and
        # corrupt multi-byte UTF-8 characters (e.g. ⊕, ★, −, ″ → â…).
        raw = GLib.Bytes.new(html_text.encode("utf-8"))
        self._view.load_bytes(raw, "text/html", "utf-8", "file:///")

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
