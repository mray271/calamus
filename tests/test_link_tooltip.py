"""Tests for link tooltip functionality."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from calamus.link_tooltip import AbstractLinkTooltip, LinkTooltipManager


class TestAbstractLinkTooltip:
    """Test abstract base class."""

    def test_cannot_instantiate_abstract_class(self):
        """Cannot instantiate abstract class directly."""
        with pytest.raises(TypeError, match="abstract"):
            AbstractLinkTooltip()

    def test_has_required_methods(self):
        """Abstract class defines all required methods."""
        required_methods = [
            "set_content",
            "set_visible",
            "is_visible",
            "update_styling",
            "on_theme_changed",
            "refresh_layout",
            "get_widget",
            "show",
            "hide",
        ]
        for method in required_methods:
            assert hasattr(AbstractLinkTooltip, method), f"Missing method: {method}"


class TestLinkTooltipManager:
    """Test LinkTooltipManager implementation."""

    @patch("calamus.link_tooltip.Adw.StyleManager")
    def test_initialization(self, mock_style_manager):
        """Should initialize with proper state."""
        mock_manager = MagicMock()
        mock_style_manager.get_default.return_value = mock_manager

        tooltip = LinkTooltipManager()

        assert tooltip is not None
        assert tooltip._visible is False
        # Should have created a widget
        assert tooltip.get_widget() is not None

    @patch("calamus.link_tooltip.Adw.StyleManager")
    def test_set_content(self, mock_style_manager):
        """Should set content in label."""
        mock_manager = MagicMock()
        mock_style_manager.get_default.return_value = mock_manager

        tooltip = LinkTooltipManager()
        tooltip.set_content("https://example.com")

        # Verify the label text was set
        assert tooltip._label.get_text() == "https://example.com"

    @patch("calamus.link_tooltip.Adw.StyleManager")
    def test_set_visible_true(self, mock_style_manager):
        """Should show widget when set_visible(True)."""
        mock_manager = MagicMock()
        mock_style_manager.get_default.return_value = mock_manager

        tooltip = LinkTooltipManager()
        tooltip.set_visible(True)

        assert tooltip.is_visible() is True
        assert tooltip._widget.get_visible() is True

    @patch("calamus.link_tooltip.Adw.StyleManager")
    def test_set_visible_false(self, mock_style_manager):
        """Should hide widget when set_visible(False)."""
        mock_manager = MagicMock()
        mock_style_manager.get_default.return_value = mock_manager

        tooltip = LinkTooltipManager()
        tooltip.set_visible(True)
        tooltip.set_visible(False)

        assert tooltip.is_visible() is False
        assert tooltip._widget.get_visible() is False

    @patch("calamus.link_tooltip.Adw.StyleManager")
    def test_show_method(self, mock_style_manager):
        """show() should set content and visibility."""
        mock_manager = MagicMock()
        mock_style_manager.get_default.return_value = mock_manager

        tooltip = LinkTooltipManager()
        tooltip.show("https://example.com/test")

        assert tooltip._label.get_text() == "https://example.com/test"
        assert tooltip.is_visible() is True

    @patch("calamus.link_tooltip.Adw.StyleManager")
    def test_hide_method(self, mock_style_manager):
        """hide() should hide tooltip."""
        mock_manager = MagicMock()
        mock_style_manager.get_default.return_value = mock_manager

        tooltip = LinkTooltipManager()
        tooltip.show("https://example.com")
        assert tooltip.is_visible() is True

        tooltip.hide()

        assert tooltip.is_visible() is False
        assert tooltip._widget.get_visible() is False

    @patch("calamus.link_tooltip.Adw.StyleManager")
    def test_get_widget(self, mock_style_manager):
        """Should return the GTK widget."""
        mock_manager = MagicMock()
        mock_style_manager.get_default.return_value = mock_manager

        tooltip = LinkTooltipManager()
        widget = tooltip.get_widget()

        assert widget is not None
        assert hasattr(widget, "get_visible")

    @patch("calamus.link_tooltip.Gtk.CssProvider")
    @patch("calamus.link_tooltip.Adw.StyleManager")
    def test_update_styling_dark_mode(self, mock_style_manager, mock_css_provider):
        """Should apply dark mode styling."""
        mock_manager = MagicMock()
        mock_manager.get_dark.return_value = True
        mock_style_manager.get_default.return_value = mock_manager

        mock_css_instance = MagicMock()
        mock_css_provider.return_value = mock_css_instance

        tooltip = LinkTooltipManager()
        tooltip.update_styling()

        # Verify CSS provider was created and loaded
        mock_css_provider.assert_called()
        mock_css_instance.load_from_data.assert_called()

        # Verify dark mode CSS was used
        call_args = mock_css_instance.load_from_data.call_args[0][0]
        assert b"#383838" in call_args  # Dark background

    @patch("calamus.link_tooltip.Gtk.CssProvider")
    @patch("calamus.link_tooltip.Adw.StyleManager")
    def test_update_styling_light_mode(self, mock_style_manager, mock_css_provider):
        """Should apply light mode styling."""
        mock_manager = MagicMock()
        mock_manager.get_dark.return_value = False
        mock_style_manager.get_default.return_value = mock_manager

        mock_css_instance = MagicMock()
        mock_css_provider.return_value = mock_css_instance

        tooltip = LinkTooltipManager()
        tooltip.update_styling()

        # Verify CSS provider was created
        mock_css_provider.assert_called()
        mock_css_instance.load_from_data.assert_called()

        # Verify light mode CSS was used
        call_args = mock_css_instance.load_from_data.call_args[0][0]
        assert b"#e8eaed" in call_args  # Light background

    @patch("calamus.link_tooltip.Adw.StyleManager")
    def test_on_theme_changed(self, mock_style_manager):
        """Should update styling when theme changes."""
        mock_manager = MagicMock()
        mock_style_manager.get_default.return_value = mock_manager

        tooltip = LinkTooltipManager()

        with patch.object(tooltip, "update_styling") as mock_update:
            tooltip.on_theme_changed(mock_manager, None)
            mock_update.assert_called_once()

    @patch("calamus.link_tooltip.Adw.StyleManager")
    def test_refresh_layout(self, mock_style_manager):
        """Should queue resize and redraw."""
        mock_manager = MagicMock()
        mock_style_manager.get_default.return_value = mock_manager

        tooltip = LinkTooltipManager()

        with patch.object(tooltip._widget, "queue_resize") as mock_resize:
            with patch.object(tooltip._widget, "queue_draw") as mock_draw:
                tooltip.refresh_layout()

                mock_resize.assert_called_once()
                mock_draw.assert_called_once()
