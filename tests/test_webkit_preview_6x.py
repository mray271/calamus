"""Tests for WebKit 6.0 preview implementation."""

import base64
import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch
from urllib.parse import quote

import pytest

from calamus import webkit_preview_6x
from calamus.mermaid_support import SubprocessMermaidRenderer

MERMAID_SVG_FIXTURE = (
    Path(__file__).resolve().parent / "fixtures" / "mermaid_sample.svg"
)
SAMPLE_DOC_PATH = (
    Path(__file__).resolve().parent.parent
    / "samples"
    / "why_claude_sonnet_fails_to_discover_music.md"
)
ORO_SAMPLE_PATH = (
    Path(__file__).resolve().parent.parent
    / "samples"
    / "oro_se_do_bheatha_abhaile_lyrics.md"
)
ORO_SAMPLE_MD = ORO_SAMPLE_PATH.read_text(encoding="utf-8")


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


class TestDataUriDecode:
    def test_decodes_base64_svg_and_preserves_text(self):
        svg = "<svg><text>Mermaid Label</text></svg>".encode("utf-8")
        uri = f"data:image/svg+xml;base64,{base64.b64encode(svg).decode('ascii')}"
        mime, raw = webkit_preview_6x._decode_data_uri_bytes(uri)
        assert mime == "image/svg+xml"
        assert b"Mermaid Label" in raw

    def test_decodes_urlencoded_svg_and_preserves_text(self):
        svg = "<svg><text>Node A</text></svg>"
        uri = f"data:image/svg+xml,{quote(svg)}"
        mime, raw = webkit_preview_6x._decode_data_uri_bytes(uri)
        assert mime == "image/svg+xml"
        assert b"Node A" in raw


def test_svg_compatibility_transform_rewrites_foreign_object():
    raw = (
        b'<svg xmlns="http://www.w3.org/2000/svg">'
        b'<g><foreignObject><div xmlns="http://www.w3.org/1999/xhtml">Node A</div></foreignObject></g>'
        b"</svg>"
    )
    converted = webkit_preview_6x._svg_to_compatibility_mode(raw).decode("utf-8")
    assert "<foreignObject" not in converted
    assert "text" in converted
    assert "Node A" in converted


def test_is_svg_uri_detects_data_and_file_paths():
    assert webkit_preview_6x._is_svg_uri("data:image/svg+xml;base64,PHN2Zw==")
    assert webkit_preview_6x._is_svg_uri("file:///tmp/diagram.svg")
    assert webkit_preview_6x._is_svg_uri("https://example.com/diagram.svg")
    assert not webkit_preview_6x._is_svg_uri("https://example.com/image.png")


def test_write_image_uri_to_path_saves_svg_text(tmp_path):
    preview = object.__new__(webkit_preview_6x.WebKitPreview_6x)
    svg = "<svg><text>Mermaid Label</text></svg>"
    uri = f"data:image/svg+xml,{quote(svg)}"
    dest = tmp_path / "saved.svg"

    webkit_preview_6x.WebKitPreview_6x._write_image_uri_to_path(preview, uri, str(dest))

    saved = dest.read_bytes()
    assert b"Mermaid Label" in saved


def test_write_image_uri_to_path_compatibility_mode_rewrites_foreign_object(tmp_path):
    preview = object.__new__(webkit_preview_6x.WebKitPreview_6x)
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg">'
        '<g><foreignObject><div xmlns="http://www.w3.org/1999/xhtml">Node A</div></foreignObject></g>'
        "</svg>"
    )
    uri = f"data:image/svg+xml,{quote(svg)}"
    dest = tmp_path / "saved-compat.svg"

    webkit_preview_6x.WebKitPreview_6x._write_image_uri_to_path(
        preview, uri, str(dest), compatibility_mode=True
    )

    saved = dest.read_text(encoding="utf-8")
    assert "<foreignObject" not in saved
    assert "text" in saved
    assert "Node A" in saved


def test_write_image_uri_to_path_roundtrip_mermaid_svg_fixture_urlencoded(tmp_path):
    preview = object.__new__(webkit_preview_6x.WebKitPreview_6x)
    svg_text = MERMAID_SVG_FIXTURE.read_text(encoding="utf-8")
    uri = f"data:image/svg+xml,{quote(svg_text)}"
    dest = tmp_path / "saved-mermaid-url.svg"

    webkit_preview_6x.WebKitPreview_6x._write_image_uri_to_path(preview, uri, str(dest))

    saved = dest.read_text(encoding="utf-8")
    assert "Start Node" in saved
    assert "End Node" in saved
    assert "Mermaid Note: This text should survive Save Image As round-trip." in saved


def test_write_image_uri_to_path_roundtrip_mermaid_svg_fixture_base64(tmp_path):
    preview = object.__new__(webkit_preview_6x.WebKitPreview_6x)
    svg_raw = MERMAID_SVG_FIXTURE.read_bytes()
    uri = f"data:image/svg+xml;base64,{base64.b64encode(svg_raw).decode('ascii')}"
    dest = tmp_path / "saved-mermaid-b64.svg"

    webkit_preview_6x.WebKitPreview_6x._write_image_uri_to_path(preview, uri, str(dest))

    saved_raw = dest.read_bytes()
    assert b"Start Node" in saved_raw
    assert b"End Node" in saved_raw
    assert (
        b"Mermaid Note: This text should survive Save Image As round-trip." in saved_raw
    )


@pytest.mark.skipif(
    not SubprocessMermaidRenderer().is_available(), reason="mmdc not installed"
)
def test_save_roundtrip_uses_sample_original_flawed_mermaid_block(tmp_path):
    from calamus.mermaid_support import get_mermaid_html_labels, set_mermaid_html_labels
    from calamus.renderer import MistuneRenderer

    original = get_mermaid_html_labels()
    set_mermaid_html_labels(False)
    try:
        markdown = SAMPLE_DOC_PATH.read_text(encoding="utf-8")
        match = re.search(
            r"### Original \(Flawed\) Approach\n\n```mermaid\n(.*?)```",
            markdown,
            re.DOTALL,
        )
        assert match, "Could not locate the expected Mermaid block in sample document"

        mermaid_block = f"```mermaid\n{match.group(1)}```\n"
        html = MistuneRenderer().render(mermaid_block)
        data_uri_match = re.search(
            r"data:image/svg\+xml;base64,([A-Za-z0-9+/=]+)", html
        )
        assert data_uri_match, "Rendered Mermaid block did not produce an SVG data URI"

        uri = f"data:image/svg+xml;base64,{data_uri_match.group(1)}"
        dest = tmp_path / "sample-mermaid-roundtrip.svg"
        webkit_preview_6x.WebKitPreview_6x._write_image_uri_to_path(
            object.__new__(webkit_preview_6x.WebKitPreview_6x), uri, str(dest)
        )

        saved_svg = dest.read_text(encoding="utf-8")
        assert "<foreignObject" not in saved_svg
        assert "<text" in saved_svg
        for token in (
            "Receive",
            "Query",
            "Kenilworth",
            "Katrina",
            "ADST",
            "Music",
            "found",
        ):
            assert token in saved_svg
    finally:
        set_mermaid_html_labels(original)


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


class _FakeContextMenu:
    def __init__(self):
        self._items = []
        self.appended = []
        self.removed = []

    def get_items(self):
        return self._items

    def append(self, item):
        self.appended.append(item)

    def remove(self, item):
        self.removed.append(item)


class _FakeHitTest:
    def __init__(self, is_image, uri):
        self._is_image = is_image
        self._uri = uri

    def context_is_image(self):
        return self._is_image

    def get_image_uri(self):
        return self._uri


def test_on_context_menu_returns_false_for_image(monkeypatch):
    preview = object.__new__(webkit_preview_6x.WebKitPreview_6x)
    preview._context_menu_actions = []
    preview._save_image = lambda *_: None
    preview._copy_image = lambda *_: None
    preview._copy_to_clipboard = lambda *_: None
    preview._uri_to_markdown_image = lambda *_: "![img](x)"

    fake_webkit = SimpleNamespace(
        ContextMenuAction=SimpleNamespace(
            COPY_IMAGE_URL_TO_CLIPBOARD=1,
            DOWNLOAD_IMAGE_TO_DISK=2,
        ),
        ContextMenuItem=SimpleNamespace(
            new_from_gaction=lambda action, label: (action, label)
        ),
    )
    monkeypatch.setattr(webkit_preview_6x, "WebKit", fake_webkit)

    monkeypatch.setattr(
        webkit_preview_6x.Gio.SimpleAction,
        "new",
        lambda *_: MagicMock(),
    )

    menu = _FakeContextMenu()
    hit = _FakeHitTest(True, "file:///tmp/image.png")

    handled = webkit_preview_6x.WebKitPreview_6x._on_context_menu(
        preview, None, menu, hit
    )

    assert handled is False
    assert len(menu.appended) == 3


def test_on_context_menu_adds_compatibility_save_for_svg(monkeypatch):
    preview = object.__new__(webkit_preview_6x.WebKitPreview_6x)
    preview._context_menu_actions = []
    preview._save_image = lambda *_: None
    preview._copy_image = lambda *_: None
    preview._copy_to_clipboard = lambda *_: None
    preview._uri_to_markdown_image = lambda *_: "![img](x)"

    fake_webkit = SimpleNamespace(
        ContextMenuAction=SimpleNamespace(
            COPY_IMAGE_URL_TO_CLIPBOARD=1,
            DOWNLOAD_IMAGE_TO_DISK=2,
        ),
        ContextMenuItem=SimpleNamespace(
            new_from_gaction=lambda action, label: (action, label)
        ),
    )
    monkeypatch.setattr(webkit_preview_6x, "WebKit", fake_webkit)
    monkeypatch.setattr(
        webkit_preview_6x.Gio.SimpleAction, "new", lambda *_: MagicMock()
    )

    menu = _FakeContextMenu()
    hit = _FakeHitTest(True, "data:image/svg+xml;base64,PHN2Zz48L3N2Zz4=")

    handled = webkit_preview_6x.WebKitPreview_6x._on_context_menu(
        preview, None, menu, hit
    )

    assert handled is False
    labels = [item[1] for item in menu.appended]
    assert "Copy Image (Compatibility SVG)" in labels
    assert "Save Image As..." in labels
    assert "Save Image As (Compatibility SVG)..." in labels


def test_on_context_menu_does_not_add_compatibility_items_for_png(monkeypatch):
    preview = object.__new__(webkit_preview_6x.WebKitPreview_6x)
    preview._context_menu_actions = []
    preview._save_image = lambda *_: None
    preview._copy_image = lambda *_: None
    preview._copy_to_clipboard = lambda *_: None
    preview._uri_to_markdown_image = lambda *_: "![img](x)"

    fake_webkit = SimpleNamespace(
        ContextMenuAction=SimpleNamespace(
            COPY_IMAGE_URL_TO_CLIPBOARD=1,
            DOWNLOAD_IMAGE_TO_DISK=2,
        ),
        ContextMenuItem=SimpleNamespace(
            new_from_gaction=lambda action, label: (action, label)
        ),
    )
    monkeypatch.setattr(webkit_preview_6x, "WebKit", fake_webkit)
    monkeypatch.setattr(
        webkit_preview_6x.Gio.SimpleAction, "new", lambda *_: MagicMock()
    )

    menu = _FakeContextMenu()
    hit = _FakeHitTest(True, "file:///tmp/image.png")

    handled = webkit_preview_6x.WebKitPreview_6x._on_context_menu(
        preview, None, menu, hit
    )

    assert handled is False
    labels = [item[1] for item in menu.appended]
    assert "Copy Image (Compatibility SVG)" not in labels
    assert "Save Image As (Compatibility SVG)..." not in labels


def test_copy_image_data_svg_compatibility_mode_rewrites_foreign_object():
    preview = object.__new__(webkit_preview_6x.WebKitPreview_6x)
    copied = []
    preview._set_clipboard_svg = lambda raw: copied.append(raw)
    preview._set_clipboard_texture_from_bytes = MagicMock()

    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg">'
        '<foreignObject><div xmlns="http://www.w3.org/1999/xhtml">Node A</div></foreignObject>'
        "</svg>"
    )
    uri = f"data:image/svg+xml,{quote(svg)}"
    webkit_preview_6x.WebKitPreview_6x._copy_image(
        preview, uri, compatibility_mode=True
    )

    saved = copied[0].decode("utf-8")
    assert "<foreignObject" not in saved
    assert "text" in saved
    assert "Node A" in saved
    preview._set_clipboard_texture_from_bytes.assert_not_called()


def test_copy_image_file_uri_uses_texture_loader():
    preview = object.__new__(webkit_preview_6x.WebKitPreview_6x)
    loaded_paths = []
    preview._set_clipboard_texture = lambda path: loaded_paths.append(path)

    webkit_preview_6x.WebKitPreview_6x._copy_image(
        preview, "file:///tmp/my%20image.png"
    )

    assert loaded_paths == ["/tmp/my image.png"]


def test_copy_image_file_svg_uses_svg_clipboard(monkeypatch):
    preview = object.__new__(webkit_preview_6x.WebKitPreview_6x)
    copied = []
    preview._set_clipboard_svg = lambda raw: copied.append(raw)
    preview._set_clipboard_texture = MagicMock()

    m = MagicMock()
    m.__enter__.return_value.read.return_value = b"<svg/>"
    m.__exit__.return_value = False
    monkeypatch.setattr("builtins.open", lambda *_args, **_kwargs: m)

    webkit_preview_6x.WebKitPreview_6x._copy_image(preview, "file:///tmp/diagram.svg")

    assert copied == [b"<svg/>"]
    preview._set_clipboard_texture.assert_not_called()


def test_copy_image_data_svg_uses_svg_clipboard():
    preview = object.__new__(webkit_preview_6x.WebKitPreview_6x)
    copied = []
    preview._set_clipboard_svg = lambda raw: copied.append(raw)
    preview._set_clipboard_texture_from_bytes = MagicMock()

    webkit_preview_6x.WebKitPreview_6x._copy_image(
        preview, "data:image/svg+xml;base64,PHN2Zz48L3N2Zz4="
    )

    assert copied == [b"<svg></svg>"]
    preview._set_clipboard_texture_from_bytes.assert_not_called()


def test_set_clipboard_texture_sets_png_content(monkeypatch):
    preview = object.__new__(webkit_preview_6x.WebKitPreview_6x)

    clipboard = MagicMock()
    primary_clipboard = MagicMock()
    display = SimpleNamespace(
        get_clipboard=lambda: clipboard,
        get_primary_clipboard=lambda: primary_clipboard,
    )
    monkeypatch.setattr(webkit_preview_6x.Gdk.Display, "get_default", lambda: display)

    texture = SimpleNamespace(save_to_png_bytes=lambda: b"PNGDATA")
    monkeypatch.setattr(
        webkit_preview_6x.Gdk.Texture, "new_from_filename", lambda _path: texture
    )

    providers = []
    monkeypatch.setattr(
        webkit_preview_6x.Gdk.ContentProvider,
        "new_for_bytes",
        lambda mime, data: providers.append((mime, data)) or ("provider", mime),
    )

    webkit_preview_6x.WebKitPreview_6x._set_clipboard_texture(preview, "/tmp/image.png")

    assert providers == [("image/png", b"PNGDATA")]
    clipboard.set_content.assert_called_once_with(("provider", "image/png"))
    primary_clipboard.set_content.assert_called_once_with(("provider", "image/png"))


def test_set_clipboard_svg_sets_svg_provider(monkeypatch):
    preview = object.__new__(webkit_preview_6x.WebKitPreview_6x)
    preview._set_clipboard_provider = MagicMock()

    providers = []
    monkeypatch.setattr(
        webkit_preview_6x.Gdk.ContentProvider,
        "new_for_bytes",
        lambda mime, data: providers.append((mime, data))
        or SimpleNamespace(mime=mime, data=data),
    )
    monkeypatch.setattr(
        webkit_preview_6x.Gdk.ContentProvider,
        "new_union",
        lambda p: SimpleNamespace(union=p),
    )
    monkeypatch.setattr(webkit_preview_6x.Gdk.Texture, "new_from_filename", MagicMock())

    webkit_preview_6x.WebKitPreview_6x._set_clipboard_svg(preview, b"<svg/>")

    assert providers[0][0] == "image/svg+xml"
    preview._set_clipboard_provider.assert_called_once()


def test_on_create_web_view_opens_uri_externally():
    preview = object.__new__(webkit_preview_6x.WebKitPreview_6x)
    opened = []
    preview._open_uri_externally = lambda uri: opened.append(uri)

    nav_action = SimpleNamespace(
        get_request=lambda: SimpleNamespace(
            get_uri=lambda: "https://example.com/photo.jpg"
        )
    )

    result = webkit_preview_6x.WebKitPreview_6x._on_create_web_view(
        preview, None, nav_action
    )

    assert result is None
    assert opened == ["https://example.com/photo.jpg"]


def test_open_uri_externally_launches_default_without_callback(monkeypatch):
    preview = object.__new__(webkit_preview_6x.WebKitPreview_6x)
    preview._on_open_path = None
    preview._open_data_uri_externally = MagicMock()

    launched = []
    monkeypatch.setattr(
        webkit_preview_6x.Gio,
        "AppInfo",
        SimpleNamespace(launch_default_for_uri=lambda uri, _ctx: launched.append(uri)),
    )

    webkit_preview_6x.WebKitPreview_6x._open_uri_externally(
        preview, "https://example.com/resource"
    )

    assert launched == ["https://example.com/resource"]
    preview._open_data_uri_externally.assert_not_called()


def test_open_uri_externally_file_uri_uses_default_launcher(monkeypatch):
    preview = object.__new__(webkit_preview_6x.WebKitPreview_6x)
    preview._on_open_path = MagicMock()
    preview._open_data_uri_externally = MagicMock()

    launched = []
    monkeypatch.setattr(
        webkit_preview_6x.Gio,
        "AppInfo",
        SimpleNamespace(launch_default_for_uri=lambda uri, _ctx: launched.append(uri)),
    )

    webkit_preview_6x.WebKitPreview_6x._open_uri_externally(
        preview, "file:///tmp/example.md#section"
    )

    assert launched == ["file:///tmp/example.md#section"]
    preview._on_open_path.assert_not_called()
    preview._open_data_uri_externally.assert_not_called()


def test_open_uri_externally_http_does_not_use_file_callback(monkeypatch):
    preview = object.__new__(webkit_preview_6x.WebKitPreview_6x)
    opened_paths = []
    preview._on_open_path = lambda path: opened_paths.append(path)
    preview._open_data_uri_externally = MagicMock()

    launched = []
    monkeypatch.setattr(
        webkit_preview_6x.Gio,
        "AppInfo",
        SimpleNamespace(launch_default_for_uri=lambda uri, _ctx: launched.append(uri)),
    )

    webkit_preview_6x.WebKitPreview_6x._open_uri_externally(
        preview, "https://example.com/resource"
    )

    assert opened_paths == []
    assert launched == ["https://example.com/resource"]


def test_on_decide_policy_allows_same_document_file_anchor(monkeypatch):
    preview = object.__new__(webkit_preview_6x.WebKitPreview_6x)
    preview._base_uri = "file:///tmp/example.md"
    preview._open_uri_externally = MagicMock()

    fake_webkit = SimpleNamespace(
        PolicyDecisionType=SimpleNamespace(NAVIGATION_ACTION=1),
        NavigationType=SimpleNamespace(LINK_CLICKED=2),
    )
    monkeypatch.setattr(webkit_preview_6x, "WebKit", fake_webkit)

    decision = MagicMock()
    decision.get_navigation_action.return_value = SimpleNamespace(
        get_request=lambda: SimpleNamespace(
            get_uri=lambda: "file:///tmp/example.md#h1"
        ),
        get_navigation_type=lambda: fake_webkit.NavigationType.LINK_CLICKED,
    )

    webkit_preview_6x.WebKitPreview_6x._on_decide_policy(
        preview, None, decision, fake_webkit.PolicyDecisionType.NAVIGATION_ACTION
    )

    decision.ignore.assert_not_called()
    preview._open_uri_externally.assert_not_called()


def test_on_decide_policy_file_link_uses_open_path_callback(monkeypatch):
    preview = object.__new__(webkit_preview_6x.WebKitPreview_6x)
    preview._base_uri = "file:///tmp/current.md"
    opened_paths = []
    preview._on_open_path = lambda path: opened_paths.append(path)

    fake_webkit = SimpleNamespace(
        PolicyDecisionType=SimpleNamespace(NAVIGATION_ACTION=1),
        NavigationType=SimpleNamespace(LINK_CLICKED=2),
    )
    monkeypatch.setattr(webkit_preview_6x, "WebKit", fake_webkit)

    decision = MagicMock()
    decision.get_navigation_action.return_value = SimpleNamespace(
        get_request=lambda: SimpleNamespace(get_uri=lambda: "file:///tmp/other.md#h1"),
        get_navigation_type=lambda: fake_webkit.NavigationType.LINK_CLICKED,
    )

    webkit_preview_6x.WebKitPreview_6x._on_decide_policy(
        preview, None, decision, fake_webkit.PolicyDecisionType.NAVIGATION_ACTION
    )

    decision.ignore.assert_called_once()
    assert opened_paths == ["/tmp/other.md"]


def test_open_data_uri_svg_uses_image_viewer_window(monkeypatch):
    import sys

    preview = object.__new__(webkit_preview_6x.WebKitPreview_6x)

    presented = []

    class FakeViewer:
        def __init__(self, uri, title):
            presented.append((uri, title))

        def present(self):
            presented.append("presented")

    monkeypatch.setitem(
        sys.modules,
        "calamus.imageviewer",
        SimpleNamespace(ImageViewerWindow=FakeViewer),
    )

    webkit_preview_6x.WebKitPreview_6x._open_data_uri_externally(
        preview, "data:image/svg+xml;base64,PHN2Zz48L3N2Zz4="
    )

    assert presented[0][1] == "SVG Viewer"
    assert presented[1] == "presented"


def test_open_data_uri_png_opens_temp_file_externally(monkeypatch):
    preview = object.__new__(webkit_preview_6x.WebKitPreview_6x)

    launched = []
    monkeypatch.setattr(
        webkit_preview_6x.Gio,
        "AppInfo",
        SimpleNamespace(launch_default_for_uri=lambda uri, _ctx: launched.append(uri)),
    )

    webkit_preview_6x.WebKitPreview_6x._open_data_uri_externally(
        preview, "data:image/png;base64,iVBORw0KGgo="
    )

    assert len(launched) == 1
    assert launched[0].startswith("file://")


# ---------------------------------------------------------------------------
# "Copy Markdown Image" for SVG data: URIs — issue #91
# ---------------------------------------------------------------------------


def _make_svg_preview_6x(monkeypatch):
    """Return a minimal WebKitPreview_6x instance with context-menu stubs."""
    preview = object.__new__(webkit_preview_6x.WebKitPreview_6x)
    preview._context_menu_actions = []
    preview._save_image = lambda *_: None
    preview._copy_image = lambda *_: None
    preview._copy_to_clipboard = lambda *_: None
    preview._copy_svg_data_uri_as_markdown = lambda *_: None
    preview._uri_to_markdown_image = lambda *_: "![img](x)"

    fake_webkit = SimpleNamespace(
        ContextMenuAction=SimpleNamespace(
            COPY_IMAGE_URL_TO_CLIPBOARD=1,
            DOWNLOAD_IMAGE_TO_DISK=2,
        ),
        ContextMenuItem=SimpleNamespace(
            new_from_gaction=lambda action, label: (action, label)
        ),
    )
    monkeypatch.setattr(webkit_preview_6x, "WebKit", fake_webkit)
    monkeypatch.setattr(
        webkit_preview_6x.Gio.SimpleAction, "new", lambda *_: MagicMock()
    )
    return preview


def test_on_context_menu_svg_data_uri_has_copy_markdown_image(monkeypatch):
    """SVG data: URIs should get a 'Copy Markdown Image' context menu entry."""
    preview = _make_svg_preview_6x(monkeypatch)
    menu = _FakeContextMenu()
    hit = _FakeHitTest(True, "data:image/svg+xml;base64,PHN2Zz48L3N2Zz4=")

    webkit_preview_6x.WebKitPreview_6x._on_context_menu(preview, None, menu, hit)

    labels = [item[1] for item in menu.appended]
    assert "Copy Markdown Image" in labels


def test_on_context_menu_non_svg_data_uri_no_copy_markdown_image(monkeypatch):
    """Non-SVG data: URIs (e.g. PNG) should NOT get 'Copy Markdown Image'."""
    preview = _make_svg_preview_6x(monkeypatch)
    menu = _FakeContextMenu()
    hit = _FakeHitTest(True, "data:image/png;base64,iVBORw0KGgo=")

    webkit_preview_6x.WebKitPreview_6x._on_context_menu(preview, None, menu, hit)

    labels = [item[1] for item in menu.appended]
    assert "Copy Markdown Image" not in labels


def test_copy_svg_data_uri_as_markdown_copies_svg_text():
    """_copy_svg_data_uri_as_markdown should decode SVG and copy as plain text."""
    import base64 as _b64

    preview = object.__new__(webkit_preview_6x.WebKitPreview_6x)
    copied = []
    preview._copy_to_clipboard = lambda text: copied.append(text)

    svg = "<svg><circle r='10'/></svg>"
    uri = f"data:image/svg+xml;base64,{_b64.b64encode(svg.encode()).decode()}"
    webkit_preview_6x.WebKitPreview_6x._copy_svg_data_uri_as_markdown(preview, uri)

    assert copied == [svg]


# ---------------------------------------------------------------------------
# _copy_to_clipboard sets CLIPBOARD and PRIMARY — issue #92
# ---------------------------------------------------------------------------


def test_copy_to_clipboard_sets_clipboard_and_primary(monkeypatch):
    """_copy_to_clipboard must write to both CLIPBOARD and PRIMARY selections."""
    preview = object.__new__(webkit_preview_6x.WebKitPreview_6x)

    clipboard = MagicMock()
    primary = MagicMock()
    provider_calls = []

    monkeypatch.setattr(
        webkit_preview_6x.Gdk.Display,
        "get_default",
        lambda: SimpleNamespace(
            get_clipboard=lambda: clipboard,
            get_primary_clipboard=lambda: primary,
        ),
    )
    monkeypatch.setattr(
        webkit_preview_6x.Gdk.ContentProvider,
        "new_for_value",
        lambda v: provider_calls.append(v) or "provider",
    )

    webkit_preview_6x.WebKitPreview_6x._copy_to_clipboard(preview, "hello")

    clipboard.set_content.assert_called_once_with("provider")
    primary.set_content.assert_called_once_with("provider")


def test_copy_to_clipboard_tolerates_no_primary(monkeypatch):
    """_copy_to_clipboard must not raise when get_primary_clipboard returns None."""
    preview = object.__new__(webkit_preview_6x.WebKitPreview_6x)

    clipboard = MagicMock()
    monkeypatch.setattr(
        webkit_preview_6x.Gdk.Display,
        "get_default",
        lambda: SimpleNamespace(
            get_clipboard=lambda: clipboard,
            get_primary_clipboard=lambda: None,
        ),
    )
    monkeypatch.setattr(
        webkit_preview_6x.Gdk.ContentProvider,
        "new_for_value",
        lambda v: "provider",
    )

    webkit_preview_6x.WebKitPreview_6x._copy_to_clipboard(preview, "hello")

    clipboard.set_content.assert_called_once_with("provider")


# ---------------------------------------------------------------------------
# Find in preview pane — issue #93
# ---------------------------------------------------------------------------


def _make_find_preview():
    """Return a minimal WebKitPreview_6x with find-controller stub."""
    preview = object.__new__(webkit_preview_6x.WebKitPreview_6x)
    preview._find_controller = MagicMock()
    preview._js_find_valid = False
    preview._last_js_key = None
    preview._js_calls = []
    preview._js_run = lambda js: preview._js_calls.append(js)
    return preview


def _make_state(
    needle="hello",
    case_sensitive=False,
    whole_word=False,
    match_diacritics=True,
):
    from calamus.search import SearchState

    s = SearchState()
    s.push_find(needle)
    s.case_sensitive = case_sensitive
    s.whole_word = whole_word
    s.match_diacritics = match_diacritics
    return s


def test_find_next_calls_search_and_search_next(monkeypatch):
    preview = _make_find_preview()
    fake_options = SimpleNamespace(WRAP_AROUND=1, CASE_INSENSITIVE=2, AT_WORD_STARTS=4)
    monkeypatch.setattr(
        webkit_preview_6x,
        "WebKit",
        SimpleNamespace(
            FindOptions=fake_options,
            ContextMenuAction=SimpleNamespace(
                COPY_IMAGE_URL_TO_CLIPBOARD=1, DOWNLOAD_IMAGE_TO_DISK=2
            ),
            ContextMenuItem=SimpleNamespace(new_from_gaction=lambda a, l: (a, l)),
        ),
    )
    state = _make_state("hello")
    result = webkit_preview_6x.WebKitPreview_6x.find_next(preview, state)
    assert result is True
    preview._find_controller.search.assert_called_once_with("hello", 1 | 2, 500)
    preview._find_controller.search_next.assert_called_once()


def test_find_previous_calls_search_and_search_previous(monkeypatch):
    preview = _make_find_preview()
    fake_options = SimpleNamespace(WRAP_AROUND=1, CASE_INSENSITIVE=2, AT_WORD_STARTS=4)
    monkeypatch.setattr(
        webkit_preview_6x,
        "WebKit",
        SimpleNamespace(
            FindOptions=fake_options,
            ContextMenuAction=SimpleNamespace(
                COPY_IMAGE_URL_TO_CLIPBOARD=1, DOWNLOAD_IMAGE_TO_DISK=2
            ),
            ContextMenuItem=SimpleNamespace(new_from_gaction=lambda a, l: (a, l)),
        ),
    )
    state = _make_state("hello")
    result = webkit_preview_6x.WebKitPreview_6x.find_previous(preview, state)
    assert result is True
    preview._find_controller.search.assert_called_once_with("hello", 1 | 2, 500)
    preview._find_controller.search_previous.assert_called_once()


def test_find_next_returns_false_on_empty_history(monkeypatch):
    from calamus.search import SearchState

    preview = _make_find_preview()
    fake_options = SimpleNamespace(WRAP_AROUND=1, CASE_INSENSITIVE=2, AT_WORD_STARTS=4)
    monkeypatch.setattr(
        webkit_preview_6x,
        "WebKit",
        SimpleNamespace(
            FindOptions=fake_options,
            ContextMenuAction=SimpleNamespace(
                COPY_IMAGE_URL_TO_CLIPBOARD=1, DOWNLOAD_IMAGE_TO_DISK=2
            ),
            ContextMenuItem=SimpleNamespace(new_from_gaction=lambda a, l: (a, l)),
        ),
    )
    state = SearchState()  # no history
    result = webkit_preview_6x.WebKitPreview_6x.find_next(preview, state)
    assert result is False
    preview._find_controller.search.assert_not_called()


def test_find_next_respects_case_sensitive_flag(monkeypatch):
    preview = _make_find_preview()
    fake_options = SimpleNamespace(WRAP_AROUND=1, CASE_INSENSITIVE=2, AT_WORD_STARTS=4)
    monkeypatch.setattr(
        webkit_preview_6x,
        "WebKit",
        SimpleNamespace(
            FindOptions=fake_options,
            ContextMenuAction=SimpleNamespace(
                COPY_IMAGE_URL_TO_CLIPBOARD=1, DOWNLOAD_IMAGE_TO_DISK=2
            ),
            ContextMenuItem=SimpleNamespace(new_from_gaction=lambda a, l: (a, l)),
        ),
    )
    state = _make_state("Hello", case_sensitive=True)
    webkit_preview_6x.WebKitPreview_6x.find_next(preview, state)
    # CASE_INSENSITIVE should NOT be set when case_sensitive=True
    call_args = preview._find_controller.search.call_args[0]
    assert call_args[1] & 2 == 0  # CASE_INSENSITIVE bit not set


def test_find_next_respects_whole_word_flag(monkeypatch):
    preview = _make_find_preview()
    fake_options = SimpleNamespace(WRAP_AROUND=1, CASE_INSENSITIVE=2, AT_WORD_STARTS=4)
    monkeypatch.setattr(
        webkit_preview_6x,
        "WebKit",
        SimpleNamespace(
            FindOptions=fake_options,
            ContextMenuAction=SimpleNamespace(
                COPY_IMAGE_URL_TO_CLIPBOARD=1, DOWNLOAD_IMAGE_TO_DISK=2
            ),
            ContextMenuItem=SimpleNamespace(new_from_gaction=lambda a, l: (a, l)),
        ),
    )
    state = _make_state("hello", whole_word=True)
    webkit_preview_6x.WebKitPreview_6x.find_next(preview, state)
    call_args = preview._find_controller.search.call_args[0]
    assert call_args[1] & 4 != 0  # AT_WORD_STARTS bit is set


# ---------------------------------------------------------------------------
# Regex find-in-preview — issue #96
# ---------------------------------------------------------------------------


def _make_regex_find_preview():
    """Return a WebKitPreview_6x stub with JS-find state initialised."""
    return _make_find_preview()


def _make_regex_state(
    needle="hel+o",
    case_sensitive=False,
    use_regex=True,
    match_diacritics=False,
):
    from calamus.search import SearchState

    s = SearchState()
    s.push_find(needle)
    s.case_sensitive = case_sensitive
    s.use_regex = use_regex
    s.match_diacritics = match_diacritics
    return s


def test_build_regex_flags_case_insensitive():
    preview = _make_regex_find_preview()
    state = _make_regex_state(case_sensitive=False)
    flags = webkit_preview_6x.WebKitPreview_6x._build_regex_flags(preview, state)
    assert "g" in flags
    assert "u" in flags
    assert "i" in flags


def test_build_regex_flags_case_sensitive():
    preview = _make_regex_find_preview()
    state = _make_regex_state(case_sensitive=True)
    flags = webkit_preview_6x.WebKitPreview_6x._build_regex_flags(preview, state)
    assert "g" in flags
    assert "u" in flags
    assert "i" not in flags


def test_find_next_regex_injects_helper_and_searches_on_first_call():
    preview = _make_regex_find_preview()
    state = _make_regex_state("hel+o")
    result = webkit_preview_6x.WebKitPreview_6x.find_next(preview, state)
    assert result is True
    assert preview._js_find_valid is True
    assert len(preview._js_calls) == 1
    js = preview._js_calls[0]
    # Helper must be injected and search + next called
    assert "__calamusFind" in js
    assert ".search(" in js
    assert ".next()" in js
    # FindController should NOT be called in regex mode
    preview._find_controller.search.assert_not_called()


def test_find_next_regex_navigates_without_reinit_when_valid():
    preview = _make_regex_find_preview()
    preview._js_find_valid = True
    preview._last_js_key = ("hel+o", "gui", True, False)
    state = _make_regex_state("hel+o", case_sensitive=False)
    webkit_preview_6x.WebKitPreview_6x.find_next(preview, state)
    js = preview._js_calls[0]
    # Should just navigate, not re-inject helper or re-search
    assert ".next()" in js
    assert ".search(" not in js


def test_find_next_regex_reinits_when_needle_changes():
    preview = _make_regex_find_preview()
    preview._js_find_valid = True
    preview._last_js_key = ("old", "gui", True, False)
    state = _make_regex_state("new_pattern")
    webkit_preview_6x.WebKitPreview_6x.find_next(preview, state)
    js = preview._js_calls[0]
    assert ".search(" in js
    assert ".next()" in js


def test_find_previous_regex_calls_prev():
    preview = _make_regex_find_preview()
    state = _make_regex_state("hel+o")
    webkit_preview_6x.WebKitPreview_6x.find_previous(preview, state)
    js = preview._js_calls[0]
    assert ".prev()" in js


def test_switching_from_regex_to_plain_clears_js_highlights():
    preview = _make_regex_find_preview()
    preview._js_find_valid = True  # was in regex mode
    preview._last_js_key = ("hel+o", "gui", False, False)
    state = _make_regex_state("hello", use_regex=False, match_diacritics=True)

    fake_options = SimpleNamespace(WRAP_AROUND=1, CASE_INSENSITIVE=2, AT_WORD_STARTS=4)
    import unittest.mock as _mock

    with _mock.patch.object(webkit_preview_6x, "WebKit") as mock_wk:
        mock_wk.FindOptions = fake_options
        webkit_preview_6x.WebKitPreview_6x.find_next(preview, state)

    # JS clear must have been called
    assert any(".clear()" in js for js in preview._js_calls)
    assert preview._js_find_valid is False
    # FindController must have been used
    preview._find_controller.search.assert_called_once()
    preview._find_controller.search_next.assert_called_once()


def test_find_next_plain_text_match_diacritics_off_uses_js_literal_search():
    preview = _make_regex_find_preview()
    state = _make_regex_state("cafe", use_regex=False, match_diacritics=False)
    webkit_preview_6x.WebKitPreview_6x.find_next(preview, state)
    js = preview._js_calls[0]
    assert "__calamusFind.search" in js
    assert "true, true" in js
    preview._find_controller.search.assert_not_called()


def test_find_next_regex_match_diacritics_off_folds_pattern():
    preview = _make_regex_find_preview()
    state = _make_regex_state("café", use_regex=True, match_diacritics=False)
    webkit_preview_6x.WebKitPreview_6x.find_next(preview, state)
    js = preview._js_calls[0]
    assert "cafe" in js
    assert "café" not in js


def test_find_next_match_diacritics_off_navigates_all_oro_sample_matches():
    preview = _make_regex_find_preview()
    state = _make_regex_state("Óró", use_regex=False, match_diacritics=False)
    expected = ORO_SAMPLE_MD.count("Óró")

    for _ in range(expected):
        assert webkit_preview_6x.WebKitPreview_6x.find_next(preview, state) is True

    assert len(preview._js_calls) == expected
    assert "Oro" in preview._js_calls[0]
