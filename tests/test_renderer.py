"""Unit tests for calamus.renderer — MistuneRenderer."""

import re

import pytest


def test_mistune_renderer_renders_heading():
    from calamus.renderer import MistuneRenderer

    r = MistuneRenderer()
    html = r.render("# Hello")
    assert "<h1" in html
    assert "Hello" in html


def test_mistune_renderer_heading_levels():
    from calamus.renderer import MistuneRenderer

    r = MistuneRenderer()
    for level in range(1, 7):
        html = r.render(f"{'#' * level} Heading {level}")
        assert f"<h{level}" in html


def test_mistune_renderer_bold():
    from calamus.renderer import MistuneRenderer

    r = MistuneRenderer()
    html = r.render("**bold text**")
    assert "<strong>" in html
    assert "bold text" in html


def test_mistune_renderer_italic():
    from calamus.renderer import MistuneRenderer

    r = MistuneRenderer()
    html = r.render("*italic text*")
    assert "<em>" in html


def test_mistune_renderer_bold_italic():
    from calamus.renderer import MistuneRenderer

    r = MistuneRenderer()
    html = r.render("***bold italic***")
    assert "<strong>" in html
    assert "<em>" in html


def test_mistune_renderer_strikethrough():
    from calamus.renderer import MistuneRenderer

    r = MistuneRenderer()
    html = r.render("~~strikethrough~~")
    assert "<del>" in html or "strikethrough" in html


def test_mistune_renderer_inline_code():
    from calamus.renderer import MistuneRenderer

    r = MistuneRenderer()
    html = r.render("`inline code`")
    assert "<code>" in html


def test_mistune_renderer_code_block():
    from calamus.renderer import MistuneRenderer

    r = MistuneRenderer()
    html = r.render("```\ncode block\n```")
    assert "<pre>" in html or "<code>" in html


def test_mistune_renderer_blockquote():
    from calamus.renderer import MistuneRenderer

    r = MistuneRenderer()
    html = r.render("> This is a quote")
    assert "<blockquote>" in html


def test_mistune_renderer_ordered_list():
    from calamus.renderer import MistuneRenderer

    r = MistuneRenderer()
    html = r.render("1. First\n2. Second")
    assert "<ol>" in html
    assert "<li>" in html


def test_mistune_renderer_unordered_list():
    from calamus.renderer import MistuneRenderer

    r = MistuneRenderer()
    html = r.render("- Item one\n- Item two")
    assert "<ul>" in html
    assert "<li>" in html


def test_mistune_renderer_link():
    from calamus.renderer import MistuneRenderer

    r = MistuneRenderer()
    html = r.render("[GitHub](https://github.com)")
    assert "<a" in html
    hrefs = re.findall(r'href="([^"]+)"', html)
    assert any(href == "https://github.com" for href in hrefs)


def test_mistune_renderer_image():
    from calamus.renderer import MistuneRenderer

    r = MistuneRenderer()
    html = r.render("![alt text](https://example.com/img.png)")
    assert "<img" in html


def test_mistune_renderer_horizontal_rule():
    from calamus.renderer import MistuneRenderer

    r = MistuneRenderer()
    html = r.render("---")
    assert "<hr" in html


def test_mistune_renderer_preserves_mermaid_block():
    from calamus.renderer import MistuneRenderer

    r = MistuneRenderer()
    md = "```mermaid\ngraph TD\nA-->B\n```"
    html = r.render(md)
    # When mmdc is available the block becomes an inline SVG <img>;
    # when it isn't, it becomes <pre class="mermaid"> for browser-side rendering.
    assert "mermaid" in html or "svg" in html.lower() or "A--&gt;B" in html


def test_mistune_renderer_get_version_returns_string():
    from calamus.renderer import MistuneRenderer

    r = MistuneRenderer()
    version = r.get_version()
    assert isinstance(version, str)
    assert len(version) > 0


def test_mistune_renderer_mermaid_version_constant():
    from calamus.renderer import MistuneRenderer

    assert MistuneRenderer.MERMAID_VERSION == "11.5.0"


def test_mistune_renderer_empty_input():
    from calamus.renderer import MistuneRenderer

    r = MistuneRenderer()
    html = r.render("")
    assert isinstance(html, str)


def test_mistune_renderer_mixed_content():
    from calamus.renderer import MistuneRenderer

    r = MistuneRenderer()
    md = "# Title\n\nSome **bold** and *italic* text.\n\n- item 1\n- item 2"
    html = r.render(md)
    assert "<h1" in html
    assert "<strong>" in html
    assert "<em>" in html
    assert "<ul>" in html


def test_mistune_renderer_adjacent_footnotes_render_as_two_superscripts():
    from calamus.renderer import MistuneRenderer

    r = MistuneRenderer()
    md = (
        "This is some text with footnotes[^1][^2].\n\n"
        "[^1]: This is footnote 1.\n"
        "[^2]: This is footnote 2.\n"
    )
    html = r.render(md)
    assert html.count('class="footnote-ref"') == 2
    assert 'footnotes.<sup class="footnote-ref"' in html
    assert '</a>,</sup><sup class="footnote-ref"' in html
    assert "</sup>." not in html
    assert '<section class="footnotes">' in html
    assert "This is footnote 1." in html
    assert "This is footnote 2." in html


def test_mistune_renderer_respects_explicit_heading_id_syntax():
    from calamus.renderer import MistuneRenderer

    r = MistuneRenderer()
    html = r.render("### My Great Heading {#custom-id}")
    assert '<h3 id="custom-id">My Great Heading</h3>' in html
    assert "{#custom-id}" not in html


def test_mistune_renderer_highlight_syntax_renders_mark():
    from calamus.renderer import MistuneRenderer

    r = MistuneRenderer()
    html = r.render("I need ==very important words== highlighted.")
    assert "<mark>very important words</mark>" in html


def test_add_heading_ids_non_string_passthrough():
    from calamus.renderer import _add_heading_ids

    result = _add_heading_ids(42)
    assert result == 42


def test_add_heading_ids_empty_slug_preserves_original():
    from calamus.renderer import _add_heading_ids

    # Heading whose text is all punctuation → slug becomes empty → return m.group(0)
    html = "<h1>!!!</h1>"
    result = _add_heading_ids(html)
    assert result == html


def test_render_glfm_toc_non_string_passthrough():
    from calamus.renderer import _render_glfm_toc

    result = _render_glfm_toc(42)
    assert result == 42


def test_render_glfm_toc_replaces_marker_with_nav():
    from calamus.renderer import _render_glfm_toc

    html = '<h1 id="heading">Heading</h1>\n<p>[[<em>TOC</em>]]</p>\n'
    result = _render_glfm_toc(html)
    assert '<nav class="table-of-contents glfm-toc">' in result
    assert '<a href="#heading">Heading</a>' in result
    assert "[[<em>TOC</em>]]" not in result


def test_render_glfm_emoji_shortcodes_non_string_passthrough():
    from calamus.renderer import _render_glfm_emoji_shortcodes

    result = _render_glfm_emoji_shortcodes(42)
    assert result == 42


def test_render_glfm_color_chips_non_string_passthrough():
    from calamus.renderer import _render_glfm_color_chips

    result = _render_glfm_color_chips(42)
    assert result == 42


def test_render_glfm_color_chips_replaces_inline_hex_code():
    from calamus.renderer import _render_glfm_color_chips

    result = _render_glfm_color_chips("<p>See <code>#FF0000</code>.</p>")
    assert 'class="glfm-color-chip"' in result
    assert "glfm-color-chip-swatch" in result
    assert "background-color: #ff0000" in result
    assert "<code>#FF0000</code>" in result


def test_render_glfm_color_chips_replaces_inline_color_function_code():
    from calamus.renderer import _render_glfm_color_chips

    result = _render_glfm_color_chips("<p>See <code>RGB(255, 0, 0)</code>.</p>")
    assert 'class="glfm-color-chip"' in result
    assert "glfm-color-chip-swatch" in result
    assert "background-color: rgb(255, 0, 0)" in result
    assert "<code>RGB(255, 0, 0)</code>" in result


def test_render_glfm_color_chips_leaves_invalid_color_function_code_unchanged():
    from calamus.renderer import _render_glfm_color_chips

    result = _render_glfm_color_chips("<p>See <code>RGBA(255, 0, 0, 2)</code>.</p>")
    assert "<code>RGBA(255, 0, 0, 2)</code>" in result
    assert 'class="glfm-color-chip"' not in result


def test_render_glfm_color_chips_skips_fenced_code_blocks():
    from calamus.renderer import _render_glfm_color_chips

    result = _render_glfm_color_chips("<pre><code>#00FF00</code></pre>")
    assert "<pre><code>#00FF00</code></pre>" in result
    assert 'class="glfm-color-chip"' not in result


def test_render_glfm_emoji_shortcodes_replaces_known_shortcode():
    from calamus.renderer import _render_glfm_emoji_shortcodes

    result = _render_glfm_emoji_shortcodes("<p>Hello :smile: and :+1:</p>")
    assert "😄" in result
    assert "👍" in result
    assert ":smile:" not in result


def test_render_glfm_emoji_shortcodes_preserves_unknown_shortcode():
    from calamus.renderer import _render_glfm_emoji_shortcodes

    result = _render_glfm_emoji_shortcodes("<p>Hello :not_real_emoji:</p>")
    assert ":not_real_emoji:" in result


def test_render_glfm_emoji_shortcodes_skips_code_and_pre():
    from calamus.renderer import _render_glfm_emoji_shortcodes

    result = _render_glfm_emoji_shortcodes("<code>:smile:</code><pre>:rocket:</pre>")
    assert "<code>:smile:</code>" in result
    assert "<pre>:rocket:</pre>" in result


def test_renderer_render_fallback_path_when_mmdc_unavailable(monkeypatch):
    from calamus.mermaid_support import SubprocessMermaidRenderer
    from calamus.renderer import MistuneRenderer

    monkeypatch.setattr(SubprocessMermaidRenderer, "_mmdc_available", False)

    r = MistuneRenderer()
    result = r.render("```mermaid\ngraph TD\nA-->B\n```\n")
    assert '<pre class="mermaid">' in result


def test_renderer_render_mmdc_available_path(monkeypatch):
    import shutil

    from calamus.mermaid_support import SubprocessMermaidRenderer
    from calamus.renderer import MistuneRenderer

    # Force mmdc to appear available so render() takes the preprocess branch (lines 93-94)
    monkeypatch.setattr(SubprocessMermaidRenderer, "_mmdc_available", None)
    monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/mmdc")

    r = MistuneRenderer()
    result = r.render(
        "# Hello"
    )  # no mermaid blocks — preprocess returns text unchanged
    assert "<h1" in result


# ---------------------------------------------------------------------------
# Preview._open_uri_externally — "Open Image in New Window" regression
# ---------------------------------------------------------------------------


def test_webkit_preview_new_window_action_opens_uri_externally(monkeypatch):
    """The 'create' signal (fired by right-click → Open Image in New Window)
    must open the URI externally and return None — never creating a new window."""
    import types

    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")

    import calamus.preview as preview_mod

    opened_uris: list[str] = []

    import gi.repository as gi_repo

    class FakeAppInfo:
        @staticmethod
        def launch_default_for_uri(uri, _ctx):
            opened_uris.append(uri)

    monkeypatch.setattr(gi_repo.Gio, "AppInfo", FakeAppInfo)

    preview = object.__new__(preview_mod.WebKitPreview)

    class FakeNavAction:
        def get_request(self):
            return types.SimpleNamespace(
                get_uri=lambda: "https://example.com/photo.jpg"
            )

    result = preview_mod.WebKitPreview._on_create_web_view(
        preview, None, FakeNavAction()
    )

    assert result is None, "_on_create_web_view must return None (no new window)"
    assert opened_uris == [
        "https://example.com/photo.jpg"
    ], "URI must be opened in the system browser/image viewer"


def test_webkit_preview_svg_data_uri_opens_viewer_window(monkeypatch):
    """SVG data: URIs must open in Calamus's ImageViewerWindow, not a temp file,
    because system image viewers (gthumb, eog) do not fully support SVG."""
    import base64 as b64

    import calamus.preview as preview_mod

    presented: list[str] = []

    class FakeViewer:
        def __init__(self, uri, title="Image Viewer", **_kwargs):
            self._uri = uri

        def present(self):
            presented.append(self._uri)

    monkeypatch.setattr("calamus.imageviewer.ImageViewerWindow", FakeViewer)

    preview = object.__new__(preview_mod.WebKitPreview)

    svg_content = b"<svg xmlns='http://www.w3.org/2000/svg'><rect/></svg>"
    encoded = b64.b64encode(svg_content).decode("ascii")
    data_uri = f"data:image/svg+xml;base64,{encoded}"

    preview_mod.WebKitPreview._open_uri_externally(preview, data_uri)

    assert len(presented) == 1, "Expected ImageViewerWindow.present() to be called"
    assert presented[0] == data_uri, "Viewer must receive the original data: URI"


def test_webkit_preview_non_svg_data_uri_written_to_temp_file(monkeypatch, tmp_path):
    """Non-SVG data: URIs (PNG, JPEG, etc.) must be decoded to a temp file
    and opened with the system default application."""
    import base64 as b64

    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")

    import calamus.preview as preview_mod

    opened_uris: list[str] = []

    import gi.repository as gi_repo

    class FakeAppInfo:
        @staticmethod
        def launch_default_for_uri(uri, _ctx):
            opened_uris.append(uri)

    monkeypatch.setattr(gi_repo.Gio, "AppInfo", FakeAppInfo)

    import tempfile as tf

    monkeypatch.setattr(tf, "gettempdir", lambda: str(tmp_path))

    preview = object.__new__(preview_mod.WebKitPreview)

    # Minimal 1×1 PNG
    png_b64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
        "YPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
    )
    data_uri = f"data:image/png;base64,{png_b64}"

    preview_mod.WebKitPreview._open_uri_externally(preview, data_uri)

    assert len(opened_uris) == 1, "Expected exactly one URI to be opened"
    assert opened_uris[0].startswith("file://"), "Must open a file:// URI"
    opened_path = opened_uris[0][len("file://"):]
    assert opened_path.endswith(".png"), "Temp file must have .png extension"
    with open(opened_path, "rb") as f:
        assert f.read() == b64.b64decode(png_b64)
