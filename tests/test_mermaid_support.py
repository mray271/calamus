"""Tests for mermaid_support module."""

import shutil


def test_extract_mermaid_blocks_finds_blocks():
    from calamus.mermaid_support import extract_mermaid_blocks

    text = "Hello\n```mermaid\ngraph TD\nA-->B\n```\nWorld"
    blocks = extract_mermaid_blocks(text)
    assert len(blocks) == 1
    assert "graph TD" in blocks[0][1]


def test_extract_mermaid_blocks_empty():
    from calamus.mermaid_support import extract_mermaid_blocks

    assert extract_mermaid_blocks("no diagrams here") == []


def test_extract_multiple_blocks():
    from calamus.mermaid_support import extract_mermaid_blocks

    text = "```mermaid\nA-->B\n```\ntext\n```mermaid\nC-->D\n```"
    blocks = extract_mermaid_blocks(text)
    assert len(blocks) == 2


def test_extract_returns_positions():
    from calamus.mermaid_support import extract_mermaid_blocks

    text = "prefix\n```mermaid\ngraph TD\nA-->B\n```"
    blocks = extract_mermaid_blocks(text)
    assert len(blocks) == 1
    pos, src = blocks[0]
    assert isinstance(pos, int)
    assert pos >= 0


def test_fallback_renderer_is_available():
    from calamus.mermaid_support import FallbackMermaidRenderer

    renderer = FallbackMermaidRenderer()
    assert renderer.is_available() is True


def test_fallback_renderer_returns_svg():
    from calamus.mermaid_support import FallbackMermaidRenderer

    renderer = FallbackMermaidRenderer()
    svg = renderer.render_to_svg("graph TD\nA-->B")
    assert svg is not None
    assert "<svg" in svg


def test_fallback_renderer_escapes_html_in_source():
    from calamus.mermaid_support import FallbackMermaidRenderer

    renderer = FallbackMermaidRenderer()
    svg = renderer.render_to_svg("<script>alert('xss')</script>")
    assert "<script>" not in svg


def test_subprocess_renderer_unavailable_when_no_mmdc(monkeypatch):
    """SubprocessMermaidRenderer.is_available() returns False when mmdc is not on PATH."""
    monkeypatch.setattr(shutil, "which", lambda _: None)
    from calamus.mermaid_support import SubprocessMermaidRenderer

    monkeypatch.setattr(SubprocessMermaidRenderer, "_mmdc_available", None)
    from calamus.mermaid_support import SubprocessMermaidRenderer

    renderer = SubprocessMermaidRenderer()
    assert renderer.is_available() is False


def test_subprocess_renderer_render_returns_none_when_unavailable(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda _: None)
    from calamus.mermaid_support import SubprocessMermaidRenderer

    monkeypatch.setattr(SubprocessMermaidRenderer, "_mmdc_available", None)
    from calamus.mermaid_support import SubprocessMermaidRenderer

    renderer = SubprocessMermaidRenderer()
    result = renderer.render_to_svg("graph TD\nA-->B")
    assert result is None


def test_get_best_renderer_returns_fallback_when_no_mmdc(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda _: None)
    from calamus.mermaid_support import SubprocessMermaidRenderer

    monkeypatch.setattr(SubprocessMermaidRenderer, "_mmdc_available", None)
    from calamus.mermaid_support import FallbackMermaidRenderer, get_best_renderer

    renderer = get_best_renderer()
    assert isinstance(renderer, FallbackMermaidRenderer)


def test_get_best_renderer_returns_subprocess_when_mmdc_available(monkeypatch):
    from calamus.mermaid_support import SubprocessMermaidRenderer, get_best_renderer

    # Reset the class-level cache so is_available() re-checks shutil.which.
    # Without this, a prior test run in the full suite may have cached False.
    monkeypatch.setattr(SubprocessMermaidRenderer, "_mmdc_available", None)
    monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/mmdc")

    renderer = get_best_renderer()
    assert isinstance(renderer, SubprocessMermaidRenderer)


def test_get_best_renderer_returns_renderer():
    from calamus.mermaid_support import AbstractMermaidRenderer, get_best_renderer

    renderer = get_best_renderer()
    assert isinstance(renderer, AbstractMermaidRenderer)
    assert renderer.is_available() is True


def test_mermaid_version_constant():
    from calamus.mermaid_support import MERMAID_VERSION

    assert MERMAID_VERSION == "11.5.0"


def test_mermaid_cdn_url_contains_version():
    from calamus.mermaid_support import MERMAID_CDN_URL, MERMAID_VERSION

    assert MERMAID_VERSION in MERMAID_CDN_URL
    assert "jsdelivr" in MERMAID_CDN_URL


def test_get_mermaid_script_tag_cdn_fallback():
    from calamus.mermaid_support import get_mermaid_script_tag

    tag = get_mermaid_script_tag(local_first=False)
    assert "<script" in tag
    assert "mermaid" in tag


def test_get_mermaid_script_tag_local_missing_falls_back_to_cdn(tmp_path, monkeypatch):
    """When local file does not exist, should fall back to CDN URL."""
    import calamus.mermaid_support as ms

    monkeypatch.setattr(ms, "MERMAID_LOCAL_PATH", str(tmp_path / "nonexistent.js"))
    monkeypatch.setattr(
        ms, "MERMAID_SYSTEM_PATH", str(tmp_path / "nonexistent_system.js")
    )
    tag = ms.get_mermaid_script_tag(local_first=True)
    assert "cdn.jsdelivr.net" in tag


def test_get_mermaid_script_tag_local_file_preferred(tmp_path, monkeypatch):
    """When local file exists, its content is inlined instead of using the CDN."""
    import calamus.mermaid_support as ms

    local = tmp_path / "mermaid.min.js"
    local.write_text("// fake mermaid")
    monkeypatch.setattr(ms, "MERMAID_LOCAL_PATH", str(local))
    tag = ms.get_mermaid_script_tag(local_first=True)
    assert "// fake mermaid" in tag
    assert "cdn.jsdelivr.net" not in tag


def test_get_mermaid_init_script():
    from calamus.mermaid_support import get_mermaid_init_script

    script = get_mermaid_init_script()
    assert "<script>" in script or "<script" in script
    assert "mermaid.initialize" in script
    assert "startOnLoad" in script


def test_preprocess_replaces_mermaid_blocks():
    from calamus.mermaid_support import preprocess_markdown_for_static_export

    text = "Before\n```mermaid\ngraph TD\nA-->B\n```\nAfter"
    result = preprocess_markdown_for_static_export(text)
    assert "```mermaid" not in result
    assert "After" in result
    assert "Before" in result


def test_preprocess_result_contains_image_tag():
    from calamus.mermaid_support import preprocess_markdown_for_static_export

    text = "```mermaid\ngraph TD\nA-->B\n```"
    result = preprocess_markdown_for_static_export(text)
    assert "<img" in result
    assert "data:image/svg+xml;base64," in result


def test_preprocess_no_mermaid_unchanged():
    from calamus.mermaid_support import preprocess_markdown_for_static_export

    text = "# Just markdown\n\nNo diagrams here."
    result = preprocess_markdown_for_static_export(text)
    assert result == text


def test_preprocess_multiple_blocks():
    from calamus.mermaid_support import preprocess_markdown_for_static_export

    text = "```mermaid\ngraph TD\nA-->B\n```\nMiddle\n```mermaid\nsequenceDiagram\nA->>B: Hi\n```"
    result = preprocess_markdown_for_static_export(text)
    assert "```mermaid" not in result
    assert "Middle" in result
    assert result.count("<img") == 2
