"""Link tooltip footer for displaying URLs on hover.

Implements a simple footer widget that displays the URL of the link
currently being hovered over in the preview pane.
"""

from abc import ABC, abstractmethod
import logging

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

_logger = logging.getLogger(__name__)


class AbstractLinkTooltip(ABC):
    """Abstract base class for link tooltip implementations."""

    @abstractmethod
    def show(self, url: str) -> None:
        """Show the tooltip with the given URL."""
        pass

    @abstractmethod
    def hide(self) -> None:
        """Hide the tooltip."""
        pass

    @abstractmethod
    def get_widget(self) -> Gtk.Widget:
        """Return the tooltip widget."""
        pass


class LinkTooltipManager(AbstractLinkTooltip):
    """Manages URL tooltip display as a persistent footer widget.
    
    The tooltip is a footer bar at the bottom of the preview pane that
    displays the URL of the currently hovered link. It remains visible
    at the bottom regardless of scrolling.
    """

    def __init__(self) -> None:
        """Initialize the link tooltip manager."""
        self._widget = self._create_footer_widget()
        self._visible = False

    def _create_footer_widget(self) -> Gtk.Widget:
        """Create the footer widget.
        
        Returns:
            A GTK widget containing the footer.
        """
        # Create a box for the footer (doesn't expand to full width)
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        box.set_hexpand(False)
        box.set_vexpand(False)
        box.set_halign(Gtk.Align.START)
        box.set_size_request(-1, 32)
        box.set_name("url-tooltip-footer")
        
        # Store reference to update colors when theme changes
        self._footer_box = box
        
        # Create label for URL text
        self._label = Gtk.Label()
        self._label.set_text("")
        self._label.set_wrap(False)
        self._label.set_hexpand(False)
        self._label.set_halign(Gtk.Align.START)
        self._label.set_ellipsize(3)  # Ellipsize at end (END=3)
        
        box.append(self._label)
        
        # Apply initial styling
        self._update_footer_styling()
        
        # Listen for theme changes
        style_manager = Adw.StyleManager.get_default()
        style_manager.connect("notify::dark", self._on_theme_changed)
        
        # Hide by default - only show on hover
        box.set_visible(False)
        
        return box
    
    def _update_footer_styling(self) -> None:
        """Update footer styling based on current theme."""
        style_manager = Adw.StyleManager.get_default()
        is_dark = style_manager.get_dark()
        
        css_provider = Gtk.CssProvider()
        
        if is_dark:
            # Dark mode: slightly lighter than black
            css = b"""
#url-tooltip-footer {
    background-color: #383838;
    color: @view_fg_color;
    border-top: 1px solid @borders;
    border-radius: 0 8px 0 0;
    padding: 4px 12px;
    max-width: 100%;
}
            """
        else:
            # Light mode: slightly darker than white
            css = b"""
#url-tooltip-footer {
    background-color: #e8eaed;
    color: @view_fg_color;
    border-top: 1px solid @borders;
    border-radius: 0 8px 0 0;
    padding: 4px 12px;
    max-width: 100%;
}
            """
        
        css_provider.load_from_data(css)
        
        context = self._footer_box.get_style_context()
        context.add_provider(css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        
        _logger.info(f"[Tooltip] Updated styling for {'dark' if is_dark else 'light'} mode")
    
    def _on_theme_changed(self, style_manager, param) -> None:
        """Handle theme change events."""
        self._update_footer_styling()
    def show(self, url: str) -> None:
        """Show the tooltip with the given URL.
        
        Args:
            url: The URL to display in the tooltip.
        """
        print(f"[TOOLTIP] LinkTooltipManager.show() called: url={url}", flush=True)
        _logger.info(f"[Tooltip] show() called: url={url}")
        self._label.set_text(url)
        self._widget.set_visible(True)
        self._visible = True

    def hide(self) -> None:
        """Hide the tooltip."""
        print("[TOOLTIP] LinkTooltipManager.hide() called", flush=True)
        _logger.info(f"[Tooltip] hide() called")
        self._widget.set_visible(False)
        self._visible = False

    def get_widget(self) -> Gtk.Widget:
        """Return the tooltip widget.
        
        Returns:
            The GTK widget for the footer.
        """
        return self._widget

    def is_visible(self) -> bool:
        """Return whether the tooltip is currently visible.
        
        Returns:
            True if the tooltip is visible, False otherwise.
        """
        return self._visible
