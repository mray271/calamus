"""Tests for mermaid_support module."""

import re
import shutil
from urllib.parse import urlparse


def script_src_hosts(html: str) -> set[str]:
    """Extract hostnames from script src attributes."""
    sources = re.findall(r'<script[^>]*\ssrc="([^"]+)"', html)
    return {urlparse(source).netloc for source in sources}


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
    assert "cdn.jsdelivr.net" in script_src_hosts(tag)


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


# ---------------------------------------------------------------------------
# MermaidCache
# ---------------------------------------------------------------------------


def test_mermaid_cache_put_and_get():
    from calamus.mermaid_support import MermaidCache

    cache = MermaidCache()
    cache.put("graph TD\nA-->B", "<svg>test</svg>")
    assert cache.get("graph TD\nA-->B") == "<svg>test</svg>"


def test_mermaid_cache_miss_returns_none():
    from calamus.mermaid_support import MermaidCache

    cache = MermaidCache()
    assert cache.get("nonexistent diagram") is None


def test_mermaid_cache_has_returns_false_before_put():
    from calamus.mermaid_support import MermaidCache

    cache = MermaidCache()
    assert cache.has("anything") is False


def test_mermaid_cache_has_returns_true_after_put():
    from calamus.mermaid_support import MermaidCache

    cache = MermaidCache()
    cache.put("diagram source", "<svg/>")
    assert cache.has("diagram source") is True


def test_mermaid_cache_stores_multiple_entries_independently():
    from calamus.mermaid_support import MermaidCache

    cache = MermaidCache()
    cache.put("A", "<svg>A</svg>")
    cache.put("B", "<svg>B</svg>")
    assert cache.get("A") == "<svg>A</svg>"
    assert cache.get("B") == "<svg>B</svg>"


# ---------------------------------------------------------------------------
# preprocess_with_cache
# ---------------------------------------------------------------------------


def test_preprocess_with_cache_hit_returns_img_tag():
    from calamus.mermaid_support import MermaidCache, preprocess_with_cache

    cache = MermaidCache()
    diagram = "graph TD\nA-->B"
    cache.put(diagram, "<svg>cached</svg>")
    result = preprocess_with_cache(f"```mermaid\n{diagram}\n```", cache)
    assert "<img" in result
    assert "data:image/svg+xml;base64," in result
    assert "```mermaid" not in result


def test_preprocess_with_cache_miss_returns_pre_mermaid():
    from calamus.mermaid_support import MermaidCache, preprocess_with_cache

    cache = MermaidCache()
    result = preprocess_with_cache("```mermaid\ngraph TD\nA-->B\n```", cache)
    assert '<pre class="mermaid">' in result
    assert "```mermaid" not in result


def test_preprocess_with_cache_passthrough_when_no_blocks():
    from calamus.mermaid_support import MermaidCache, preprocess_with_cache

    cache = MermaidCache()
    text = "# Just markdown\nNo diagrams."
    assert preprocess_with_cache(text, cache) == text


# ---------------------------------------------------------------------------
# SubprocessMermaidRenderer — output file not created
# ---------------------------------------------------------------------------


def test_subprocess_renderer_returns_none_when_output_not_created(monkeypatch):
    """render_to_svg returns None when subprocess succeeds but creates no output file."""
    import subprocess

    from calamus.mermaid_support import SubprocessMermaidRenderer

    monkeypatch.setattr(SubprocessMermaidRenderer, "_mmdc_available", None)
    monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/mmdc")

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    renderer = SubprocessMermaidRenderer()
    assert renderer.render_to_svg("graph TD\nA-->B") is None
