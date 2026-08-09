"""Link tooltip manager for displaying URLs on hover.

Implements the LinkTooltipManager class using GTK widgets for maximum
compatibility and positioning reliability.
"""

from abc import ABC, abstractmethod

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw


class AbstractLinkTooltip(ABC):
    """Abstract base class for link tooltip implementations."""

    @abstractmethod
    def show(self, url: str, x: int, y: int) -> None:
        """Show the tooltip at the given position with the specified URL."""
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
    """Manages URL tooltip display using GTK widgets.
    
    The tooltip is a floating widget positioned at the bottom-left of the
    preview pane. It uses GTK's native rendering, ensuring consistent
    styling and reliable positioning.
    """

    def __init__(self) -> None:
        """Initialize the link tooltip manager."""
        self._widget = self._create_tooltip_widget()
        self._visible = False

    def _create_tooltip_widget(self) -> Gtk.Widget:
        """Create the tooltip widget.
        
        Returns:
            A GTK widget containing the tooltip box.
        """
        # Create a box to hold the tooltip
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.set_name("url-tooltip")
        
        # Add CSS styling
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(self._get_css().encode())
        
        context = box.get_style_context()
        context.add_provider(css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        
        # Create label for URL text
        self._label = Gtk.Label()
        self._label.set_wrap(False)
        self._label.set_ellipsize(3)  # END
        self._label.set_margin_top(8)
        self._label.set_margin_bottom(8)
        self._label.set_margin_start(12)
        self._label.set_margin_end(12)
        self._label.add_css_class("monospace")
        
        box.append(self._label)
        
        return box

    def _get_css(self) -> str:
        """Generate CSS for the tooltip widget.
        
        Returns:
            CSS string with light and dark mode variants.
        """
        return """
#url-tooltip {
    background-color: #f6f8fa;
    color: #1c1c1c;
    border-top: 1px solid #e1e4e8;
    border-right: 1px solid #e1e4e8;
    border-radius: 0px 8px 0px 0px;
    box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.15);
    font-size: 0.8125em;
}

#url-tooltip:disabled {
    opacity: 0;
    pointer-events: none;
}

@media (prefers-color-scheme: dark) {
    #url-tooltip {
        background-color: #24292e;
        color: #e1e4e8;
        border-top-color: #30363d;
        border-right-color: #30363d;
    }
}
"""

    def show(self, url: str, x: int, y: int) -> None:
        """Show the tooltip with the given URL at the specified position.
        
        Args:
            url: The URL to display in the tooltip.
            x: X coordinate for positioning (relative to WebView).
            y: Y coordinate for positioning (relative to WebView).
        """
        self._label.set_text(url)
        self._widget.set_visible(True)
        self._visible = True

    def hide(self) -> None:
        """Hide the tooltip."""
        self._widget.set_visible(False)
        self._visible = False

    def get_widget(self) -> Gtk.Widget:
        """Return the tooltip widget.
        
        Returns:
            The GTK widget for the tooltip.
        """
        return self._widget

    def is_visible(self) -> bool:
        """Return whether the tooltip is currently visible.
        
        Returns:
            True if the tooltip is visible, False otherwise.
        """
        return self._visible
