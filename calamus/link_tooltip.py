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
        # Create a box to hold the footer
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        box.set_name("url-tooltip-footer")
        box.set_height_request(32)
        
        # Add CSS styling
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(self._get_css().encode())
        
        context = box.get_style_context()
        context.add_provider(css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        
        # Create label for URL text
        self._label = Gtk.Label()
        self._label.set_wrap(False)
        self._label.set_ellipsize(3)  # END
        self._label.set_margin_start(12)
        self._label.set_margin_end(12)
        self._label.add_css_class("monospace")
        self._label.set_hexpand(True)
        self._label.set_halign(Gtk.Align.START)
        
        box.append(self._label)
        
        return box

    def _get_css(self) -> str:
        """Generate CSS for the footer widget.
        
        Returns:
            CSS string with light and dark mode variants.
        """
        return """
#url-tooltip-footer {
    background-color: #f6f8fa;
    color: #1c1c1c;
    border-top: 1px solid #e1e4e8;
    font-size: 0.8125em;
}

@media (prefers-color-scheme: dark) {
    #url-tooltip-footer {
        background-color: #24292e;
        color: #e1e4e8;
        border-top-color: #30363d;
    }
}
"""

    def show(self, url: str) -> None:
        """Show the tooltip with the given URL.
        
        Args:
            url: The URL to display in the tooltip.
        """
        _logger.info(f"[Tooltip] show() called: url={url}")
        self._label.set_text(url)
        self._widget.set_visible(True)
        self._visible = True

    def hide(self) -> None:
        """Hide the tooltip."""
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
