"""Markdown preview abstractions and implementations."""

from __future__ import annotations

import base64
import json
import logging
import os
import shutil
import tempfile
import threading
import urllib.request
from abc import ABC, abstractmethod
from collections.abc import Callable
from urllib.parse import unquote, urlparse

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk

from calamus.highlight_support import get_highlight_css_tag, get_highlight_script_tag
from calamus.link_tooltip import LinkTooltipManager
from calamus.mermaid_support import (
    MermaidCache,
    SubprocessMermaidRenderer,
    extract_mermaid_blocks,
    get_mermaid_init_script,
    get_mermaid_script_tag,
    preprocess_with_cache,
)
from calamus.renderer import AbstractMarkdownRenderer, MistuneRenderer

_logger = logging.getLogger(__name__)

try:
    gi.require_version("WebKit", "6.0")
    from gi.repository import WebKit as _WebKitModule
    gi.require_version("JavaScriptCore", "6.0")
    from gi.repository import JavaScriptCore as _JavaScriptCoreModule

    _WEBKIT_AVAILABLE = True
except (ImportError, ValueError):
    # WebKit2 4.1 uses GTK3 internally and cannot be loaded alongside GTK4.
    # Install webkitgtk6.0 for the live preview to work.
    _WebKitModule = None
    _JavaScriptCoreModule = None
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
    unicode-range: U+1F700-U+1F77F, U+1F780-U+1F7FF, U+1F800-U+1F8FF;
  }}
  @font-face {{
    font-family: "NotoSymbols";
    src: local("Noto Sans Symbols"), local("NotoSansSymbols");
    unicode-range: U+2100-U+214F, U+2190-U+21FF, U+2200-U+22FF, U+2300-U+23FF;
  }}
  :root {{
    --bg: #ffffff;
    --fg: #1c1c1c;
    --code-bg: #f4f4f4;
    --blockquote-color: #666666;
    --blockquote-border: #cccccc;
    --link-color: #0066cc;
    --alert-note-border: #3b82f6;
    --alert-tip-border: #10b981;
    --alert-important-border: #8b5cf6;
    --alert-caution-border: #f59e0b;
    --alert-warning-border: #ef4444;
    --alert-bg: rgba(127, 127, 127, 0.08);
    --mark-bg: #fcf8e3;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #1e1e1e;
      --fg: #eeeeee;
      --code-bg: #2d2d2d;
      --blockquote-color: #aaaaaa;
      --blockquote-border: #555555;
      --link-color: #6699cc;
      --alert-note-border: #60a5fa;
      --alert-tip-border: #34d399;
      --alert-important-border: #a78bfa;
      --alert-caution-border: #fbbf24;
      --alert-warning-border: #f87171;
      --alert-bg: rgba(255, 255, 255, 0.06);
      --mark-bg: #6a6233;
    }}
  }}
  body {{ font-family: "Noto Sans", "DejaVu Sans", "Noto Color Emoji", "Apple Color Emoji", "Segoe UI Emoji", "Noto Emoji", "NotoSymbols2", "NotoSymbols", sans-serif; font-size: __PREVIEW_FONT_SCALE__em; max-width: 800px; margin: 2em auto; padding: 0 1em; line-height: 1.6; background: var(--bg); color: var(--fg); }}
  a {{ color: var(--link-color); }}
  code {{ background: var(--code-bg); padding: 2px 4px; border-radius: 3px; font-family: monospace; }}
  pre {{ background: var(--code-bg); padding: 1em; border-radius: 4px; overflow-x: auto; }}
  pre.mermaid {{ background: transparent; padding: 0; }}
  blockquote {{ border-left: 4px solid var(--blockquote-border); margin: 0; padding-left: 1em; color: var(--blockquote-color); }}
  .glfm-alert {{ margin: 0; padding: 0.5em 0 0.5em 1em; color: var(--fg); background: var(--alert-bg); border-radius: 0 4px 4px 0; }}
  .glfm-alert-title {{ margin: 0 0 0.35em; font-weight: 700; color: var(--fg); }}
  .glfm-alert-note {{ border-left-color: var(--alert-note-border); }}
  .glfm-alert-tip {{ border-left-color: var(--alert-tip-border); }}
  .glfm-alert-important {{ border-left-color: var(--alert-important-border); }}
  .glfm-alert-caution {{ border-left-color: var(--alert-caution-border); }}
  .glfm-alert-warning {{ border-left-color: var(--alert-warning-border); }}
  .glfm-color-chip {{ display: inline-flex; align-items: center; gap: 0.35em; }}
  mark {{
    background: var(--mark-bg);
    color: inherit;
  }}
  .glfm-color-chip-swatch {{
    width: 0.85em;
    height: 0.85em;
    border-radius: 2px;
    border: 1px solid var(--blockquote-border);
    flex: 0 0 auto;
  }}
  li.task-list-item {{
    list-style: none;
  }}
  li.task-list-item::marker {{
    content: "";
  }}
  li.task-list-item > .task-list-item-checkbox {{
    margin-right: 0.45em;
    vertical-align: middle;
  }}
  dt {{
    font-weight: 700;
  }}
  img {{ max-width: 100%; transform: scale(__PREVIEW_FONT_SCALE__); transform-origin: left top; }}
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
  // Note: Tooltip hover detection is now injected via UserScript
  // in _inject_tooltip_script() to ensure it has access to window.webkit

  }})();
</script>
</body>
</html>
"""


def _is_same_document_file_anchor(path: str, base_uri: str) -> bool:
    """Return True when a file:// URL path points at the current preview document."""
    if path in ("", "/"):
        return True
    if not base_uri.startswith("file://"):
        return False

    base_path = unquote(urlparse(base_uri).path)
    if not base_path:
        return False

    normalized_path = os.path.normpath(path)
    normalized_base = os.path.normpath(base_path)
    return normalized_path == normalized_base


_SAVE_MIME_NAMES: dict[str, str] = {
    "image/svg+xml": "diagram.svg",
    "image/png": "image.png",
    "image/jpeg": "image.jpg",
    "image/gif": "image.gif",
    "image/webp": "image.webp",
}


def _default_save_filename(uri: str) -> str:
    """Return a reasonable default save filename derived from *uri*."""
    if uri.startswith("data:"):
        mime = uri[len("data:") :].partition(";")[0].partition(",")[0].strip().lower()
        return _SAVE_MIME_NAMES.get(mime, "download")
    last_segment = urlparse(uri).path.rstrip("/").rsplit("/", 1)[-1]
    return unquote(last_segment) if last_segment else "image"


class AbstractPreview(ABC):
    """Defines preview behavior."""

    @abstractmethod
    def update(self, markdown_text: str) -> None:
        """Update the preview with Markdown text."""

    @abstractmethod
    def get_widget(self) -> Gtk.Widget:
        """Return the widget used to render the preview."""

    @abstractmethod
    def set_file_path(self, path: str | None) -> None:
        """Notify the preview of the current file path for relative link resolution."""

    @abstractmethod
    def set_base_path(self, path: str | None) -> None:
        """Override the preview base path for resolving relative links."""

    @abstractmethod
    def zoom_by(self, factor: float) -> None:
        """Scale preview text by a factor."""

    @abstractmethod
    def reset_zoom(self) -> None:
        """Reset preview zoom to its default."""


class WebKitPreview(AbstractPreview):
    """Preview implementation backed by WebKit (6.0) or WebKit2 (4.1)."""

    _MIN_ZOOM = 0.5
    _MAX_ZOOM = 3.0
    _DEFAULT_ZOOM = 1.0

    def __init__(
        self,
        renderer: AbstractMarkdownRenderer | None = None,
        on_open_path: Callable[[str], None] | None = None,
        on_link_hover: Callable[[str], None] | None = None,
    ) -> None:
        self._renderer = renderer or MistuneRenderer()
        self._on_open_path = on_open_path
        self._on_link_hover = on_link_hover
        self._tooltip_manager = LinkTooltipManager()
        self._base_uri = "file:///"
        
        # Disable the bwrap/dbus-proxy sandbox — required when running inside
        # Docker where bubblewrap cannot create user namespaces.
        context = _WebKitModule.WebContext.get_default()
        if hasattr(context, "set_sandbox_enabled"):
            context.set_sandbox_enabled(False)
        
        # Create WebView
        self._view = _WebKitModule.WebView()
        
        # Get UserContentManager and register message handler for tooltip
        self._user_content_manager = self._view.get_user_content_manager()
        
        # Connect signal BEFORE registering the handler (critical to avoid race conditions)
        # Per PyGObject WebKit-6.0 API docs, the signal passes a JavaScriptCore.Value
        self._user_content_manager.connect("script-message-received::tooltip", self._on_tooltip_message)
        
        # Now register the handler
        self._user_content_manager.register_script_message_handler("tooltip")
        
        # Inject tooltip script into all web pages before they load
        self._inject_tooltip_script()
        self._view.set_hexpand(True)
        self._view.set_vexpand(True)
        self._view.connect("decide-policy", self._on_decide_policy)
        self._view.connect("create", self._on_create_web_view)
        self._view.connect("context-menu", self._on_context_menu)
        self._view.connect("load-changed", self._on_load_changed)
        # "Save Image As" (and any other download) is silently abandoned by
        # WebKit unless a handler sets the destination.
        # WebKit 6.0 moved download-started from WebContext to NetworkSession.
        # Try the WebView's own session first (most specific), then the module-
        # level NetworkSession, then fall back to WebContext for WebKit2 4.1.
        self._connect_download_signal(context)
        self._last_markdown: str = ""
        self._zoom_level = self._DEFAULT_ZOOM
        self._pending_scroll_restore_ratio: float | None = None
        self._style_manager = Adw.StyleManager.get_default()
        self._style_manager.connect("notify::dark", self._on_dark_changed)
        # Holds Gio.SimpleAction objects for the current context menu.
        # Must be kept alive on self — PyGObject's GC drops the Python wrapper
        # and silently loses the 'activate' callback if the action is only
        # referenced by a local variable inside _on_context_menu.
        self._context_menu_actions: list[object] = []
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
        
        # Create a container with WebView on top and tooltip footer on bottom
        self._container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._container.set_hexpand(True)
        self._container.set_vexpand(True)
        
        # Add WebView (takes most of the space)
        self._container.append(self._view)
        
        # Create a wrapper for the footer that can be hidden
        self._footer_wrapper = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self._footer_wrapper.set_hexpand(False)
        self._footer_wrapper.set_vexpand(False)
        self._footer_wrapper.set_halign(Gtk.Align.START)
        self._footer_wrapper.set_valign(Gtk.Align.START)
        self._footer_wrapper.set_spacing(0)
        # Constrain width to prevent expanding to full width
        self._footer_wrapper.set_size_request(420, -1)
        self._footer_wrapper.set_visible(False)  # Hide initially
        self._footer_wrapper.set_name("footer-wrapper")
        
        # Make wrapper transparent so only the inner tooltip shows
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
#footer-wrapper {
    background-color: transparent;
    padding: 0;
    margin: 0;
}
        """)
        context = self._footer_wrapper.get_style_context()
        context.add_provider(css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        
        # Add tooltip footer to wrapper
        tooltip_widget = self._tooltip_manager.get_widget()
        self._footer_wrapper.append(tooltip_widget)
        
        # Add wrapper to container
        self._container.append(self._footer_wrapper)

    def set_file_path(self, path: str | None) -> None:
        """Update the base URI used for resolving relative links in the preview."""
        self.set_base_path(path)

    def set_base_path(self, path: str | None) -> None:
        """Set the base directory or file path used to resolve relative links."""
        if path is None:
            self._base_uri = "file:///"
            return

        resolved = os.path.abspath(path)
        directory = resolved if os.path.isdir(resolved) else os.path.dirname(resolved)
        self._base_uri = f"file://{directory}/"

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
        uri = nav_action.get_request().get_uri()

        if uri.startswith("file://"):
            raw_path = unquote(uri[len("file://") :])
            path, _, fragment = raw_path.partition("#")
            # Same-document anchor links must be handled manually because
            # load_bytes pages do not reliably scroll by URL fragment alone.
            if fragment and _is_same_document_file_anchor(path, self._base_uri):
                decision.ignore()
                self._scroll_to_anchor(fragment)
                return

        if (
            nav_action.get_navigation_type()
            != _WebKitModule.NavigationType.LINK_CLICKED
        ):
            decision.use()
            return

        if uri.startswith("file://"):
            raw_path = unquote(uri[len("file://") :])
            path, _, fragment = raw_path.partition("#")
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

    def _on_context_menu(
        self,
        _webview: object,
        context_menu: object,
        *args: object,
    ) -> bool:
        """Customise the right-click context menu when an image is right-clicked.

        WebKit 6.0 signal:  (webview, context_menu, hit_test_result) → bool
        WebKit 4.x signal:  (webview, context_menu, event, hit_test_result) → bool
        Using *args makes the handler version-agnostic; hit_test_result is always last.

        Actions taken:
          - Remove "Copy Image Address" — for data: URIs it copies a useless
            base64 blob; for file:// it copies a non-portable absolute path.
          - Remove "Save Image As" (stock DOWNLOAD_IMAGE_TO_DISK) and replace
            with our own implementation that bypasses WebKit's download state
            machine entirely.  WebKit's async download-started handler is
            unreliable for "Save Image As" because WebKit abandons the download
            before the user can pick a destination file.
          - Add "Copy Markdown Image" for http/https/file images.
          - data: URI images (Mermaid diagrams) get "Save Image As…" only;
            "Copy Markdown Image" is omitted (no stable file address).
        """
        hit_test_result = args[-1]
        if not hit_test_result.context_is_image():
            return False

        image_uri = hit_test_result.get_image_uri() or ""

        # Remove stock items we are replacing with better alternatives.
        _remove = {
            _WebKitModule.ContextMenuAction.COPY_IMAGE_URL_TO_CLIPBOARD,
            _WebKitModule.ContextMenuAction.DOWNLOAD_IMAGE_TO_DISK,
        }
        for item in list(context_menu.get_items()):
            if hasattr(item, "get_stock_action") and item.get_stock_action() in _remove:
                context_menu.remove(item)

        # Clear previous actions — new ones are appended below.
        self._context_menu_actions = []

        # "Copy Markdown Image" — only useful for non-data: URIs.
        if not image_uri.startswith("data:"):
            md = self._uri_to_markdown_image(image_uri)
            copy_action = Gio.SimpleAction.new("copy-markdown-image", None)
            copy_action.connect(
                "activate", lambda _a, _p, t=md: self._copy_to_clipboard(t)
            )
            self._context_menu_actions.append(copy_action)
            try:
                context_menu.append(
                    _WebKitModule.ContextMenuItem.new_from_gaction(
                        copy_action, "Copy Markdown Image", None
                    )
                )
            except Exception:
                pass

        # "Save Image As…" — all image types, fully self-contained.
        save_action = Gio.SimpleAction.new("save-image-as", None)
        save_action.connect("activate", lambda _a, _p, u=image_uri: self._save_image(u))
        self._context_menu_actions.append(save_action)
        try:
            context_menu.append(
                _WebKitModule.ContextMenuItem.new_from_gaction(
                    save_action, "Save Image As\u2026", None
                )
            )
        except Exception:
            pass

        return False

    def _save_image(self, image_uri: str) -> None:
        """Show a save dialog then write the image to the chosen path.

        Handles all three URI types without going through WebKit's download
        state machine (which abandons the request before the async file dialog
        can respond):
          data:   — decode the base64 payload and write directly.
          file:// — copy the local file with shutil.
          http(s) — fetch in a daemon thread with urllib so the UI stays live.
        """
        dialog = Gtk.FileDialog.new()
        dialog.set_initial_name(_default_save_filename(image_uri))
        parent = self._view.get_root() if self._view else None
        dialog.save(
            parent,
            None,
            lambda d, r: self._on_save_image_response(d, r, image_uri),
        )

    def _on_save_image_response(
        self,
        dialog: Gtk.FileDialog,
        result: object,
        image_uri: str,
    ) -> None:
        try:
            gfile = dialog.save_finish(result)
        except GLib.Error:
            return
        if gfile is None:
            return
        path = gfile.get_path()
        if not path:
            return

        if image_uri.startswith("data:"):
            try:
                header, _, data_part = image_uri.partition(",")
                raw = (
                    base64.b64decode(data_part)
                    if ";base64" in header
                    else unquote(data_part).encode("utf-8")
                )
                with open(path, "wb") as fh:
                    fh.write(raw)
            except Exception:
                pass

        elif image_uri.startswith("file://"):
            src = unquote(urlparse(image_uri).path)
            try:
                shutil.copy2(src, path)
            except OSError:
                pass

        else:
            # Remote image — fetch in a background thread so the UI stays live.
            # A browser-compatible User-Agent is required; many servers return
            # 403 Forbidden to Python's default urllib agent.
            def _fetch(url: str = image_uri, dest: str = path) -> None:
                try:
                    req = urllib.request.Request(
                        url,
                        headers={
                            "User-Agent": (
                                "Mozilla/5.0 (X11; Linux x86_64) "
                                "Gecko/20100101 Firefox/128.0"
                            )
                        },
                    )
                    with urllib.request.urlopen(req) as resp:
                        with open(dest, "wb") as fh:
                            fh.write(resp.read())
                except Exception:
                    pass

            threading.Thread(target=_fetch, daemon=True).start()

    def _uri_to_markdown_image(self, uri: str) -> str:
        """Return a Markdown image snippet for *uri*.

        file:// URIs are converted to a path relative to the current document
        directory so the snippet works when the Markdown file is moved.
        http/https URIs are used verbatim.
        """
        if uri.startswith(("http://", "https://")):
            return f"![image]({uri})"
        if uri.startswith("file://"):
            image_path = unquote(urlparse(uri).path)
            base_path = unquote(urlparse(self._base_uri).path).rstrip("/")
            try:
                rel = os.path.relpath(image_path, base_path).replace(os.sep, "/")
                return f"![image]({rel})"
            except ValueError:
                return f"![image]({image_path})"
        return f"![image]({uri})"

    def _copy_to_clipboard(self, text: str) -> None:
        """Copy *text* to the system clipboard."""
        try:
            display = Gdk.Display.get_default()
            if display is None:
                return
            provider = Gdk.ContentProvider.new_for_value(GObject.Value(str, text))
            display.get_clipboard().set_content(provider)
        except Exception:
            pass

    def _connect_download_signal(self, context: object) -> None:
        """Connect the download-started signal to _on_download_started.

        The signal location changed between WebKit versions:
          WebKit 6.0  — WebKitNetworkSession (via view.get_network_session()
                         or NetworkSession.get_default())
          WebKit2 4.1 — WebKitWebContext
        """
        source = None
        if hasattr(self._view, "get_network_session"):
            source = self._view.get_network_session()
        elif hasattr(_WebKitModule, "NetworkSession"):
            source = _WebKitModule.NetworkSession.get_default()
        else:
            source = context
        if source is not None:
            try:
                source.connect("download-started", self._on_download_started)
            except TypeError:
                pass  # signal unavailable on this WebKit build — silently skip

    def _on_download_started(self, _context: object, download: object) -> None:
        """Show a save dialog when WebKit initiates a download (e.g. 'Save Image As').

        WebKit silently abandons downloads unless a handler calls
        ``download.set_destination()``.  We restrict handling to downloads that
        originated from our own WebView so other WebViews in the same process
        (e.g. the ImageViewerWindow) are unaffected.
        """
        if (
            hasattr(download, "get_web_view")
            and download.get_web_view() is not self._view
        ):
            return

        uri = download.get_request().get_uri()
        # get_suggested_filename() was removed in WebKit 6.0; fall back to
        # extracting a name from the URI (or a sensible default for data: URIs).
        suggested = _default_save_filename(uri)

        dialog = Gtk.FileDialog.new()
        dialog.set_initial_name(suggested)
        parent = self._view.get_root() if self._view else None
        dialog.save(
            parent,
            None,
            lambda d, r: self._on_save_dialog_response(d, r, download),
        )

    def _on_save_dialog_response(
        self,
        dialog: Gtk.FileDialog,
        result: object,
        download: object,
    ) -> None:
        try:
            gfile = dialog.save_finish(result)
        except GLib.Error:
            # User dismissed the dialog — no destination set, WebKit
            # abandons the download automatically. Do NOT call cancel();
            # it segfaults in WebKit 6.0.
            return
        if gfile is None:
            return

        uri = download.get_request().get_uri()
        if uri.startswith("data:"):
            # WebKit cannot stream data: URIs to disk (no response body exists).
            # Write the decoded bytes directly and let the WebKit download
            # exhaust itself — calling cancel() on a data: URI download
            # segfaults in WebKit 6.0.
            path = gfile.get_path()
            if not path:
                return
            try:
                header, _, data_part = uri.partition(",")
                if ";base64" in header:
                    raw = base64.b64decode(data_part)
                else:
                    raw = unquote(data_part).encode("utf-8")
                with open(path, "wb") as fh:
                    fh.write(raw)
            except Exception:
                pass
        else:
            # WebKit 6.0: set_destination() expects an absolute path.
            # WebKit 4.x expected a file:// URI — get_path() works for both
            # since it always returns an absolute filesystem path.
            path = gfile.get_path()
            if path:
                download.set_destination(path)

    def _on_create_web_view(
        self, _webview: object, navigation_action: object
    ) -> object:
        """Handle WebKit's request to open a new window (e.g. right-click →
        'Open Image in New Window' or 'Open Link in New Window').

        We never create a new WebView window. Instead we open the URI in the
        system's default application (image viewer for local files, browser
        for http/https) and return None to cancel the new-window creation.
        """
        try:
            uri = navigation_action.get_request().get_uri()
        except Exception:
            return None
        self._open_uri_externally(uri)
        return None

    def _open_uri_externally(self, uri: str) -> None:
        """Open *uri* in the system default application (browser / image viewer).

        ``data:`` URIs (e.g. inline SVG Mermaid diagrams) are written to a
        temporary file first, because ``Gio.AppInfo.launch_default_for_uri``
        does not handle ``data:`` scheme URIs.
        """
        if uri.startswith("data:"):
            self._open_data_uri_externally(uri)
            return
        try:
            Gio.AppInfo.launch_default_for_uri(uri, None)
        except GLib.Error:
            pass

    def _open_data_uri_externally(self, uri: str) -> None:
        """Display or open a data: URI appropriately.

        SVG images are opened in Calamus's own WebKit viewer window because
        common system image viewers (gthumb, eog) do not fully support SVG.
        All other image types are decoded to a temporary file and opened with
        the system default application.
        """
        header, _, data_part = uri.partition(",")
        mime = header[len("data:") :].split(";")[0].strip().lower()

        if mime == "image/svg+xml":
            # Use the built-in WebKit viewer — it renders SVG perfectly.
            from calamus.imageviewer import ImageViewerWindow

            viewer = ImageViewerWindow(uri, title="SVG Viewer")
            viewer.present()
            return

        # For other image types decode to a temp file and use the system app.
        try:
            _MIME_EXTS = {
                "image/png": ".png",
                "image/jpeg": ".jpg",
                "image/gif": ".gif",
                "image/webp": ".webp",
            }
            ext = _MIME_EXTS.get(mime, "")
            is_base64 = ";base64" in header
            if is_base64:
                raw = base64.b64decode(data_part)
            else:
                raw = unquote(data_part).encode("utf-8")
            with tempfile.NamedTemporaryFile(
                suffix=ext, delete=False, prefix="calamus_img_"
            ) as tmp:
                tmp.write(raw)
                tmp_path = tmp.name
        except Exception:
            return
        try:
            Gio.AppInfo.launch_default_for_uri(f"file://{tmp_path}", None)
        except GLib.Error:
            pass

    def _on_dark_changed(
        self, _style_manager: Adw.StyleManager, _param: object
    ) -> None:
        if self._last_markdown:
            self.update(self._last_markdown)

    def _inject_tooltip_script(self) -> None:
        """Inject tooltip hover detection script into all web pages.
        
        This script is injected via UserContentManager.add_script() so it runs
        in the WebView's JavaScript context and has access to window.webkit
        message handlers.
        """
        script_source = """
console.log('[TOOLTIP-JS] Script injected via UserContentManager');

// Post a test message to verify script is running
try {
  if (window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.tooltip) {
    window.webkit.messageHandlers.tooltip.postMessage(JSON.stringify({
      href: '[TOOLTIP-JS] Script initialization test',
      state: 'test'
    }));
  }
} catch(e) {
  console.log('[TOOLTIP-JS] Error in test message:', e);
}

function attachTooltipsToLinks() {
  const links = document.querySelectorAll('a[href]');
  console.log(`[TOOLTIP-JS] attachTooltipsToLinks: found ${links.length} links`);
  
  links.forEach((link, idx) => {
    console.log(`[TOOLTIP-JS] Attaching listeners to link ${idx}: ${link.href}`);
    
    link.addEventListener('mouseenter', function() {
      const href = this.getAttribute('href');
      console.log(`[TOOLTIP-JS] mouseenter on link: ${href}`);
      
      if (href) {
        console.log(`[TOOLTIP-JS] href exists: ${href}`);
        if (window.webkit) {
          console.log('[TOOLTIP-JS] window.webkit exists');
          if (window.webkit.messageHandlers) {
            console.log('[TOOLTIP-JS] window.webkit.messageHandlers exists');
            if (window.webkit.messageHandlers.tooltip) {
              console.log('[TOOLTIP-JS] window.webkit.messageHandlers.tooltip exists');
              window.webkit.messageHandlers.tooltip.postMessage(JSON.stringify({
                href: href,
                state: 'enter'
              }));
              console.log('[TOOLTIP-JS] postMessage sent for enter');
            } else {
              console.log('[TOOLTIP-JS] window.webkit.messageHandlers.tooltip does NOT exist');
            }
          } else {
            console.log('[TOOLTIP-JS] window.webkit.messageHandlers does NOT exist');
          }
        } else {
          console.log('[TOOLTIP-JS] window.webkit does NOT exist');
        }
      } else {
        console.log('[TOOLTIP-JS] href is empty');
      }
    }, false);
    
    link.addEventListener('mouseleave', function() {
      console.log('[TOOLTIP-JS] mouseleave fired');
      if (window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.tooltip) {
        window.webkit.messageHandlers.tooltip.postMessage(JSON.stringify({
          href: '',
          state: 'leave'
        }));
        console.log('[TOOLTIP-JS] postMessage sent for leave');
      }
    }, false);
  });
}

// Attach when DOM is ready
if (document.readyState === 'loading') {
  console.log('[TOOLTIP-JS] DOM still loading, waiting for DOMContentLoaded');
  document.addEventListener('DOMContentLoaded', function() {
    console.log('[TOOLTIP-JS] DOMContentLoaded fired');
    attachTooltipsToLinks();
  }, false);
} else {
  console.log('[TOOLTIP-JS] DOM already loaded, attaching immediately');
  attachTooltipsToLinks();
}

// Re-attach when content is dynamically added (Mermaid, etc)
const observer = new MutationObserver(function(mutations) {
  console.log('[TOOLTIP-JS] MutationObserver fired');
  const hasNewLinks = mutations.some(m => 
    Array.from(m.addedNodes).some(n => 
      n.nodeName === 'A' || (n.querySelectorAll && n.querySelectorAll('a').length > 0)
    )
  );
  if (hasNewLinks) {
    console.log('[TOOLTIP-JS] New links detected, re-attaching');
    attachTooltipsToLinks();
  }
});

if (document.body) {
  console.log('[TOOLTIP-JS] Setting up MutationObserver on document.body');
  observer.observe(document.body, { childList: true, subtree: true });
} else {
  console.log('[TOOLTIP-JS] document.body does not exist');
}

console.log('[TOOLTIP-JS] Script initialization complete');
"""
        try:
            script = _WebKitModule.UserScript(
                script_source,
                _WebKitModule.UserContentInjectedFrames.ALL_FRAMES,
                _WebKitModule.UserScriptInjectionTime.END,  # END not END_OF_DOCUMENT
                None,  # allow_list
                None,  # block_list
            )
            self._user_content_manager.add_script(script)
        except Exception as e:
            import traceback
            traceback.print_exc()

    def _on_load_changed(self, _webview: object, load_event: object) -> None:
        if load_event != _WebKitModule.LoadEvent.FINISHED:
            return
        if self._pending_scroll_restore_ratio is None:
            return
        ratio = self._pending_scroll_restore_ratio
        self._pending_scroll_restore_ratio = None
        self._restore_scroll_ratio(ratio)

    def _on_tooltip_message(self, manager: object, js_value: object, *args) -> None:
        """Handle messages from JavaScript link hover detection.
        
        Per official PyGObject WebKit-6.0 API docs:
        https://api.pygobject.gnome.org/WebKit-6.0/class-UserContentManager.html#signal-UserContentManager.script-message-received
        
        Signal parameters: manager (UserContentManager), value (JavaScriptCore.Value)
        
        Args:
            manager: The UserContentManager that received the message.
            js_value: The JavaScriptCore.Value containing the JavaScript data.
        """
        try:
            # js_value is a JavaScriptCore.Value
            # to_json(indent) returns a JSON-encoded string representation
            if not hasattr(js_value, "to_json"):
                return
            
            # to_json(indent) - indent=0 means no indentation
            json_encoded = js_value.to_json(0)
            
            if not json_encoded or json_encoded.strip() == "":
                return
            
            # to_json() returns a JSON-encoded string, so we need to parse it twice:
            # First parse extracts the JSON string itself
            # Second parse converts the JSON string to the actual object
            json_str = json.loads(json_encoded)
            data = json.loads(json_str)
            
            href = data.get("href", "")
            state = data.get("state", "")
            
            # Show or hide tooltip based on state
            if state == "enter" and href and not href.startswith("[TOOLTIP"):
                self._tooltip_manager.show(href)
                self._footer_wrapper.set_visible(True)
                if self._on_link_hover:
                    self._on_link_hover(href)
            elif state == "leave":
                self._tooltip_manager.hide()
                self._footer_wrapper.set_visible(False)
        except (json.JSONDecodeError, AttributeError, TypeError):
            pass

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
        """Main-thread callback: re-render once background SVGs are ready.

        Captures the current scroll position before reloading the page and
        restores it after WebKit finishes loading, so the view doesn't snap
        back to the top when a Mermaid diagram finishes rendering.
        """
        if markdown_text == self._last_markdown:
            self._capture_scroll_ratio(self._apply_async_render_with_scroll)
        return GLib.SOURCE_REMOVE

    def _apply_async_render_with_scroll(self, ratio: float | None) -> None:
        """Re-render the page and schedule a scroll restore for the given ratio."""
        if ratio is not None:
            self._pending_scroll_restore_ratio = ratio
        preprocessed = preprocess_with_cache(self._last_markdown, self._mermaid_cache)
        html_body = self._renderer.render_preprocessed(preprocessed)
        self._render_page(html_body, "", self._style_manager.get_dark())

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
        html_text = html_text.replace(
            "__PREVIEW_FONT_SCALE__", f"{self._zoom_level:.3f}"
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
        return self._container

    def zoom_by(self, factor: float) -> None:
        if factor <= 0:
            return
        next_level = max(
            self._MIN_ZOOM,
            min(self._MAX_ZOOM, round(self._zoom_level * factor, 3)),
        )
        if next_level == self._zoom_level:
            return
        self._set_zoom_preserving_scroll(next_level)

    def reset_zoom(self) -> None:
        if self._zoom_level == self._DEFAULT_ZOOM:
            return
        self._set_zoom_preserving_scroll(self._DEFAULT_ZOOM)

    def _set_zoom_preserving_scroll(self, next_level: float) -> None:
        self._capture_scroll_ratio(
            lambda ratio: self._apply_zoom_with_scroll_restore(next_level, ratio)
        )

    def _apply_zoom_with_scroll_restore(
        self, next_level: float, ratio: float | None
    ) -> None:
        self._pending_scroll_restore_ratio = ratio
        self._zoom_level = next_level
        self.update(self._last_markdown)

    def _capture_scroll_ratio(self, callback: Callable[[float | None], None]) -> None:
        js = """
            (() => {
              const maxY = Math.max(
                1,
                document.documentElement.scrollHeight - window.innerHeight
              );
              const y = Math.max(0, window.scrollY || window.pageYOffset || 0);
              return y / maxY;
            })();
        """
        if hasattr(self._view, "evaluate_javascript"):
            self._view.evaluate_javascript(
                js,
                -1,
                None,
                None,
                None,
                self._on_capture_scroll_ratio_done,
                callback,
            )
            return
        callback(None)

    def _on_capture_scroll_ratio_done(
        self,
        webview: object,
        result: object,
        callback: Callable[[float | None], None],
    ) -> None:
        callback(self._extract_scroll_ratio(webview, result))

    def _extract_scroll_ratio(self, webview: object, result: object) -> float | None:
        js_result = self._finish_javascript(webview, result)
        if js_result is None:
            return None
        if hasattr(js_result, "is_number") and js_result.is_number():
            return max(0.0, min(1.0, float(js_result.to_double())))
        return None

    def _finish_javascript(self, webview: object, result: object) -> object | None:
        if hasattr(webview, "evaluate_javascript_finish"):
            try:
                return webview.evaluate_javascript_finish(result)
            except GLib.Error:
                return None
        return None

    def _restore_scroll_ratio(self, ratio: float | None) -> None:
        if ratio is None:
            return
        safe_ratio = max(0.0, min(1.0, ratio))
        js = (
            "(() => {"
            "const maxY = Math.max(0, document.documentElement.scrollHeight - window.innerHeight);"
            f"window.scrollTo(0, maxY * {safe_ratio:.6f});"
            "})();"
        )
        if hasattr(self._view, "evaluate_javascript"):
            self._view.evaluate_javascript(js, -1, None, None, None, None, None)
        elif hasattr(self._view, "run_javascript"):
            self._view.run_javascript(js, None, None, None)


class TextViewPreview(AbstractPreview):
    """Fallback preview that shows raw Markdown text."""

    def __init__(self) -> None:
        self._view = Gtk.TextView()
        self._view.set_editable(False)
        self._view.set_wrap_mode(Gtk.WrapMode.WORD)
        self._view.set_hexpand(True)
        self._view.set_vexpand(True)
        self._css_provider = Gtk.CssProvider()
        self._font_size_pt = 11.0
        self._default_font_size_pt = self._font_size_pt
        self._view.add_css_class("calamus-preview-fallback")
        self._apply_font_size(self._font_size_pt)

    def update(self, markdown_text: str) -> None:
        self._view.get_buffer().set_text(markdown_text)

    def set_file_path(self, path: str | None) -> None:
        """Text fallback does not resolve links."""

    def set_base_path(self, path: str | None) -> None:
        """Text fallback does not resolve links."""

    def get_widget(self) -> Gtk.Widget:
        return self._view

    def zoom_by(self, factor: float) -> None:
        if factor <= 0:
            return
        size = max(8.0, min(48.0, round(self._font_size_pt * factor, 1)))
        self._apply_font_size(size)

    def reset_zoom(self) -> None:
        self._apply_font_size(self._default_font_size_pt)

    def _apply_font_size(self, size_pt: float) -> None:
        self._font_size_pt = size_pt
        self._css_provider.load_from_string(
            f"textview.calamus-preview-fallback {{ font-size: {self._font_size_pt}pt; }}"
        )
        Gtk.StyleContext.add_provider_for_display(
            self._view.get_display(),
            self._css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )


def create_preview(
    on_open_path: Callable[[str], None] | None = None,
    on_link_hover: Callable[[str], None] | None = None,
) -> AbstractPreview:
    """Create the best preview implementation for the current system."""
    if _WEBKIT_AVAILABLE:
        return WebKitPreview(on_open_path=on_open_path, on_link_hover=on_link_hover)
    return TextViewPreview()
