"""Markdown preview abstractions and implementations."""

from __future__ import annotations

import os
import threading
from abc import ABC, abstractmethod
from collections.abc import Callable
from urllib.parse import unquote

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, Gtk

from calamus.highlight_support import get_highlight_css_tag, get_highlight_script_tag
from calamus.mermaid_support import (
    MermaidCache,
    SubprocessMermaidRenderer,
    extract_mermaid_blocks,
    get_mermaid_init_script,
    get_mermaid_script_tag,
    preprocess_with_cache,
)
from calamus.renderer import AbstractMarkdownRenderer, MistuneRenderer

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
  if (typeof mermaid !== 'undefined') {{
    mermaid.initialize({{ startOnLoad: false, theme: '{mermaid_theme}' }});
    mermaid.run({{ querySelector: '.mermaid' }});
  }}
  if (typeof hljs !== 'undefined') {{
    hljs.highlightAll();
  }}
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

    def set_file_path(self, path: str | None) -> None:
        """Notify the preview of the current file path for relative link resolution."""


class WebKitPreview(AbstractPreview):
    """Preview implementation backed by WebKit (6.0) or WebKit2 (4.1)."""

    def __init__(
        self,
        renderer: AbstractMarkdownRenderer | None = None,
        on_open_path: Callable[[str], None] | None = None,
    ) -> None:
        self._renderer = renderer or MistuneRenderer()
        self._on_open_path = on_open_path
        self._base_uri = "file:///"
        # Disable the bwrap/dbus-proxy sandbox — required when running inside
        # Docker where bubblewrap cannot create user namespaces.
        context = _WebKitModule.WebContext.get_default()
        if hasattr(context, "set_sandbox_enabled"):
            context.set_sandbox_enabled(False)
        self._view = _WebKitModule.WebView()
        self._view.set_hexpand(True)
        self._view.set_vexpand(True)
        self._view.connect("decide-policy", self._on_decide_policy)
        self._last_markdown: str = ""
        self._style_manager = Adw.StyleManager.get_default()
        self._style_manager.connect("notify::dark", self._on_dark_changed)
        # Layer 2 & 3: async rendering + SVG cache
        self._mermaid_cache = MermaidCache()
        self._mmdc_available: bool = SubprocessMermaidRenderer().is_available()
        # Generation counter: incremented on every update() call.
        # Background threads check this before posting results — stale renders
        # (superseded by a newer edit) are silently discarded rather than
        # updating the preview with out-of-date content.
        self._render_generation: int = 0
        # Semaphore: at most one mmdc process runs at a time.
        # Without this, rapid typing spawns unbounded Chromium processes,
        # exhausting memory and hanging the application.
        self._mmdc_semaphore = threading.Semaphore(1)

    def set_file_path(self, path: str | None) -> None:
        """Update the base URI used for resolving relative links in the preview."""
        if path is not None:
            directory = os.path.dirname(os.path.abspath(path))
            self._base_uri = f"file://{directory}/"
        else:
            self._base_uri = "file:///"

    def _on_decide_policy(
        self,
        _webview: object,
        decision: object,
        decision_type: object,
    ) -> None:
        """Intercept all WebKit navigation to prevent the preview from navigating away.

        * In-page anchor links (#section) → let WebKit handle natively (scroll).
        * file:// links to .md files → open in the editor via callback.
        * http/https links → open in the system default browser.
        * Everything else → silently ignored (preview stays on current content).
        """
        if decision_type != _WebKitModule.PolicyDecisionType.NAVIGATION_ACTION:
            decision.use()
            return
        nav_action = decision.get_navigation_action()
        if (
            nav_action.get_navigation_type()
            != _WebKitModule.NavigationType.LINK_CLICKED
        ):
            decision.use()
            return
        uri = nav_action.get_request().get_uri()

        if uri.startswith("file://"):
            raw_path = unquote(uri[len("file://") :])
            path, _, fragment = raw_path.partition("#")
            # Pure anchor link — path resolves to the current directory.
            # WebKit can't scroll within load_bytes pages by URL fragment, so
            # we do it explicitly with JavaScript.
            if not path or os.path.isdir(path):
                decision.ignore()
                if fragment:
                    self._scroll_to_anchor(fragment)
                return
            decision.ignore()
            if self._on_open_path is not None:
                self._on_open_path(path)
        elif uri.startswith(("http://", "https://")):
            decision.ignore()
            try:
                Gio.AppInfo.launch_default_for_uri(uri, None)
            except GLib.Error:
                pass
        else:
            decision.ignore()

    def _on_dark_changed(
        self, _style_manager: Adw.StyleManager, _param: object
    ) -> None:
        if self._last_markdown:
            self.update(self._last_markdown)

    def update(self, markdown_text: str) -> None:
        self._last_markdown = markdown_text
        dark = self._style_manager.get_dark()

        if not self._mmdc_available:
            # No mmdc — use browser-side mermaid.js (instant, no subprocess).
            html_body = self._renderer.render(markdown_text)
            self._render_page(html_body, get_mermaid_script_tag(), dark)
            return

        # Fast path: render immediately using cached SVGs where available.
        # Uncached blocks fall back to browser-side mermaid.js until the
        # background thread produces their SVGs.
        preprocessed = preprocess_with_cache(markdown_text, self._mermaid_cache)
        html_body = self._renderer.render_preprocessed(preprocessed)
        uncached = [
            src
            for _, src in extract_mermaid_blocks(markdown_text)
            if not self._mermaid_cache.has(src)
        ]
        self._render_page(
            html_body,
            get_mermaid_script_tag() if uncached else "",
            dark,
        )
        # Layer 2: background thread renders uncached diagrams, then refreshes.
        if uncached:
            self._render_generation += 1
            generation = self._render_generation
            thread = threading.Thread(
                target=self._async_render_worker,
                args=(markdown_text, uncached, generation),
                daemon=True,
            )
            thread.start()

    def _async_render_worker(
        self, markdown_text: str, uncached: list[str], generation: int
    ) -> None:
        """Background thread: render uncached diagrams and schedule UI update.

        Acquires ``_mmdc_semaphore`` so only one mmdc process runs at a time.
        Checks ``_render_generation`` before each diagram and before posting
        the result — if the user has typed more, the work is abandoned so the
        next queued thread can run instead.
        """
        if not self._mmdc_semaphore.acquire(timeout=60):
            return  # another render is stuck; give up rather than hang
        try:
            renderer = SubprocessMermaidRenderer()
            for source in uncached:
                if generation != self._render_generation:
                    return  # superseded by a newer edit
                svg = renderer.render_to_svg(source)
                if svg:
                    self._mermaid_cache.put(source, svg)
        finally:
            self._mmdc_semaphore.release()
        if generation == self._render_generation:
            GLib.idle_add(self._on_async_render_done, markdown_text)

    def _on_async_render_done(self, markdown_text: str) -> bool:
        """Main-thread callback: re-render once background SVGs are ready."""
        if markdown_text == self._last_markdown:
            preprocessed = preprocess_with_cache(markdown_text, self._mermaid_cache)
            html_body = self._renderer.render_preprocessed(preprocessed)
            self._render_page(html_body, "", self._style_manager.get_dark())
        return GLib.SOURCE_REMOVE

    def _render_page(self, html_body: str, mermaid_script: str, dark: bool) -> None:
        color_scheme = "dark" if dark else "light"
        mermaid_theme = "dark" if dark else "default"
        html_text = _HTML_TEMPLATE.format(
            body=html_body,
            mermaid_script=mermaid_script,
            color_scheme=color_scheme,
            mermaid_theme=mermaid_theme,
            highlight_css=get_highlight_css_tag(dark=dark),
            highlight_script=get_highlight_script_tag(),
        )
        # Use load_bytes (not load_html) to prevent Latin-1 charset sniffing
        # that would corrupt multi-byte UTF-8 characters (e.g. ⊕, ★, −, ″).
        raw = GLib.Bytes.new(html_text.encode("utf-8"))
        self._view.load_bytes(raw, "text/html", "utf-8", self._base_uri)

    def _scroll_to_anchor(self, anchor_id: str) -> None:
        """Scroll the preview to the element with the given id."""
        # Sanitize: only allow characters valid in HTML id attributes.
        safe = "".join(c for c in anchor_id if c.isalnum() or c in "-_")
        if not safe:
            return
        js = (
            f"var el = document.getElementById('{safe}');"
            f"if (el) el.scrollIntoView({{behavior:'smooth', block:'start'}});"
        )
        if hasattr(self._view, "evaluate_javascript"):
            self._view.evaluate_javascript(js, -1, None, None, None, None, None)
        elif hasattr(self._view, "run_javascript"):
            self._view.run_javascript(js, None, None, None)

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


def create_preview(
    on_open_path: Callable[[str], None] | None = None,
) -> AbstractPreview:
    """Create the best preview implementation for the current system."""
    if _WEBKIT_AVAILABLE:
        return WebKitPreview(on_open_path=on_open_path)
    return TextViewPreview()
