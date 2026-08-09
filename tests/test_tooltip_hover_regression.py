"""Regression test for tooltip hover issue from PR #79.

This test ensures that hovering over links in the markdown preview does not
attempt to open the URL as a file path.

Issue: When hovering over a link, the tooltip hover callback should NOT be invoked
to open the URL as a file. The callback is intended for CLICKING links, not hovering.

The bug was in _on_tooltip_message which called self._on_link_hover(href) with a URL,
causing an attempt to load the URL as a local file.
"""

import json
from unittest.mock import MagicMock, Mock

import pytest


def create_preview_with_mocked_webkit():
    """Create a preview instance with WebKit fully mocked to test _on_tooltip_message."""
    # Import here to patch at module level
    from calamus.webkit_preview_6x import WebKitPreview_6x

    # Create a preview-like object that has the _on_tooltip_message method
    # without requiring full WebKit initialization
    preview = object.__new__(WebKitPreview_6x)

    # Initialize only what we need for the tooltip handler
    preview._tooltip_manager = MagicMock()
    preview._footer_wrapper = MagicMock()
    preview._on_link_hover = None

    return preview


class TestTooltipHoverRegressionPR79:
    """Test that tooltip hover doesn't trigger file opening."""

    def test_tooltip_enter_does_not_call_on_link_hover(self):
        """Hovering over link should show tooltip but NOT call on_link_hover callback.

        The on_link_hover callback was incorrectly being called with the URL,
        which caused it to try to open the URL as a file path (PR #79 regression).
        """
        preview = create_preview_with_mocked_webkit()

        # Create a mock callback that tracks if it was called
        mock_hover_callback = Mock()
        preview._on_link_hover = mock_hover_callback

        # Create a tooltip message as it would come from JavaScript
        tooltip_message = {
            "href": "https://adst.bandcamp.com/",
            "state": "enter"
        }
        json_string = json.dumps(tooltip_message)

        # Create a mock JavaScriptCore.Value that implements to_json()
        mock_js_value = MagicMock()
        mock_js_value.to_json.return_value = json.dumps(json_string)

        # Import the method we're testing
        from calamus.webkit_preview_6x import WebKitPreview_6x

        # Call the tooltip message handler
        WebKitPreview_6x._on_tooltip_message(preview, MagicMock(), mock_js_value)

        # The callback should NOT have been called
        mock_hover_callback.assert_not_called()

    def test_tooltip_enter_shows_tooltip(self):
        """Hovering should show the tooltip display."""
        preview = create_preview_with_mocked_webkit()

        # Create a tooltip message
        tooltip_message = {
            "href": "https://example.com/page",
            "state": "enter"
        }
        json_string = json.dumps(tooltip_message)

        # Create mock JS value
        mock_js_value = MagicMock()
        mock_js_value.to_json.return_value = json.dumps(json_string)

        # Call the handler
        from calamus.webkit_preview_6x import WebKitPreview_6x
        WebKitPreview_6x._on_tooltip_message(preview, MagicMock(), mock_js_value)

        # The tooltip manager should have been shown with the URL
        preview._tooltip_manager.show.assert_called_once_with(
            "https://example.com/page"
        )
        # Footer should be made visible
        preview._footer_wrapper.set_visible.assert_called_with(True)

    def test_tooltip_leave_hides_tooltip(self):
        """Leaving a link should hide the tooltip."""
        preview = create_preview_with_mocked_webkit()

        # Create a tooltip leave message
        tooltip_message = {
            "href": "https://example.com/page",
            "state": "leave"
        }
        json_string = json.dumps(tooltip_message)

        # Create mock JS value
        mock_js_value = MagicMock()
        mock_js_value.to_json.return_value = json.dumps(json_string)

        # Call the handler
        from calamus.webkit_preview_6x import WebKitPreview_6x
        WebKitPreview_6x._on_tooltip_message(preview, MagicMock(), mock_js_value)

        # The tooltip manager should have been hidden
        preview._tooltip_manager.hide.assert_called_once()
        # Footer should be hidden
        preview._footer_wrapper.set_visible.assert_called_with(False)

    def test_tooltip_with_no_href_ignored(self):
        """Tooltip message without href should be ignored."""
        preview = create_preview_with_mocked_webkit()

        # Create a tooltip message without href
        tooltip_message = {
            "state": "enter"
        }
        json_string = json.dumps(tooltip_message)

        mock_js_value = MagicMock()
        mock_js_value.to_json.return_value = json.dumps(json_string)

        # Call the handler
        from calamus.webkit_preview_6x import WebKitPreview_6x
        WebKitPreview_6x._on_tooltip_message(preview, MagicMock(), mock_js_value)

        # Tooltip should not have been shown
        preview._tooltip_manager.show.assert_not_called()

    def test_tooltip_malformed_json_ignored(self):
        """Malformed JSON should be silently ignored."""
        preview = create_preview_with_mocked_webkit()

        # Create a mock JS value that returns invalid JSON
        mock_js_value = MagicMock()
        mock_js_value.to_json.return_value = "not valid json"

        # Should not raise an exception
        from calamus.webkit_preview_6x import WebKitPreview_6x
        WebKitPreview_6x._on_tooltip_message(preview, MagicMock(), mock_js_value)

        # Tooltip should not have been shown
        preview._tooltip_manager.show.assert_not_called()
