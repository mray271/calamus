"""Unit tests for calamus.renderer — MistuneRenderer."""

import pytest


def test_mistune_renderer_renders_heading():
    from calamus.renderer import MistuneRenderer

    r = MistuneRenderer()
    html = r.render("# Hello")
    assert "<h1>" in html
    assert "Hello" in html


def test_mistune_renderer_heading_levels():
    from calamus.renderer import MistuneRenderer

    r = MistuneRenderer()
    for level in range(1, 7):
        html = r.render(f"{'#' * level} Heading {level}")
        assert f"<h{level}>" in html


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
    assert "https://github.com" in html


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
    # Mermaid blocks become <pre class="mermaid"> for WebKit JS rendering
    assert "mermaid" in html
    assert "graph TD" in html or "A--&gt;B" in html


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
    assert "<h1>" in html
    assert "<strong>" in html
    assert "<em>" in html
    assert "<ul>" in html
