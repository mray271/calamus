"""Link tooltip footer for displaying URLs on hover.

Implements a simple footer widget that displays the URL of the link
currently being hovered over in the preview pane.
"""

import logging
from abc import ABC, abstractmethod

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

_logger = logging.getLogger(__name__)


class AbstractLinkTooltip(ABC):
    """Abstract base class for link tooltip implementations.

    Defines the interface for tooltip widgets that display URLs on hover.
    Subclasses should implement styling, visibility, and content management.
    """

    @abstractmethod
    def set_content(self, content: str) -> None:
        """Display content in the tooltip.

        Args:
            content: The content to display (typically a URL).
        """

    @abstractmethod
    def set_visible(self, visible: bool) -> None:
        """Set tooltip visibility state.

        Args:
            visible: True to show the tooltip, False to hide it.
        """

    @abstractmethod
    def is_visible(self) -> bool:
        """Check if tooltip is currently visible.

        Returns:
            True if the tooltip is visible, False otherwise.
        """

    @abstractmethod
    def update_styling(self) -> None:
        """Apply styling based on current theme.

        Subclasses should update colors, fonts, and other styling
        according to the active theme (light/dark mode).
        """

    @abstractmethod
    def on_theme_changed(self, style_manager: object, param: object) -> None:
        """Handle theme change events.

        Args:
            style_manager: The Adwaita StyleManager that changed.
            param: The parameter that changed.
        """

    @abstractmethod
    def refresh_layout(self) -> None:
        """Refresh the widget layout and redraw.

        Subclasses should call queue_resize() and queue_draw()
        to force layout recalculation and redrawing.
        """

    @abstractmethod
    def get_widget(self) -> Gtk.Widget:
        """Return the tooltip widget.

        Returns:
            The GTK widget for the tooltip.
        """

    def show(self, url: str) -> None:
        """Show the tooltip with the given URL.

        Default implementation calls set_content(), set_visible(),
        and refresh_layout(). Override to customize behavior.

        Args:
            url: The URL to display in the tooltip.
        """
        _logger.info(f"[Tooltip] show() called: url={url}")
        self.set_content(url)
        self.set_visible(True)
        self.refresh_layout()

    def hide(self) -> None:
        """Hide the tooltip.

        Default implementation calls set_visible() and refresh_layout().
        Override to customize behavior.
        """
        _logger.info(f"[Tooltip] hide() called")
        self.set_visible(False)
        self.refresh_layout()


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
        # Listen for theme changes
        style_manager = Adw.StyleManager.get_default()
        style_manager.connect("notify::dark", self.on_theme_changed)

    def _create_footer_widget(self) -> Gtk.Widget:
        """Create the footer widget.

        Returns:
            A GTK widget containing the footer.
        """
        # Create a box for the footer (doesn't expand to full width)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.set_hexpand(False)
        box.set_vexpand(False)
        box.set_halign(Gtk.Align.START)
        box.set_valign(Gtk.Align.START)
        box.set_spacing(0)
        # Don't constrain width - let it size to content
        box.set_name("url-tooltip-footer")

        # Store reference to update colors when theme changes
        self._footer_box = box

        # Create label for URL text
        self._label = Gtk.Label()
        self._label.set_text("")
        self._label.set_wrap(False)
        self._label.set_hexpand(False)
        self._label.set_halign(Gtk.Align.START)
        self._label.set_valign(Gtk.Align.CENTER)
        self._label.set_ellipsize(3)  # Ellipsize at end (END=3)

        box.append(self._label)

        # Apply initial styling
        self.update_styling()

        # Hide by default - only show on hover
        box.set_visible(False)

        return box

    def set_content(self, content: str) -> None:
        """Display content in the tooltip.

        Args:
            content: The URL text to display.
        """
        self._label.set_text(content)

    def set_visible(self, visible: bool) -> None:
        """Set tooltip visibility state.

        Args:
            visible: True to show the tooltip, False to hide it.
        """
        self._widget.set_visible(visible)
        self._visible = visible

    def is_visible(self) -> bool:
        """Check if tooltip is currently visible.

        Returns:
            True if the tooltip is visible, False otherwise.
        """
        return self._visible

    def update_styling(self) -> None:
        """Apply styling based on current theme."""
        style_manager = Adw.StyleManager.get_default()
        is_dark = style_manager.get_dark()

        css_provider = Gtk.CssProvider()

        if is_dark:
            # Dark mode: muted gray (not bright white)
            css = b"""
#url-tooltip-footer {
    background-color: #383838;
    color: #b0b0b0;
    border-top: 1px solid @borders;
    border-radius: 0 8px 0 0;
    padding: 2px 4px;
    min-width: 0;
    min-height: 0;
}
            """
        else:
            # Light mode: muted gray (not dark/black)
            css = b"""
#url-tooltip-footer {
    background-color: #e8eaed;
    color: #666666;
    border-top: 1px solid @borders;
    border-radius: 0 8px 0 0;
    padding: 2px 4px;
    min-width: 0;
    min-height: 0;
}
            """

        css_provider.load_from_data(css)

        context = self._footer_box.get_style_context()
        context.add_provider(css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        _logger.info(
            f"[Tooltip] Updated styling for {'dark' if is_dark else 'light'} mode"
        )

    def on_theme_changed(self, style_manager: object, param: object) -> None:
        """Handle theme change events.

        Args:
            style_manager: The Adwaita StyleManager that changed.
            param: The parameter that changed.
        """
        self.update_styling()

    def refresh_layout(self) -> None:
        """Refresh the widget layout and redraw."""
        self._widget.queue_resize()
        self._widget.queue_draw()

    def get_widget(self) -> Gtk.Widget:
        """Return the tooltip widget.

        Returns:
            The GTK widget for the footer.
        """
        return self._widget
