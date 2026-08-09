"""Tests for WebKit 6.0 preview implementation."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from calamus import webkit_preview_6x


class TestWebKitPreview6x:
    """Test WebKit 6.0-specific implementation."""

    def test_class_exists_and_inherits_from_abstract(self):
        """WebKitPreview_6x should inherit from AbstractWebKitPreview."""
        from calamus.webkit_preview_base import AbstractWebKitPreview

        assert issubclass(webkit_preview_6x.WebKitPreview_6x, AbstractWebKitPreview)

    def test_has_required_public_methods(self):
        """Should implement all required public methods."""
        required_methods = [
            "update",
            "get_widget",
            "set_file_path",
            "set_base_path",
            "zoom_by",
            "reset_zoom",
        ]
        for method in required_methods:
            assert hasattr(
                webkit_preview_6x.WebKitPreview_6x, method
            ), f"Missing method: {method}"

    def test_has_required_hook_methods(self):
        """Should implement all required hook methods."""
        hook_methods = [
            "_setup_webkit_context",
            "_setup_sandbox",
            "_connect_download_signal",
            "_on_context_menu",
            "_on_tooltip_message",
        ]
        for method in hook_methods:
            assert hasattr(
                webkit_preview_6x.WebKitPreview_6x, method
            ), f"Missing hook method: {method}"


class TestDefaultSaveFilename:
    """Test filename generation from URIs."""

    def test_generates_filename_from_data_uri_svg(self):
        """Should generate .svg filename for SVG data URIs."""
        uri = "data:image/svg+xml;base64,PHN2Zz4..."
        filename = webkit_preview_6x._default_save_filename(uri)
        assert filename == "diagram.svg"

    def test_generates_filename_from_data_uri_png(self):
        """Should generate .png filename for PNG data URIs."""
        uri = "data:image/png;base64,iVBORw0KG..."
        filename = webkit_preview_6x._default_save_filename(uri)
        assert filename == "image.png"

    def test_generates_filename_from_regular_uri(self):
        """Should extract filename from regular URIs."""
        uri = "https://example.com/downloads/document.pdf"
        filename = webkit_preview_6x._default_save_filename(uri)
        assert filename == "document.pdf"

    def test_handles_encoded_filenames(self):
        """Should decode URL-encoded filenames."""
        uri = "https://example.com/files/my%20file.txt"
        filename = webkit_preview_6x._default_save_filename(uri)
        assert filename == "my file.txt"

    def test_handles_root_path(self):
        """Should generate generic name for URIs with no filename."""
        uri = "https://example.com/"
        filename = webkit_preview_6x._default_save_filename(uri)
        # When path is root, returns empty, so we get generic fallback
        assert filename == "image" or filename == "download"

    def test_handles_unknown_mime_type(self):
        """Should use generic name for unknown MIME types."""
        uri = "data:application/unknown;base64,xyz"
        filename = webkit_preview_6x._default_save_filename(uri)
        assert filename == "download"


class TestIsSameDocumentFileAnchor:
    """Test document anchor detection."""

    def test_detects_same_document_empty_path(self):
        """Empty path or '/' refers to same document."""
        base_uri = "file:///home/user/document.md"
        assert webkit_preview_6x._is_same_document_file_anchor("", base_uri)
        assert webkit_preview_6x._is_same_document_file_anchor("/", base_uri)

    def test_detects_same_document_exact_match(self):
        """Exact path match refers to same document."""
        base_uri = "file:///home/user/document.md"
        assert webkit_preview_6x._is_same_document_file_anchor(
            "/home/user/document.md", base_uri
        )

    def test_detects_different_document(self):
        """Different file refers to different document."""
        base_uri = "file:///home/user/document.md"
        assert not webkit_preview_6x._is_same_document_file_anchor(
            "/home/user/other.md", base_uri
        )

    def test_handles_non_file_uris(self):
        """Non-file URIs are never same-document."""
        base_uri = "https://example.com/document.html"
        assert not webkit_preview_6x._is_same_document_file_anchor(
            "/any/path", base_uri
        )

    def test_handles_normalized_paths(self):
        """Normalizes paths before comparison."""
        base_uri = "file:///home/user/doc.md"
        # Both refer to the same file (with . normalization)
        assert webkit_preview_6x._is_same_document_file_anchor(
            "/home/user/./doc.md", base_uri
        )
