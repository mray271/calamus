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

import base64
import json
import logging
import os
import shutil
import tempfile
import threading
import urllib.request
import xml.etree.ElementTree as ET
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


def _decode_data_uri_bytes(uri: str) -> tuple[str, bytes]:
    """Decode a data: URI into ``(mime, raw_bytes)``."""
    header, _, data_part = uri.partition(",")
    mime = header[len("data:") :].split(";")[0].strip().lower()
    raw = (
        base64.b64decode(data_part)
        if ";base64" in header
        else unquote(data_part).encode("utf-8")
    )
    return mime, raw


def _is_svg_uri(uri: str) -> bool:
    """Return True when *uri* likely points to SVG content."""
    if uri.startswith("data:"):
        mime, _raw = _decode_data_uri_bytes(uri)
        return mime == "image/svg+xml"
    return urlparse(uri).path.lower().endswith(".svg")


def _svg_to_compatibility_mode(raw: bytes) -> bytes:
    """Rewrite SVG foreignObject labels into plain <text> nodes when possible."""
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return raw

    parent_map = {child: parent for parent in root.iter() for child in parent}
    updated = False
    for node in list(root.iter()):
        if not node.tag.endswith("foreignObject"):
            continue
        parent = parent_map.get(node)
        if parent is None:
            continue
        label = " ".join(part.strip() for part in node.itertext() if part.strip())
        ns = node.tag.split("}")[0].strip("{") if node.tag.startswith("{") else ""
        text_tag = f"{{{ns}}}text" if ns else "text"
        text_el = ET.Element(
            text_tag,
            {
                "x": "0",
                "y": "0",
                "text-anchor": "middle",
                "dominant-baseline": "middle",
            },
        )
        text_el.text = label
        idx = list(parent).index(node)
        parent.remove(node)
        parent.insert(idx, text_el)
        updated = True

    if not updated:
        return raw
    return ET.tostring(root, encoding="utf-8")


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
  pre.mermaid {{
    background: transparent;
    padding: 0;
    border: none;
    text-align: center;
  }}
  pre.mermaid svg {{
    display: inline-block;
  }}
  img.mermaid-diagram {{
    display: block;
    margin-left: auto;
    margin-right: auto;
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

    _LOADING_INDICATOR_DELAY_MS = 200

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
        self._render_spinner_timeout_id: int | None = None
        self._has_rendered_content: bool = False

        # Footer widget setup
        self._setup_footer_widget()
        self._setup_loading_overlay()

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

    def _setup_loading_overlay(self) -> None:
        """Create and configure the loading overlay shown during render work."""
        self._loading_overlay = Gtk.Box.new(Gtk.Orientation.VERTICAL, 6)
        self._loading_overlay.set_halign(Gtk.Align.CENTER)
        self._loading_overlay.set_valign(Gtk.Align.CENTER)
        self._loading_overlay.set_visible(False)
        self._loading_overlay.set_name("preview-loading-overlay")

        css_provider = Gtk.CssProvider.new()
        css_provider.load_from_data(b"""
#preview-loading-overlay {
  background-color: alpha(@theme_bg_color, 0.82);
  border: 1px solid alpha(@theme_fg_color, 0.18);
  border-radius: 8px;
  padding: 10px 14px;
}
        """)
        style_context = self._loading_overlay.get_style_context()
        style_context.add_provider(
            css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        self._loading_spinner = Gtk.Spinner.new()
        self._loading_overlay.append(self._loading_spinner)

        label = Gtk.Label.new("Rendering preview...")
        self._loading_overlay.append(label)

        self._overlay.add_overlay(self._loading_overlay)

    def _set_loading_visible(self, visible: bool) -> None:
        """Show/hide loading overlay and spinner."""
        if visible:
            self._loading_spinner.start()
            self._loading_overlay.set_visible(True)
        else:
            self._loading_spinner.stop()
            self._loading_overlay.set_visible(False)

    def _clear_loading_spinner_timeout(self) -> None:
        """Cancel any pending delayed-show timeout for the loading overlay."""
        if self._render_spinner_timeout_id is None:
            return
        GLib.source_remove(self._render_spinner_timeout_id)
        self._render_spinner_timeout_id = None

    def _show_loading_if_current_generation(self, generation: int) -> bool:
        """Delayed callback to show loading overlay only for latest render."""
        self._render_spinner_timeout_id = None
        if generation != self._render_generation:
            return False
        self._set_loading_visible(True)
        return False

    def _begin_render_loading(self, generation: int) -> None:
        """Start loading indicator flow for a render generation."""
        self._clear_loading_spinner_timeout()
        if not self._has_rendered_content:
            self._set_loading_visible(True)
            return
        self._render_spinner_timeout_id = GLib.timeout_add(
            self._LOADING_INDICATOR_DELAY_MS,
            lambda: self._show_loading_if_current_generation(generation),
        )

    def _end_render_loading(self) -> None:
        """Stop loading indicator after render is complete or fails."""
        self._clear_loading_spinner_timeout()
        self._set_loading_visible(False)

    def _on_decide_policy(
        self,
        _webview: object,
        decision: object,
        decision_type: object,
    ) -> None:
        """Intercept WebKit navigation to prevent preview from navigating away."""
        if decision_type != WebKit.PolicyDecisionType.NAVIGATION_ACTION:
            decision.use()
            return

        action = decision.get_navigation_action()
        request = action.get_request()
        uri = request.get_uri()

        # Allow in-page anchors to be handled by WebKit.
        if uri.startswith("#"):
            return

        # Allow file:// same-document anchors.
        if uri.startswith("file://"):
            raw_path = unquote(uri[len("file://") :])
            path, _, fragment = raw_path.partition("#")
            if fragment and _is_same_document_file_anchor(path, self._base_uri):
                return

        # Ignore non-link navigation
        if action.get_navigation_type() != WebKit.NavigationType.LINK_CLICKED:
            decision.use()
            return

        if uri.startswith("file://"):
            raw_path = unquote(uri[len("file://") :])
            path, _, _fragment = raw_path.partition("#")
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
        copy_image_action = getattr(
            WebKit.ContextMenuAction, "COPY_IMAGE_TO_CLIPBOARD", None
        )
        if copy_image_action is not None:
            _remove.add(copy_image_action)
        for item in list(context_menu.get_items()):
            if hasattr(item, "get_stock_action") and item.get_stock_action() in _remove:
                context_menu.remove(item)

        # Clear and add custom actions
        self._context_menu_actions = []

        # Add "Copy Image" action
        copy_image_action = Gio.SimpleAction.new("copy-image", None)
        copy_image_action.connect("activate", lambda *_: self._copy_image(image_uri))
        self._context_menu_actions.append(copy_image_action)

        copy_image_item = WebKit.ContextMenuItem.new_from_gaction(
            copy_image_action, "Copy Image"
        )
        context_menu.append(copy_image_item)

        if _is_svg_uri(image_uri):
            copy_compat_action = Gio.SimpleAction.new("copy-image-compat", None)
            copy_compat_action.connect(
                "activate",
                lambda *_: self._copy_image(image_uri, compatibility_mode=True),
            )
            self._context_menu_actions.append(copy_compat_action)
            copy_compat_item = WebKit.ContextMenuItem.new_from_gaction(
                copy_compat_action, "Copy Image (Compatibility SVG)"
            )
            context_menu.append(copy_compat_item)

        # Add "Save Image As..." action
        save_action = Gio.SimpleAction.new("save-image", None)
        save_action.connect("activate", lambda *_: self._save_image(image_uri))
        self._context_menu_actions.append(save_action)

        save_item = WebKit.ContextMenuItem.new_from_gaction(
            save_action, "Save Image As..."
        )
        context_menu.append(save_item)

        if _is_svg_uri(image_uri):
            save_compat_action = Gio.SimpleAction.new("save-image-compat", None)
            save_compat_action.connect(
                "activate",
                lambda *_: self._save_image(image_uri, compatibility_mode=True),
            )
            self._context_menu_actions.append(save_compat_action)
            save_compat_item = WebKit.ContextMenuItem.new_from_gaction(
                save_compat_action, "Save Image As (Compatibility SVG)..."
            )
            context_menu.append(save_compat_item)

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

            markdown_item = WebKit.ContextMenuItem.new_from_gaction(
                markdown_action, "Copy Markdown Image"
            )
            context_menu.append(markdown_item)

        return False

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

    def _save_image(self, image_uri: str, compatibility_mode: bool = False) -> None:
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
                        self._write_image_uri_to_path(
                            url, dest, compatibility_mode=compatibility_mode
                        )
                    except Exception as e:
                        _logger.error(f"Failed to save image: {e}")

                # Run in background thread
                threading.Thread(target=_fetch, daemon=True).start()
            except GLib.GError:
                pass

        dialog.save(parent, None, handle_response)

    def _write_image_uri_to_path(
        self, image_uri: str, dest: str, compatibility_mode: bool = False
    ) -> None:
        """Write image URI payload to *dest* path."""
        if image_uri.startswith("data:"):
            mime, data = _decode_data_uri_bytes(image_uri)
            if compatibility_mode and mime == "image/svg+xml":
                data = _svg_to_compatibility_mode(data)
            with open(dest, "wb") as f:
                f.write(data)
            return

        if image_uri.startswith("file://"):
            src = unquote(urlparse(image_uri).path)
            with open(src, "rb") as in_f:
                data = in_f.read()
            if compatibility_mode and src.lower().endswith(".svg"):
                data = _svg_to_compatibility_mode(data)
            with open(dest, "wb") as out_f:
                out_f.write(data)
            return

        req = urllib.request.Request(
            image_uri,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) " "Gecko/20100101 Firefox/128.0"
                )
            },
        )
        with urllib.request.urlopen(req) as response:
            data = response.read()
            mime = response.headers.get_content_type()
        if compatibility_mode and (
            mime == "image/svg+xml" or urlparse(image_uri).path.lower().endswith(".svg")
        ):
            data = _svg_to_compatibility_mode(data)
        with open(dest, "wb") as f:
            f.write(data)

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
            if display is None:
                return
            provider = Gdk.ContentProvider.new_for_value(GObject.Value(str, text))
            display.get_clipboard().set_content(provider)
        except Exception:
            pass

    def _copy_image(self, image_uri: str, compatibility_mode: bool = False) -> None:
        """Copy image data from *image_uri* into the system clipboard."""
        if image_uri.startswith("file://"):
            path = unquote(urlparse(image_uri).path)
            if path.lower().endswith(".svg"):
                try:
                    with open(path, "rb") as fh:
                        raw = fh.read()
                    if compatibility_mode:
                        raw = _svg_to_compatibility_mode(raw)
                    self._set_clipboard_svg(raw)
                except OSError:
                    pass
                return
            self._set_clipboard_texture(path)
            return

        if image_uri.startswith("data:"):
            try:
                mime, raw = _decode_data_uri_bytes(image_uri)
                if mime == "image/svg+xml":
                    if compatibility_mode:
                        raw = _svg_to_compatibility_mode(raw)
                    self._set_clipboard_svg(raw)
                    return
                suffix = ".img"
                self._set_clipboard_texture_from_bytes(raw, suffix)
            except Exception:
                pass
            return

        def _fetch_and_copy() -> None:
            try:
                req = urllib.request.Request(
                    image_uri,
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (X11; Linux x86_64) "
                            "Gecko/20100101 Firefox/128.0"
                        )
                    },
                )
                with urllib.request.urlopen(req) as response:
                    raw = response.read()
                    mime = response.headers.get_content_type()
                parsed = urlparse(image_uri)
                ext = os.path.splitext(parsed.path)[1] or ".img"
                if mime == "image/svg+xml" or ext.lower() == ".svg":
                    if compatibility_mode:
                        raw = _svg_to_compatibility_mode(raw)
                    GLib.idle_add(lambda b=raw: self._set_clipboard_svg(b) or False)
                else:
                    GLib.idle_add(
                        lambda b=raw, s=ext: self._set_clipboard_texture_from_bytes(
                            b, s
                        )
                        or False
                    )
            except Exception:
                pass

        threading.Thread(target=_fetch_and_copy, daemon=True).start()

    def _set_clipboard_texture_from_bytes(self, raw: bytes, suffix: str) -> None:
        try:
            fd, path = tempfile.mkstemp(suffix=suffix)
            with os.fdopen(fd, "wb") as fh:
                fh.write(raw)
            self._set_clipboard_texture(path)
        except Exception:
            pass

    def _set_clipboard_texture(self, path: str) -> None:
        try:
            texture = Gdk.Texture.new_from_filename(path)
            png_bytes = texture.save_to_png_bytes()
            provider = Gdk.ContentProvider.new_for_bytes("image/png", png_bytes)
            self._set_clipboard_provider(provider)
        except Exception as exc:
            _logger.error("Failed to copy image to clipboard: %s", exc)

    def _set_clipboard_svg(self, raw: bytes) -> None:
        """Set clipboard image content for an SVG payload."""
        try:
            providers = [
                Gdk.ContentProvider.new_for_bytes("image/svg+xml", GLib.Bytes.new(raw))
            ]
            try:
                fd, path = tempfile.mkstemp(suffix=".svg", prefix="calamus_svg_")
                with os.fdopen(fd, "wb") as fh:
                    fh.write(raw)
                texture = Gdk.Texture.new_from_filename(path)
                providers.append(
                    Gdk.ContentProvider.new_for_bytes(
                        "image/png", texture.save_to_png_bytes()
                    )
                )
            except Exception:
                pass

            provider = (
                providers[0]
                if len(providers) == 1
                else Gdk.ContentProvider.new_union(providers)
            )
            self._set_clipboard_provider(provider)
        except Exception as exc:
            _logger.error("Failed to copy SVG image to clipboard: %s", exc)

    def _set_clipboard_provider(self, provider: object) -> None:
        """Publish clipboard provider to CLIPBOARD and PRIMARY selections."""
        display = Gdk.Display.get_default()
        if display is None:
            return
        display.get_clipboard().set_content(provider)
        primary = display.get_primary_clipboard()
        if primary is not None:
            primary.set_content(provider)

    def _on_create_web_view(
        self, _webview: object, navigation_action: object
    ) -> object | None:
        """Handle link opening in new window/tab."""
        try:
            uri = navigation_action.get_request().get_uri()
        except Exception:
            return None
        self._open_uri_externally(uri)
        return None

    def _open_uri_externally(self, uri: str) -> None:
        """Open URI in external application."""
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
        common system image viewers do not fully support SVG interaction.
        Other image types are decoded to temp files and opened externally.
        """
        try:
            mime, raw = _decode_data_uri_bytes(uri)

            if mime == "image/svg+xml":
                from calamus.imageviewer import ImageViewerWindow

                viewer = ImageViewerWindow(uri, title="SVG Viewer")
                viewer.present()
                return

            mime_exts = {
                "image/png": ".png",
                "image/jpeg": ".jpg",
                "image/gif": ".gif",
                "image/webp": ".webp",
            }
            ext = mime_exts.get(mime, "")

            with tempfile.NamedTemporaryFile(
                suffix=ext, delete=False, prefix="calamus_img_"
            ) as tmp:
                tmp.write(raw)
                tmp_path = tmp.name
            Gio.AppInfo.launch_default_for_uri(f"file://{tmp_path}", None)
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
        if load_event == WebKit.LoadEvent.FINISHED:
            if self._pending_scroll_restore_ratio is not None:
                ratio = self._pending_scroll_restore_ratio
                self._pending_scroll_restore_ratio = None
                self._restore_scroll_ratio(ratio)
            self._has_rendered_content = True
            self._end_render_loading()

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
        self._render_generation += 1
        generation = self._render_generation
        self._begin_render_loading(generation)
        self._capture_scroll_ratio(
            lambda ratio: self._start_async_render(markdown_text, generation, ratio)
        )

    def _start_async_render(
        self, markdown_text: str, generation: int, scroll_ratio: float | None
    ) -> None:
        """Start async render worker after capturing the current scroll ratio."""
        if generation != self._render_generation:
            return

        # Run async rendering
        def worker() -> None:
            try:
                renderer = self._renderer or MistuneRenderer()
                html = renderer.render(markdown_text)
                GLib.idle_add(
                    lambda g=generation, h=html, r=scroll_ratio: self._on_async_render_done(
                        g, h, r
                    )
                )
            except Exception as e:
                _logger.error(f"Render error: {e}")
                GLib.idle_add(lambda g=generation: self._on_async_render_failed(g))

        threading.Thread(target=worker, daemon=True).start()

    def _on_async_render_done(
        self, generation: int, html: str, scroll_ratio: float | None
    ) -> bool:
        """Handle async render completion."""
        if generation != self._render_generation:
            return False
        self._pending_scroll_restore_ratio = scroll_ratio

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

    def _on_async_render_failed(self, generation: int) -> bool:
        """Handle async render failure for current generation."""
        if generation == self._render_generation:
            self._end_render_loading()
        return False

    def _capture_scroll_ratio(self, callback: Callable[[float | None], None]) -> None:
        """Capture normalized vertical scroll ratio before triggering re-render."""
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
        """Finish evaluate_javascript callback and pass extracted ratio onward."""
        callback(self._extract_scroll_ratio(webview, result))

    def _extract_scroll_ratio(self, webview: object, result: object) -> float | None:
        """Extract scroll ratio from JavaScript result object."""
        js_result = self._finish_javascript(webview, result)
        if js_result is None:
            return None
        if hasattr(js_result, "is_number") and js_result.is_number():
            return max(0.0, min(1.0, float(js_result.to_double())))
        return None

    def _finish_javascript(self, webview: object, result: object) -> object | None:
        """Finish an evaluate_javascript operation, handling errors safely."""
        if hasattr(webview, "evaluate_javascript_finish"):
            try:
                return webview.evaluate_javascript_finish(result)
            except GLib.Error:
                return None
        return None

    def _restore_scroll_ratio(self, ratio: float | None) -> None:
        """Restore vertical scroll position from normalized ratio."""
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
