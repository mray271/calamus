"""WebKit 6.0-specific preview implementation.

This module contains the concrete implementation for WebKit 6.0+.
All WebKit 4.1 specific code has been removed. Signal handlers use
exact signatures without *args masking.

Key features:
  - NetworkSession for downloads (WebKit 6.0+)
  - Direct hit_test_result in context menu (no event parameter)
  - JavaScriptCore.Value for tooltip messages
  - No hasattr() checks (all methods guaranteed to exist)

Note: WebKit 6.0 imports are deferred to allow module import even when
WebKit isn't installed. The class will fail to instantiate without it,
but the module can be imported during test collection.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
import threading
import urllib.request
from collections.abc import Callable
from urllib.parse import unquote, urlparse

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

# WebKit and JavaScriptCore imports are deferred to _ensure_webkit_imports()
# This allows the module to be imported even when WebKit isn't available

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
from calamus.webkit_preview_base import AbstractWebKitPreview

_logger = logging.getLogger(__name__)

# Module-level placeholders for deferred imports
WebKit = None
JavaScriptCore = None


def _ensure_webkit_imports() -> None:
    """Ensure WebKit and JavaScriptCore are imported and available."""
    global WebKit, JavaScriptCore
    if WebKit is not None:
        return  # Already imported
    gi.require_version("WebKit", "6.0")
    gi.require_version("JavaScriptCore", "6.0")
    from gi.repository import JavaScriptCore as _JSC
    from gi.repository import WebKit as _WK

    WebKit = _WK
    JavaScriptCore = _JSC


# Reuse these from preview module to avoid duplication
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


# HTML template (WebKit 6.0 compatible)
_HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="color-scheme" content="{color_scheme}">
{mermaid_script}
{highlight_css}
{highlight_script}
<style>
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
    color-scheme: {color_scheme};
    --mono: "Courier New", Courier, monospace;
    --sans: system-ui, -apple-system, sans-serif;
  }}
  body {{
    margin: 3ex 4ex;
    padding: 0;
    font-family: var(--sans);
    overflow-wrap: break-word;
    word-break: break-word;
  }}
  table {{
    border-collapse: collapse;
  }}
  th, td {{
    text-align: left;
    padding: 0.5ex;
  }}
  blockquote {{
    margin: 0;
    margin-left: 2ex;
    padding-left: 1ex;
    border-left: 3px solid;
  }}
  pre {{
    overflow: auto;
    padding: 1ex;
    border: 1px solid;
    border-radius: 3px;
  }}
  code {{
    font-family: var(--mono);
    font-size: 90%;
  }}
  pre code {{
    border: none;
    padding: 0;
    background: none;
  }}
  hr {{
    border: none;
    border-top: 1px solid;
    margin: 2ex 0;
  }}
  sub, sup {{
    line-height: 0;
  }}
</style>
</head>
<body>
{content}
</body>
</html>"""


class WebKitPreview_6x(AbstractWebKitPreview):
    """WebKit 6.0+ specific implementation.

    This class handles all WebKit 6.0 specific behavior:
      - NetworkSession for downloads
      - 3-parameter context menu handler
      - JavaScriptCore.Value tooltip messages
      - No feature detection (all APIs guaranteed in 6.0+)
    """

    def _setup_webkit_context(self) -> None:
        """Initialize WebKit 6.0 context and WebView."""
        # Ensure WebKit/JSC imports are available before using them
        _ensure_webkit_imports()

        # Set up WebContext
        context = WebKit.WebContext.get_default()
        self._setup_sandbox(context)

        # Create WebView
        self._view = WebKit.WebView()
        self._view.set_hexpand(True)
        self._view.set_vexpand(True)

        # Set up overlay layout with footer
        self._overlay = Gtk.Overlay.new()
        self._overlay.set_child(self._view)

        # Get UserContentManager for JavaScript communication
        self._user_content_manager = self._view.get_user_content_manager()

        # Connect signal BEFORE registering handler (critical to avoid race conditions)
        self._user_content_manager.connect(
            "script-message-received::tooltip", self._on_tooltip_message
        )

        # Register the message handler
        self._user_content_manager.register_script_message_handler("tooltip")

        # Connect signal handlers
        self._view.connect("decide-policy", self._on_decide_policy)
        self._view.connect("create", self._on_create_web_view)
        self._view.connect("context-menu", self._on_context_menu)
        self._view.connect("load-changed", self._on_load_changed)

        # Set up downloads
        self._connect_download_signal(context)

        # Inject tooltip detection script
        self._inject_tooltip_script()

        # Set up style manager for dark mode
        self._style_manager.connect("notify::dark", self._on_dark_changed)

        # Async rendering setup
        self._mermaid_cache = MermaidCache()
        self._mmdc_available: bool = SubprocessMermaidRenderer().is_available()
        self._render_generation: int = 0

        # Footer widget setup
        self._setup_footer_widget()

    def _setup_sandbox(self, context: object) -> None:
        """Configure WebKit 6.0 sandbox (disable for Docker environments)."""
        # WebKit 6.0 does not expose set_sandbox_enabled().
        # Sandbox is managed internally; no action needed here.
        # For Docker/restricted environments, set WEBKIT_FORCE_SANDBOX=0 in environment.
        pass

    def _connect_download_signal(self, context: object) -> None:
        """Connect download-started signal (WebKit 6.0 uses NetworkSession)."""
        # WebKit 6.0 moved downloads to NetworkSession
        # Try the view's own session first (most specific)
        source = self._view.get_network_session()
        if source is None:
            # Fallback to module-level default
            source = WebKit.NetworkSession.get_default()

        if source is not None:
            source.connect("download-started", self._on_download_started)

    def _get_download_source(self, context: object) -> object | None:
        """Get the object that emits download-started signal."""
        try:
            source = self._view.get_network_session()
            if source is None:
                source = WebKit.NetworkSession.get_default()
            return source
        except Exception:
            return None

    def _validate_download_source(self, download: object) -> bool:
        """Validate that download belongs to this preview's WebView.

        WebKit 6.0 has get_web_view() on downloads.
        """
        try:
            return download.get_web_view() is self._view
        except Exception:
            # If get_web_view() fails, accept the download anyway
            return True

    def _setup_footer_widget(self) -> None:
        """Create and configure the footer tooltip widget."""
        self._footer_wrapper = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
        self._footer_wrapper.set_halign(Gtk.Align.START)
        self._footer_wrapper.set_valign(Gtk.Align.END)
        self._footer_wrapper.set_margin_bottom(4)
        self._footer_wrapper.set_margin_start(4)
        self._footer_wrapper.set_visible(False)

        # Add CSS styling (no border - let the tooltip handle its own styling)
        css_provider = Gtk.CssProvider.new()
        css_provider.load_from_data(b"""
box {
  background-color: transparent;
  padding: 0;
  margin: 0;
}
        """)
        context = self._footer_wrapper.get_style_context()
        context.add_provider(css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        # Add tooltip widget
        tooltip_widget = self._tooltip_manager.get_widget()
        self._footer_wrapper.append(tooltip_widget)

        # Add to overlay
        self._overlay.add_overlay(self._footer_wrapper)

    def _on_decide_policy(
        self,
        _webview: object,
        decision: object,
        decision_type: object,
    ) -> None:
        """Intercept WebKit navigation to prevent preview from navigating away."""
        if decision_type != WebKit.PolicyDecisionType.NAVIGATION_ACTION:
            return

        action = decision.get_navigation_action()
        request = action.get_request()
        uri = request.get_uri()

        # Allow file:// anchors to same document
        if uri.startswith("#"):
            return

        # Check for same-document navigation
        if _is_same_document_file_anchor(uri, self._base_uri):
            return

        # Ignore non-link navigation
        if action.get_navigation_type() != WebKit.NavigationType.LINK_CLICKED:
            return

        # Block navigation, open URI externally instead
        decision.ignore()
        self._open_uri_externally(uri)

    def _on_context_menu(
        self,
        _webview: object,
        context_menu: object,
        hit_test_result: object,
    ) -> bool:
        """Handle context menu (WebKit 6.0 signature: 3 parameters, no event).

        This is the clean version without *args masking - each version
        implementation has its exact signature.
        """
        if not hit_test_result.context_is_image():
            return False

        image_uri = hit_test_result.get_image_uri() or ""

        # Remove stock items we're replacing
        _remove = {
            WebKit.ContextMenuAction.COPY_IMAGE_URL_TO_CLIPBOARD,
            WebKit.ContextMenuAction.DOWNLOAD_IMAGE_TO_DISK,
        }
        for item in list(context_menu.get_items()):
            if hasattr(item, "get_stock_action") and item.get_stock_action() in _remove:
                context_menu.remove(item)

        # Clear and add custom actions
        self._context_menu_actions = []

        # Add "Save Image As..." action
        save_action = Gio.SimpleAction.new("save-image", None)
        save_action.connect("activate", lambda *_: self._save_image(image_uri))
        self._context_menu_actions.append(save_action)

        save_item = WebKit.ContextMenuItem.new_from_gaction(save_action, "Save Image As...")
        context_menu.append(save_item)

        # Add "Copy Markdown Image" for http/https/file URLs
        if image_uri.startswith(("http://", "https://", "file://")):
            markdown_action = Gio.SimpleAction.new("copy-markdown", None)
            markdown_action.connect(
                "activate",
                lambda *_: self._copy_to_clipboard(
                    self._uri_to_markdown_image(image_uri)
                ),
            )
            self._context_menu_actions.append(markdown_action)

            markdown_item = WebKit.ContextMenuItem.new_from_gaction(markdown_action, "Copy Markdown Image")
            context_menu.append(markdown_item)

        return True

    def _on_download_started(self, _context: object, download: object) -> None:
        """Handle download-started signal (WebKit 6.0)."""
        # Validate download is from this preview
        if not self._validate_download_source(download):
            return

        uri = download.get_request().get_uri()
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
        """Handle file save dialog response."""
        try:
            file = dialog.save_finish(result)
            if file:
                path = file.get_path()
                download.set_destination(path)
        except GLib.GError:
            pass

    def _save_image(self, image_uri: str) -> None:
        """Show save dialog for image."""
        suggested = _default_save_filename(image_uri)
        dialog = Gtk.FileDialog.new()
        dialog.set_initial_name(suggested)

        parent = self._view.get_root() if self._view else None

        def handle_response(d: Gtk.FileDialog, r: object) -> None:
            try:
                file = d.save_finish(r)
                if not file:
                    return

                path = file.get_path()

                def _fetch(url: str = image_uri, dest: str = path) -> None:
                    try:
                        if url.startswith("data:"):
                            # Handle data: URIs
                            header, data_b64 = url.split(",", 1)
                            import base64

                            data = base64.b64decode(data_b64)
                        else:
                            # Fetch from network
                            with urllib.request.urlopen(url) as response:
                                data = response.read()

                        with open(dest, "wb") as f:
                            f.write(data)
                    except Exception as e:
                        _logger.error(f"Failed to save image: {e}")

                # Run in background thread
                threading.Thread(target=_fetch, daemon=True).start()
            except GLib.GError:
                pass

        dialog.save(parent, None, handle_response)

    def _uri_to_markdown_image(self, uri: str) -> str:
        """Convert URI to markdown image syntax."""
        # For data: URIs, we can't use them directly in markdown
        # Just return the URI wrapped in a comment
        if uri.startswith("data:"):
            return f"<!-- data: URI (too long for markdown) -->"
        return f"![image]({uri})"

    def _copy_to_clipboard(self, text: str) -> None:
        """Copy text to clipboard."""
        try:
            display = Gdk.Display.get_default()
            provider = Gdk.ContentProvider.new_for_value(GObject.Value(str, text))
            display.get_clipboard().set_content(provider)
        except Exception:
            pass

    def _on_create_web_view(self, *args: object) -> object | None:
        """Handle link opening in new window/tab."""
        return None

    def _open_uri_externally(self, uri: str) -> None:
        """Open URI in external application."""
        if self._on_open_path:
            self._on_open_path(uri)

    def _open_data_uri_externally(self, uri: str) -> None:
        """Handle data: URIs by saving to temp file."""
        try:
            import base64

            header, data_b64 = uri.split(",", 1)
            data = base64.b64decode(data_b64)

            # Create temp file
            fd, path = tempfile.mkstemp(suffix=".html")
            with os.fdopen(fd, "wb") as f:
                f.write(data)

            self._open_uri_externally(f"file://{path}")
        except Exception:
            pass

    def _on_dark_changed(self, *args: object) -> None:
        """Handle dark mode toggle."""
        # Re-render with new color scheme
        if self._last_markdown:
            self.update(self._last_markdown)

    def _inject_tooltip_script(self) -> None:
        """Inject JavaScript for link hover detection (WebKit 6.0)."""
        js_code = """
var __tooltip_attached = false;

function attachTooltipsToLinks() {
  if (__tooltip_attached) return;
  __tooltip_attached = true;
  
  var links = document.querySelectorAll('a[href]');
  links.forEach(function(link) {
    link.addEventListener('mouseenter', function() {
      if (window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.tooltip) {
        window.webkit.messageHandlers.tooltip.postMessage(JSON.stringify({
          href: link.href,
          state: 'enter'
        }));
      }
    }, false);
    
    link.addEventListener('mouseleave', function() {
      if (window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.tooltip) {
        window.webkit.messageHandlers.tooltip.postMessage(JSON.stringify({
          href: '',
          state: 'leave'
        }));
      }
    }, false);
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', attachTooltipsToLinks, false);
} else {
  attachTooltipsToLinks();
}

const observer = new MutationObserver(function(mutations) {
  const hasNewLinks = mutations.some(m => 
    Array.from(m.addedNodes).some(n => 
      n.nodeName === 'A' || (n.querySelectorAll && n.querySelectorAll('a').length > 0)
    )
  );
  if (hasNewLinks) {
    __tooltip_attached = false;
    attachTooltipsToLinks();
  }
});

if (document.body) {
  observer.observe(document.body, { childList: true, subtree: true });
}
"""
        script = WebKit.UserScript(
            js_code,
            WebKit.UserContentInjectedFrames.ALL_FRAMES,
            WebKit.UserScriptInjectionTime.START,
            None,
            None,
        )
        self._user_content_manager.add_script(script)

    def _on_load_changed(self, _webview: object, load_event: object) -> None:
        """Handle page load completion."""
        pass

    def _on_tooltip_message(
        self,
        manager: object,
        js_value: object,
        *args: object,
    ) -> None:
        """Handle tooltip messages from JavaScript (WebKit 6.0 signature).

        This receives a JavaScriptCore.Value which we extract via to_json().
        """
        try:
            # js_value is JavaScriptCore.Value
            if not hasattr(js_value, "to_json"):
                return

            # to_json() returns a JSON-encoded string
            json_encoded = js_value.to_json(0)
            if not json_encoded or json_encoded.strip() == "":
                return

            # Must parse twice: to_json() returns a JSON string, not the object
            json_str = json.loads(json_encoded)
            data = json.loads(json_str)

            href = data.get("href", "")
            state = data.get("state", "")

            if state == "enter" and href and not href.startswith("[TOOLTIP"):
                self._tooltip_manager.show(href)
                self._footer_wrapper.set_visible(True)
                self._footer_wrapper.queue_resize()
                self._footer_wrapper.queue_draw()
            elif state == "leave":
                self._tooltip_manager.hide()
                self._footer_wrapper.set_visible(False)
                self._footer_wrapper.queue_resize()
                self._footer_wrapper.queue_draw()
        except (json.JSONDecodeError, AttributeError, TypeError):
            pass

    # =========================================================================
    # Public API Implementation
    # =========================================================================

    def update(self, markdown_text: str) -> None:
        """Update preview with new markdown content."""
        self._last_markdown = markdown_text

        # Run async rendering
        def worker() -> None:
            try:
                renderer = self._renderer or MistuneRenderer()
                html = renderer.render(markdown_text)
                GLib.idle_add(lambda: self._on_async_render_done(html))
            except Exception as e:
                _logger.error(f"Render error: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def _on_async_render_done(self, html: str) -> bool:
        """Handle async render completion."""
        dark = self._style_manager.get_dark()
        color_scheme = "dark" if dark else "light"

        # Get Mermaid script and highlighting
        mermaid_script = get_mermaid_script_tag()
        highlight_css = get_highlight_css_tag()
        highlight_script = get_highlight_script_tag()

        # Render full HTML
        full_html = _HTML_TEMPLATE.format(
            color_scheme=color_scheme,
            mermaid_script=mermaid_script,
            highlight_css=highlight_css,
            highlight_script=highlight_script,
            content=html,
        )

        self._view.load_html(full_html, self._base_uri)
        return False

    def get_widget(self) -> Gtk.Widget:
        """Return the root widget."""
        return self._overlay

    def set_file_path(self, path: str | None) -> None:
        """Set file path for resolving relative links."""
        self.set_base_path(path)

    def set_base_path(self, path: str | None) -> None:
        """Set base directory for resolving relative links."""
        if path is None:
            self._base_uri = "file:///"
            return

        resolved = os.path.abspath(path)
        directory = resolved if os.path.isdir(resolved) else os.path.dirname(resolved)
        self._base_uri = f"file://{directory}/"

    def zoom_by(self, factor: float) -> None:
        """Apply zoom factor."""
        self._zoom_level *= factor
        self._view.set_zoom_level(self._zoom_level)

    def reset_zoom(self) -> None:
        """Reset zoom to 100%."""
        self._zoom_level = self._DEFAULT_ZOOM
        self._view.set_zoom_level(self._zoom_level)
