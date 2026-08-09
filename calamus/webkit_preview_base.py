"""Abstract base class for WebKit-based markdown preview implementations.

This module defines the interface that all WebKit version-specific implementations
must follow. It uses the Template Method pattern to provide shared logic while
allowing subclasses to implement version-specific behavior.

ARCHITECTURE:
  Each WebKit version (6.0, 7.0, etc.) is a separate class:
  - calamus/webkit_preview_6x.py (WebKit 6.0+)
  - calamus/webkit_preview_7x.py (WebKit 7.0+) [future]
  
  All inherit from AbstractWebKitPreview and implement the same interface,
  allowing drop-in replacement by version.

LIFECYCLE:
  When a new WebKit version arrives:
    1. Create webkit_preview_Nx.py by copying the latest version
    2. Update only the API calls that changed in that version
    3. Leave the rest identical (inheritance takes care of it)
    4. No conditional logic, no hasattr() checks
    5. Each version is self-contained in one file
  
  When an old version reaches EOL:
    1. Delete its file (webkit_preview_Nx.py)
    2. Remove from version detection
    3. Done. No scattered cleanup needed.
  
  This design eliminates the scattered version conditionals that plagued
  the old preview.py (15+ hasattr() checks, 2 *args masking patterns).

VERSION DIFFERENCES:
  Each WebKit version may have different:
  - Signal parameter counts and types
  - API availability (methods that exist only in certain versions)
  - Signal locations (download-started moved between versions)
  - Optional features (sandbox support varies)

By separating these concerns into distinct classes, we achieve:
  - Clear separation of version-specific logic
  - Easier testing and maintenance
  - Better scalability for future versions
  - No scattered hasattr() checks or *args masking
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk

from calamus.link_tooltip import LinkTooltipManager
from calamus.renderer import AbstractMarkdownRenderer

_logger = logging.getLogger(__name__)


class AbstractWebKitPreview(ABC):
    """Abstract base for all WebKit preview implementations.

    Public API (implemented by all subclasses):
      - update(markdown_text: str) → None
      - get_widget() → Gtk.Widget
      - set_file_path(path: str | None) → None
      - set_base_path(path: str | None) → None
      - zoom_by(factor: float) → None
      - reset_zoom() → None

    Version-specific hook methods (implemented differently by each subclass):
      - _setup_webkit_context() → None
      - _setup_sandbox(context: object) → None
      - _connect_download_signal(context: object) → None
      - _on_context_menu(webview, context_menu, *args) → bool
      - _on_tooltip_message(manager, js_value, *args) → None
      - _get_download_source(context: object) → object | None
      - _validate_download_source(download: object) → bool

    Template Method pattern:
      - __init__() is concrete, calls abstract _setup_webkit_context()
      - update() is concrete, calls protected _render_page()
      - Signal handlers are abstract (different signatures per version)
    """

    # Default zoom level (used across all versions)
    _DEFAULT_ZOOM = 1.0

    def __init__(
        self,
        renderer: AbstractMarkdownRenderer | None = None,
        on_open_path: Callable[[str], None] | None = None,
        on_link_hover: Callable[[str], None] | None = None,
    ) -> None:
        """Initialize the preview widget.

        This is a concrete method that calls abstract _setup_webkit_context()
        to allow version-specific initialization.

        Args:
            renderer: Optional custom markdown renderer (defaults to Mistune).
            on_open_path: Optional callback when user clicks a file link.
            on_link_hover: Optional callback when user hovers over a link.
        """
        self._renderer = renderer
        self._on_open_path = on_open_path
        self._on_link_hover = on_link_hover
        self._tooltip_manager = LinkTooltipManager()
        self._base_uri = "file:///"
        self._zoom_level = self._DEFAULT_ZOOM
        self._last_markdown: str = ""
        self._style_manager = Adw.StyleManager.get_default()
        self._context_menu_actions: list[object] = []
        self._pending_scroll_restore_ratio: float | None = None

        # Version-specific WebKit setup (implemented by subclasses)
        self._setup_webkit_context()

    # =========================================================================
    # Abstract methods: Version-specific implementations
    # =========================================================================

    @abstractmethod
    def _setup_webkit_context(self) -> None:
        """Set up WebKit context and create WebView widget.

        This is called during __init__(). Subclasses must:
          1. Initialize _view (WebKitWebView)
          2. Set up sandbox configuration via _setup_sandbox()
          3. Connect all version-specific signal handlers
          4. Register message handlers for JavaScript communication
          5. Set up font and CSS rendering
          6. Set up download handling via _connect_download_signal()

        This method completely encapsulates version-specific initialization.
        """
        pass

    @abstractmethod
    def _setup_sandbox(self, context: object) -> None:
        """Configure WebKit sandbox settings.

        Different versions have different sandbox APIs:
          - WebKit 6.0: context.set_sandbox_enabled() exists
          - WebKit 4.1: may not have set_sandbox_enabled()

        Subclasses implement version-appropriate sandbox setup.

        Args:
            context: The WebKitWebContext object (version-specific).
        """
        pass

    @abstractmethod
    def _connect_download_signal(self, context: object) -> None:
        """Connect the download-started signal to _on_download_started.

        Signal location varies by version:
          - WebKit 6.0: NetworkSession.download-started
          - WebKit 4.1: WebContext.download-started

        Subclasses implement version-specific signal connection logic.

        Args:
            context: The WebKitWebContext object.
        """
        pass

    @abstractmethod
    def _get_download_source(self, context: object) -> object | None:
        """Get the appropriate object to connect download signal to.

        Version-specific method to locate the object that emits
        the download-started signal.

        Args:
            context: The WebKitWebContext object.

        Returns:
            The object to connect the signal to, or None if unavailable.
        """
        pass

    @abstractmethod
    def _on_context_menu(
        self,
        _webview: object,
        context_menu: object,
        *args: object,
    ) -> bool:
        """Handle context menu (right-click) events.

        Signal signature differs by version:
          - WebKit 6.0: (webview, context_menu, hit_test_result) → bool
          - WebKit 4.1: (webview, context_menu, event, hit_test_result) → bool

        This is why we use distinct implementations per version instead of *args.

        Args:
            _webview: The WebKitWebView.
            context_menu: The context menu being shown.
            *args: Version-specific parameters (event, hit_test_result, etc).

        Returns:
            True to stop propagation, False to allow default handling.
        """
        pass

    @abstractmethod
    def _on_tooltip_message(
        self,
        manager: object,
        js_value: object,
        *args: object,
    ) -> None:
        """Handle messages from JavaScript link hover detection.

        Called when JavaScript sends a tooltip message via
        UserContentManager.postMessage().

        Args:
            manager: The UserContentManager.
            js_value: The message data (JavaScriptCore.Value or similar).
            *args: Version-specific additional parameters.
        """
        pass

    @abstractmethod
    def _validate_download_source(self, download: object) -> bool:
        """Validate that a download belongs to this preview's WebView.

        Some WebKit versions have get_web_view() on download objects,
        others don't. Version-specific validation.

        Args:
            download: The WebKitDownload object.

        Returns:
            True if the download is from this preview, False otherwise.
        """
        pass

    # =========================================================================
    # Protected methods: Shared implementation (may be overridden)
    # =========================================================================

    def _render_page(self, html_body: str, mermaid_script: str, dark: bool) -> None:
        """Render HTML content to the WebView.

        This is a shared implementation across all versions.
        Subclasses should not override this.

        Args:
            html_body: The HTML body content.
            mermaid_script: The Mermaid initialization script.
            dark: Whether to use dark color scheme.
        """
        raise NotImplementedError("Subclass must implement _render_page()")

    def _inject_tooltip_script(self) -> None:
        """Inject JavaScript for link hover detection.

        This is a shared implementation across all versions.
        Subclasses should not override this.
        """
        raise NotImplementedError("Subclass must implement _inject_tooltip_script()")

    # =========================================================================
    # Public API (Template Method pattern)
    # =========================================================================

    @abstractmethod
    def update(self, markdown_text: str) -> None:
        """Update the preview with new markdown content.

        Args:
            markdown_text: The markdown text to render.
        """
        pass

    @abstractmethod
    def get_widget(self) -> Gtk.Widget:
        """Get the root GTK widget for this preview.

        Returns:
            The Gtk.Widget (usually a container).
        """
        pass

    @abstractmethod
    def set_file_path(self, path: str | None) -> None:
        """Set the file path for resolving relative links.

        Args:
            path: The file path, or None to reset to root.
        """
        pass

    @abstractmethod
    def set_base_path(self, path: str | None) -> None:
        """Set the base directory for resolving relative links.

        Args:
            path: The directory path, or None to reset.
        """
        pass

    @abstractmethod
    def zoom_by(self, factor: float) -> None:
        """Apply a zoom factor to the preview.

        Args:
            factor: Zoom factor (1.0 = no change, 2.0 = double, 0.5 = half).
        """
        pass

    @abstractmethod
    def reset_zoom(self) -> None:
        """Reset zoom level to 100%."""
        pass
