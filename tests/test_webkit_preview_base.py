"""Tests for WebKit preview base classes."""

from unittest.mock import MagicMock, patch

import pytest

from calamus import webkit_preview_base


class TestAbstractWebKitPreview:
    """Test abstract base class interface."""

    def test_abstract_class_cannot_be_instantiated(self):
        """AbstractWebKitPreview should not be instantiable."""
        with pytest.raises(TypeError, match="abstract"):
            webkit_preview_base.AbstractWebKitPreview()

    def test_subclass_must_implement_required_methods(self):
        """Subclass must implement all abstract methods."""

        # Create a minimal subclass that doesn't implement all methods
        class IncompletePreview(webkit_preview_base.AbstractWebKitPreview):
            def _setup_webkit_context(self):
                pass

        with pytest.raises(TypeError, match="abstract"):
            IncompletePreview()

    def test_complete_subclass_can_be_instantiated(self):
        """Complete subclass implementation can be instantiated."""

        class CompletePreview(webkit_preview_base.AbstractWebKitPreview):
            def __init__(self):
                self.renderer = MagicMock()

            def _setup_webkit_context(self):
                pass

            def _setup_sandbox(self, context):
                pass

            def _connect_download_signal(self, context):
                pass

            def _get_download_source(self, download):
                return None

            def _validate_download_source(self, source):
                return True

            def _on_context_menu(self, webview, context_menu, *args):
                return False

            def _on_tooltip_message(self, manager, js_value, *args):
                pass

            def update(self, markdown_text):
                pass

            def get_widget(self):
                return MagicMock()

            def set_file_path(self, path):
                pass

            def set_base_path(self, path):
                pass

            def zoom_by(self, factor):
                pass

            def reset_zoom(self):
                pass

        instance = CompletePreview()
        assert instance is not None

    def test_public_api_exists(self):
        """Abstract class defines all required public methods."""
        public_methods = [
            "update",
            "get_widget",
            "set_file_path",
            "set_base_path",
            "zoom_by",
            "reset_zoom",
        ]
        for method in public_methods:
            assert hasattr(
                webkit_preview_base.AbstractWebKitPreview, method
            ), f"Missing public method: {method}"

    def test_has_required_hook_methods(self):
        """Should implement all required hook methods."""
        hook_methods = [
            "_setup_webkit_context",
            "_setup_sandbox",
            "_connect_download_signal",
            "_get_download_source",
            "_validate_download_source",
            "_on_context_menu",
            "_on_tooltip_message",
        ]
        for method in hook_methods:
            assert hasattr(
                webkit_preview_base.AbstractWebKitPreview, method
            ), f"Missing hook method: {method}"
